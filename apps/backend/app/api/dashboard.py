from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.dashboard import unified_dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/agency/summary")
def agency_dashboard_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=6))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    metrics = unified_dashboard_service.get_agency_dashboard(start_date=resolved_start, end_date=resolved_end)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.agency.view",
        resource="agency:dashboard",
        details={"start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat()},
    )
    return metrics


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
