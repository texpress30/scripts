from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.api.dependencies import (
    enforce_action_scope,
    enforce_agency_navigation_access,
    enforce_subaccount_module_access,
    get_current_user,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.dashboard import unified_dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class TikTokAccountDailyRepairRequest(BaseModel):
    start_date: date
    end_date: date
    account_id: str | None = None
    dry_run: bool = True


class CurrencyDriftRepairRequest(BaseModel):
    client_id: int | None = None
    dry_run: bool = True



@router.get("/agency/summary")
def agency_dashboard_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_dashboard")

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
    enforce_agency_navigation_access(user=user, permission_key="agency_dashboard")

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


@router.post("/debug/clients/{client_id}/tiktok-account-daily-repair")
def client_tiktok_account_daily_repair_debug(
    client_id: int,
    payload: TikTokAccountDailyRepairRequest,
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_dashboard")

    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    try:
        result = unified_dashboard_service.repair_client_tiktok_account_daily(
            client_id=client_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            account_id=payload.account_id,
            dry_run=bool(payload.dry_run),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.debug.tiktok_account_daily_repair.run",
        resource=f"client:{client_id}:tiktok_ads",
        details={
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "account_id": payload.account_id,
            "dry_run": bool(payload.dry_run),
            "safe_repair_candidate_units": result.get("safe_repair_candidate_units"),
            "applied_units": result.get("applied_units"),
            "skipped_units": result.get("skipped_units"),
        },
    )
    return result

@router.post("/debug/currency-drift-repair")
def currency_drift_repair_debug(
    payload: CurrencyDriftRepairRequest,
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_dashboard")

    result = unified_dashboard_service.audit_and_repair_client_display_currency_drift(
        client_id=payload.client_id,
        dry_run=bool(payload.dry_run),
    )

    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    resource = f"client:{payload.client_id}" if payload.client_id is not None else "agency:clients"
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.debug.currency_drift_repair.run",
        resource=resource,
        details={
            "client_id": payload.client_id,
            "dry_run": bool(payload.dry_run),
            "total_clients_scanned": result.get("total_clients_scanned"),
            "clients_with_drift": result.get("clients_with_drift"),
            "clients_repaired": result.get("clients_repaired"),
            "configs_repaired": result.get("configs_repaired"),
            "clients_skipped": result.get("clients_skipped"),
        },
    )
    return result


@router.get("/debug/clients/{client_id}/dashboard-reconciliation")
def client_dashboard_reconciliation_debug(
    client_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_dashboard")

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
    enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="dashboard")

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


@router.get("/{client_id}/google-ads-table")
def client_google_ads_table(
    client_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
    response: Response = None,
) -> dict[str, object]:
    enforce_action_scope(user=user, action="dashboard:view", scope="subaccount")
    enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="dashboard")

    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=29))
    if resolved_start > resolved_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date must be <= end_date")

    try:
        payload = unified_dashboard_service.get_client_google_ads_account_performance(
            client_id=client_id,
            start_date=resolved_start,
            end_date=resolved_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if response is not None:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="dashboard.sub.google_ads_table.view",
        resource=f"client:{client_id}:google_ads",
        details={"start_date": resolved_start.isoformat(), "end_date": resolved_end.isoformat()},
    )
    return payload
