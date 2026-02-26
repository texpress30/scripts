from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.client import AttachGoogleAccountRequest, CreateClientRequest
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def list_clients(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, str | int | None]]]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")

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
def create_client(payload: CreateClientRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str | int | None]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

    created = client_registry_service.create_client(name=payload.name, owner_email=user.email)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.create",
        resource=f"client:{created['id']}",
        details={"name": payload.name},
    )
    return created


@router.get("/accounts/summary")
def platform_account_summary(user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict[str, str | int | None]]]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items = client_registry_service.platform_account_summary()
    return {"items": items}


@router.get("/accounts/google")
def list_google_accounts(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items = client_registry_service.list_platform_accounts(platform="google_ads")
    return {
        "items": items,
        "count": len(items),
        "last_import_at": client_registry_service.get_last_import_at(platform="google_ads"),
    }


@router.post("/{client_id}/attach-google-account")
def attach_google_account(client_id: int, payload: AttachGoogleAccountRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, str | int | None]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    updated = client_registry_service.assign_google_customer(client_id=client_id, customer_id=payload.customer_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Client not found")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.attach_google_account",
        resource=f"client:{client_id}",
        details={"customer_id": payload.customer_id},
    )
    return updated
