from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.schemas.client import CreateClientRequest
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.rbac import AuthorizationError, require_permission

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def list_clients(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, str | int]]]:
    try:
        require_permission(user.role, "clients:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    records = client_registry_service.list_clients()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.list",
        resource="client",
        details={"count": len(records)},
    )
    return {"items": records}


@router.post("")
def create_client(payload: CreateClientRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str | int]:
    try:
        require_permission(user.role, "clients:create")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    created = client_registry_service.create_client(name=payload.name, owner_email=user.email)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.create",
        resource=f"client:{created['id']}",
        details={"name": payload.name},
    )
    return created
