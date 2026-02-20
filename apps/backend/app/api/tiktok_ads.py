from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service

router = APIRouter(prefix="/integrations/tiktok-ads", tags=["tiktok-ads"])


@router.get("/status")
def tiktok_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    try:
        enforce_action_scope(user=user, action="integrations:tiktok:status", scope="agency")
        rate_limiter_service.check(f"tiktok_status:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    status_payload = tiktok_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.status",
        resource="integration:tiktok_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload


@router.post("/{client_id}/sync")
def sync_tiktok_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, int | str]:
    try:
        enforce_action_scope(user=user, action="integrations:tiktok:sync", scope="subaccount")
        rate_limiter_service.check(f"tiktok_sync:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    try:
        snapshot = tiktok_ads_service.sync_client(client_id=client_id)
    except TikTokAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="TikTok Ads API unavailable") from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.sync.start",
        resource=f"client:{client_id}",
        details={"phase": "start"},
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="tiktok_ads.sync.accepted",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
