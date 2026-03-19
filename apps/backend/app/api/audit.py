from fastapi import APIRouter, Depends

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_events(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, object]]]:
    enforce_action_scope(user=user, action="audit:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_audit")
    return {"items": audit_log_service.list_events()}
