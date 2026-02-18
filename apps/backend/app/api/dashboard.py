from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
<<<<<<< codex/clarify-requirements-for-ai-app-development-pehcq8
from app.services.dashboard import unified_dashboard_service
=======
from app.services.google_ads import google_ads_service
>>>>>>> main
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{client_id}")
<<<<<<< codex/clarify-requirements-for-ai-app-development-pehcq8
def client_dashboard(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
=======
def client_dashboard(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, float | int | bool | str]:
>>>>>>> main
    try:
        require_permission(user.role, "clients:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

<<<<<<< codex/clarify-requirements-for-ai-app-development-pehcq8
    metrics = unified_dashboard_service.get_client_dashboard(client_id=client_id)
=======
    metrics = google_ads_service.get_dashboard_metrics(client_id=client_id)
>>>>>>> main
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.view",
        resource=f"client:{client_id}",
        details={"is_synced": metrics["is_synced"]},
    )
    return metrics
