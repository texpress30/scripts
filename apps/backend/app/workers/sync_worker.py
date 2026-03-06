from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import os
import time

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.entity_performance_reports import upsert_ad_group_performance_reports, upsert_campaign_performance_reports
from app.services.platform_entity_store import upsert_platform_ad_groups, upsert_platform_campaigns
from app.services.google_ads import google_ads_service
from app.services.platform_watermarks_reconcile import reconcile_platform_account_watermarks
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store

logger = logging.getLogger(__name__)

_SUPPORTED_GRAINS = {"account_daily", "campaign_daily", "ad_group_daily", "ad_daily"}
_GRAIN_NOT_SUPPORTED_ERROR = "grain_not_supported"


def _as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    parsed = date.fromisoformat(str(value))
    return parsed


def _normalize_run_grain(run: dict[str, object]) -> str:
    grain = str(run.get("grain") or "account_daily").strip().lower()
    if grain == "":
        return "account_daily"
    return grain


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
    run_grain = _normalize_run_grain(run)

    if int(counts.get("errors") or 0) > 0:
        run_error = str(run.get("error") or "one or more chunks failed")
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="error",
            mark_finished=True,
            error=run_error,
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
            if platform == "google_ads" and run_grain in ("campaign_daily", "ad_group_daily"):
                with sync_runs_store._connect() as conn:
                    reconcile_platform_account_watermarks(
                        conn,
                        platform=platform,
                        account_id=account_id,
                        grains=[run_grain],
                    )
                    conn.commit()


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

    grain = _normalize_run_grain(run)
    if grain not in _SUPPORTED_GRAINS:
        chunk_error = f"{_GRAIN_NOT_SUPPORTED_ERROR}:{grain}"
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="error",
            error=chunk_error,
            metadata={"grain": grain, "error_code": _GRAIN_NOT_SUPPORTED_ERROR},
            rows_written=0,
            duration_ms=0,
            mark_finished=True,
        )
        sync_runs_store.update_sync_run_progress(
            job_id=job_id,
            chunks_done_delta=1,
            rows_written_delta=0,
        )
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="error",
            mark_finished=True,
            error=chunk_error,
        )
        logger.error("sync_worker.unsupported_grain job_id=%s grain=%s", job_id, grain)
        return True

    started = time.monotonic()
    rows_written = 0
    chunk_error: str | None = None

    try:
        platform = str(run.get("platform") or "").strip()
        if grain != "account_daily" and platform != "google_ads":
            raise RuntimeError(f"{_GRAIN_NOT_SUPPORTED_ERROR}:{grain}")
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

        if grain == "campaign_daily":
            chunk_end_exclusive = chunk_end + timedelta(days=1)
            campaign_rows = google_ads_service.fetch_campaign_daily_metrics(
                customer_id=account_id,
                start_date=chunk_start,
                end_date_exclusive=chunk_end_exclusive,
            )
            campaign_entity_by_id: dict[str, dict[str, object]] = {}
            for row in campaign_rows:
                campaign_id = str(row.get("campaign_id") or "").strip()
                if campaign_id == "":
                    continue
                campaign_entity_by_id[campaign_id] = {
                    "platform": platform,
                    "account_id": account_id,
                    "campaign_id": campaign_id,
                    "name": row.get("campaign_name"),
                    "status": row.get("campaign_status"),
                    "raw_payload": row.get("campaign_raw") if isinstance(row.get("campaign_raw"), dict) else {},
                    "payload_hash": row.get("campaign_payload_hash"),
                }

            upsert_rows = [
                {
                    "platform": platform,
                    "account_id": account_id,
                    "campaign_id": row.get("campaign_id"),
                    "report_date": row.get("report_date"),
                    "spend": row.get("spend", 0),
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "conversions": row.get("conversions", 0),
                    "conversion_value": row.get("conversion_value", 0),
                    "extra_metrics": row.get("extra_metrics") if isinstance(row.get("extra_metrics"), dict) else {},
                    "source_window_start": chunk_start,
                    "source_window_end": chunk_end_exclusive,
                    "source_job_id": job_id,
                }
                for row in campaign_rows
            ]
            with sync_runs_store._connect() as conn:
                upsert_platform_campaigns(conn, list(campaign_entity_by_id.values()))
                rows_written = int(upsert_campaign_performance_reports(conn, upsert_rows) or 0)
                conn.commit()
        elif grain == "ad_group_daily":
            chunk_end_exclusive = chunk_end + timedelta(days=1)
            ad_group_rows = google_ads_service.fetch_ad_group_daily_metrics(
                customer_id=account_id,
                start_date=chunk_start,
                end_date_exclusive=chunk_end_exclusive,
                source_job_id=job_id,
            )
            ad_group_entity_by_id: dict[str, dict[str, object]] = {}
            for row in ad_group_rows:
                ad_group_id = str(row.get("ad_group_id") or "").strip()
                if ad_group_id == "":
                    continue
                ad_group_entity_by_id[ad_group_id] = {
                    "platform": platform,
                    "account_id": account_id,
                    "ad_group_id": ad_group_id,
                    "campaign_id": row.get("campaign_id"),
                    "name": row.get("ad_group_name"),
                    "status": None,
                    "raw_payload": {
                        "campaign_id": row.get("campaign_id"),
                        "campaign_name": row.get("campaign_name"),
                        "ad_group_id": row.get("ad_group_id"),
                        "ad_group_name": row.get("ad_group_name"),
                    },
                    "payload_hash": f"{ad_group_id}:{row.get('campaign_id')}:{row.get('ad_group_name')}",
                }

            upsert_rows = [
                {
                    "platform": platform,
                    "account_id": account_id,
                    "ad_group_id": row.get("ad_group_id"),
                    "campaign_id": row.get("campaign_id"),
                    "report_date": row.get("report_date"),
                    "spend": row.get("spend", 0),
                    "impressions": row.get("impressions", 0),
                    "clicks": row.get("clicks", 0),
                    "conversions": row.get("conversions", 0),
                    "conversion_value": row.get("conversion_value", 0),
                    "extra_metrics": row.get("extra_metrics") if isinstance(row.get("extra_metrics"), dict) else {},
                    "source_window_start": chunk_start,
                    "source_window_end": chunk_end_exclusive,
                    "source_job_id": job_id,
                }
                for row in ad_group_rows
            ]
            with sync_runs_store._connect() as conn:
                upsert_platform_ad_groups(conn, list(ad_group_entity_by_id.values()))
                rows_written = int(upsert_ad_group_performance_reports(conn, upsert_rows) or 0)
                conn.commit()
        elif job_type == "historical_backfill":
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
        raw_error = str(exc)[:300]
        if raw_error.startswith(f"{_GRAIN_NOT_SUPPORTED_ERROR}:"):
            chunk_error = raw_error
        else:
            chunk_error = raw_error

    duration_ms = int((time.monotonic() - started) * 1000)

    if chunk_error is None:
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="done",
            metadata={"grain": grain},
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
        run["error"] = chunk_error
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="error",
            error=chunk_error,
            metadata={"grain": grain},
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
