from datetime import date, datetime, timedelta
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.sync_engine import backfill_job_store
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_state_store import sync_state_store
from app.services.sync_constants import PLATFORM_GOOGLE_ADS, SYNC_GRAIN_ACCOUNT_DAILY, SYNC_STATUS_DONE, SYNC_STATUS_ERROR, SYNC_STATUS_QUEUED, SYNC_STATUS_RUNNING

router = APIRouter(prefix="/integrations/google-ads", tags=["google-ads"])
logger = logging.getLogger(__name__)

UI_ROLLING_SYNC_DAYS = 30
UI_ROLLING_SYNC_CHUNK_DAYS = 7


def _resolve_ui_rolling_window(*, client_id: int | None, start_date: date | None, end_date: date | None, days: int, chunk_days: int) -> tuple[date, date, int]:
    effective_end = datetime.utcnow().date() - timedelta(days=1)
    effective_start = effective_end - timedelta(days=UI_ROLLING_SYNC_DAYS - 1)
    ignored_inputs: dict[str, object] = {}
    if start_date is not None:
        ignored_inputs["start_date"] = start_date.isoformat()
    if end_date is not None:
        ignored_inputs["end_date"] = end_date.isoformat()
    if int(days) != UI_ROLLING_SYNC_DAYS:
        ignored_inputs["days"] = int(days)
    if int(chunk_days) != UI_ROLLING_SYNC_CHUNK_DAYS:
        ignored_inputs["chunk_days"] = int(chunk_days)

    if ignored_inputs:
        logger.warning(
            "google_ads.sync_now ui_rolling_mode ignoring_request_range client_id=%s mode=rolling_30d effective_start_date=%s effective_end_date=%s chunk_days=%s ignored=%s",
            client_id,
            effective_start.isoformat(),
            effective_end.isoformat(),
            UI_ROLLING_SYNC_CHUNK_DAYS,
            ignored_inputs,
        )
    else:
        logger.info(
            "google_ads.sync_now ui_rolling_mode client_id=%s mode=rolling_30d effective_start_date=%s effective_end_date=%s chunk_days=%s",
            client_id,
            effective_start.isoformat(),
            effective_end.isoformat(),
            UI_ROLLING_SYNC_CHUNK_DAYS,
        )

    return effective_start, effective_end, UI_ROLLING_SYNC_CHUNK_DAYS


def _log_best_effort_warning(*, operation: str, error: Exception, job_id: str | None = None, account_id: str | None = None, status_value: str | None = None, grain: str | None = None, platform: str | None = None) -> None:
    logger.warning(
        "best_effort_op_failed operation=%s job_id=%s platform=%s account_id=%s status=%s grain=%s error=%s",
        operation,
        job_id,
        platform,
        account_id,
        status_value,
        grain,
        str(error)[:300],
    )


def _mask_customer_id(customer_id: str) -> str:
    normalized = customer_id.strip()
    if len(normalized) < 4:
        return "****"
    return f"***{normalized[-4:]}"


def _mirror_sync_run_create(*, job_id: str, platform: str, status: str, client_id: int | None, account_id: str | None, date_start: date, date_end: date, chunk_days: int, metadata: dict[str, object] | None = None) -> None:
    try:
        sync_runs_store.create_sync_run(
            job_id=job_id,
            platform=platform,
            status=status,
            client_id=client_id,
            account_id=account_id,
            date_start=date_start,
            date_end=date_end,
            chunk_days=chunk_days,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_create", error=exc, job_id=job_id, platform=PLATFORM_GOOGLE_ADS)


def _mirror_sync_run_status(*, job_id: str, status: str, error: str | None = None, mark_started: bool = False, mark_finished: bool = False, metadata: dict[str, object] | None = None) -> None:
    try:
        sync_runs_store.update_sync_run_status(
            job_id=job_id,
            status=status,
            error=error,
            mark_started=mark_started,
            mark_finished=mark_finished,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_status", error=exc, job_id=job_id, status_value=status, platform=PLATFORM_GOOGLE_ADS)


def _build_job_date_chunks(*, date_start: date, date_end: date, chunk_days: int) -> list[tuple[int, date, date]]:
    if chunk_days <= 0:
        chunk_days = 7

    chunks: list[tuple[int, date, date]] = []
    cursor = date_start
    chunk_index = 0
    while cursor <= date_end:
        chunk_end = min(date_end, cursor + timedelta(days=int(chunk_days) - 1))
        chunks.append((chunk_index, cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
        chunk_index += 1
    return chunks


def _mirror_sync_run_chunks_create(*, job_id: str, date_start: date, date_end: date, chunk_days: int, mapped_accounts_count: int, total_days: int) -> None:
    try:
        planned_chunks = _build_job_date_chunks(date_start=date_start, date_end=date_end, chunk_days=int(chunk_days))
        for chunk_index, chunk_start, chunk_end in planned_chunks:
            sync_run_chunks_store.create_sync_run_chunk(
                job_id=job_id,
                chunk_index=int(chunk_index),
                status=SYNC_STATUS_QUEUED,
                date_start=chunk_start,
                date_end=chunk_end,
                metadata={
                    "days": int(total_days),
                    "chunk_days": int(chunk_days),
                    "mapped_accounts_count": int(mapped_accounts_count),
                },
            )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_run_chunks_create", error=exc, job_id=job_id, platform=PLATFORM_GOOGLE_ADS)


@router.get("/status")
def google_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:status", scope="agency")
        rate_limiter_service.check(f"google_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = google_ads_service.integration_status()
    google_accounts = client_registry_service.list_platform_accounts(platform=PLATFORM_GOOGLE_ADS)
    status_payload["connected_accounts_count"] = len(google_accounts)
    status_payload["last_import_at"] = client_registry_service.get_last_import_at(platform=PLATFORM_GOOGLE_ADS)

    diagnostics = google_ads_service.run_diagnostics()
    mapped_accounts = client_registry_service.list_google_mapped_accounts()
    status_payload["accounts_found"] = diagnostics.get("accessible_customers_count", 0)
    status_payload["rows_in_db_last_30_days"] = diagnostics.get("rows_in_db_last_30_days", diagnostics.get("db_rows_last_30_days", 0))
    status_payload["last_sync_at"] = diagnostics.get("last_sync_at")
    status_payload["last_error"] = diagnostics.get("last_error")
    status_payload["mapped_accounts_count"] = len(mapped_accounts)
    status_payload["sample_customer_ids"] = [_mask_customer_id(str(item.get("customer_id") or "")) for item in mapped_accounts[:10]]
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.status",
        resource="integration:google_ads",
        details={"status": status_payload["status"], "mode": status_payload.get("mode", "mock")},
    )
    return status_payload


@router.get("/connect")
def connect_google_ads(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    try:
        payload = google_ads_service.build_oauth_authorize_url()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.connect.start",
        resource="integration:google_ads",
        details={"state": payload["state"]},
    )
    return payload


@router.post("/oauth/exchange")
def google_ads_oauth_exchange(
    payload: dict[str, str],
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    code = str(payload.get("code", "")).strip()
    state = str(payload.get("state", "")).strip()
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state for OAuth exchange")

    try:
        response_payload = google_ads_service.exchange_oauth_code(code=code, state=state)
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.connect.success",
        resource="integration:google_ads",
        details={"customers": len(response_payload.get("accessible_customers", []))},
    )
    return response_payload




@router.get("/accounts")
def list_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    normalized_items = [
        {
            "customer_id": str(item.get("id", "")).replace("-", "").strip(),
            "name": str(item.get("name") or str(item.get("id") or "")),
            "is_manager": bool(item.get("is_manager", False)),
            "currency_code": (str(item.get("currency_code")).strip() if item.get("currency_code") is not None else None),
        }
        for item in accounts
    ]

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.accounts.list",
        resource="integration:google_ads",
        details={"count": len(normalized_items)},
    )
    return {"items": normalized_items, "count": len(normalized_items)}


@router.post("/import-accounts")
def import_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    imported_accounts = [{"id": item["id"], "name": item["name"]} for item in accounts]

    client_registry_service.upsert_platform_accounts(platform=PLATFORM_GOOGLE_ADS, accounts=imported_accounts)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.import_accounts",
        resource="integration:google_ads",
        details={"imported": len(imported_accounts), "accessible": len(imported_accounts)},
    )

    return {
        "status": "ok",
        "accessible_customers": [item["id"] for item in imported_accounts],
        "imported_accounts": imported_accounts,
        "imported_count": len(imported_accounts),
        "last_import_at": client_registry_service.get_last_import_at(platform=PLATFORM_GOOGLE_ADS),
    }


@router.post("/refresh-account-names")
def refresh_google_account_names(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refreshed_accounts = [{"id": item["id"], "name": item["name"]} for item in accounts]
    client_registry_service.upsert_platform_accounts(platform=PLATFORM_GOOGLE_ADS, accounts=refreshed_accounts)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.refresh_account_names",
        resource="integration:google_ads",
        details={"refreshed": len(refreshed_accounts)},
    )
    return {
        "status": "ok",
        "refreshed_count": len(refreshed_accounts),
        "items": refreshed_accounts,
        "last_import_at": client_registry_service.get_last_import_at(platform=PLATFORM_GOOGLE_ADS),
    }


@router.get("/diagnostics")
def google_ads_diagnostics(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    details = google_ads_service.run_diagnostics()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.diagnostics",
        resource="integration:google_ads",
        details={"warnings": len(details.get("warnings", []))},
    )
    return details






@router.get("/db-debug")
def google_ads_db_debug(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    diagnostics = google_ads_service.run_diagnostics()
    db_debug = google_ads_service.db_debug_summary()
    payload = {
        "oauth_ok": bool(diagnostics.get("oauth_ok")),
        "rows_in_db_last_30_days": int(diagnostics.get("rows_in_db_last_30_days", 0) or 0),
        "last_sync_at": diagnostics.get("last_sync_at"),
        "last_error": diagnostics.get("last_error"),
        "db_debug": db_debug,
    }
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.db_debug",
        resource="integration:google_ads",
        details={"db_ok": bool(db_debug.get("db_ok")), "table_exists": bool(db_debug.get("table_exists"))},
    )
    return payload

def _mirror_platform_account_operational_metadata(
    *,
    platform: str,
    account_id: str,
    status: str | None = None,
    currency_code: str | None = None,
    account_timezone: str | None = None,
    sync_start_date: date | None = None,
    last_synced_at: datetime | None = None,
) -> None:
    payload: dict[str, object] = {
        "platform": platform,
        "account_id": account_id,
        "sync_start_date": sync_start_date,
    }
    if status is not None and status.strip() != "":
        payload["status"] = status.strip()
    if currency_code is not None and currency_code.strip() != "":
        payload["currency_code"] = currency_code.strip().upper()
    if account_timezone is not None and account_timezone.strip() != "":
        payload["account_timezone"] = account_timezone.strip()
    if last_synced_at is not None:
        payload["last_synced_at"] = last_synced_at

    try:
        client_registry_service.update_platform_account_operational_metadata(**payload)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="platform_account_metadata_update", error=exc, account_id=account_id, platform=PLATFORM_GOOGLE_ADS)


def _mirror_sync_state_upsert(
    *,
    platform: str,
    account_id: str,
    grain: str,
    last_status: str,
    last_job_id: str,
    last_attempted_at: datetime,
    last_successful_at: datetime | None = None,
    last_successful_date: date | None = None,
    error: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    try:
        sync_state_store.upsert_sync_state(
            platform=platform,
            account_id=account_id,
            grain=grain,
            last_status=last_status,
            last_job_id=last_job_id,
            last_attempted_at=last_attempted_at,
            last_successful_at=last_successful_at,
            last_successful_date=last_successful_date,
            error=error,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_state_upsert", error=exc, account_id=account_id, status_value=last_status, grain=grain, platform=platform)


def _run_google_backfill_job(job_id: str, *, mapped_accounts: list[dict[str, object]], resolved_start: date, resolved_end: date, days: int, chunk_days: int, requested_client_id: int | None) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status=SYNC_STATUS_RUNNING, mark_started=True)

    attempts: list[dict[str, object]] = []
    errors_summary: list[dict[str, str | int]] = []
    inserted_rows_total = 0

    try:
        for item in mapped_accounts:
            client_id = int(item.get("client_id") or 0)
            raw_customer_id = str(item.get("customer_id") or "").strip()
            masked_customer_id = f"***{raw_customer_id[-4:]}" if len(raw_customer_id) >= 4 else "****"
            attempt_now = datetime.utcnow()
            account_status = str(item.get("status") or "").strip() or None
            account_currency_code = str(item.get("currency_code") or "").strip() or None
            account_timezone = str(item.get("account_timezone") or "").strip() or None
            _mirror_platform_account_operational_metadata(
                platform=PLATFORM_GOOGLE_ADS,
                account_id=raw_customer_id,
                status=account_status,
                currency_code=account_currency_code,
                account_timezone=account_timezone,
                sync_start_date=resolved_start,
            )
            sync_state_metadata = {
                "client_id": client_id,
                "date_start": resolved_start.isoformat(),
                "date_end": resolved_end.isoformat(),
                "chunk_days": int(chunk_days),
                "job_type": "backfill",
            }
            _mirror_sync_state_upsert(
                platform=PLATFORM_GOOGLE_ADS,
                account_id=raw_customer_id,
                grain=SYNC_GRAIN_ACCOUNT_DAILY,
                last_status=SYNC_STATUS_RUNNING,
                last_job_id=job_id,
                last_attempted_at=attempt_now,
                error=None,
                metadata=sync_state_metadata,
            )
            try:
                snapshot = google_ads_service.sync_customer_for_client(
                    client_id=client_id,
                    customer_id=raw_customer_id,
                    days=days,
                    start_date=resolved_start,
                    end_date=resolved_end,
                    chunk_days=chunk_days,
                )
                inserted_rows = int(snapshot.get("inserted_rows", 0) or 0)
                inserted_rows_total += inserted_rows
                attempts.append(
                    {
                        "client_id": client_id,
                        "customer_id_masked": masked_customer_id,
                        "status": "ok",
                        "inserted_rows": inserted_rows,
                        "gaql_rows_fetched": int(snapshot.get("gaql_rows_fetched", 0) or 0),
                        "db_rows_last_30_for_customer": int(snapshot.get("db_rows_last_30_for_customer", 0) or 0),
                        "reason_if_zero": snapshot.get("reason_if_zero"),
                    }
                )
                success_now = datetime.utcnow()
                _mirror_platform_account_operational_metadata(
                    platform=PLATFORM_GOOGLE_ADS,
                    account_id=raw_customer_id,
                    status=account_status,
                    currency_code=account_currency_code,
                    account_timezone=account_timezone,
                    sync_start_date=resolved_start,
                    last_synced_at=success_now,
                )
                _mirror_sync_state_upsert(
                    platform=PLATFORM_GOOGLE_ADS,
                    account_id=raw_customer_id,
                    grain=SYNC_GRAIN_ACCOUNT_DAILY,
                    last_status=SYNC_STATUS_DONE,
                    last_job_id=job_id,
                    last_attempted_at=success_now,
                    last_successful_at=success_now,
                    last_successful_date=resolved_end,
                    error=None,
                    metadata=sync_state_metadata,
                )
            except Exception as exc:  # noqa: BLE001
                safe_message = str(exc).replace(raw_customer_id, "***")[:300]
                attempts.append(
                    {
                        "client_id": client_id,
                        "customer_id_masked": masked_customer_id,
                        "status": SYNC_STATUS_ERROR,
                        "gaql_rows_fetched": 0,
                        "inserted_rows": 0,
                        "db_rows_last_30_for_customer": 0,
                        "reason_if_zero": "DB_INSERT_FAILED",
                    }
                )
                errors_summary.append(
                    {
                        "client_id": client_id,
                        "customer_id_masked": masked_customer_id,
                        "error": safe_message,
                    }
                )
                _mirror_sync_state_upsert(
                    platform=PLATFORM_GOOGLE_ADS,
                    account_id=raw_customer_id,
                    grain=SYNC_GRAIN_ACCOUNT_DAILY,
                    last_status=SYNC_STATUS_ERROR,
                    last_job_id=job_id,
                    last_attempted_at=datetime.utcnow(),
                    error=safe_message,
                    metadata=sync_state_metadata,
                )

        succeeded_accounts_count = len([item for item in attempts if item["status"] == "ok"])
        failed_accounts_count = len([item for item in attempts if item["status"] == "error"])
        payload = {
            "status": "ok" if failed_accounts_count == 0 else "partial",
            "mapped_accounts_count": len(mapped_accounts),
            "attempted_accounts_count": len(attempts),
            "succeeded_accounts_count": succeeded_accounts_count,
            "failed_accounts_count": failed_accounts_count,
            "inserted_rows_total": inserted_rows_total,
            "date_range": {"start": resolved_start.isoformat(), "end": resolved_end.isoformat()},
            "sample_customer_ids": [item["customer_id_masked"] for item in attempts[:10]],
            "errors_summary": errors_summary,
            "attempts": attempts,
            "client_id": requested_client_id,
            "days": int(days),
            "chunk_days": int(chunk_days),
        }
        backfill_job_store.set_done(job_id, result=payload)
        _mirror_sync_run_status(
            job_id=job_id,
            status=SYNC_STATUS_DONE,
            mark_finished=True,
            metadata={
                "mapped_accounts_count": len(mapped_accounts),
                "successful_accounts": succeeded_accounts_count,
                "failed_accounts": failed_accounts_count,
                "days": int(days),
                "chunk_days": int(chunk_days),
            },
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = str(exc)[:300]
        backfill_job_store.set_error(job_id, error=safe_error)
        _mirror_sync_run_status(job_id=job_id, status=SYNC_STATUS_ERROR, error=safe_error, mark_finished=True)


@router.post("/sync-now")
def sync_google_ads_now(
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
    client_id: int | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=3660),
    async_mode: bool = Query(default=True),
    chunk_days: int = Query(default=7, ge=1, le=31),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    requested_client_id = client_id
    mapped_accounts = client_registry_service.list_google_mapped_accounts()
    if requested_client_id is not None:
        mapped_accounts = [item for item in mapped_accounts if int(item.get("client_id") or 0) == int(requested_client_id)]

    resolved_start, resolved_end, effective_chunk_days = _resolve_ui_rolling_window(
        client_id=requested_client_id,
        start_date=start_date,
        end_date=end_date,
        days=int(days),
        chunk_days=int(chunk_days),
    )

    if len(mapped_accounts) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No mapped Google Ads customer IDs for any subaccount")

    if async_mode:
        job_id = backfill_job_store.create(
            payload={
                "platform": PLATFORM_GOOGLE_ADS,
                "client_id": requested_client_id,
                "date_range": {"start": resolved_start.isoformat(), "end": resolved_end.isoformat()},
                "mapped_accounts_count": len(mapped_accounts),
                "chunk_days": int(effective_chunk_days),
                "mode": "rolling_30d",
                "effective_start_date": resolved_start.isoformat(),
                "effective_end_date": resolved_end.isoformat(),
            }
        )
        background_tasks.add_task(
            _run_google_backfill_job,
            job_id,
            mapped_accounts=mapped_accounts,
            resolved_start=resolved_start,
            resolved_end=resolved_end,
            days=max(1, (resolved_end - resolved_start).days + 1),
            chunk_days=int(effective_chunk_days),
            requested_client_id=requested_client_id,
        )
        _mirror_sync_run_create(
            job_id=job_id,
            platform=PLATFORM_GOOGLE_ADS,
            status=SYNC_STATUS_QUEUED,
            client_id=requested_client_id,
            account_id=None,
            date_start=resolved_start,
            date_end=resolved_end,
            chunk_days=int(effective_chunk_days),
            metadata={"job_type": "rolling_sync", "mode": "rolling_30d", "source": "google_ads_api", "mapped_accounts_count": len(mapped_accounts)},
        )
        _mirror_sync_run_chunks_create(
            job_id=job_id,
            date_start=resolved_start,
            date_end=resolved_end,
            chunk_days=int(effective_chunk_days),
            mapped_accounts_count=len(mapped_accounts),
            total_days=max(1, (resolved_end - resolved_start).days + 1),
        )
        return {
            "status": SYNC_STATUS_QUEUED,
            "job_id": job_id,
            "mapped_accounts_count": len(mapped_accounts),
            "date_range": {"start": resolved_start.isoformat(), "end": resolved_end.isoformat()},
            "client_id": requested_client_id,
            "chunk_days": int(effective_chunk_days),
            "mode": "rolling_30d",
            "effective_start_date": resolved_start.isoformat(),
            "effective_end_date": resolved_end.isoformat(),
        }

    # Synchronous fallback
    job_id = backfill_job_store.create(payload={"platform": PLATFORM_GOOGLE_ADS, "chunk_days": int(effective_chunk_days)})
    _run_google_backfill_job(
        job_id,
        mapped_accounts=mapped_accounts,
        resolved_start=resolved_start,
        resolved_end=resolved_end,
        days=max(1, (resolved_end - resolved_start).days + 1),
        chunk_days=int(chunk_days),
        requested_client_id=requested_client_id,
    )
    result = backfill_job_store.get(job_id) or {}
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.sync_now",
        resource="integration:google_ads",
        details={
            "mapped_accounts_count": len(mapped_accounts),
            "client_id": requested_client_id,
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "chunk_days": int(effective_chunk_days),
            "mode": "rolling_30d",
            "effective_start_date": resolved_start.isoformat(),
            "effective_end_date": resolved_end.isoformat(),
        },
    )
    payload = dict(result.get("result") or {"status": SYNC_STATUS_ERROR, "job_id": job_id})
    payload.setdefault("mode", "rolling_30d")
    payload.setdefault("effective_start_date", resolved_start.isoformat())
    payload.setdefault("effective_end_date", resolved_end.isoformat())
    return payload


def _build_chunk_summary(chunks: list[dict[str, object]]) -> dict[str, int]:
    summary = {"total": len(chunks), SYNC_STATUS_QUEUED: 0, SYNC_STATUS_RUNNING: 0, SYNC_STATUS_DONE: 0, SYNC_STATUS_ERROR: 0}
    for item in chunks:
        status_value = str(item.get("status") or "").strip().lower()
        if status_value in summary:
            summary[status_value] += 1
    return summary


def _to_chunk_status_payload(chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for item in chunks:
        payload.append(
            {
                "chunk_index": int(item.get("chunk_index") or 0),
                "status": str(item.get("status") or SYNC_STATUS_QUEUED),
                "date_start": item.get("date_start"),
                "date_end": item.get("date_end"),
                "started_at": item.get("started_at"),
                "finished_at": item.get("finished_at"),
                "error": item.get("error"),
                "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            }
        )
    return payload


def _attach_job_chunks_payload(*, job_id: str, payload: dict[str, object]) -> dict[str, object]:
    enriched = dict(payload)
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_run_chunks_read", error=exc, job_id=job_id, platform=PLATFORM_GOOGLE_ADS)
        return enriched

    chunk_items = _to_chunk_status_payload(chunks)
    enriched["chunk_summary"] = _build_chunk_summary(chunk_items)
    enriched["chunks"] = chunk_items
    return enriched


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

    for field in ("date_range", "mapped_accounts_count", "chunk_days", "platform", "client_id"):
        value = metadata.get(field)
        if value is not None and field not in payload:
            payload[field] = value

    return payload


@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is not None:
        return _attach_job_chunks_payload(job_id=job_id, payload=payload)

    try:
        sync_run = sync_runs_store.get_sync_run(job_id)
    except Exception as exc:  # noqa: BLE001
        _log_best_effort_warning(operation="sync_runs_read", error=exc, job_id=job_id, platform=PLATFORM_GOOGLE_ADS)
        sync_run = None

    if sync_run is not None:
        mapped_payload = _map_sync_run_to_job_status_payload(sync_run)
        return _attach_job_chunks_payload(job_id=job_id, payload=mapped_payload)

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

@router.post("/{client_id}/sync")
def sync_google_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | str]:
    try:
        enforce_action_scope(user=user, action="integrations:sync", scope="subaccount")
        rate_limiter_service.check(f"google_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        snapshot = google_ads_service.sync_client(client_id=client_id)
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google Ads API unavailable: {str(exc)[:200]}") from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.sync",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
