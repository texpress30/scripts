from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_events(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, object]]]:
    try:
        require_permission(user.role, "audit:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return {"items": audit_log_service.list_events()}
