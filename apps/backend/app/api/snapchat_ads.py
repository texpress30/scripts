import logging
import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.snapchat_ads import SnapchatAdsIntegrationError, snapchat_ads_service
from app.services.snapchat_observability import snapchat_sync_metrics
from app.services.sync_constants import PLATFORM_SNAPCHAT_ADS, SYNC_GRAIN_ACCOUNT_DAILY, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING
from app.services.sync_engine import backfill_job_store
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_state_store import sync_state_store

router = APIRouter(prefix="/integrations/snapchat-ads", tags=["snapchat-ads"])
logger = logging.getLogger("app.snapchat_ads")


def _resolve_snapchat_account_id(*, client_id: int, job_id: str | None = None) -> str | None:
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_SNAPCHAT_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("snapchat_account_lookup_failed client_id=%s job_id=%s error=%s", int(client_id), job_id, str(exc)[:300])
        return None

    account_ids = [str(item.get("id") or "").strip() for item in accounts if isinstance(item, dict)]
    account_ids = [item for item in account_ids if item != ""]
    if len(account_ids) == 1:
        return account_ids[0]
    if len(account_ids) == 0:
        logger.warning("snapchat_account_id_missing client_id=%s job_id=%s", int(client_id), job_id)
        return None

    logger.warning("snapchat_account_id_ambiguous client_id=%s job_id=%s account_count=%s", int(client_id), job_id, len(account_ids))
    return None


def _resolve_snapchat_account_metadata(*, client_id: int, job_id: str | None = None) -> dict[str, object]:
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_SNAPCHAT_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("snapchat_operational_metadata_lookup_failed client_id=%s job_id=%s error=%s", int(client_id), job_id, str(exc)[:300])
        return {"account_id": None}

    rows = [item for item in accounts if isinstance(item, dict)]
    account_ids = [str(item.get("id") or "").strip() for item in rows]
    account_ids = [item for item in account_ids if item != ""]
    if len(account_ids) != 1:
        if len(account_ids) == 0:
            logger.warning("snapchat_operational_metadata_account_id_missing client_id=%s job_id=%s", int(client_id), job_id)
        else:
            logger.warning("snapchat_operational_metadata_account_id_ambiguous client_id=%s job_id=%s account_count=%s", int(client_id), job_id, len(account_ids))
        return {"account_id": None}

    selected = rows[0]
    metadata: dict[str, object] = {"account_id": account_ids[0]}

    status_value = selected.get("status")
    if isinstance(status_value, str) and status_value.strip() != "":
        metadata["status"] = status_value.strip()

    currency_candidates = (selected.get("currency_code"), selected.get("currency"))
    for currency_value in currency_candidates:
        if isinstance(currency_value, str) and currency_value.strip() != "":
            metadata["currency_code"] = currency_value.strip().upper()
            break

    timezone_candidates = (selected.get("account_timezone"), selected.get("timezone"))
    for tz_value in timezone_candidates:
        if isinstance(tz_value, str) and tz_value.strip() != "":
            metadata["account_timezone"] = tz_value.strip()
            break

    return metadata


def _mirror_snapchat_platform_account_operational_metadata(*, client_id: int, account_id: str | None, date_start: str, job_id: str, phase: str, include_last_synced_at: bool = False, account_status: str | None = None, currency_code: str | None = None, account_timezone: str | None = None) -> None:
    if account_id is None:
        logger.warning("snapchat_operational_metadata_skip_missing_account_id client_id=%s job_id=%s phase=%s", int(client_id), job_id, phase)
        return

    payload: dict[str, object] = {
        "platform": PLATFORM_SNAPCHAT_ADS,
        "account_id": str(account_id),
        "sync_start_date": datetime.fromisoformat(date_start).date(),
    }
    if isinstance(account_status, str) and account_status.strip() != "":
        payload["status"] = account_status.strip()
    if isinstance(currency_code, str) and currency_code.strip() != "":
        payload["currency_code"] = currency_code.strip().upper()
    if isinstance(account_timezone, str) and account_timezone.strip() != "":
        payload["account_timezone"] = account_timezone.strip()
    if include_last_synced_at:
        payload["last_synced_at"] = datetime.utcnow()

    try:
        client_registry_service.update_platform_account_operational_metadata(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "snapchat_operational_metadata_update_failed platform=%s account_id=%s job_id=%s phase=%s error=%s",
            PLATFORM_SNAPCHAT_ADS,
            account_id,
            job_id,
            phase,
            str(exc)[:300],
        )


def _mirror_sync_run_create(*, job_id: str, client_id: int, account_id: str | None, date_start_iso: str, date_end_iso: str) -> None:
    try:
        sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=PLATFORM_SNAPCHAT_ADS,
            status=SYNC_STATUS_QUEUED,
            client_id=int(client_id),
            account_id=account_id,
            date_start=datetime.fromisoformat(date_start_iso).date(),
            date_end=datetime.fromisoformat(date_end_iso).date(),
            chunk_days=1,
            metadata={"job_type": "sync", "source": "snapchat_ads_api"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "snapchat_sync_runs_create_failed platform=%s account_id=%s job_id=%s status=%s error=%s",
            PLATFORM_SNAPCHAT_ADS,
            account_id,
            job_id,
            SYNC_STATUS_QUEUED,
            str(exc)[:300],
        )


def _mirror_sync_run_status(*, job_id: str, status_value: str, error: str | None = None, mark_started: bool = False, mark_finished: bool = False) -> None:
    try:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status=status_value,
            error=error,
            mark_started=mark_started,
            mark_finished=mark_finished,
            metadata=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "snapchat_sync_runs_status_failed platform=%s job_id=%s status=%s error=%s",
            PLATFORM_SNAPCHAT_ADS,
            job_id,
            status_value,
            str(exc)[:300],
        )


def _map_sync_run_to_job_status_payload(sync_run: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "job_id": str(sync_run.get("job_id") or ""),
        "status": str(sync_run.get("status") or SYNC_STATUS_QUEUED),
        "platform": sync_run.get("platform") or PLATFORM_SNAPCHAT_ADS,
    }
    for field in ("client_id", "account_id", "date_start", "date_end", "chunk_days", "created_at", "started_at", "finished_at", "error", "metadata"):
        value = sync_run.get(field)
        if value is not None:
            payload[field] = value
    return payload


def _mirror_snapchat_sync_state_upsert(*, account_id: str | None, job_id: str, status_value: str, client_id: int, date_start: str, date_end: str, error: str | None = None, include_success: bool = False) -> None:
    if account_id is None:
        logger.warning("snapchat_sync_state_skip_missing_account_id client_id=%s job_id=%s status=%s", int(client_id), job_id, status_value)
        return

    now_utc = datetime.utcnow()
    payload: dict[str, object] = {
        "platform": PLATFORM_SNAPCHAT_ADS,
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
            "snapchat_sync_state_upsert_failed platform=%s account_id=%s job_id=%s status=%s error=%s",
            PLATFORM_SNAPCHAT_ADS,
            account_id,
            job_id,
            status_value,
            str(exc)[:300],
        )


def _run_snapchat_sync_job(job_id: str, *, client_id: int) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_RUNNING, mark_started=True)
    date_end = datetime.utcnow().date().isoformat()
    date_start = date_end
    account_metadata = _resolve_snapchat_account_metadata(client_id=int(client_id), job_id=job_id)
    account_id = account_metadata.get("account_id") if isinstance(account_metadata.get("account_id"), str) else None
    account_status = account_metadata.get("status") if isinstance(account_metadata.get("status"), str) else None
    currency_code = account_metadata.get("currency_code") if isinstance(account_metadata.get("currency_code"), str) else None
    account_timezone = account_metadata.get("account_timezone") if isinstance(account_metadata.get("account_timezone"), str) else None
    _mirror_snapchat_platform_account_operational_metadata(
        client_id=int(client_id),
        account_id=account_id,
        date_start=date_start,
        job_id=job_id,
        phase="start",
        include_last_synced_at=False,
        account_status=account_status,
        currency_code=currency_code,
        account_timezone=account_timezone,
    )
    _mirror_snapchat_sync_state_upsert(
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
        snapshot = snapchat_ads_service.sync_client(client_id=client_id)
        payload = {
            "status": SYNC_STATUS_DONE,
            "job_id": job_id,
            "client_id": int(client_id),
            "platform": PLATFORM_SNAPCHAT_ADS,
            "result": snapshot,
        }
        backfill_job_store.set_done(job_id, result=payload)
        _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_DONE, mark_finished=True)
        _mirror_snapchat_platform_account_operational_metadata(
            client_id=int(client_id),
            account_id=account_id,
            date_start=date_start,
            job_id=job_id,
            phase="success",
            include_last_synced_at=True,
            account_status=account_status,
            currency_code=currency_code,
            account_timezone=account_timezone,
        )
        _mirror_snapchat_sync_state_upsert(
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
        _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_ERROR, error=safe_error, mark_finished=True)
        _mirror_snapchat_sync_state_upsert(
            account_id=account_id,
            job_id=job_id,
            status_value=SYNC_STATUS_ERROR,
            client_id=int(client_id),
            date_start=date_start,
            date_end=date_end,
            error=safe_error,
            include_success=False,
        )


@router.post("/sync-now")
def sync_snapchat_ads_now(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    client_id: int = Query(..., ge=1),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    today_iso = datetime.utcnow().date().isoformat()
    job_id = backfill_job_store.create(payload={"platform": PLATFORM_SNAPCHAT_ADS, "client_id": int(client_id)})
    snapchat_account_id = _resolve_snapchat_account_id(client_id=int(client_id), job_id=job_id)
    _mirror_sync_run_create(
        job_id=job_id,
        client_id=int(client_id),
        account_id=snapchat_account_id,
        date_start_iso=today_iso,
        date_end_iso=today_iso,
    )
    background_tasks.add_task(_run_snapchat_sync_job, job_id, client_id=int(client_id))
    return {
        "status": SYNC_STATUS_QUEUED,
        "job_id": job_id,
        "client_id": int(client_id),
        "platform": PLATFORM_SNAPCHAT_ADS,
    }


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:snapchat:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return payload

    try:
        sync_run = sync_runs_store.get_sync_run(job_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("snapchat_sync_runs_read_failed platform=%s job_id=%s error=%s", PLATFORM_SNAPCHAT_ADS, job_id, str(exc)[:300])
        sync_run = None

    if sync_run is not None:
        return _map_sync_run_to_job_status_payload(sync_run)

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
