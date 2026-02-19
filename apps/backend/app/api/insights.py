from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.insights import insights_service
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/weekly/{client_id}/generate")
def generate_weekly(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        require_permission(user.role, "clients:create")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    item = insights_service.generate_weekly_insight(client_id)
    audit_log_service.log(
        actor_email="system_bot",
        actor_role="system",
        action="ai.weekly_insight.generate",
        resource=f"client:{client_id}",
        details={"created_at": item["created_at"]},
    )
    return item


@router.get("/weekly/{client_id}")
def get_latest_weekly(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        require_permission(user.role, "clients:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    item = insights_service.get_latest(client_id)
    if item is None:
        return {"client_id": client_id, "summary": "Nu am destule date"}
    return item
