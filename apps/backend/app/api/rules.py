from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, enforce_subaccount_module_access, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.notifications import notification_service
from app.services.rate_limiter import RateLimitExceeded, rate_limiter_service
from app.services.rules_engine import rules_engine_service

router = APIRouter(prefix="/rules", tags=["rules"])


class CreateRuleRequest(BaseModel):
    name: str
    rule_type: str
    threshold: float
    action_value: float
    status: str = "active"


@router.get("/{client_id}")
def list_rules(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="rules:list", scope="subaccount")
        enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="rules")
        rate_limiter_service.check(f"rules_list:{user.email}", limit=60, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    items = rules_engine_service.list_rules(client_id)
    return {"client_id": client_id, "items": items}


@router.post("/{client_id}")
def create_rule(client_id: int, payload: CreateRuleRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="rules:create", scope="subaccount")
        enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="rules")
        rate_limiter_service.check(f"rules_write:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    if payload.rule_type not in {"stop_loss", "auto_scale"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported rule_type")
    if payload.status not in {"active", "paused"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status")

    created = rules_engine_service.create_rule(
        client_id=client_id,
        name=payload.name,
        rule_type=payload.rule_type,
        threshold=payload.threshold,
        action_value=payload.action_value,
        status=payload.status,
    )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="rules.create",
        resource=f"client:{client_id}",
        details=created,
    )
    return created


@router.post("/{client_id}/evaluate")
def evaluate_rules(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    try:
        enforce_action_scope(user=user, action="rules:evaluate", scope="subaccount")
        enforce_subaccount_module_access(user=user, subaccount_id=client_id, module_key="rules")
        rate_limiter_service.check(f"rules_eval:{user.email}", limit=30, window_seconds=60)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    actions = rules_engine_service.evaluate_client_rules(client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="rules.evaluate",
        resource=f"client:{client_id}",
        details={"triggered_count": len(actions)},
    )

    notifications = []
    for action in actions:
        notifications.append(
            notification_service.send_email_mock(
                to_email=user.email,
                subject=f"Rule triggered for client {client_id}",
                message=f"{action['rule_name']} -> {action['action']}",
            )
        )

    return {
        "client_id": client_id,
        "triggered_count": len(actions),
        "actions": actions,
        "notifications": notifications,
    }
