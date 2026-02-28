from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service

router = APIRouter(prefix="/integrations/google-ads", tags=["google-ads"])


def _mask_customer_id(customer_id: str) -> str:
    normalized = customer_id.strip()
    if len(normalized) < 4:
        return "****"
    return f"***{normalized[-4:]}"


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

@router.post("/sync-now")
def sync_google_ads_now(
    user: AuthUser = Depends(get_current_user),
    client_id: int | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=90),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    requested_client_id = client_id
    mapped_accounts = client_registry_service.list_google_mapped_accounts()
    if requested_client_id is not None:
        mapped_accounts = [item for item in mapped_accounts if int(item.get("client_id") or 0) == int(requested_client_id)]
    mapped_accounts_count = len(mapped_accounts)

    if mapped_accounts_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No mapped Google Ads customer IDs for any subaccount",
        )

    attempts: list[dict[str, object]] = []
    errors_summary: list[dict[str, str | int]] = []
    inserted_rows_total = 0

    for item in mapped_accounts:
        client_id = int(item.get("client_id") or 0)
        raw_customer_id = str(item.get("customer_id") or "").strip()
        masked_customer_id = f"***{raw_customer_id[-4:]}" if len(raw_customer_id) >= 4 else "****"
        try:
            snapshot = google_ads_service.sync_customer_for_client(client_id=client_id, customer_id=raw_customer_id, days=days)
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
            message = str(exc)
            safe_message = message.replace(raw_customer_id, "***")[:300]
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
    attempted_accounts_count = len(attempts)
    sample_customer_ids = [item["customer_id_masked"] for item in attempts[:10]]

    today = datetime.utcnow().date()
    start = today - timedelta(days=int(days) - 1)
    payload = {
        "status": "ok" if failed_accounts_count == 0 else "partial",
        "mapped_accounts_count": mapped_accounts_count,
        "attempted_accounts_count": attempted_accounts_count,
        "succeeded_accounts_count": succeeded_accounts_count,
        "failed_accounts_count": failed_accounts_count,
        "inserted_rows_total": inserted_rows_total,
        "date_range": {"start": start.isoformat(), "end": today.isoformat()},
        "sample_customer_ids": sample_customer_ids,
        "errors_summary": errors_summary,
        "attempts": attempts,
        "client_id": requested_client_id,
        "days": int(days),
    }

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.sync_now",
        resource="integration:google_ads",
        details={
            "mapped_accounts_count": mapped_accounts_count,
            "attempted_accounts_count": attempted_accounts_count,
            "succeeded_accounts_count": succeeded_accounts_count,
            "failed_accounts_count": failed_accounts_count,
            "inserted_rows_total": inserted_rows_total,
            "client_id": requested_client_id,
            "days": int(days),
        },
    )

    return payload
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
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google Ads API unavailable") from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.sync",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
