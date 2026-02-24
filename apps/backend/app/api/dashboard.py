from fastapi import APIRouter, Depends

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.dashboard import unified_dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{client_id}")
def client_dashboard(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="subaccount")

    metrics = unified_dashboard_service.get_client_dashboard(client_id=client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.view",
        resource=f"client:{client_id}",
        details={"is_synced": metrics["is_synced"]},
    )
    return metrics
