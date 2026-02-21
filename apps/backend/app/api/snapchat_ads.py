from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.snapchat_ads import SnapchatAdsIntegrationError, snapchat_ads_service

router = APIRouter(prefix="/integrations/snapchat-ads", tags=["snapchat-ads"])


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
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action="snapchat_ads.sync.fail",
            resource=f"client:{client_id}",
            details={"error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="snapchat_ads.sync.success",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
