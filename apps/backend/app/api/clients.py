from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.client import (
    AttachGoogleAccountRequest,
    CreateClientRequest,
    DetachGoogleAccountRequest,
    UpdateClientProfileRequest,
)
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
    updated = client_registry_service.attach_platform_account_to_client(
        platform="google_ads",
        client_id=client_id,
        account_id=payload.customer_id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Client or Google account not found")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.attach_google_account",
        resource=f"client:{client_id}",
        details={"customer_id": payload.customer_id},
    )
    return updated


@router.delete("/{client_id}/detach-google-account")
def detach_google_account(client_id: int, payload: DetachGoogleAccountRequest, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    deleted = client_registry_service.detach_platform_account_from_client(
        platform="google_ads",
        client_id=client_id,
        account_id=payload.customer_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Google account mapping not found")

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="clients.detach_google_account",
        resource=f"client:{client_id}",
        details={"customer_id": payload.customer_id},
    )
    return {"status": "ok", "client_id": client_id, "customer_id": payload.customer_id}


@router.get("/display/{display_id}")
def get_client_details(display_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    payload = client_registry_service.get_client_details_by_display_id(display_id=display_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return payload


@router.patch("/display/{display_id}")
def update_client_profile(
    display_id: int,
    payload: UpdateClientProfileRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    updated = client_registry_service.update_client_profile_by_display_id(
        display_id=display_id,
        client_type=payload.client_type,
        account_manager=payload.account_manager,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@router.get("/{client_id}/accounts")
def list_client_google_accounts(client_id: int, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items = client_registry_service.list_client_platform_accounts(platform="google_ads", client_id=client_id)
    return {"items": items, "count": len(items)}
