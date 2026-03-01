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

router = APIRouter(prefix="/integrations/google-ads", tags=["google-ads"])
logger = logging.getLogger(__name__)


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
        logger.warning("sync_runs mirror write failed for google_ads job_id=%s error=%s", job_id, str(exc)[:300])


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
        logger.warning("sync_runs mirror status update failed for google_ads job_id=%s status=%s error=%s", job_id, status, str(exc)[:300])


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
                status="queued",
                date_start=chunk_start,
                date_end=chunk_end,
                metadata={
                    "days": int(total_days),
                    "chunk_days": int(chunk_days),
                    "mapped_accounts_count": int(mapped_accounts_count),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_run_chunks mirror write failed for google_ads job_id=%s error=%s", job_id, str(exc)[:300])


@router.get("/status")
def google_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="integrations:status", scope="agency")
        rate_limiter_service.check(f"google_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = google_ads_service.integration_status()
    google_accounts = client_registry_service.list_platform_accounts(platform="google_ads")
    status_payload["connected_accounts_count"] = len(google_accounts)
    status_payload["last_import_at"] = client_registry_service.get_last_import_at(platform="google_ads")

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

    client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=imported_accounts)

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
        "last_import_at": client_registry_service.get_last_import_at(platform="google_ads"),
    }


@router.post("/refresh-account-names")
def refresh_google_account_names(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    refreshed_accounts = [{"id": item["id"], "name": item["name"]} for item in accounts]
    client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=refreshed_accounts)

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
        "last_import_at": client_registry_service.get_last_import_at(platform="google_ads"),
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

def _run_google_backfill_job(job_id: str, *, mapped_accounts: list[dict[str, object]], resolved_start: date, resolved_end: date, days: int, chunk_days: int, requested_client_id: int | None) -> None:
    backfill_job_store.set_running(job_id)
    _mirror_sync_run_status(job_id=job_id, status="running", mark_started=True)

    attempts: list[dict[str, object]] = []
    errors_summary: list[dict[str, str | int]] = []
    inserted_rows_total = 0

    try:
        for item in mapped_accounts:
            client_id = int(item.get("client_id") or 0)
            raw_customer_id = str(item.get("customer_id") or "").strip()
            masked_customer_id = f"***{raw_customer_id[-4:]}" if len(raw_customer_id) >= 4 else "****"
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
            except Exception as exc:  # noqa: BLE001
                safe_message = str(exc).replace(raw_customer_id, "***")[:300]
                attempts.append(
                    {
                        "client_id": client_id,
                        "customer_id_masked": masked_customer_id,
                        "status": "error",
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
            status="done",
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
        _mirror_sync_run_status(job_id=job_id, status="error", error=safe_error, mark_finished=True)


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

    yesterday = datetime.utcnow().date() - timedelta(days=1)
    resolved_end = end_date or yesterday
    if start_date is not None:
        resolved_start = start_date
    elif end_date is not None:
        resolved_start = resolved_end - timedelta(days=int(days) - 1)
    else:
        resolved_start = date(2026, 1, 1)
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    if len(mapped_accounts) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No mapped Google Ads customer IDs for any subaccount")

    if async_mode:
        job_id = backfill_job_store.create(
            payload={
                "platform": "google_ads",
                "client_id": requested_client_id,
                "date_range": {"start": resolved_start.isoformat(), "end": resolved_end.isoformat()},
                "mapped_accounts_count": len(mapped_accounts),
                "chunk_days": int(chunk_days),
            }
        )
        background_tasks.add_task(
            _run_google_backfill_job,
            job_id,
            mapped_accounts=mapped_accounts,
            resolved_start=resolved_start,
            resolved_end=resolved_end,
            days=max(1, (resolved_end - resolved_start).days + 1),
            chunk_days=int(chunk_days),
            requested_client_id=requested_client_id,
        )
        _mirror_sync_run_create(
            job_id=job_id,
            platform="google_ads",
            status="queued",
            client_id=requested_client_id,
            account_id=None,
            date_start=resolved_start,
            date_end=resolved_end,
            chunk_days=int(chunk_days),
            metadata={"job_type": "backfill", "source": "google_ads_api", "mapped_accounts_count": len(mapped_accounts)},
        )
        _mirror_sync_run_chunks_create(
            job_id=job_id,
            date_start=resolved_start,
            date_end=resolved_end,
            chunk_days=int(chunk_days),
            mapped_accounts_count=len(mapped_accounts),
            total_days=max(1, (resolved_end - resolved_start).days + 1),
        )
        return {
            "status": "queued",
            "job_id": job_id,
            "mapped_accounts_count": len(mapped_accounts),
            "date_range": {"start": resolved_start.isoformat(), "end": resolved_end.isoformat()},
            "client_id": requested_client_id,
            "chunk_days": int(chunk_days),
        }

    # Synchronous fallback
    job_id = backfill_job_store.create(payload={"platform": "google_ads", "chunk_days": int(chunk_days)})
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
            "chunk_days": int(chunk_days),
        },
    )
    return dict(result.get("result") or {"status": "error", "job_id": job_id})


def _build_chunk_summary(chunks: list[dict[str, object]]) -> dict[str, int]:
    summary = {"total": len(chunks), "queued": 0, "running": 0, "done": 0, "error": 0}
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
                "status": str(item.get("status") or "queued"),
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
        logger.warning("sync_run_chunks read failed for google_ads job_id=%s error=%s", job_id, str(exc)[:300])
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
        "status": str(sync_run.get("status") or "queued"),
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

    for field in ("platform", "client_id", "account_id", "date_start", "date_end", "chunk_days"):
        value = sync_run.get(field)
        if value is not None:
            payload[field] = value

    for field in ("date_range", "mapped_accounts_count", "chunk_days", "platform", "client_id"):
        value = metadata.get(field)
        if value is not None and field not in payload:
            payload[field] = value


def _attach_job_chunks_payload(*, job_id: str, payload: dict[str, object]) -> dict[str, object]:
    enriched = dict(payload)
    try:
        chunks = sync_run_chunks_store.list_sync_run_chunks(job_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_run_chunks read failed for google_ads job_id=%s error=%s", job_id, str(exc)[:300])
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
        "status": str(sync_run.get("status") or "queued"),
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

    for field in ("date_range", "mapped_accounts_count", "chunk_days", "platform", "client_id"):
        value = metadata.get(field)
        if value is not None and field not in payload:
            payload[field] = value

    for field in ("date_range", "mapped_accounts_count", "chunk_days", "platform", "client_id"):
        value = metadata.get(field)
        if value is not None and field not in payload:
            payload[field] = value

@router.get("/sync-now/jobs/{job_id}")
def sync_now_job_status(job_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    payload = backfill_job_store.get(job_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
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
        logger.warning("sync_runs fallback read failed for google_ads job_id=%s error=%s", job_id, str(exc)[:300])
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
