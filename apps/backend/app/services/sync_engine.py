from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import logging
from threading import Lock
from typing import Callable
from uuid import uuid4


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyMetricRow:
    platform: str
    account_id: str
    client_id: int
    report_date: date
    spend: float
    impressions: int
    clicks: int
    conversions: float
    revenue: float
    extra_metrics: dict[str, object] = field(default_factory=dict)


@dataclass
class BackfillChunkResult:
    start_date: date
    end_date: date
    fetched_rows: int
    upserted_rows: int
    spend: float
    impressions: int
    clicks: int
    conversions: float
    revenue: float
    status: str
    error: str | None = None


@dataclass
class BackfillRunResult:
    platform: str
    account_id: str
    client_id: int
    start_date: date
    end_date: date
    chunk_days: int
    attempted_chunks: int
    successful_chunks: int
    failed_chunks: int
    fetched_rows_total: int
    upserted_rows_total: int
    chunks: list[BackfillChunkResult]


def _iter_chunks(*, start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=chunk_days - 1))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def enqueue_backfill(
    *,
    platform: str,
    account_id: str,
    client_id: int,
    start: date,
    end: date,
    chunk_days: int = 7,
    fetch_chunk: Callable[[str, date, date], object],
    normalize_to_rows: Callable[[object, str, int], list[DailyMetricRow]],
    upsert_rows: Callable[[list[DailyMetricRow]], int],
) -> BackfillRunResult:
    if chunk_days <= 0:
        chunk_days = 7

    if start > end:
        start, end = end, start

    chunk_ranges = _iter_chunks(start=start, end=end, chunk_days=chunk_days)
    chunk_results: list[BackfillChunkResult] = []
    fetched_rows_total = 0
    upserted_rows_total = 0

    for chunk_index, (chunk_start, chunk_end) in enumerate(chunk_ranges, start=1):
        logger.info(
            "Procesez chunk-ul %s/%s pentru contul %s (%s -> %s)",
            chunk_index,
            len(chunk_ranges),
            account_id,
            chunk_start.isoformat(),
            chunk_end.isoformat(),
        )
        try:
            raw_payload = fetch_chunk(account_id, chunk_start, chunk_end)
            normalized_rows = normalize_to_rows(raw_payload, account_id, client_id)
            fetched_count = len(normalized_rows)
            upserted_count = upsert_rows(normalized_rows)
            spend_sum = sum(float(row.spend) for row in normalized_rows)
            impressions_sum = sum(int(row.impressions) for row in normalized_rows)
            clicks_sum = sum(int(row.clicks) for row in normalized_rows)
            conversions_sum = sum(float(row.conversions) for row in normalized_rows)
            revenue_sum = sum(float(row.revenue) for row in normalized_rows)
            fetched_rows_total += fetched_count
            upserted_rows_total += upserted_count
            chunk_results.append(
                BackfillChunkResult(
                    start_date=chunk_start,
                    end_date=chunk_end,
                    fetched_rows=fetched_count,
                    upserted_rows=upserted_count,
                    spend=spend_sum,
                    impressions=impressions_sum,
                    clicks=clicks_sum,
                    conversions=conversions_sum,
                    revenue=revenue_sum,
                    status="ok",
                )
            )
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "http_status", None) == 429:
                raise
            chunk_results.append(
                BackfillChunkResult(
                    start_date=chunk_start,
                    end_date=chunk_end,
                    fetched_rows=0,
                    upserted_rows=0,
                    spend=0.0,
                    impressions=0,
                    clicks=0,
                    conversions=0.0,
                    revenue=0.0,
                    status="error",
                    error=str(exc)[:300],
                )
            )

    failed = len([c for c in chunk_results if c.status == "error"])
    successful = len(chunk_results) - failed
    return BackfillRunResult(
        platform=platform,
        account_id=account_id,
        client_id=client_id,
        start_date=start,
        end_date=end,
        chunk_days=chunk_days,
        attempted_chunks=len(chunk_results),
        successful_chunks=successful,
        failed_chunks=failed,
        fetched_rows_total=fetched_rows_total,
        upserted_rows_total=upserted_rows_total,
        chunks=chunk_results,
    )


class BackfillJobStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._jobs: dict[str, dict[str, object]] = {}

    def create(self, *, payload: dict[str, object]) -> str:
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"status": "queued", **payload}
        return job_id

    def set_running(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "running"

    def set_done(self, job_id: str, *, result: dict[str, object]) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "done"
                self._jobs[job_id]["result"] = result

    def set_error(self, job_id: str, *, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "error"
                self._jobs[job_id]["error"] = error[:300]

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            data = self._jobs.get(job_id)
            return dict(data) if data is not None else None


backfill_job_store = BackfillJobStore()
