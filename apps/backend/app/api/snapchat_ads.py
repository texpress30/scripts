import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.snapchat_ads import SnapchatAdsIntegrationError, snapchat_ads_service
from app.services.snapchat_observability import snapchat_sync_metrics
from app.services.sync_engine import backfill_job_store

router = APIRouter(prefix="/integrations/snapchat-ads", tags=["snapchat-ads"])
logger = logging.getLogger("app.snapchat_ads")


def _run_snapchat_sync_job(job_id: str, *, client_id: int) -> None:
    backfill_job_store.set_running(job_id)

    try:
        snapshot = snapchat_ads_service.sync_client(client_id=client_id)
        payload = {
            "status": "done",
            "job_id": job_id,
            "client_id": int(client_id),
            "platform": "snapchat_ads",
            "result": snapshot,
        }
        backfill_job_store.set_done(job_id, result=payload)
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)


@router.post("/sync-now")
def sync_snapchat_ads_now(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    client_id: int = Query(..., ge=1),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    job_id = backfill_job_store.create(payload={"platform": "snapchat_ads", "client_id": int(client_id)})
    background_tasks.add_task(_run_snapchat_sync_job, job_id, client_id=int(client_id))
    return {
        "status": "queued",
        "job_id": job_id,
        "client_id": int(client_id),
        "platform": "snapchat_ads",
    }


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:snapchat:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return payload
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")


@router.get("/status")
def snapchat_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    try:
        enforce_action_scope(user=user, action="integrations:snapchat:status", scope="agency")
        rate_limiter_service.check(f"snapchat_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = snapchat_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="snapchat_ads.status",
        resource="integration:snapchat_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload


@router.post("/{client_id}/sync")
def sync_snapchat_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | str]:
    try:
        enforce_action_scope(user=user, action="integrations:snapchat:sync", scope="subaccount")
        rate_limiter_service.check(f"snapchat_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    started_at = time.perf_counter()
    snapchat_sync_metrics.increment("sync_started")
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="snapchat_ads.sync.start",
        resource=f"client:{client_id}",
        details={"phase": "start"},
    )

    try:
        snapshot = snapchat_ads_service.sync_client(client_id=client_id)
    except SnapchatAdsIntegrationError as exc:
        snapchat_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "snapchat_sync_fail",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms, "reason": str(exc)},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="snapchat_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": str(exc), "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        snapchat_sync_metrics.increment("sync_failed")
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "snapchat_sync_fail_unhandled",
            extra={"client_id": client_id, "email": user.email, "duration_ms": duration_ms},
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="snapchat_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": "Snapchat Ads API unavailable", "duration_ms": duration_ms},
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Snapchat Ads API unavailable") from exc

    snapchat_sync_metrics.increment("sync_succeeded")
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "snapchat_sync_success",
        extra={
            "client_id": client_id,
            "email": user.email,
            "duration_ms": duration_ms,
            "attempts": snapshot.get("attempts", 1),
            "metrics": snapchat_sync_metrics.snapshot(),
        },
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="snapchat_ads.sync.success",
        resource=f"client:{client_id}",
        details={**snapshot, "duration_ms": duration_ms},
    )
    return snapshot
