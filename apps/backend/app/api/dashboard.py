from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

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
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=6))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    metrics = unified_dashboard_service.get_agency_dashboard(start_date=resolved_start, end_date=resolved_end)
    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.agency.view",
        resource="agency:dashboard",
        details={"start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat()},
    )
    return metrics






@router.get("/debug/clients/{client_id}/platform-sync-audit")
def client_platform_sync_audit_debug(
    client_id: int,
    platform: str = Query(..., description="meta_ads or tiktok_ads"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    account_id: str | None = Query(default=None),
    include_daily_breakdown: bool = Query(default=False),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    try:
        payload = unified_dashboard_service.get_client_platform_sync_audit(
            client_id=client_id,
            platform=platform,
            start_date=resolved_start,
            end_date=resolved_end,
            account_id=account_id,
            include_daily_breakdown=include_daily_breakdown,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.debug.platform_sync_audit.view",
        resource=f"client:{client_id}:{platform}",
        details={
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "account_id": account_id,
            "include_daily_breakdown": include_daily_breakdown,
        },
    )
    return payload
@router.get("/debug/clients/{client_id}/dashboard-reconciliation")
def client_dashboard_reconciliation_debug(
    client_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    payload = unified_dashboard_service.get_client_dashboard_reconciliation(
        client_id=client_id,
        start_date=resolved_start,
        end_date=resolved_end,
    )

    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.debug.reconciliation.view",
        resource=f"client:{client_id}",
        details={"start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat()},
    )
    return payload


@router.get("/{client_id}")
def client_dashboard(
    client_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    business_period_grain: str = Query(default="day"),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="subaccount")

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
        action="dashboard.view",
        resource=f"client:{client_id}",
        details={"is_synced": metrics["is_synced"], "start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat(), "business_period_grain": business_period_grain},
    )
    return metrics
