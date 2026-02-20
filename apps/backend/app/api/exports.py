from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.bigquery_export import bigquery_export_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("/bigquery/{client_id}")
def run_bigquery_export(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="exports:run", scope="subaccount")
        rate_limiter_service.check(f"export:{user.email}", limit=10, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    run = bigquery_export_service.run_export_for_client(client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="export.bigquery.run",
        resource=f"client:{client_id}",
        details={"status": run["status"]},
    )
    return run


@router.get("/bigquery/runs")
def list_bigquery_runs(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="exports:list", scope="agency")
    return {"items": bigquery_export_service.list_runs()}
