import logging
import time
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.sync_engine import backfill_job_store
from app.services.sync_state_store import sync_state_store
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_constants import PLATFORM_TIKTOK_ADS, SYNC_GRAIN_ACCOUNT_DAILY, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service
from app.services.tiktok_observability import tiktok_sync_metrics

router = APIRouter(prefix="/integrations/tiktok-ads", tags=["tiktok-ads"])
logger = logging.getLogger("app.tiktok_ads")

_TIKTOK_BACKFILL_DEFAULT_START = date(2024, 1, 9)
_TIKTOK_BACKFILL_DEFAULT_GRAINS: tuple[str, ...] = ("account_daily", "campaign_daily", "ad_group_daily", "ad_daily")
_TIKTOK_BACKFILL_CHUNK_DAYS = 30


def _normalize_tiktok_backfill_grains(grains: list[str] | None) -> list[str]:
    allowed = set(_TIKTOK_BACKFILL_DEFAULT_GRAINS)
    values = grains if grains is not None and len(grains) > 0 else list(_TIKTOK_BACKFILL_DEFAULT_GRAINS)
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        grain = str(value or "").strip().lower()
        if grain not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported TikTok backfill grain '{value}'. Allowed: {list(_TIKTOK_BACKFILL_DEFAULT_GRAINS)}",
            )
        if grain in seen:
            continue
        seen.add(grain)
        normalized.append(grain)
    return normalized


def _build_tiktok_backfill_chunks(*, start_date: date, end_date: date, chunk_days: int = _TIKTOK_BACKFILL_CHUNK_DAYS) -> list[tuple[date, date]]:
    if start_date > end_date:
        return []
    ranges: list[tuple[date, date]] = []
    cursor = start_date
    effective_chunk_days = max(1, int(chunk_days))
    while cursor <= end_date:
        chunk_end = min(end_date, cursor + timedelta(days=effective_chunk_days - 1))
        ranges.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return ranges


class TikTokSyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grain: Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"] | None = None


class TikTokBackfillRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grains: list[Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]] | None = None



class TikTokSyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grain: Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"] | None = None



class TikTokSyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grain: Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"] | None = None



def _log_best_effort_warning(
    *,
    operation: str,
    error: Exception,
    job_id: str | None = None,
    status_value: str | None = None,
    platform: str | None = None,
    account_id: str | None = None,
) -> None:
    logger.warning(
        "best_effort_op_failed operation=%s job_id=%s status=%s platform=%s account_id=%s error=%s",
        operation,
        job_id,
        status_value,
        platform,
        account_id,
        str(error)[:300],
    )


def _resolve_tiktok_account_id(*, client_id: int, job_id: str | None = None) -> str | None:
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_TIKTOK_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="tiktok_account_lookup", error=exc, job_id=job_id, platform=PLATFORM_TIKTOK_ADS)
        return None

    account_ids = [str(item.get("id") or "").strip() for item in accounts if isinstance(item, dict)]
    account_ids = [item for item in account_ids if item != ""]
    if len(account_ids) == 1:
        return account_ids[0]
    if len(account_ids) == 0:
        logger.warning("tiktok_account_id_missing client_id=%s job_id=%s", int(client_id), job_id)
        return None

    logger.warning("tiktok_account_id_ambiguous client_id=%s job_id=%s account_count=%s", int(client_id), job_id, len(account_ids))
    return None


def _mirror_sync_run_create(*, job_id: str, status_value: str, client_id: int, date_start: date, date_end: date, account_id: str | None = None) -> None:
    try:
        sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=PLATFORM_TIKTOK_ADS,
            status=status_value,
            client_id=client_id,
            account_id=account_id,
            date_start=date_start,
            date_end=date_end,
            chunk_days=1,
            metadata={"job_type": "sync", "source": "tiktok_ads_api"},
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_create", error=exc, job_id=job_id, status_value=status_value, platform=PLATFORM_TIKTOK_ADS, account_id=account_id)


def _mirror_sync_run_status(*, job_id: str, status_value: str, error: str | None = None, mark_started: bool = False, mark_finished: bool = False, metadata: dict[str, object] | None = None) -> None:
    try:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status=status_value,
            error=error,
            mark_started=mark_started,
            mark_finished=mark_finished,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_status", error=exc, job_id=job_id, status_value=status_value, platform=PLATFORM_TIKTOK_ADS)


def _mirror_tiktok_sync_state_upsert(
    *,
    job_id: str,
    account_id: str,
    last_status: str,
    last_attempted_at: datetime,
    date_end: date,
    error: str | None = None,
    last_successful_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    try:
        sync_state_store.upsert_sync_state(
            platform=PLATFORM_TIKTOK_ADS,
            account_id=account_id,
            grain=SYNC_GRAIN_ACCOUNT_DAILY,
            last_status=last_status,
            last_job_id=job_id,
            last_attempted_at=last_attempted_at,
            last_successful_at=last_successful_at,
            last_successful_date=date_end if last_successful_at is not None else None,
            error=error,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(
            operation="sync_state_upsert",
            error=exc,
            job_id=job_id,
            status_value=last_status,
            platform=PLATFORM_TIKTOK_ADS,
            account_id=account_id,
        )


def _resolve_tiktok_account_operational_context(*, client_id: int, account_id: str, job_id: str) -> dict[str, str]:
    payload: dict[str, str] = {"account_id": account_id}
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_TIKTOK_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="tiktok_account_metadata_lookup", error=exc, job_id=job_id, platform=PLATFORM_TIKTOK_ADS, account_id=account_id)
        return payload

    matched = None
    for item in accounts:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip() == account_id:
            matched = item
            break
    if matched is None:
        return payload

    raw_status = str(matched.get("status") or "").strip()
    if raw_status != "":
        payload["status"] = raw_status
    raw_currency = str(matched.get("currency_code") or matched.get("currency") or "").strip().upper()
    if raw_currency != "":
        payload["currency_code"] = raw_currency
    raw_timezone = str(matched.get("account_timezone") or "").strip()
    if raw_timezone != "":
        payload["account_timezone"] = raw_timezone
    return payload


def _mirror_tiktok_platform_account_operational_metadata(
    *,
    job_id: str,
    account_context: dict[str, str] | None,
    sync_start_date: date,
    last_synced_at: datetime | None = None,
    last_success_at: datetime | None = None,
    backfill_completed_through: date | None = None,
) -> None:
    account_id = str((account_context or {}).get("account_id") or "").strip()
    if account_id == "":
        logger.warning("tiktok_operational_metadata_skipped_missing_account_id job_id=%s", job_id)
        return

    update_payload: dict[str, object] = {
        "platform": PLATFORM_TIKTOK_ADS,
        "account_id": account_id,
        "sync_start_date": sync_start_date,
    }
    raw_status = str((account_context or {}).get("status") or "").strip()
    if raw_status != "":
        update_payload["status"] = raw_status
    raw_currency = str((account_context or {}).get("currency_code") or "").strip().upper()
    if raw_currency != "":
        update_payload["currency_code"] = raw_currency
    raw_timezone = str((account_context or {}).get("account_timezone") or "").strip()
    if raw_timezone != "":
        update_payload["account_timezone"] = raw_timezone
    if last_synced_at is not None:
        update_payload["last_synced_at"] = last_synced_at
    if last_success_at is not None:
        update_payload["last_success_at"] = last_success_at
    if backfill_completed_through is not None:
        update_payload["backfill_completed_through"] = backfill_completed_through

    try:
        client_registry_service.update_platform_account_operational_metadata(**update_payload)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(
            operation="platform_account_metadata_update",
            error=exc,
            job_id=job_id,
            platform=PLATFORM_TIKTOK_ADS,
            account_id=account_id,
        )


def _run_tiktok_sync_job(job_id: str, *, client_id: int, account_id: str | None = None) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_RUNNING, mark_started=True)

    today = datetime.utcnow().date()
    date_start = today - timedelta(days=30)
    date_end = today
    sync_state_metadata = {
        "client_id": int(client_id),
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "job_type": "sync",
    }

    account_context = _resolve_tiktok_account_operational_context(client_id=int(client_id), account_id=account_id, job_id=job_id) if account_id is not None else None
    _mirror_tiktok_platform_account_operational_metadata(
        job_id=job_id,
        account_context=account_context,
        sync_start_date=date_start,
    )

    if account_id is None:
        logger.warning("tiktok_sync_state_skipped_missing_account_id job_id=%s client_id=%s", job_id, int(client_id))
    else:
        _mirror_tiktok_sync_state_upsert(
            job_id=job_id,
            account_id=account_id,
            last_status=SYNC_STATUS_RUNNING,
            last_attempted_at=datetime.utcnow(),
            date_end=date_end,
            error=None,
            metadata=sync_state_metadata,
        )

    try:
        snapshot = tiktok_ads_service.sync_client(client_id=client_id)
        success_now = datetime.utcnow()
        payload = {
            "status": SYNC_STATUS_DONE,
            "job_id": job_id,
            "client_id": int(client_id),
            "result": snapshot,
        }
        backfill_job_store.set_done(job_id, result=payload)
        done_metadata: dict[str, object] = {"client_id": int(client_id)}
        if account_id is not None:
            done_metadata["account_id"] = account_id
            _mirror_tiktok_sync_state_upsert(
                job_id=job_id,
                account_id=account_id,
                last_status=SYNC_STATUS_DONE,
                last_attempted_at=success_now,
                last_successful_at=success_now,
                date_end=date_end,
                error=None,
                metadata=sync_state_metadata,
            )
        _mirror_tiktok_platform_account_operational_metadata(
            job_id=job_id,
            account_context=account_context,
            sync_start_date=date_start,
            last_synced_at=success_now,
            last_success_at=success_now,
        )
        _mirror_sync_run_status(
            job_id=job_id,
            status_value=SYNC_STATUS_DONE,
            mark_finished=True,
            metadata=done_metadata,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)
        if account_id is not None:
            _mirror_tiktok_sync_state_upsert(
                job_id=job_id,
                account_id=account_id,
                last_status=SYNC_STATUS_ERROR,
                last_attempted_at=datetime.utcnow(),
                date_end=date_end,
                error=safe_error,
                metadata=sync_state_metadata,
            )
        _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_ERROR, error=safe_error, mark_finished=True)



def _run_tiktok_historical_backfill_job(
    job_id: str,
    *,
    client_id: int,
    start_date: date,
    end_date: date,
    grains: list[str],
    chunk_days: int = _TIKTOK_BACKFILL_CHUNK_DAYS,
) -> None:
    backfill_job_store.set_running(job_id)
    chunks = _build_tiktok_backfill_chunks(start_date=start_date, end_date=end_date, chunk_days=chunk_days)

    rows_written = 0
    account_ids_seen: set[str] = set()
    accounts_processed_max = 0

    try:
        for grain in grains:
            for chunk_start, chunk_end in chunks:
                result = tiktok_ads_service.sync_client(
                    client_id=int(client_id),
                    start_date=chunk_start,
                    end_date=chunk_end,
                    grain=grain,
                )
                rows_written += int(result.get("rows_written") or 0)
                accounts_processed_max = max(accounts_processed_max, int(result.get("accounts_processed") or 0))
                for account_id in (result.get("account_ids") or []):
                    if isinstance(account_id, str) and account_id.strip() != "":
                        account_ids_seen.add(account_id.strip())

        result_payload = {
            "status": "success",
            "mode": "historical_backfill",
            "message": "TikTok Ads historical backfill completed.",
            "platform": PLATFORM_TIKTOK_ADS,
            "client_id": int(client_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "grains": grains,
            "chunk_days": int(chunk_days),
            "chunks_processed": len(chunks),
            "jobs_enqueued": len(chunks) * len(grains),
            "accounts_processed": accounts_processed_max,
            "account_ids": sorted(account_ids_seen),
            "rows_written": rows_written,
        }
        success_now = datetime.utcnow()
        account_context = _resolve_tiktok_account_operational_context(client_id=int(client_id), account_id=None, job_id=job_id)
        _mirror_tiktok_platform_account_operational_metadata(
            job_id=job_id,
            account_context=account_context,
            sync_start_date=start_date,
            last_synced_at=success_now,
            last_success_at=success_now,
            backfill_completed_through=end_date,
        )
        backfill_job_store.set_done(job_id, result=result_payload)
    except Exception as exc:  # noqa: BLE001
        backfill_job_store.set_error(job_id, error=str(exc)[:300])


def _map_sync_run_to_job_status_payload(sync_run: dict[str, object]) -> dict[str, object]:
    metadata = sync_run.get("metadata") if isinstance(sync_run.get("metadata"), dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    payload: dict[str, object] = {
        "job_id": str(sync_run.get("job_id") or ""),
        "status": str(sync_run.get("status") or SYNC_STATUS_QUEUED),
        "created_at": sync_run.get("created_at"),
        "started_at": sync_run.get("started_at"),
        "finished_at": sync_run.get("finished_at"),
        "error": sync_run.get("error"),
        "metadata": metadata,
    }

    for field in ("platform", "client_id", "account_id", "date_start", "date_end", "chunk_days"):
        value = sync_run.get(field)
        if value is not None:
            payload[field] = value

    return payload


@router.get("/status")
def tiktok_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
        rate_limiter_service.check(f"tiktok_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = tiktok_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.status",
        resource="integration:tiktok_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload


@router.get("/connect")
def connect_tiktok_ads(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
    try:
        payload = tiktok_ads_service.build_oauth_authorize_url()
    except TikTokAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.connect.start",
        resource="integration:tiktok_ads",
        details={"state": payload["state"]},
    )
    return payload


@router.post("/oauth/exchange")
def tiktok_ads_oauth_exchange(
    payload: dict[str, str],
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
    code = str(payload.get("code", "")).strip()
    state = str(payload.get("state", "")).strip()
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state for OAuth exchange")

    try:
        response_payload = tiktok_ads_service.exchange_oauth_code(code=code, state=state)
    except TikTokAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.connect.success",
        resource="integration:tiktok_ads",
        details={"status": response_payload.get("status")},
    )
    return response_payload


@router.post("/import-accounts")
def import_tiktok_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
    try:
        payload = tiktok_ads_service.import_accounts()
    except TikTokAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.import_accounts",
        resource="integration:tiktok_ads",
        details={"status": payload.get("status"), "imported": payload.get("imported", 0)},
    )
    return payload


@router.post("/sync-now")
def sync_tiktok_ads_now(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    client_id: int = Query(..., ge=1),
    async_mode: bool = Query(default=True),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    today = datetime.utcnow().date()
    date_start = today - timedelta(days=30)
    date_end = today

    if async_mode:
        job_id = backfill_job_store.create(payload={"platform": PLATFORM_TIKTOK_ADS, "client_id": int(client_id)})
        tiktok_account_id = _resolve_tiktok_account_id(client_id=int(client_id), job_id=job_id)
        background_tasks.add_task(_run_tiktok_sync_job, job_id, client_id=int(client_id), account_id=tiktok_account_id)
        _mirror_sync_run_create(
            job_id=job_id,
            status_value=SYNC_STATUS_QUEUED,
            client_id=int(client_id),
            date_start=date_start,
            date_end=date_end,
            account_id=tiktok_account_id,
        )
        return {"status": SYNC_STATUS_QUEUED, "job_id": job_id, "client_id": int(client_id)}

    job_id = backfill_job_store.create(payload={"platform": PLATFORM_TIKTOK_ADS, "client_id": int(client_id)})
    tiktok_account_id = _resolve_tiktok_account_id(client_id=int(client_id), job_id=job_id)
    _run_tiktok_sync_job(job_id, client_id=int(client_id), account_id=tiktok_account_id)
    payload = backfill_job_store.get(job_id) or {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if isinstance(result, dict) and len(result) > 0:
        return result
    return {"status": SYNC_STATUS_ERROR, "job_id": job_id, "client_id": int(client_id)}


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return payload

    try:
        sync_run = sync_runs_store.get_sync_run(job_id)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_read", error=exc, job_id=job_id, platform=PLATFORM_TIKTOK_ADS)
        sync_run = None

    if sync_run is not None:
        return _map_sync_run_to_job_status_payload(sync_run)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")


@router.post("/{client_id}/sync")
def sync_tiktok_ads(client_id: int, payload: TikTokSyncRequest | None = None, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:tiktok:sync", scope="subaccount")
        rate_limiter_service.check(f"tiktok_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    started_at = time.perf_counter()
    tiktok_sync_metrics.increment("sync_started")
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.sync.start",
        resource=f"client:{client_id}",
        details={"phase": "start"},
    )

    try:
        snapshot = tiktok_ads_service.sync_client(
            client_id=client_id,
            start_date=(payload.start_date if payload is not None else None),
            end_date=(payload.end_date if payload is not None else None),
            grain=(str(payload.grain).strip().lower() if payload is not None and payload.grain is not None else "account_daily"),
        )
    except TikTokAdsIntegrationError as exc:
        tiktok_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "tiktok_sync_fail",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms, "reason": str(exc)},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="tiktok_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": str(exc), "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        tiktok_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "tiktok_sync_fail_unhandled",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="tiktok_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": "TikTok Ads API unavailable", "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="TikTok Ads API unavailable") from exc

    tiktok_sync_metrics.increment("sync_succeeded")
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "tiktok_sync_success",
        extra={
            "client_id": client_id,
            "email": user.email,
            "duration_ms": duration_ms,
            "attempts": snapshot.get("attempts", 1),
            "metrics": tiktok_sync_metrics.snapshot(),
        },
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.sync.success",
        resource=f"client:{client_id}",
        details={**snapshot, "duration_ms": duration_ms},
    )
    return snapshot


@router.post("/{client_id}/backfill")
def backfill_tiktok_ads(
    client_id: int,
    background_tasks: BackgroundTasks,
    payload: TikTokBackfillRequest | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:tiktok:sync", scope="subaccount")
        rate_limiter_service.check(f"tiktok_backfill:{user.email}", limit=10, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    settings = load_settings()
    if not settings.ff_tiktok_integration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TikTok integration is disabled by feature flag.")

    today = datetime.utcnow().date()
    default_end = today - timedelta(days=1)
    resolved_start = payload.start_date if payload is not None and payload.start_date is not None else _TIKTOK_BACKFILL_DEFAULT_START
    resolved_end = payload.end_date if payload is not None and payload.end_date is not None else default_end

    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date cannot be after end_date")

    grains_input = payload.grains if payload is not None else None
    resolved_grains = _normalize_tiktok_backfill_grains(list(grains_input) if grains_input is not None else None)

    status_payload = tiktok_ads_service.integration_status()
    if not bool(status_payload.get("has_usable_token")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TikTok backfill requires a usable OAuth token. Connect TikTok first.")

    attached_accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_TIKTOK_ADS, client_id=int(client_id))
    account_ids = [str(item.get("id") or "").strip() for item in attached_accounts if isinstance(item, dict)]
    account_ids = [item for item in account_ids if item != ""]
    if len(account_ids) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No TikTok advertiser accounts are attached to this client.")

    chunks = _build_tiktok_backfill_chunks(start_date=resolved_start, end_date=resolved_end, chunk_days=_TIKTOK_BACKFILL_CHUNK_DAYS)

    job_id = backfill_job_store.create(
        payload={
            "platform": PLATFORM_TIKTOK_ADS,
            "client_id": int(client_id),
            "mode": "historical_backfill",
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "grains": resolved_grains,
            "chunk_days": _TIKTOK_BACKFILL_CHUNK_DAYS,
            "chunks_enqueued": len(chunks),
        }
    )
    background_tasks.add_task(
        _run_tiktok_historical_backfill_job,
        job_id,
        client_id=int(client_id),
        start_date=resolved_start,
        end_date=resolved_end,
        grains=resolved_grains,
        chunk_days=_TIKTOK_BACKFILL_CHUNK_DAYS,
    )

    response = {
        "status": "queued",
        "mode": "enqueued",
        "message": "TikTok Ads historical backfill enqueued.",
        "platform": PLATFORM_TIKTOK_ADS,
        "client_id": int(client_id),
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "grains": resolved_grains,
        "chunk_days": _TIKTOK_BACKFILL_CHUNK_DAYS,
        "chunks_enqueued": len(chunks),
        "jobs_enqueued": len(chunks) * len(resolved_grains),
        "job_id": job_id,
    }

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.backfill.enqueue",
        resource=f"client:{client_id}",
        details={
            "job_id": job_id,
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "grains": resolved_grains,
            "chunks_enqueued": len(chunks),
        },
    )

    return response
