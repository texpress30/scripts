from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import base64
from time import perf_counter
import logging
import os
from typing import Literal
from uuid import uuid4
from urllib import parse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store
from app.workers.rolling_scheduler import enqueue_rolling_sync_runs

router = APIRouter(prefix="/agency/sync-runs", tags=["sync-orchestration"])
logger = logging.getLogger(__name__)


_ALLOWED_GRAINS = ("account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily")
GrainValue = Literal["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"]


class CreateBatchSyncRunsRequest(BaseModel):
    platform: Literal["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]
    account_ids: list[str]
    job_type: Literal["historical_backfill", "rolling_refresh", "manual"] = "manual"
    start_date: date | None = None
    end_date: date | None = None
    days: int | None = Field(default=None, ge=1, le=3650)
    chunk_days: int = Field(default=7, ge=1, le=31)
    grain: GrainValue | None = None
    grains: list[GrainValue] | None = None



_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200

class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200

class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200


class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200


class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200


class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200


class BatchAccountProgressRequest(BaseModel):
    account_ids: list[str]
    limit_active_only: bool = True


_MAX_PROGRESS_BATCH_ACCOUNT_IDS = 200

class RollingEnqueueRequest(BaseModel):
    platform: Literal["google_ads"] = "google_ads"
    limit: int = Field(default=500, ge=1, le=5000)
    chunk_days: int = Field(default=7, ge=1, le=31)
    force: bool = False

def _normalize_account_id(value: str, *, platform: str | None = None) -> str:
    raw = str(value).strip()
    if raw == "":
        return ""

    normalized = raw.replace("-", "")
    normalized_platform = str(platform or "").strip().lower()
    if normalized_platform == "meta_ads":
        lowered = normalized.lower()
        if lowered.startswith("act_"):
            normalized = normalized[4:]
            lowered = normalized.lower()
        elif lowered.startswith("act") and normalized[3:].isdigit():
            normalized = normalized[3:]
    return normalized


def _is_platform_sync_enabled(platform: str) -> tuple[bool, str | None]:
    normalized = str(platform or "").strip().lower()
    settings = load_settings()
    if normalized == "tiktok_ads" and not settings.ff_tiktok_integration:
        return False, "TikTok integration is disabled by feature flag."
    if normalized == "pinterest_ads" and not settings.ff_pinterest_integration:
        return False, "Pinterest integration is disabled by feature flag."
    if normalized == "snapchat_ads" and not settings.ff_snapchat_integration:
        return False, "Snapchat integration is disabled by feature flag."
    return True, None


def _resolve_date_range(payload: CreateBatchSyncRunsRequest) -> tuple[date, date]:
    if payload.start_date is not None or payload.end_date is not None:
        if payload.start_date is None or payload.end_date is None:
            raise HTTPException(status_code=400, detail="start_date și end_date trebuie furnizate împreună")
        if payload.end_date < payload.start_date:
            raise HTTPException(status_code=400, detail="end_date trebuie să fie >= start_date")
        return payload.start_date, payload.end_date

    if payload.days is None:
        raise HTTPException(status_code=400, detail="Trebuie furnizat fie start_date/end_date, fie days")

    utc_today = datetime.now(timezone.utc).date()
    end_date = utc_today - timedelta(days=1)
    start_date = end_date - timedelta(days=max(1, int(payload.days)) - 1)
    return start_date, end_date


def _build_chunks(*, start_date: date, end_date: date, chunk_days: int) -> list[tuple[int, date, date]]:
    chunks: list[tuple[int, date, date]] = []
    current = start_date
    idx = 0
    while current <= end_date:
        chunk_end = min(current + timedelta(days=max(1, int(chunk_days)) - 1), end_date)
        chunks.append((idx, current, chunk_end))
        idx += 1
        current = chunk_end + timedelta(days=1)
    return chunks


def _entity_grains_enabled() -> bool:
    raw_values = (
        str(os.environ.get("ENTITY_GRAINS_ENABLED", "") or "").strip().lower(),
        str(os.environ.get("ROLLING_ENTITY_GRAINS_ENABLED", "") or "").strip().lower(),
    )
    return any(value in {"1", "true", "yes", "on"} for value in raw_values)


def _coerce_account_sync_start_date(value: object | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _effective_historical_window_for_account(*, platform: str, job_type: str, requested_start: date, requested_end: date, account_sync_start_date: date | None) -> tuple[date, date]:
    normalized_platform = str(platform or "").strip().lower()
    normalized_job_type = str(job_type or "").strip().lower()
    if normalized_platform != "tiktok_ads" or normalized_job_type != "historical_backfill":
        return requested_start, requested_end

    today = datetime.now(timezone.utc).date()
    one_year_floor = today - timedelta(days=_MAX_TIKTOK_HISTORICAL_DAYS)
    baseline_start = account_sync_start_date if account_sync_start_date is not None else requested_start
    effective_start = max(requested_start, baseline_start, one_year_floor)
    if effective_start > requested_end:
        effective_start = requested_end
    return effective_start, requested_end


def _effective_chunk_days(*, platform: str, job_type: str, requested_chunk_days: int) -> int:
    normalized_platform = str(platform or "").strip().lower()
    normalized_job_type = str(job_type or "").strip().lower()
    resolved = max(1, int(requested_chunk_days))
    if normalized_platform == "tiktok_ads" and normalized_job_type == "historical_backfill":
        return min(resolved, _MAX_TIKTOK_HISTORICAL_CHUNK_DAYS)
    return resolved


def _resolve_grains(payload: CreateBatchSyncRunsRequest) -> list[str]:
    explicit_grains_list = payload.grains is not None
    raw_grains = payload.grains
    if raw_grains is None:
        raw_grains = [payload.grain] if payload.grain is not None else []

    normalized: list[str] = []
    for grain in raw_grains:
        value = str(grain).strip().lower()
        if value == "":
            continue
        if value not in _ALLOWED_GRAINS:
            raise HTTPException(status_code=400, detail=f"grain invalid: {value}")
        if value not in normalized:
            normalized.append(value)

    if len(normalized) <= 0:
        normalized = ["account_daily"]

    legacy_request = not explicit_grains_list
    is_google = str(payload.platform).strip().lower() == "google_ads"
    legacy_account_daily_default = len(normalized) == 1 and normalized[0] == "account_daily"
    if legacy_request and is_google and legacy_account_daily_default and _entity_grains_enabled():
        normalized = ["account_daily", "campaign_daily", "ad_group_daily", "keyword_daily", "ad_daily"]

    return normalized





_ACTIVE_CHUNK_STATUSES = {"queued", "running", "pending"}
_SUCCESS_CHUNK_STATUSES = {"done", "success", "completed"}
_ERROR_CHUNK_STATUSES = {"error", "failed"}
_MAX_TIKTOK_HISTORICAL_DAYS = 365
_MAX_TIKTOK_HISTORICAL_CHUNK_DAYS = 30


_SENSITIVE_TOKEN_PARTS = ("token", "secret", "password", "authorization", "api_key", "apikey", "refresh_token")


def _is_sensitive_key(value: object) -> bool:
    key = str(value or "").strip().lower()
    if key == "":
        return False
    return any(part in key for part in _SENSITIVE_TOKEN_PARTS)


def _sanitize_string_for_secrets(value: str) -> str:
    raw = str(value or "")
    if raw == "":
        return ""
    try:
        parsed_url = parse.urlsplit(raw)
        if parsed_url.scheme == "" and parsed_url.netloc == "" and parsed_url.query == "":
            return raw
        query_pairs = parse.parse_qsl(parsed_url.query, keep_blank_values=True)
        if len(query_pairs) <= 0:
            return raw
        sanitized_pairs: list[tuple[str, str]] = []
        for key, item in query_pairs:
            sanitized_pairs.append((key, "***" if _is_sensitive_key(key) else item))
        return parse.urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parse.urlencode(sanitized_pairs), parsed_url.fragment))
    except Exception:
        return raw



def to_json_safe(value: object) -> object:
    if value is None:
        return value
    if isinstance(value, str):
        return _sanitize_string_for_secrets(value)
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return to_json_safe(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except Exception:
            return f"base64:{base64.b64encode(value).decode('ascii')}"
    if isinstance(value, dict):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            normalized_key = str(key)
            normalized[normalized_key] = "***" if _is_sensitive_key(normalized_key) else to_json_safe(item)
        return normalized
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    return str(value)



def _normalize_status(value: object, default: str = "queued") -> str:
    normalized = str(value or default).strip().lower()
    return normalized if normalized != "" else default


def _summarize_run_from_chunks(run: dict[str, object], chunks: list[dict[str, object]]) -> dict[str, object]:
    total_chunks = len(chunks)
    if total_chunks <= 0:
        fallback_total = max(0, int(run.get("chunks_total") or 0))
        fallback_done = max(0, int(run.get("chunks_done") or 0))
        fallback_rows = max(0, int(run.get("rows_written") or 0))
        fallback_status = _normalize_status(run.get("status"), default="queued")
        percent = 0.0 if fallback_total <= 0 else round((fallback_done / fallback_total) * 100.0, 2)
        return {
            "status": fallback_status,
            "chunks_total": fallback_total,
            "chunks_done": fallback_done,
            "error_chunks": 0,
            "active_chunks": 0 if fallback_status in {"done", "error", "partial", "failed", "completed", "success"} else max(0, fallback_total - fallback_done),
            "rows_written": fallback_rows,
            "percent_complete": percent,
        }

    success_chunks = 0
    error_chunks = 0
    active_chunks = 0
    rows_written = 0

    for chunk in chunks:
        chunk_status = _normalize_status(chunk.get("status"), default="queued")
        if chunk_status in _SUCCESS_CHUNK_STATUSES:
            success_chunks += 1
        elif chunk_status in _ERROR_CHUNK_STATUSES:
            error_chunks += 1
        elif chunk_status in _ACTIVE_CHUNK_STATUSES:
            active_chunks += 1
        rows_written += max(0, int(chunk.get("rows_written") or 0))

    if active_chunks > 0:
        original = _normalize_status(run.get("status"), default="queued")
        reconciled_status = "queued" if success_chunks <= 0 and error_chunks <= 0 and original in {"queued", "pending"} else "running"
    else:
        if error_chunks <= 0:
            reconciled_status = "done"
        elif success_chunks > 0:
            reconciled_status = "partial"
        else:
            reconciled_status = "error"

    percent_complete = 0.0 if total_chunks <= 0 else round((success_chunks / total_chunks) * 100.0, 2)
    return {
        "status": reconciled_status,
        "chunks_total": total_chunks,
        "chunks_done": success_chunks,
        "error_chunks": error_chunks,
        "active_chunks": active_chunks,
        "rows_written": rows_written,
        "percent_complete": percent_complete,
    }


def _reconcile_run_payload(run: dict[str, object]) -> dict[str, object]:
    job_id = str(run.get("job_id") or "").strip()
    if job_id == "":
        return dict(run)
    chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    summary = _summarize_run_from_chunks(run, chunks)
    payload = dict(run)
    payload.update(summary)

    platform = str(payload.get("platform") or "").strip().lower()
    if platform == "tiktok_ads":
        existing_metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        merged_metadata = dict(existing_metadata)
        aggregate_rows = _aggregate_tiktok_run_rows_from_chunks(chunks)
        merged_metadata["rows_downloaded"] = int(aggregate_rows.get("rows_downloaded") or 0)
        merged_metadata["rows_mapped"] = int(aggregate_rows.get("rows_mapped") or 0)
        payload["metadata"] = merged_metadata

    return payload



def _coerce_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except Exception:
        return 0


def _aggregate_tiktok_run_rows_from_chunks(chunks: list[dict[str, object]]) -> dict[str, int]:
    latest_by_chunk_index: dict[int, dict[str, object]] = {}
    for idx, chunk in enumerate(chunks):
        chunk_index = chunk.get("chunk_index")
        if chunk_index is None:
            chunk_index = idx
        try:
            normalized_index = int(chunk_index)
        except Exception:
            normalized_index = idx
        latest_by_chunk_index[normalized_index] = chunk

    rows_downloaded = 0
    rows_mapped = 0
    for chunk in latest_by_chunk_index.values():
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        rows_downloaded += _coerce_non_negative_int(metadata.get("rows_downloaded") or metadata.get("provider_row_count"))
        rows_mapped += _coerce_non_negative_int(metadata.get("rows_mapped"))

    return {
        "rows_downloaded": int(rows_downloaded),
        "rows_mapped": int(rows_mapped),
    }


def _summarize_batch_from_runs(runs: list[dict[str, object]]) -> dict[str, object]:
    status_counts = {"queued": 0, "running": 0, "done": 0, "error": 0, "partial": 0}
    chunks_total = 0
    chunks_done = 0
    rows_written = 0
    no_data_success_runs = 0

    for run in runs:
        status = _normalize_status(run.get("status"), default="queued")
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["queued"] += 1
        chunks_total += max(0, int(run.get("chunks_total") or 0))
        chunks_done += max(0, int(run.get("chunks_done") or 0))
        rows_written += max(0, int(run.get("rows_written") or 0))
        metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
        if _is_success_status(status) and bool(metadata.get("no_data_success")):
            no_data_success_runs += 1

    percent = 0.0 if chunks_total <= 0 else round((chunks_done / chunks_total) * 100.0, 2)
    is_all_done = len(runs) > 0 and status_counts.get("done", 0) == len(runs)
    operational_status = "completed_with_no_data" if is_all_done and no_data_success_runs == len(runs) else "normal"
    return {
        "total_runs": len(runs),
        "status_counts": status_counts,
        "chunks_total_sum": chunks_total,
        "chunks_done_sum": chunks_done,
        "rows_written_sum": rows_written,
        "no_data_success_runs": no_data_success_runs,
        "operational_status": operational_status,
        "percent": percent,
    }

def _is_success_status(value: object | None) -> bool:
    return str(value or "").strip().lower() in {"done", "success", "completed"}


def _serialize_run(item: dict[str, object]) -> dict[str, object]:
    metadata = to_json_safe(item.get("metadata") if isinstance(item.get("metadata"), dict) else {})
    trigger_source = metadata.get("trigger_source") or metadata.get("source") or "manual"
    if str(trigger_source) in {"agency_batch", "manual"}:
        trigger_source = "manual"
    elif str(trigger_source) in {"rolling_scheduler", "cron"}:
        trigger_source = "cron"
    run_status = str(item.get("status") or "").strip().lower()
    is_success = _is_success_status(run_status)
    raw_last_error_summary = metadata.get("last_error_summary") or item.get("error")
    raw_last_error_details = metadata.get("last_error_details") if isinstance(metadata, dict) and isinstance(metadata.get("last_error_details"), dict) else None
    last_error_summary = None if is_success else raw_last_error_summary
    last_error_details = None if is_success else raw_last_error_details
    last_error_category = None if is_success else (str((last_error_details or {}).get("error_category") or "").strip() or None)
    operational_status = run_status
    if bool(metadata.get("parser_failure")):
        operational_status = "parser_failure"
    elif is_success and bool(metadata.get("no_data_success")):
        operational_status = "no_data_success"

    return {
        "job_id": item.get("job_id"),
        "batch_id": item.get("batch_id"),
        "job_type": item.get("job_type"),
        "grain": item.get("grain"),
        "platform": item.get("platform"),
        "account_id": item.get("account_id"),
        "client_id": item.get("client_id"),
        "status": item.get("status"),
        "operational_status": operational_status,
        "date_start": item.get("date_start"),
        "date_end": item.get("date_end"),
        "chunk_days": item.get("chunk_days"),
        "chunks_total": item.get("chunks_total"),
        "chunks_done": item.get("chunks_done"),
        "rows_written": item.get("rows_written"),
        "error_chunks": item.get("error_chunks"),
        "active_chunks": item.get("active_chunks"),
        "percent_complete": item.get("percent_complete"),
        "error": None if is_success else item.get("error"),
        "last_error_summary": last_error_summary,
        "last_error_details": last_error_details,
        "last_error_category": last_error_category,
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "metadata": metadata,
        "trigger_source": str(trigger_source),
    }


def _serialize_chunk(item: dict[str, object]) -> dict[str, object]:
    chunk_status = str(item.get("status") or "").strip().lower()
    chunk_success = chunk_status in {"done", "success", "completed"}
    metadata = to_json_safe(item.get("metadata") or {})
    return {
        "id": item.get("id"),
        "job_id": item.get("job_id"),
        "chunk_index": item.get("chunk_index"),
        "status": item.get("status"),
        "date_start": item.get("date_start"),
        "date_end": item.get("date_end"),
        "attempts": item.get("attempts"),
        "rows_written": item.get("rows_written"),
        "duration_ms": item.get("duration_ms"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "error": None if chunk_success else item.get("error"),
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


@router.post("/batch")
def create_batch_sync_runs(payload: CreateBatchSyncRunsRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:sync", scope="agency")

    enabled, disabled_reason = _is_platform_sync_enabled(payload.platform)
    if not enabled:
        raise HTTPException(status_code=400, detail=str(disabled_reason or "Platform integration is disabled by feature flag."))

    normalized_account_ids: list[str] = []
    for raw in payload.account_ids:
        normalized = _normalize_account_id(raw, platform=payload.platform)
        if normalized != "" and normalized not in normalized_account_ids:
            normalized_account_ids.append(normalized)

    if len(normalized_account_ids) <= 0:
        raise HTTPException(status_code=400, detail="account_ids trebuie să conțină cel puțin un id valid")

    start_date, end_date = _resolve_date_range(payload)
    grains = _resolve_grains(payload)

    platform_accounts = client_registry_service.list_platform_accounts(platform=payload.platform)
    accounts_map: dict[str, int | None] = {}
    canonical_to_stored_account_id: dict[str, str] = {}
    canonical_to_sync_start_date: dict[str, date | None] = {}
    for item in platform_accounts:
        stored_account_id = str(item.get("id") or item.get("account_id") or "").strip()
        normalized = _normalize_account_id(stored_account_id, platform=payload.platform)
        if normalized == "":
            continue
        attached = item.get("attached_client_id")
        accounts_map[normalized] = int(attached) if attached is not None else None
        canonical_to_stored_account_id[normalized] = stored_account_id
        canonical_to_sync_start_date[normalized] = _coerce_account_sync_start_date(item.get("sync_start_date"))

    valid_account_ids = [account_id for account_id in normalized_account_ids if account_id in accounts_map and accounts_map.get(account_id) is not None]
    invalid_account_ids = [account_id for account_id in normalized_account_ids if account_id not in accounts_map or accounts_map.get(account_id) is None]

    if len(valid_account_ids) <= 0:
        raise HTTPException(status_code=400, detail={"message": "Niciun account_id valid pentru platformă", "invalid_account_ids": invalid_account_ids})

    batch_id = uuid4().hex
    created_runs: list[dict[str, object]] = []
    account_results: list[dict[str, object]] = []
    already_exists_count = 0

    for account_id in valid_account_ids:
        stored_account_id = canonical_to_stored_account_id.get(account_id, account_id)
        for grain in grains:
            job_id = uuid4().hex
            account_sync_start_date = canonical_to_sync_start_date.get(account_id)
            effective_start_date, effective_end_date = _effective_historical_window_for_account(
                platform=payload.platform,
                job_type=payload.job_type,
                requested_start=start_date,
                requested_end=end_date,
                account_sync_start_date=account_sync_start_date,
            )
            effective_chunk_days = _effective_chunk_days(
                platform=payload.platform,
                job_type=payload.job_type,
                requested_chunk_days=int(payload.chunk_days),
            )
            chunks = _build_chunks(start_date=effective_start_date, end_date=effective_end_date, chunk_days=effective_chunk_days)
            create_metadata = {
                "source": "manual",
                "trigger_source": "manual",
                "job_type": payload.job_type,
                "grain": grain,
                "batch_id": batch_id,
            }
            if payload.job_type == "historical_backfill":
                outcome = sync_runs_store.create_historical_sync_run_if_not_active(
                    job_id=job_id,
                    platform=payload.platform,
                    date_start=effective_start_date,
                    date_end=effective_end_date,
                    chunk_days=int(effective_chunk_days),
                    client_id=accounts_map.get(account_id),
                    account_id=stored_account_id,
                    metadata=create_metadata,
                    batch_id=batch_id,
                    grain=grain,
                    chunks_total=len(chunks),
                    chunks_done=0,
                    rows_written=0,
                )
                created_flag = bool(outcome.get("created"))
                created = outcome.get("run") if isinstance(outcome.get("run"), dict) else None
            else:
                created = sync_runs_store.create_sync_run(
                    job_id=job_id,
                    platform=payload.platform,
                    status="queued",
                    date_start=effective_start_date,
                    date_end=effective_end_date,
                    chunk_days=int(effective_chunk_days),
                    client_id=accounts_map.get(account_id),
                    account_id=stored_account_id,
                    metadata=create_metadata,
                    batch_id=batch_id,
                    job_type=payload.job_type,
                    grain=grain,
                    chunks_total=len(chunks),
                    chunks_done=0,
                    rows_written=0,
                )
                created_flag = True

            if not created_flag:
                already_exists_count += 1
                logger.info(
                    "sync_runs.dedupe.skip_existing_active platform=%s account_id=%s grain=%s job_type=%s date_start=%s date_end=%s existing_job_id=%s existing_status=%s",
                    payload.platform,
                    account_id,
                    grain,
                    payload.job_type,
                    effective_start_date,
                    effective_end_date,
                    created.get("job_id") if isinstance(created, dict) else None,
                    created.get("status") if isinstance(created, dict) else None,
                )
                account_results.append(
                    {
                        "platform": payload.platform,
                        "account_id": stored_account_id,
                        "grain": grain,
                        "client_id": created.get("client_id") if isinstance(created, dict) else accounts_map.get(account_id),
                        "result": "already_exists",
                        "job_id": created.get("job_id") if isinstance(created, dict) else None,
                        "status": created.get("status") if isinstance(created, dict) else "queued",
                        "date_start": str(created.get("date_start") if isinstance(created, dict) else effective_start_date),
                        "date_end": str(created.get("date_end") if isinstance(created, dict) else effective_end_date),
                    }
                )
                continue

            for chunk_index, chunk_start, chunk_end in chunks:
                sync_run_chunks_store.create_sync_run_chunk(
                    job_id=job_id,
                    chunk_index=chunk_index,
                    status="queued",
                    date_start=chunk_start,
                    date_end=chunk_end,
                    metadata={
                        "source": "manual",
                        "trigger_source": "manual",
                        "batch_id": batch_id,
                        "job_type": payload.job_type,
                        "grain": grain,
                    },
                )

            logger.info(
                "sync_runs.created platform=%s account_id=%s grain=%s job_type=%s date_start=%s date_end=%s job_id=%s chunks_total=%s",
                payload.platform,
                account_id,
                grain,
                payload.job_type,
                effective_start_date,
                effective_end_date,
                created.get("job_id") if created is not None else job_id,
                len(chunks),
            )

            created_runs.append(
                {
                    "job_id": str(created.get("job_id") if created is not None else job_id),
                    "account_id": stored_account_id,
                    "grain": grain,
                    "client_id": created.get("client_id") if created is not None else accounts_map.get(account_id),
                    "status": "queued",
                    "chunks_total": len(chunks),
                }
            )
            account_results.append(
                {
                    "platform": payload.platform,
                    "account_id": stored_account_id,
                    "grain": grain,
                    "client_id": created.get("client_id") if created is not None else accounts_map.get(account_id),
                    "result": "created",
                    "job_id": str(created.get("job_id") if created is not None else job_id),
                    "status": "queued",
                    "date_start": str(effective_start_date),
                    "date_end": str(effective_end_date),
                }
            )

    return {
        "status": "queued",
        "batch_id": batch_id,
        "platform": payload.platform,
        "job_type": payload.job_type,
        "grain": grains[0],
        "grains": grains,
        "date_range": {"start": str(start_date), "end": str(end_date)},
        "chunk_days": _effective_chunk_days(platform=payload.platform, job_type=payload.job_type, requested_chunk_days=int(payload.chunk_days)),
        "created_count": len(created_runs),
        "already_exists_count": already_exists_count,
        "invalid_account_ids": invalid_account_ids,
        "runs": created_runs,
        "results": account_results,
    }


@router.get("/batch/{batch_id}")
def get_batch_sync_runs_status(batch_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    raw_runs = sync_runs_store.list_sync_runs_by_batch(str(batch_id))
    runs = [_reconcile_run_payload(item) for item in raw_runs]
    batch_progress = _summarize_batch_from_runs(runs)

    progress = {
        "total_runs": int(batch_progress.get("total_runs") or 0),
        "queued": int((batch_progress.get("status_counts") or {}).get("queued") or 0),
        "running": int((batch_progress.get("status_counts") or {}).get("running") or 0),
        "done": int((batch_progress.get("status_counts") or {}).get("done") or 0),
        "error": int((batch_progress.get("status_counts") or {}).get("error") or 0),
        "partial": int((batch_progress.get("status_counts") or {}).get("partial") or 0),
        "chunks_total": int(batch_progress.get("chunks_total_sum") or 0),
        "chunks_done": int(batch_progress.get("chunks_done_sum") or 0),
        "rows_written": int(batch_progress.get("rows_written_sum") or 0),
        "no_data_success_runs": int(batch_progress.get("no_data_success_runs") or 0),
        "operational_status": str(batch_progress.get("operational_status") or "normal"),
        "percent": float(batch_progress.get("percent") or 0.0),
    }

    return {
        "batch_id": str(batch_id),
        "progress": progress,
        "runs": [_serialize_run(item) for item in runs],
    }



@router.post("/accounts/{platform}/progress")
def get_accounts_active_progress_batch(
    platform: str,
    payload: BatchAccountProgressRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    normalized_platform = str(platform).strip()
    normalized_account_ids: list[str] = []
    for raw in payload.account_ids:
        normalized = _normalize_account_id(str(raw))
        if normalized == "":
            continue
        if normalized not in normalized_account_ids:
            normalized_account_ids.append(normalized)

    if len(normalized_account_ids) <= 0:
        raise HTTPException(status_code=400, detail="account_ids trebuie să conțină cel puțin un id valid")
    if len(normalized_account_ids) > _MAX_PROGRESS_BATCH_ACCOUNT_IDS:
        raise HTTPException(
            status_code=400,
            detail=f"account_ids depășește limita maximă de {_MAX_PROGRESS_BATCH_ACCOUNT_IDS}",
        )

    started_at = perf_counter()
    results = sync_runs_store.get_active_runs_progress_batch(
        platform=normalized_platform,
        account_ids=normalized_account_ids,
    )
    active_count = len([item for item in results if isinstance(item.get("active_run"), dict)])
    duration_ms = int(round((perf_counter() - started_at) * 1000.0))

    logger.info(
        "sync_runs.progress_batch platform=%s requested_count=%s returned_active_count=%s duration_ms=%s",
        normalized_platform,
        len(normalized_account_ids),
        active_count,
        duration_ms,
    )

    return {
        "platform": normalized_platform,
        "requested_count": len(normalized_account_ids),
        "results": results,
    }


@router.get("/accounts/{platform}/{account_id}")
def list_account_sync_runs(
    platform: str,
    account_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    normalized_platform = str(platform).strip()
    normalized_account_id = str(account_id).strip()
    runs = sync_runs_store.list_sync_runs_for_account(
        platform=normalized_platform,
        account_id=normalized_account_id,
        limit=int(limit),
    )

    return {
        "platform": normalized_platform,
        "account_id": normalized_account_id,
        "limit": int(limit),
        "runs": [_serialize_run(item) for item in runs],
    }


@router.get("/{job_id}")
def get_sync_run_details(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    run = sync_runs_store.get_sync_run(str(job_id).strip())
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return _serialize_run(_reconcile_run_payload(run))


@router.post("/{job_id}/repair")
def repair_sync_run(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:sync", scope="agency")

    stale_minutes = load_settings().sync_run_repair_stale_minutes
    result = sync_runs_store.repair_historical_sync_run(
        job_id=str(job_id).strip(),
        stale_after_minutes=int(stale_minutes),
        repair_source="api.sync_orchestration",
    )

    outcome = str(result.get("outcome") or "")
    logger.info(
        "sync_runs.repair outcome=%s job_id=%s reason=%s stale_chunks_closed=%s final_status=%s",
        outcome,
        str(job_id).strip(),
        result.get("reason"),
        result.get("stale_chunks_closed"),
        result.get("final_status"),
    )

    if outcome == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"message": "Sync run not found", "job_id": str(job_id).strip(), "outcome": "not_found"},
        )

    response: dict[str, object] = {
        "job_id": str(job_id).strip(),
        "outcome": outcome,
        "stale_after_minutes": int(stale_minutes),
    }
    if result.get("reason") is not None:
        response["reason"] = result.get("reason")
    if result.get("active_chunks") is not None:
        response["active_chunks"] = int(result.get("active_chunks") or 0)
    if result.get("stale_chunks") is not None:
        response["stale_chunks"] = int(result.get("stale_chunks") or 0)
    if result.get("stale_chunks_closed") is not None:
        response["stale_chunks_closed"] = int(result.get("stale_chunks_closed") or 0)
    if result.get("final_status") is not None:
        response["final_status"] = str(result.get("final_status"))

    run_payload = result.get("run")
    if isinstance(run_payload, dict):
        response["run"] = _serialize_run(_reconcile_run_payload(run_payload))

    return response


@router.post("/{job_id}/retry-failed")
def retry_failed_sync_run(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:sync", scope="agency")

    normalized_job_id = str(job_id).strip()
    retry_job_id = uuid4().hex
    result = sync_runs_store.retry_failed_historical_run(
        source_job_id=normalized_job_id,
        retry_job_id=retry_job_id,
        trigger_source="manual",
    )

    outcome = str(result.get("outcome") or "")
    logger.info(
        "sync_runs.retry_failed outcome=%s source_job_id=%s retry_job_id=%s platform=%s account_id=%s chunks_created=%s failed_chunks_count=%s",
        outcome,
        normalized_job_id,
        result.get("retry_job_id"),
        result.get("platform"),
        result.get("account_id"),
        result.get("chunks_created"),
        result.get("failed_chunks_count"),
    )

    if outcome == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"message": "Sync run not found", "job_id": normalized_job_id, "outcome": "not_found"},
        )

    response: dict[str, object] = {
        "outcome": outcome,
        "source_job_id": normalized_job_id,
    }
    for key in ("retry_job_id", "platform", "account_id", "status", "chunks_created", "failed_chunks_count"):
        if result.get(key) is not None:
            response[key] = result.get(key)

    run_payload = result.get("run")
    if isinstance(run_payload, dict):
        response["run"] = _serialize_run(_reconcile_run_payload(run_payload))

    return response


@router.get("/{job_id}/chunks")
def list_sync_run_chunks(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")

    normalized_job_id = str(job_id).strip()
    run = sync_runs_store.get_sync_run(normalized_job_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")

    chunks = sync_run_chunks_store.list_sync_run_chunks(normalized_job_id)
    return {
        "job_id": normalized_job_id,
        "chunks": [_serialize_chunk(item) for item in chunks],
    }


@router.post("/rolling/enqueue")
def enqueue_rolling_sync_runs_api(payload: RollingEnqueueRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:sync", scope="agency")
    try:
        return enqueue_rolling_sync_runs(
            platform=payload.platform,
            limit=int(payload.limit),
            chunk_days=int(payload.chunk_days),
            force=bool(payload.force),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
