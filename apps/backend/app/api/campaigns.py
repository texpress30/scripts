from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import enforce_action_scope, enforce_subaccount_module_access, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.dashboard import unified_dashboard_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/{client_id}/summary")
def campaigns_summary(
    client_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    business_period_grain: str = Query(default="day"),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="subaccount")
    enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="campaigns")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    metrics = unified_dashboard_service.get_client_dashboard(
        client_id=client_id,
        start_date=resolved_start,
        end_date=resolved_end,
        business_period_grain=business_period_grain,
    )
    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="campaigns.summary.view",
        resource=f"client:{client_id}",
        details={"start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat(), "business_period_grain": business_period_grain},
    )
    return metrics
