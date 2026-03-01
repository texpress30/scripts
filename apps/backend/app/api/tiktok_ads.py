import logging
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.sync_engine import backfill_job_store
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_constants import PLATFORM_TIKTOK_ADS, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service
from app.services.tiktok_observability import tiktok_sync_metrics

router = APIRouter(prefix="/integrations/tiktok-ads", tags=["tiktok-ads"])
logger = logging.getLogger("app.tiktok_ads")


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


def _run_tiktok_sync_job(job_id: str, *, client_id: int, account_id: str | None = None) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_RUNNING, mark_started=True)

    try:
        snapshot = tiktok_ads_service.sync_client(client_id=client_id)
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
        _mirror_sync_run_status(
            job_id=job_id,
            status_value=SYNC_STATUS_DONE,
            mark_finished=True,
            metadata=done_metadata,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)
        _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_ERROR, error=safe_error, mark_finished=True)


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
def tiktok_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
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
def sync_tiktok_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | str]:
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
        snapshot = tiktok_ads_service.sync_client(client_id=client_id)
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
