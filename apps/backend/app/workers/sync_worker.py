from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import os
import time

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.google_ads import google_ads_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store

logger = logging.getLogger(__name__)


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    parsed = date.fromisoformat(str(value))
    return parsed


def _finalize_run_if_complete(run: dict[str, object]) -> None:
    job_id = str(run.get("job_id") or "")
    counts = sync_run_chunks_store.get_sync_run_chunk_status_counts(job_id)
    if int(counts.get("remaining") or 0) > 0:
        return

    now_utc = datetime.now(timezone.utc)
    platform = str(run.get("platform") or "").strip()
    account_id = str(run.get("account_id") or "").strip()
    job_type = str(run.get("job_type") or "manual")
    run_date_end = _as_date(run.get("date_end"))

    if int(counts.get("errors") or 0) > 0:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="error",
            mark_finished=True,
            error="one or more chunks failed",
        )
        if platform != "" and account_id != "":
            client_registry_service.update_platform_account_operational_metadata(
                platform=platform,
                account_id=account_id,
                last_synced_at=now_utc,
                last_error=(str(run.get("error") or "one or more chunks failed"))[:300],
                last_run_id=job_id,
            )
    else:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="done",
            mark_finished=True,
        )
        if platform != "" and account_id != "":
            metadata_kwargs: dict[str, object] = {
                "platform": platform,
                "account_id": account_id,
                "last_synced_at": now_utc,
                "last_success_at": now_utc,
                "last_error": None,
                "last_run_id": job_id,
            }
            if job_type == "historical_backfill":
                metadata_kwargs["backfill_completed_through"] = run_date_end
            else:
                metadata_kwargs["rolling_synced_through"] = run_date_end
            client_registry_service.update_platform_account_operational_metadata(**metadata_kwargs)


def process_next_chunk(*, platform_filter: str | None = None, max_attempts: int = 5) -> bool:
    claimed = sync_run_chunks_store.claim_next_queued_chunk_any(platform=platform_filter, max_attempts=max_attempts)
    if claimed is None:
        return False

    job_id = str(claimed.get("job_id") or "")
    chunk_index = int(claimed.get("chunk_index") or 0)
    logger.info("sync_worker.chunk_claimed job_id=%s chunk_index=%s", job_id, chunk_index)

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
        logger.info("sync_worker.run_started job_id=%s", job_id)

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
        logger.info(
            "sync_worker.chunk_completed job_id=%s chunk_index=%s rows_written=%s duration_ms=%s",
            job_id,
            chunk_index,
            rows_written,
            duration_ms,
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
        logger.error(
            "sync_worker.chunk_failed job_id=%s chunk_index=%s error=%s duration_ms=%s",
            job_id,
            chunk_index,
            chunk_error,
            duration_ms,
        )

    _finalize_run_if_complete(run)
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
