from __future__ import annotations

from datetime import date
import logging
import os
import time

from app.core.config import load_settings
from app.services.google_ads import google_ads_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store

logger = logging.getLogger(__name__)


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    parsed = date.fromisoformat(str(value))
    return parsed


def _finalize_run_if_complete(job_id: str) -> None:
    counts = sync_run_chunks_store.get_sync_run_chunk_status_counts(job_id)
    if int(counts.get("remaining") or 0) > 0:
        return

    if int(counts.get("errors") or 0) > 0:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="error",
            mark_finished=True,
            error="one or more chunks failed",
        )
    else:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="done",
            mark_finished=True,
        )


def process_next_chunk(*, platform_filter: str | None = None, max_attempts: int = 5) -> bool:
    claimed = sync_run_chunks_store.claim_next_queued_chunk_any(platform=platform_filter, max_attempts=max_attempts)
    if claimed is None:
        return False

    job_id = str(claimed.get("job_id") or "")
    chunk_index = int(claimed.get("chunk_index") or 0)

    run = sync_runs_store.get_sync_run(job_id)
    if run is None:
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="error",
            error="run not found",
            rows_written=0,
            duration_ms=0,
            mark_finished=True,
        )
        sync_runs_store.update_sync_run_progress(job_id=job_id, chunks_done_delta=1, rows_written_delta=0)
        return True

    if str(run.get("status") or "") == "queued":
        sync_runs_store.update_sync_run_status(job_id=job_id, status="running", mark_started=True)

    started = time.monotonic()
    rows_written = 0
    chunk_error: str | None = None

    try:
        platform = str(run.get("platform") or "").strip()
        if platform != "google_ads":
            raise RuntimeError(f"unsupported platform '{platform}'")

        account_id = str(run.get("account_id") or "").strip()
        if account_id == "":
            raise RuntimeError("run has no account_id")

        client_id = int(run.get("client_id") or 0)
        if client_id <= 0:
            raise RuntimeError("run has no client_id mapping")

        chunk_start = _as_date(claimed.get("date_start"))
        chunk_end = _as_date(claimed.get("date_end"))
        chunk_days = int(run.get("chunk_days") or 7)
        job_type = str(run.get("job_type") or "manual")

        if job_type == "historical_backfill":
            response = google_ads_service.sync_customer_for_client_historical_range(
                client_id=client_id,
                customer_id=account_id,
                start_date=chunk_start,
                end_date=chunk_end,
                chunk_days=chunk_days,
            )
            rows_written = int(response.get("rows_upserted", 0) or 0)
        else:
            days = max(1, (chunk_end - chunk_start).days + 1)
            response = google_ads_service.sync_customer_for_client(
                client_id=client_id,
                customer_id=account_id,
                start_date=chunk_start,
                end_date=chunk_end,
                days=days,
                chunk_days=chunk_days,
            )
            rows_written = int(response.get("inserted_rows", 0) or 0)
    except Exception as exc:  # noqa: BLE001
        chunk_error = str(exc)[:300]

    duration_ms = int((time.monotonic() - started) * 1000)

    if chunk_error is None:
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="done",
            rows_written=rows_written,
            duration_ms=duration_ms,
            mark_finished=True,
        )
        sync_runs_store.update_sync_run_progress(
            job_id=job_id,
            chunks_done_delta=1,
            rows_written_delta=rows_written,
        )
    else:
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="error",
            error=chunk_error,
            rows_written=0,
            duration_ms=duration_ms,
            mark_finished=True,
        )
        sync_runs_store.update_sync_run_progress(
            job_id=job_id,
            chunks_done_delta=1,
            rows_written_delta=0,
        )

    _finalize_run_if_complete(job_id)
    return True


def run_worker() -> None:
    settings = load_settings()
    if settings.app_env == "test":
        raise RuntimeError("sync worker should not run when APP_ENV=test")

    poll_seconds = max(0.1, float(os.environ.get("SYNC_WORKER_POLL_SECONDS", "2") or "2"))
    platform_filter_raw = os.environ.get("SYNC_WORKER_PLATFORM")
    platform_filter = platform_filter_raw.strip() if platform_filter_raw is not None and platform_filter_raw.strip() != "" else None
    once = os.environ.get("SYNC_WORKER_ONCE", "0") == "1"

    logger.info("sync_worker.start poll_seconds=%s platform_filter=%s once=%s", poll_seconds, platform_filter, once)
    while True:
        processed = process_next_chunk(platform_filter=platform_filter)
        if once:
            return
        if not processed:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    run_worker()
