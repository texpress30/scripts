import logging
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.pinterest_ads import PinterestAdsIntegrationError, pinterest_ads_service
from app.services.pinterest_observability import pinterest_sync_metrics
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.sync_engine import backfill_job_store
from app.services.sync_constants import PLATFORM_PINTEREST_ADS, SYNC_GRAIN_ACCOUNT_DAILY, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING
from app.services.sync_state_store import sync_state_store

router = APIRouter(prefix="/integrations/pinterest-ads", tags=["pinterest-ads"])
logger = logging.getLogger("app.pinterest_ads")


def _resolve_pinterest_account_id(*, client_id: int, job_id: str | None = None) -> str | None:
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_PINTEREST_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("pinterest_sync_state_account_lookup_failed client_id=%s job_id=%s error=%s", int(client_id), job_id, str(exc)[:300])
        return None

    account_ids = [str(item.get("id") or "").strip() for item in accounts if isinstance(item, dict)]
    account_ids = [item for item in account_ids if item != ""]
    if len(account_ids) == 1:
        return account_ids[0]
    if len(account_ids) == 0:
        logger.warning("pinterest_sync_state_account_id_missing client_id=%s job_id=%s", int(client_id), job_id)
        return None

    logger.warning("pinterest_sync_state_account_id_ambiguous client_id=%s job_id=%s account_count=%s", int(client_id), job_id, len(account_ids))
    return None


def _mirror_pinterest_sync_state_upsert(*, account_id: str | None, job_id: str, status_value: str, client_id: int, date_start: str, date_end: str, error: str | None = None, include_success: bool = False) -> None:
    if account_id is None:
        logger.warning("pinterest_sync_state_skip_missing_account_id client_id=%s job_id=%s status=%s", int(client_id), job_id, status_value)
        return

    now_utc = datetime.utcnow()
    payload: dict[str, object] = {
        "platform": PLATFORM_PINTEREST_ADS,
        "account_id": str(account_id),
        "grain": SYNC_GRAIN_ACCOUNT_DAILY,
        "last_status": status_value,
        "last_job_id": job_id,
        "last_attempted_at": now_utc,
        "error": error,
        "metadata": {
            "client_id": int(client_id),
            "date_start": date_start,
            "date_end": date_end,
            "job_type": "sync",
        },
    }
    if include_success:
        payload["last_successful_at"] = now_utc
        payload["last_successful_date"] = datetime.fromisoformat(date_end).date()

    try:
        sync_state_store.upsert_sync_state(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "pinterest_sync_state_upsert_failed platform=%s account_id=%s job_id=%s status=%s error=%s",
            PLATFORM_PINTEREST_ADS,
            account_id,
            job_id,
            status_value,
            str(exc)[:300],
        )


def _run_pinterest_sync_job(job_id: str, *, client_id: int) -> None:
    backfill_job_store.set_running(job_id)
    date_end = datetime.utcnow().date().isoformat()
    date_start = (datetime.utcnow().date() - timedelta(days=30)).isoformat()
    account_id = _resolve_pinterest_account_id(client_id=int(client_id), job_id=job_id)
    _mirror_pinterest_sync_state_upsert(
        account_id=account_id,
        job_id=job_id,
        status_value=SYNC_STATUS_RUNNING,
        client_id=int(client_id),
        date_start=date_start,
        date_end=date_end,
        error=None,
        include_success=False,
    )

    try:
        snapshot = pinterest_ads_service.sync_client(client_id=client_id)
        payload = {
            "status": SYNC_STATUS_DONE,
            "job_id": job_id,
            "client_id": int(client_id),
            "platform": PLATFORM_PINTEREST_ADS,
            "result": snapshot,
        }
        backfill_job_store.set_done(job_id, result=payload)
        _mirror_pinterest_sync_state_upsert(
            account_id=account_id,
            job_id=job_id,
            status_value=SYNC_STATUS_DONE,
            client_id=int(client_id),
            date_start=date_start,
            date_end=date_end,
            error=None,
            include_success=True,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)
        _mirror_pinterest_sync_state_upsert(
            account_id=account_id,
            job_id=job_id,
            status_value=SYNC_STATUS_ERROR,
            client_id=int(client_id),
            date_start=date_start,
            date_end=date_end,
            error=safe_error,
            include_success=False,
        )


@router.get("/status")
def pinterest_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    try:
        enforce_action_scope(user=user, action="integrations:pinterest:status", scope="agency")
        rate_limiter_service.check(f"pinterest_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = pinterest_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="pinterest_ads.status",
        resource="integration:pinterest_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload


@router.post("/sync-now")
def sync_pinterest_ads_now(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    client_id: int = Query(..., ge=1),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    job_id = backfill_job_store.create(payload={"platform": PLATFORM_PINTEREST_ADS, "client_id": int(client_id)})
    background_tasks.add_task(_run_pinterest_sync_job, job_id, client_id=int(client_id))
    return {
        "status": SYNC_STATUS_QUEUED,
        "job_id": job_id,
        "client_id": int(client_id),
        "platform": PLATFORM_PINTEREST_ADS,
    }


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:pinterest:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return payload
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")


@router.post("/{client_id}/sync")
def sync_pinterest_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | str]:
    try:
        enforce_action_scope(user=user, action="integrations:pinterest:sync", scope="subaccount")
        rate_limiter_service.check(f"pinterest_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    started_at = time.perf_counter()
    pinterest_sync_metrics.increment("sync_started")
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="pinterest_ads.sync.start",
        resource=f"client:{client_id}",
        details={"phase": "start"},
    )

    try:
        snapshot = pinterest_ads_service.sync_client(client_id=client_id)
    except PinterestAdsIntegrationError as exc:
        pinterest_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "pinterest_sync_fail",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms, "reason": str(exc)},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="pinterest_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": str(exc), "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        pinterest_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "pinterest_sync_fail_unhandled",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="pinterest_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": "Pinterest Ads API unavailable", "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Pinterest Ads API unavailable") from exc

    pinterest_sync_metrics.increment("sync_succeeded")
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "pinterest_sync_success",
        extra={
            "client_id": client_id,
            "email": user.email,
            "duration_ms": duration_ms,
            "attempts": snapshot.get("attempts", 1),
            "metrics": pinterest_sync_metrics.snapshot(),
        },
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="pinterest_ads.sync.success",
        resource=f"client:{client_id}",
        details={**snapshot, "duration_ms": duration_ms},
    )
    return snapshot
