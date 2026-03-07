from datetime import date, datetime, timedelta
from typing import Literal
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.sync_engine import backfill_job_store
from app.services.sync_state_store import sync_state_store
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_constants import PLATFORM_META_ADS, SYNC_GRAIN_ACCOUNT_DAILY, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING

router = APIRouter(prefix="/integrations/meta-ads", tags=["meta-ads"])
logger = logging.getLogger(__name__)

_META_BACKFILL_DEFAULT_START = date(2024, 1, 9)
_META_BACKFILL_DEFAULT_GRAINS: tuple[str, ...] = ("account_daily", "campaign_daily", "ad_group_daily", "ad_daily")
_META_BACKFILL_CHUNK_DAYS = 30


def _normalize_meta_backfill_grains(grains: list[str] | None) -> list[str]:
    allowed = set(_META_BACKFILL_DEFAULT_GRAINS)
    values = grains if grains is not None and len(grains) > 0 else list(_META_BACKFILL_DEFAULT_GRAINS)
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        grain = str(value or "").strip().lower()
        if grain not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported Meta backfill grain '{value}'. Allowed: {list(_META_BACKFILL_DEFAULT_GRAINS)}",
            )
        if grain in seen:
            continue
        seen.add(grain)
        normalized.append(grain)
    return normalized


def _build_meta_backfill_chunks(*, start_date: date, end_date: date, chunk_days: int = _META_BACKFILL_CHUNK_DAYS) -> list[tuple[date, date]]:
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


class MetaSyncRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grain: Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"] | None = None


class MetaBackfillRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    grains: list[Literal["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"]] | None = None


def _log_best_effort_warning(
    *,
    operation: str,
    error: Exception,
    job_id: str | None = None,
    status_value: str | None = None,
    platform: str | None = None,
    account_id: str | None = None,
    grain: str | None = None,
) -> None:
    logger.warning(
        "best_effort_op_failed operation=%s job_id=%s status=%s platform=%s account_id=%s grain=%s error=%s",
        operation,
        job_id,
        status_value,
        platform,
        account_id,
        grain,
        str(error)[:300],
    )


def _resolve_meta_account_context(*, client_id: int, job_id: str | None = None) -> dict[str, str] | None:
    try:
        accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_META_ADS, client_id=int(client_id))
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="meta_account_lookup", error=exc, job_id=job_id, platform=PLATFORM_META_ADS)
        return None

    valid_accounts = [item for item in accounts if isinstance(item, dict) and str(item.get("id") or "").strip() != ""]
    if len(valid_accounts) == 1:
        item = valid_accounts[0]
        context: dict[str, str] = {"account_id": str(item.get("id") or "").strip()}
        raw_status = str(item.get("status") or "").strip()
        if raw_status != "":
            context["status"] = raw_status
        raw_currency = str(item.get("currency_code") or item.get("currency") or "").strip().upper()
        if raw_currency != "":
            context["currency_code"] = raw_currency
        raw_timezone = str(item.get("account_timezone") or "").strip()
        if raw_timezone != "":
            context["account_timezone"] = raw_timezone
        return context

    if len(valid_accounts) == 0:
        logger.warning("meta_account_id_missing client_id=%s job_id=%s", int(client_id), job_id)
        return None

    logger.warning("meta_account_id_ambiguous client_id=%s job_id=%s account_count=%s", int(client_id), job_id, len(valid_accounts))
    return None


def _mirror_meta_platform_account_operational_metadata(
    *,
    job_id: str,
    account_context: dict[str, str] | None,
    sync_start_date: date,
    last_synced_at: datetime | None = None,
) -> None:
    account_id = str((account_context or {}).get("account_id") or "").strip()
    if account_id == "":
        logger.warning("meta_operational_metadata_skipped_missing_account_id job_id=%s", job_id)
        return

    payload: dict[str, object] = {
        "platform": PLATFORM_META_ADS,
        "account_id": account_id,
        "sync_start_date": sync_start_date,
    }
    raw_status = str((account_context or {}).get("status") or "").strip()
    if raw_status != "":
        payload["status"] = raw_status
    raw_currency = str((account_context or {}).get("currency_code") or "").strip().upper()
    if raw_currency != "":
        payload["currency_code"] = raw_currency
    raw_timezone = str((account_context or {}).get("account_timezone") or "").strip()
    if raw_timezone != "":
        payload["account_timezone"] = raw_timezone
    if last_synced_at is not None:
        payload["last_synced_at"] = last_synced_at

    try:
        client_registry_service.update_platform_account_operational_metadata(**payload)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(
            operation="platform_account_metadata_update",
            error=exc,
            job_id=job_id,
            platform=PLATFORM_META_ADS,
            account_id=account_id,
        )


def _mirror_sync_run_create(*, job_id: str, status_value: str, client_id: int, date_start: date, date_end: date, account_id: str | None = None) -> None:
    try:
        sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=PLATFORM_META_ADS,
            status=status_value,
            client_id=client_id,
            account_id=account_id,
            date_start=date_start,
            date_end=date_end,
            chunk_days=1,
            metadata={"job_type": "sync", "source": "meta_ads_api"},
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_create", error=exc, job_id=job_id, status_value=status_value, platform=PLATFORM_META_ADS, account_id=account_id)


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
        _log_best_effort_warning(operation="sync_runs_status", error=exc, job_id=job_id, status_value=status_value, platform=PLATFORM_META_ADS)


def _mirror_meta_sync_state_upsert(
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
            platform=PLATFORM_META_ADS,
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
            platform=PLATFORM_META_ADS,
            account_id=account_id,
            grain=SYNC_GRAIN_ACCOUNT_DAILY,
        )


def _run_meta_sync_job(job_id: str, *, client_id: int, account_context: dict[str, str] | None = None) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_RUNNING, mark_started=True)

    today = datetime.utcnow().date()
    date_start = today - timedelta(days=30)
    date_end = today
    resolved_account_context = account_context or _resolve_meta_account_context(client_id=int(client_id), job_id=job_id)
    meta_account_id = str((resolved_account_context or {}).get("account_id") or "").strip() or None
    sync_state_metadata = {
        "client_id": int(client_id),
        "date_start": date_start.isoformat(),
        "date_end": date_end.isoformat(),
        "job_type": "sync",
    }
    if meta_account_id is not None:
        sync_state_metadata["account_id"] = meta_account_id

    if meta_account_id is None:
        logger.warning("meta_sync_state_skipped_missing_account_id job_id=%s client_id=%s", job_id, int(client_id))
    _mirror_meta_platform_account_operational_metadata(
        job_id=job_id,
        account_context=resolved_account_context,
        sync_start_date=date_start,
    )
    if meta_account_id is not None:
        _mirror_meta_sync_state_upsert(
            job_id=job_id,
            account_id=meta_account_id,
            last_status=SYNC_STATUS_RUNNING,
            last_attempted_at=datetime.utcnow(),
            date_end=date_end,
            error=None,
            metadata=sync_state_metadata,
        )

    try:
        snapshot = meta_ads_service.sync_client(client_id=client_id, start_date=payload.start_date if payload else None, end_date=payload.end_date if payload else None, grain=payload.grain if payload else None)
        success_now = datetime.utcnow()
        payload = {
            "status": SYNC_STATUS_DONE,
            "job_id": job_id,
            "client_id": int(client_id),
            "result": snapshot,
        }
        backfill_job_store.set_done(job_id, result=payload)
        if meta_account_id is not None:
            _mirror_meta_sync_state_upsert(
                job_id=job_id,
                account_id=meta_account_id,
                last_status=SYNC_STATUS_DONE,
                last_attempted_at=success_now,
                last_successful_at=success_now,
                date_end=date_end,
                error=None,
                metadata=sync_state_metadata,
            )
        _mirror_meta_platform_account_operational_metadata(
            job_id=job_id,
            account_context=resolved_account_context,
            sync_start_date=date_start,
            last_synced_at=success_now,
        )
        done_metadata = {"client_id": int(client_id)}
        if meta_account_id is not None:
            done_metadata["account_id"] = meta_account_id
        _mirror_sync_run_status(
            job_id=job_id,
            status_value=SYNC_STATUS_DONE,
            mark_finished=True,
            metadata=done_metadata,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)
        if meta_account_id is not None:
            _mirror_meta_sync_state_upsert(
                job_id=job_id,
                account_id=meta_account_id,
                last_status=SYNC_STATUS_ERROR,
                last_attempted_at=datetime.utcnow(),
                date_end=date_end,
                error=safe_error,
                metadata=sync_state_metadata,
            )
        _mirror_sync_run_status(job_id=job_id, status_value=SYNC_STATUS_ERROR, error=safe_error, mark_finished=True)


def _run_meta_historical_backfill_job(
    job_id: str,
    *,
    client_id: int,
    start_date: date,
    end_date: date,
    grains: list[str],
    chunk_days: int = _META_BACKFILL_CHUNK_DAYS,
) -> None:
    backfill_job_store.set_running(job_id)
    chunks = _build_meta_backfill_chunks(start_date=start_date, end_date=end_date, chunk_days=chunk_days)

    rows_written_total = 0
    accounts_processed_max = 0
    token_source: str | None = None
    execution_log: list[dict[str, object]] = []

    try:
        for grain in grains:
            for chunk_start, chunk_end in chunks:
                snapshot = meta_ads_service.sync_client(
                    client_id=int(client_id),
                    start_date=chunk_start,
                    end_date=chunk_end,
                    grain=grain,
                )
                rows_written = int(snapshot.get("rows_written") or 0)
                accounts_processed = int(snapshot.get("accounts_processed") or 0)
                rows_written_total += rows_written
                accounts_processed_max = max(accounts_processed_max, accounts_processed)
                if token_source is None:
                    token_source = str(snapshot.get("token_source") or "") or None
                execution_log.append(
                    {
                        "grain": grain,
                        "start_date": chunk_start.isoformat(),
                        "end_date": chunk_end.isoformat(),
                        "rows_written": rows_written,
                        "accounts_processed": accounts_processed,
                    }
                )

        result = {
            "status": SYNC_STATUS_DONE,
            "mode": "historical_backfill",
            "message": "Meta Ads historical backfill completed.",
            "job_id": job_id,
            "platform": PLATFORM_META_ADS,
            "client_id": int(client_id),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "grains": grains,
            "chunk_days": int(max(1, int(chunk_days))),
            "chunks_total": len(chunks),
            "chunks_processed": len(execution_log),
            "rows_written": rows_written_total,
            "accounts_processed": accounts_processed_max,
            "token_source": token_source,
            "runs": execution_log,
        }
        backfill_job_store.set_done(job_id, result=result)
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
def meta_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:status", scope="agency")
        rate_limiter_service.check(f"meta_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = meta_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.status",
        resource="integration:meta_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload




@router.get("/connect")
def connect_meta_ads(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    try:
        payload = meta_ads_service.build_oauth_authorize_url()
    except MetaAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.connect.start",
        resource="integration:meta_ads",
        details={"state": payload["state"]},
    )
    return payload


@router.post("/oauth/exchange")
def meta_ads_oauth_exchange(payload: dict[str, str], user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    code = str(payload.get("code", "")).strip()
    state = str(payload.get("state", "")).strip()
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state for OAuth exchange")

    try:
        response_payload = meta_ads_service.exchange_oauth_code(code=code, state=state)
    except MetaAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.connect.success",
        resource="integration:meta_ads",
        details={"token_source": response_payload.get("token_source")},
    )
    return response_payload



@router.post("/import-accounts")
def import_meta_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    try:
        discovered_accounts = meta_ads_service.list_accessible_ad_accounts()
    except MetaAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token_source = str(meta_ads_service.integration_status().get("token_source") or "missing")

    existing_accounts = client_registry_service.list_platform_accounts(platform=PLATFORM_META_ADS)
    existing_by_id = {str(item.get("account_id") or item.get("id") or ""): item for item in existing_accounts}

    imported = 0
    updated = 0
    unchanged = 0

    accounts_to_upsert = [{"id": str(item["id"]), "name": str(item.get("name") or item["id"])} for item in discovered_accounts]
    if len(accounts_to_upsert) > 0:
        client_registry_service.upsert_platform_accounts(platform=PLATFORM_META_ADS, accounts=accounts_to_upsert)

    for item in discovered_accounts:
        account_id = str(item.get("id") or "").strip()
        if account_id == "":
            continue

        name = str(item.get("name") or account_id)
        status_value = str(item.get("account_status") or "").strip() or None
        currency_code = str(item.get("currency_code") or "").strip().upper() or None
        account_timezone = str(item.get("account_timezone") or "").strip() or None

        existing = existing_by_id.get(account_id)
        if existing is None:
            imported += 1
            has_changes = True
        else:
            name_changed = str(existing.get("name") or "") != name
            status_changed = str(existing.get("status") or "").strip() != str(status_value or "")
            currency_changed = str(existing.get("currency") or "").strip().upper() != str(currency_code or "")
            timezone_changed = str(existing.get("timezone") or "").strip() != str(account_timezone or "")
            has_changes = name_changed or status_changed or currency_changed or timezone_changed
            if has_changes:
                updated += 1
            else:
                unchanged += 1

        if has_changes:
            client_registry_service.update_platform_account_operational_metadata(
                platform=PLATFORM_META_ADS,
                account_id=account_id,
                status=status_value,
                currency_code=currency_code,
                account_timezone=account_timezone,
            )

    summary = {
        "status": "ok",
        "message": "Meta Ads accounts import completed.",
        "platform": PLATFORM_META_ADS,
        "token_source": token_source,
        "accounts_discovered": len(discovered_accounts),
        "imported": imported,
        "updated": updated,
        "unchanged": unchanged,
    }

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.accounts.import",
        resource="integration:meta_ads",
        details=summary,
    )
    return summary

@router.post("/sync-now")
def sync_meta_ads_now(
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
        job_id = backfill_job_store.create(payload={"platform": PLATFORM_META_ADS, "client_id": int(client_id)})
        account_context = _resolve_meta_account_context(client_id=int(client_id), job_id=job_id)
        meta_account_id = str((account_context or {}).get("account_id") or "").strip() or None
        background_tasks.add_task(_run_meta_sync_job, job_id, client_id=int(client_id), account_context=account_context)
        _mirror_sync_run_create(
            job_id=job_id,
            status_value=SYNC_STATUS_QUEUED,
            client_id=int(client_id),
            date_start=date_start,
            date_end=date_end,
            account_id=meta_account_id,
        )
        return {"status": SYNC_STATUS_QUEUED, "job_id": job_id, "client_id": int(client_id)}

    job_id = backfill_job_store.create(payload={"platform": PLATFORM_META_ADS, "client_id": int(client_id)})
    account_context = _resolve_meta_account_context(client_id=int(client_id), job_id=job_id)
    _run_meta_sync_job(job_id, client_id=int(client_id), account_context=account_context)
    payload = backfill_job_store.get(job_id) or {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if isinstance(result, dict) and len(result) > 0:
        return result
    return {"status": SYNC_STATUS_ERROR, "job_id": job_id, "client_id": int(client_id)}


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return payload

    try:
        sync_run = sync_runs_store.get_sync_run(job_id)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_read", error=exc, job_id=job_id, platform=PLATFORM_META_ADS)
        sync_run = None

    if sync_run is not None:
        return _map_sync_run_to_job_status_payload(sync_run)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")


@router.post("/{client_id}/backfill")
def backfill_meta_ads(
    client_id: int,
    background_tasks: BackgroundTasks,
    payload: MetaBackfillRequest | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:sync", scope="subaccount")
        rate_limiter_service.check(f"meta_backfill:{user.email}", limit=10, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    resolved_start = payload.start_date if payload is not None and payload.start_date is not None else _META_BACKFILL_DEFAULT_START
    resolved_end = payload.end_date if payload is not None and payload.end_date is not None else (datetime.utcnow().date() - timedelta(days=1))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be before or equal to end_date")

    grains_input = payload.grains if payload is not None and payload.grains is not None else None
    resolved_grains = _normalize_meta_backfill_grains(list(grains_input) if grains_input is not None else None)

    integration_status = meta_ads_service.integration_status()
    if str(integration_status.get("token_source") or "missing") == "missing":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meta Ads token is missing or placeholder.")

    attached_accounts = client_registry_service.list_client_platform_accounts(platform=PLATFORM_META_ADS, client_id=int(client_id))
    attached_ids = sorted(
        {
            str(item.get("id") or item.get("account_id") or "").strip()
            for item in attached_accounts
            if isinstance(item, dict) and str(item.get("id") or item.get("account_id") or "").strip() != ""
        }
    )
    if len(attached_ids) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No Meta Ads accounts attached to this client.")

    chunks = _build_meta_backfill_chunks(start_date=resolved_start, end_date=resolved_end, chunk_days=_META_BACKFILL_CHUNK_DAYS)
    job_id = backfill_job_store.create(
        payload={
            "platform": PLATFORM_META_ADS,
            "client_id": int(client_id),
            "mode": "historical_backfill",
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "grains": resolved_grains,
            "chunk_days": _META_BACKFILL_CHUNK_DAYS,
        }
    )
    background_tasks.add_task(
        _run_meta_historical_backfill_job,
        job_id,
        client_id=int(client_id),
        start_date=resolved_start,
        end_date=resolved_end,
        grains=resolved_grains,
        chunk_days=_META_BACKFILL_CHUNK_DAYS,
    )

    summary = {
        "status": SYNC_STATUS_QUEUED,
        "mode": "enqueued",
        "message": "Meta Ads historical backfill enqueued.",
        "job_id": job_id,
        "client_id": int(client_id),
        "start_date": resolved_start.isoformat(),
        "end_date": resolved_end.isoformat(),
        "grains": resolved_grains,
        "chunk_days": _META_BACKFILL_CHUNK_DAYS,
        "chunks_enqueued": len(chunks),
        "jobs_enqueued": len(chunks) * len(resolved_grains),
        "accounts_detected": len(attached_ids),
        "token_source": str(integration_status.get("token_source") or "missing"),
    }
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.backfill.enqueue",
        resource=f"client:{client_id}",
        details=summary,
    )
    return summary


@router.post("/{client_id}/sync")
def sync_meta_ads(
    client_id: int,
    payload: MetaSyncRequest | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:sync", scope="subaccount")
        rate_limiter_service.check(f"meta_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        snapshot = meta_ads_service.sync_client(client_id=client_id, start_date=payload.start_date if payload else None, end_date=payload.end_date if payload else None, grain=payload.grain if payload else None)
    except MetaAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Meta Ads API unavailable") from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.sync",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
