from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.pinterest_ads import PinterestAdsIntegrationError, pinterest_ads_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service

router = APIRouter(prefix="/integrations/pinterest-ads", tags=["pinterest-ads"])


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


@router.post("/{client_id}/sync")
def sync_pinterest_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, int | str]:
    try:
        enforce_action_scope(user=user, action="integrations:pinterest:sync", scope="subaccount")
        rate_limiter_service.check(f"pinterest_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

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
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="pinterest_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="pinterest_ads.sync.accepted",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
