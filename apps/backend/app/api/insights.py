from fastapi import APIRouter, Depends

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.insights import insights_service

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/weekly/{client_id}/generate")
def generate_weekly(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="insights:generate", scope="subaccount")

    item = insights_service.generate_weekly_insight(client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="ai.weekly_insight.generate",
        resource=f"client:{client_id}",
        details={"created_at": item["created_at"]},
    )
    return item


@router.get("/weekly/{client_id}")
def get_latest_weekly(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="insights:get", scope="subaccount")

    item = insights_service.get_latest(client_id)
    if item is None:
        return {"client_id": client_id, "summary": "Nu am destule date"}
    return item
