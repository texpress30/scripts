from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/integrations/meta-ads", tags=["meta-ads"])


@router.get("/status")
def meta_ads_status(user: AuthUser = Depends(get_current_user)) -> dict[str, str]:
    try:
        require_permission(user.role, "clients:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    status_payload = meta_ads_service.integration_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.status",
        resource="integration:meta_ads",
        details={"status": status_payload["status"]},
    )
    return status_payload


@router.post("/{client_id}/sync")
def sync_meta_ads(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | str]:
    try:
        require_permission(user.role, "clients:create")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        snapshot = meta_ads_service.sync_client(client_id=client_id)
    except MetaAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="meta_ads.sync",
        resource=f"client:{client_id}",
        details=snapshot,
    )
    return snapshot
