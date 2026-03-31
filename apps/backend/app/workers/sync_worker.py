from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import os
import time

from app.core.config import load_settings
from app.services.error_observability import sanitize_payload, sanitize_text
from app.services.client_registry import client_registry_service
from app.services.entity_performance_reports import upsert_ad_group_performance_reports, upsert_ad_unit_performance_reports, upsert_campaign_performance_reports, upsert_keyword_performance_reports
from app.services.platform_entity_store import upsert_platform_ad_groups, upsert_platform_ads, upsert_platform_campaigns, upsert_platform_keywords
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.storage_media_remote_ingest import storage_media_remote_ingest_service
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service
from app.services.platform_watermarks_reconcile import reconcile_platform_account_watermarks
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store

logger = logging.getLogger(__name__)

_SUPPORTED_GRAINS = {"account_daily", "campaign_daily", "ad_group_daily", "ad_daily", "keyword_daily"}
_GRAIN_NOT_SUPPORTED_ERROR = "grain_not_supported"
_STORAGE_MEDIA_SYNC_WORKER_REMOTE_INGEST_SOURCE = "platform_sync"
_ALLOWED_STORAGE_MEDIA_KINDS = {"image", "video", "document"}

_GOOGLE_ADS_INTER_CHUNK_DELAY_SECONDS = 0.5
_GOOGLE_ADS_MAX_CONCURRENT_CHUNKS_PER_JOB = 3


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


def _storage_media_sync_worker_remote_ingest_enabled() -> bool:
    try:
        settings = load_settings()
    except Exception:  # noqa: BLE001
        return False
    return bool(getattr(settings, "storage_media_sync_worker_remote_ingest_enabled", False))


def _resolve_remote_url_for_storage_ingest(snapshot: dict[str, object]) -> str:
    candidates = (
        snapshot.get("remote_url"),
        snapshot.get("media_remote_url"),
        snapshot.get("creative_remote_url"),
        snapshot.get("document_remote_url"),
    )
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if normalized != "":
            return normalized
    return ""


def _resolve_kind_for_storage_ingest(snapshot: dict[str, object]) -> str:
    raw_kind = str(
        snapshot.get("remote_media_kind")
        or snapshot.get("media_kind")
        or "",
    ).strip().lower()
    if raw_kind in _ALLOWED_STORAGE_MEDIA_KINDS:
        return raw_kind
    return ""


def _best_effort_archive_sync_remote_media(
    *,
    platform: str,
    job_id: str,
    chunk_index: int,
    grain: str,
    account_id: str,
    client_id: int,
    snapshot: dict[str, object],
    success_metadata: dict[str, object],
) -> None:
    if not _storage_media_sync_worker_remote_ingest_enabled():
        logger.info(
            "sync_worker.remote_ingest_disabled platform=%s job_id=%s chunk_index=%s",
            platform,
            job_id,
            chunk_index,
        )
        return

    remote_url = _resolve_remote_url_for_storage_ingest(snapshot)
    if remote_url == "":
        logger.info(
            "sync_worker.remote_ingest_skipped reason=missing_remote_url platform=%s job_id=%s chunk_index=%s",
            platform,
            job_id,
            chunk_index,
        )
        return

    kind = _resolve_kind_for_storage_ingest(snapshot)
    if kind == "":
        logger.info(
            "sync_worker.remote_ingest_skipped reason=missing_kind platform=%s job_id=%s chunk_index=%s",
            platform,
            job_id,
            chunk_index,
        )
        return

    original_filename = str(snapshot.get("remote_original_filename") or "").strip() or None
    mime_type = str(snapshot.get("remote_mime_type") or "").strip() or None
    ingest_metadata = {
        "platform": platform,
        "account_id": account_id,
        "job_id": job_id,
        "chunk_index": int(chunk_index),
        "grain": grain,
    }

    try:
        ingest_result = storage_media_remote_ingest_service.upload_from_url(
            client_id=int(client_id),
            kind=kind,
            source=_STORAGE_MEDIA_SYNC_WORKER_REMOTE_INGEST_SOURCE,
            remote_url=remote_url,
            original_filename=original_filename,
            mime_type=mime_type,
            metadata=ingest_metadata,
        )
        success_metadata["storage_media_id"] = str(ingest_result.media_id)
        success_metadata["storage_bucket"] = str(ingest_result.bucket)
        success_metadata["storage_key"] = str(ingest_result.key)
        logger.info(
            "sync_worker.remote_ingest_success platform=%s job_id=%s chunk_index=%s media_id=%s",
            platform,
            job_id,
            chunk_index,
            ingest_result.media_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sync_worker.remote_ingest_failed platform=%s job_id=%s chunk_index=%s error=%s",
            platform,
            job_id,
            chunk_index,
            exc.__class__.__name__,
        )




def _resolve_successful_coverage_end(*, job_id: str, fallback_date_end: date) -> date:
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception:
        return fallback_date_end

    successful_ends: list[date] = []
    for chunk in chunks:
        status = str(chunk.get("status") or "").strip().lower()
        if status not in {"done", "success", "completed"}:
            continue
        raw_end = chunk.get("date_end")
        if raw_end is None:
            continue
        try:
            successful_ends.append(_as_date(raw_end))
        except Exception:
            continue

    if not successful_ends:
        return fallback_date_end
    return max(successful_ends)


def _is_tiktok_empty_success_run(*, job_id: str) -> bool:
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception:
        return False
    if len(chunks) <= 0:
        return False

    has_success_chunk = False
    for chunk in chunks:
        status = str(chunk.get("status") or "").strip().lower()
        if status in {"done", "success", "completed"}:
            has_success_chunk = True
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        rows_downloaded = int(metadata.get("rows_downloaded") or metadata.get("provider_row_count") or 0)
        rows_mapped = int(metadata.get("rows_mapped") or 0)
        if rows_downloaded > 0 or rows_mapped > 0:
            return False

    return has_success_chunk


def _tiktok_empty_success_summary(*, job_id: str) -> dict[str, object]:
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception:
        return {"is_empty_success": False, "rows_downloaded": 0, "rows_mapped": 0, "zero_row_marker": None}

    rows_downloaded = 0
    rows_mapped = 0
    zero_row_marker = None
    has_success_chunk = False
    for chunk in chunks:
        status = str(chunk.get("status") or "").strip().lower()
        if status in {"done", "success", "completed"}:
            has_success_chunk = True
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        rows_downloaded += int(metadata.get("rows_downloaded") or metadata.get("provider_row_count") or 0)
        rows_mapped += int(metadata.get("rows_mapped") or 0)
        if zero_row_marker is None:
            marker_candidate = str(metadata.get("zero_row_marker") or "").strip()
            if marker_candidate != "":
                zero_row_marker = marker_candidate
            else:
                nested = metadata.get("zero_row_observability")
                if isinstance(nested, list) and len(nested) > 0 and isinstance(nested[0], dict):
                    nested_marker = str((nested[0] or {}).get("zero_row_marker") or "").strip()
                    if nested_marker != "":
                        zero_row_marker = nested_marker

    return {
        "is_empty_success": bool(has_success_chunk and rows_downloaded == 0 and rows_mapped == 0),
        "rows_downloaded": int(rows_downloaded),
        "rows_mapped": int(rows_mapped),
        "zero_row_marker": zero_row_marker,
    }




def _tiktok_parser_failure_summary(*, job_id: str) -> dict[str, object]:
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception:
        return {"is_parser_failure": False, "rows_downloaded": 0, "rows_mapped": 0, "zero_row_marker": None}

    rows_downloaded = 0
    rows_mapped = 0
    zero_row_marker = None
    has_success_chunk = False
    for chunk in chunks:
        status = str(chunk.get("status") or "").strip().lower()
        if status in {"done", "success", "completed"}:
            has_success_chunk = True
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        rows_downloaded += int(metadata.get("rows_downloaded") or metadata.get("provider_row_count") or 0)
        rows_mapped += int(metadata.get("rows_mapped") or 0)
        if zero_row_marker is None:
            marker_candidate = str(metadata.get("zero_row_marker") or "").strip()
            if marker_candidate != "":
                zero_row_marker = marker_candidate
            else:
                nested = metadata.get("zero_row_observability")
                if isinstance(nested, list) and len(nested) > 0 and isinstance(nested[0], dict):
                    nested_marker = str((nested[0] or {}).get("zero_row_marker") or "").strip()
                    if nested_marker != "":
                        zero_row_marker = nested_marker

    return {
        "is_parser_failure": bool(has_success_chunk and rows_downloaded > 0 and rows_mapped == 0),
        "rows_downloaded": int(rows_downloaded),
        "rows_mapped": int(rows_mapped),
        "zero_row_marker": zero_row_marker,
    }

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
        run_error = sanitize_text(run.get("error") or "one or more chunks failed", max_len=300)
        metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
        metadata_patch = dict(metadata)
        metadata_patch["last_error_summary"] = sanitize_text(run.get("error_summary") or run_error, max_len=300)
        if isinstance(run.get("error_details"), dict):
            metadata_patch["last_error_details"] = sanitize_payload(run.get("error_details"))
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status="error",
            mark_finished=True,
            error=run_error,
            metadata=metadata_patch,
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
        if platform == "tiktok_ads":
            parser_failure_summary = _tiktok_parser_failure_summary(job_id=job_id)
            if bool(parser_failure_summary.get("is_parser_failure")):
                parser_error = "parser_failure: provider returned rows but none were mapped"
                metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
                metadata_patch = dict(metadata)
                metadata_patch["parser_failure"] = True
                metadata_patch["mapping_failure"] = True
                metadata_patch["rows_downloaded"] = int(parser_failure_summary.get("rows_downloaded") or 0)
                metadata_patch["rows_mapped"] = int(parser_failure_summary.get("rows_mapped") or 0)
                metadata_patch["zero_row_marker"] = parser_failure_summary.get("zero_row_marker")
                metadata_patch["last_error_summary"] = parser_error
                metadata_patch["last_error_details"] = {
                    "error_category": "parser_failure",
                    "provider_row_count": int(parser_failure_summary.get("rows_downloaded") or 0),
                    "rows_mapped": int(parser_failure_summary.get("rows_mapped") or 0),
                    "zero_row_marker": parser_failure_summary.get("zero_row_marker"),
                }
                sync_runs_store.update_sync_run_status(
                    job_id=job_id,
                    status="error",
                    mark_finished=True,
                    error=parser_error,
                    metadata=metadata_patch,
                )
                if account_id != "":
                    client_registry_service.update_platform_account_operational_metadata(
                        platform=platform,
                        account_id=account_id,
                        last_synced_at=now_utc,
                        last_error=parser_error,
                        last_run_id=job_id,
                    )
                logger.warning(
                    "sync_worker.tiktok_parser_failure job_id=%s account_id=%s rows_downloaded=%s",
                    job_id,
                    account_id,
                    parser_failure_summary.get("rows_downloaded"),
                )
                return

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
            status_metadata_patch: dict[str, object] = {}
            if job_type == "historical_backfill":
                if platform == "tiktok_ads":
                    empty_summary = _tiktok_empty_success_summary(job_id=job_id)
                    if bool(empty_summary.get("is_empty_success")):
                        status_metadata_patch["no_data_success"] = True
                        status_metadata_patch["empty_success"] = True
                        status_metadata_patch["rows_downloaded"] = int(empty_summary.get("rows_downloaded") or 0)
                        status_metadata_patch["rows_mapped"] = int(empty_summary.get("rows_mapped") or 0)
                        status_metadata_patch["zero_row_marker"] = empty_summary.get("zero_row_marker")
                        logger.info(
                            "sync_worker.tiktok_empty_success_no_coverage_advance job_id=%s account_id=%s",
                            job_id,
                            account_id,
                        )
                    else:
                        metadata_kwargs["backfill_completed_through"] = _resolve_successful_coverage_end(
                            job_id=job_id,
                            fallback_date_end=run_date_end,
                        )
                else:
                    metadata_kwargs["backfill_completed_through"] = _resolve_successful_coverage_end(
                        job_id=job_id,
                        fallback_date_end=run_date_end,
                    )
            else:
                metadata_kwargs["rolling_synced_through"] = run_date_end
            client_registry_service.update_platform_account_operational_metadata(**metadata_kwargs)
            if len(status_metadata_patch) > 0:
                sync_runs_store.update_sync_run_status(
                    job_id=job_id,
                    status="done",
                    metadata=status_metadata_patch,
                )
            if platform == "tiktok_ads" and job_type == "historical_backfill":
                try:
                    cleanup_result = sync_runs_store.cleanup_superseded_tiktok_failed_runs(account_ids=[account_id])
                    logger.info(
                        "sync_worker.tiktok_cleanup account_id=%s superseded=%s deleted_runs=%s deleted_chunks=%s",
                        account_id,
                        cleanup_result.get("superseded_run_count"),
                        cleanup_result.get("deleted_runs"),
                        cleanup_result.get("deleted_chunks"),
                    )
                except Exception:
                    logger.exception("sync_worker.tiktok_cleanup_failed account_id=%s job_id=%s", account_id, job_id)
            if platform == "google_ads" and run_grain in ("campaign_daily", "ad_group_daily", "ad_daily", "keyword_daily"):
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
    success_metadata: dict[str, object] = {"grain": grain}
    chunk_error: str | None = None
    chunk_error_details: dict[str, object] | None = None
    platform = str(run.get("platform") or "").strip().lower()
    account_id = str(run.get("account_id") or "").strip()
    client_id = int(run.get("client_id") or 0)

    try:

        if account_id == "":
            raise RuntimeError("run has no account_id")

        if client_id <= 0:
            raise RuntimeError("run has no client_id mapping")

        chunk_start = _as_date(claimed.get("date_start"))
        chunk_end = _as_date(claimed.get("date_end"))
        chunk_days = int(run.get("chunk_days") or 7)
        job_type = str(run.get("job_type") or "manual")

        if platform == "meta_ads":
            snapshot = meta_ads_service.sync_client(
                client_id=client_id,
                start_date=chunk_start,
                end_date=chunk_end,
                grain=grain,
                account_id=account_id,
            )
            rows_written = int(snapshot.get("rows_written") or 0)
        elif platform == "tiktok_ads":
            snapshot = tiktok_ads_service.sync_client(
                client_id=client_id,
                start_date=chunk_start,
                end_date=chunk_end,
                grain=grain,
                account_id=account_id,
            )
            rows_written = int(snapshot.get("rows_written") or 0)
            success_metadata.update(
                {
                    "rows_downloaded": int(snapshot.get("rows_downloaded") or 0),
                    "provider_row_count": int(snapshot.get("provider_row_count") or 0),
                    "rows_mapped": int(snapshot.get("rows_mapped") or 0),
                }
            )
            zero_row_observability = snapshot.get("zero_row_observability")
            if isinstance(zero_row_observability, list):
                success_metadata["zero_row_observability"] = sanitize_payload(zero_row_observability)
            _best_effort_archive_sync_remote_media(
                platform=platform,
                job_id=job_id,
                chunk_index=chunk_index,
                grain=grain,
                account_id=account_id,
                client_id=client_id,
                snapshot=snapshot,
                success_metadata=success_metadata,
            )
        elif platform != "google_ads":
            raise RuntimeError(f"unsupported platform '{platform}'")
        elif grain == "campaign_daily":
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
        elif grain == "ad_daily":
            chunk_end_exclusive = chunk_end + timedelta(days=1)
            ad_rows = google_ads_service.fetch_ad_unit_daily_metrics(
                customer_id=account_id,
                start_date=chunk_start,
                end_date_exclusive=chunk_end_exclusive,
                source_job_id=job_id,
            )
            ad_entity_by_id: dict[str, dict[str, object]] = {}
            for row in ad_rows:
                ad_id = str(row.get("ad_id") or "").strip()
                if ad_id == "":
                    continue
                ad_entity_by_id[ad_id] = {
                    "platform": platform,
                    "account_id": account_id,
                    "ad_id": ad_id,
                    "ad_group_id": row.get("ad_group_id"),
                    "campaign_id": row.get("campaign_id"),
                    "name": row.get("ad_name"),
                    "status": row.get("ad_status"),
                    "raw_payload": {
                        "campaign_id": row.get("campaign_id"),
                        "ad_group_id": row.get("ad_group_id"),
                        "ad_id": row.get("ad_id"),
                        "ad_name": row.get("ad_name"),
                        "ad_status": row.get("ad_status"),
                    },
                    "payload_hash": f"{ad_id}:{row.get('ad_group_id')}:{row.get('ad_status')}",
                }

            upsert_rows = [
                {
                    "platform": platform,
                    "account_id": account_id,
                    "ad_id": row.get("ad_id"),
                    "campaign_id": row.get("campaign_id"),
                    "ad_group_id": row.get("ad_group_id"),
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
                for row in ad_rows
            ]
            with sync_runs_store._connect() as conn:
                upsert_platform_ads(conn, list(ad_entity_by_id.values()))
                rows_written = int(upsert_ad_unit_performance_reports(conn, upsert_rows) or 0)
                conn.commit()
        elif grain == "keyword_daily":
            chunk_end_exclusive = chunk_end + timedelta(days=1)
            keyword_rows = google_ads_service.fetch_keyword_daily_metrics(
                customer_id=account_id,
                start_date=chunk_start,
                end_date_exclusive=chunk_end_exclusive,
                source_job_id=job_id,
            )
            keyword_entity_by_id: dict[str, dict[str, object]] = {}
            for row in keyword_rows:
                keyword_id = str(row.get("keyword_id") or "").strip()
                if keyword_id == "":
                    continue
                keyword_entity_by_id[keyword_id] = {
                    "platform": platform,
                    "account_id": account_id,
                    "keyword_id": keyword_id,
                    "campaign_id": row.get("campaign_id"),
                    "ad_group_id": row.get("ad_group_id"),
                    "keyword_text": row.get("keyword_text"),
                    "match_type": row.get("match_type"),
                    "status": row.get("status"),
                    "raw_payload": row.get("keyword_raw") if isinstance(row.get("keyword_raw"), dict) else {},
                    "payload_hash": row.get("keyword_payload_hash"),
                }

            upsert_rows = [
                {
                    "platform": platform,
                    "account_id": account_id,
                    "keyword_id": row.get("keyword_id"),
                    "campaign_id": row.get("campaign_id"),
                    "ad_group_id": row.get("ad_group_id"),
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
                for row in keyword_rows
            ]
            with sync_runs_store._connect() as conn:
                upsert_platform_keywords(conn, list(keyword_entity_by_id.values()))
                rows_written = int(upsert_keyword_performance_reports(conn, upsert_rows) or 0)
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
        raw_error = sanitize_text(exc, max_len=300)
        if raw_error.startswith(f"{_GRAIN_NOT_SUPPORTED_ERROR}:"):
            chunk_error = raw_error
        else:
            chunk_error = raw_error
        provider_error_code = None
        provider_error_message = None
        http_status = None
        endpoint = None
        retryable = None
        error_category = None
        token_source = None
        advertiser_id = None
        if isinstance(exc, (MetaAdsIntegrationError, TikTokAdsIntegrationError)):
            provider_error_code = exc.provider_error_code
            provider_error_message = exc.provider_error_message
            http_status = exc.http_status
            endpoint = exc.endpoint
            retryable = exc.retryable
            error_category = getattr(exc, "error_category", None)
            token_source = getattr(exc, "token_source", None)
            advertiser_id = getattr(exc, "advertiser_id", None)
            if provider_error_message and chunk_error == "":
                chunk_error = sanitize_text(provider_error_message, max_len=300)
        elif isinstance(exc, GoogleAdsIntegrationError):
            provider_error_code = exc.provider_error_code
            provider_error_message = exc.provider_error_message
            http_status = exc.http_status
            endpoint = exc.endpoint
            retryable = exc.retryable
            if provider_error_message and chunk_error == "":
                chunk_error = sanitize_text(provider_error_message, max_len=300)
        chunk_error_details = sanitize_payload(
            {
                "platform": platform,
                "account_id": account_id,
                "client_id": client_id,
                "grain": grain,
                "chunk_index": chunk_index,
                "start_date": chunk_start.isoformat() if 'chunk_start' in locals() else None,
                "end_date": chunk_end.isoformat() if 'chunk_end' in locals() else None,
                "error_summary": chunk_error,
                "provider_error_code": provider_error_code,
                "provider_error_message": provider_error_message,
                "http_status": http_status,
                "endpoint": endpoint,
                "retryable": retryable,
                "error_category": error_category,
                "token_source": token_source,
                "advertiser_id": advertiser_id,
            }
        )
        if isinstance(chunk_error_details, dict):
            chunk_error_details["error_category"] = error_category
            chunk_error_details["token_source"] = token_source
            chunk_error_details["advertiser_id"] = advertiser_id
            if isinstance(exc, GoogleAdsIntegrationError) and exc.retry_after_seconds is not None:
                chunk_error_details["retry_after_seconds"] = exc.retry_after_seconds

    duration_ms = int((time.monotonic() - started) * 1000)

    if chunk_error is None:
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="done",
            metadata=success_metadata,
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
        run["error_summary"] = chunk_error
        run["error_details"] = chunk_error_details
        sync_run_chunks_store.update_sync_run_chunk_status(
            job_id=job_id,
            chunk_index=chunk_index,
            status="error",
            error=chunk_error,
            metadata={
                "grain": grain,
                "last_error_summary": chunk_error,
                "last_error_details": chunk_error_details or {},
            },
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

        if http_status == 429 and platform == "google_ads":
            abort_error = "skipped: Google Ads API quota exhausted (RESOURCE_EXHAUSTED)"
            aborted_count = sync_run_chunks_store.fail_queued_chunks_for_job(
                job_id=job_id,
                error=abort_error,
            )
            if aborted_count > 0:
                sync_runs_store.update_sync_run_progress(
                    job_id=job_id,
                    chunks_done_delta=aborted_count,
                    rows_written_delta=0,
                )
            cross_grain_abort_error = "skipped: Google Ads API quota exhausted for account (RESOURCE_EXHAUSTED)"
            try:
                cross_result = sync_run_chunks_store.fail_queued_chunks_for_account(
                    platform=platform,
                    account_id=account_id,
                    error=cross_grain_abort_error,
                    exclude_job_id=job_id,
                )
                cross_aborted = int(cross_result.get("affected") or 0)
            except Exception:
                logger.exception("sync_worker.cross_grain_abort_failed job_id=%s account_id=%s", job_id, account_id)
                cross_aborted = 0
            logger.warning(
                "sync_worker.quota_exhausted_abort job_id=%s aborted_chunks=%s cross_grain_aborted=%s retry_after_seconds=%s",
                job_id,
                aborted_count,
                cross_aborted,
                chunk_error_details.get("retry_after_seconds") if chunk_error_details else None,
            )

    _finalize_run_if_complete(run)

    chunks_total = int(run.get("chunks_total") or 0)
    if platform == "google_ads":
        logger.info(
            "[GOOGLE-ADS-RATE] job_id=%s, chunks_total=%s, delay_ms=%s, max_workers=%s",
            job_id,
            chunks_total,
            int(_GOOGLE_ADS_INTER_CHUNK_DELAY_SECONDS * 1000),
            _GOOGLE_ADS_MAX_CONCURRENT_CHUNKS_PER_JOB,
        )
        time.sleep(_GOOGLE_ADS_INTER_CHUNK_DELAY_SECONDS)

    return True


_MAX_BACKOFF_SECONDS = 60


def run_worker() -> None:
    settings = load_settings()
    if settings.app_env == "test":
        raise RuntimeError("sync worker should not run when APP_ENV=test")

    poll_seconds = max(0.1, float(os.environ.get("SYNC_WORKER_POLL_SECONDS", "2") or "2"))
    platform_filter_raw = os.environ.get("SYNC_WORKER_PLATFORM")
    platform_filter = platform_filter_raw.strip() if platform_filter_raw is not None and platform_filter_raw.strip() != "" else None
    once = os.environ.get("SYNC_WORKER_ONCE", "0") == "1"

    logger.info("sync_worker.start poll_seconds=%s platform_filter=%s once=%s", poll_seconds, platform_filter, once)
    consecutive_errors = 0
    while True:
        try:
            processed = process_next_chunk(platform_filter=platform_filter)
            consecutive_errors = 0
            if once:
                return
            if not processed:
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            logger.info("sync_worker.shutdown")
            return
        except Exception:
            consecutive_errors += 1
            backoff = min(poll_seconds * (2 ** consecutive_errors), _MAX_BACKOFF_SECONDS)
            logger.exception("sync_worker.transient_error consecutive=%d backoff=%.1fs", consecutive_errors, backoff)
            if once:
                raise
            time.sleep(backoff)


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    run_worker()
