from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.services.ai_assistant import ai_assistant_service
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/recommendations/{client_id}")
def campaign_recommendation(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        require_permission(user.role, "clients:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    result = ai_assistant_service.generate_recommendation(client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="ai.recommendation",
        resource=f"client:{client_id}",
        details={"source": result.get("source")},
    )
    return result
