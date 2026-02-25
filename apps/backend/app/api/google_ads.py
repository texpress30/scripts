from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service

router = APIRouter(prefix="/integrations/google-ads", tags=["google-ads"])


@router.get("/status")
def google_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    try:
        enforce_action_scope(user=user, action="integrations:status", scope="agency")
        rate_limiter_service.check(f"google_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = google_ads_service.integration_status()
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
        accounts = google_ads_service.list_accessible_customers()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.accounts.list",
        resource="integration:google_ads",
        details={"count": len(accounts)},
    )
    return {"items": accounts, "count": len(accounts)}


@router.post("/import-accounts")
def import_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    try:
        customer_ids = google_ads_service.list_accessible_customers()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    created: list[dict[str, str | int]] = []
    existing = client_registry_service.list_clients()
    existing_names = {str(item["name"]).strip().lower() for item in existing}

    for customer_id in customer_ids:
        synthetic_name = f"Google Account {customer_id}"
        if synthetic_name.lower() in existing_names:
            continue
        record = client_registry_service.create_client(name=synthetic_name, owner_email=user.email)
        created.append(record)
        existing_names.add(synthetic_name.lower())

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.import_accounts",
        resource="integration:google_ads",
        details={"imported": len(created), "accessible": len(customer_ids)},
    )

    return {
        "status": "ok",
        "accessible_customers": customer_ids,
        "imported_clients": created,
        "imported_count": len(created),
    }




@router.get("/diagnostics")
def google_ads_diagnostics(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    details = google_ads_service.production_diagnostics()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="google_ads.diagnostics",
        resource="integration:google_ads",
        details={"warnings": len(details.get("warnings", []))},
    )
    return details


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
