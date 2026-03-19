from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, get_current_user
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service

router = APIRouter(prefix="/agency/clients", tags=["agency-clients", "google-ads"])


class MapGoogleAdsCustomerRequest(BaseModel):
    customer_id: str


def _mask_customer_id(customer_id: str) -> str:
    normalized = customer_id.strip()
    if len(normalized) < 4:
        return "****"
    return f"***{normalized[-4:]}"


@router.post("/{client_id}/integrations/google-ads/map")
def map_google_ads_customer(
    client_id: int,
    payload: MapGoogleAdsCustomerRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")

    normalized_customer_id = google_ads_service._normalize_customer_id(payload.customer_id)
    if not google_ads_service._is_valid_customer_id(normalized_customer_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="customer_id must be 10 digits")

    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    matched = next((item for item in accounts if str(item.get("id", "")) == normalized_customer_id), None)
    if matched is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="customer_id is not in accessible Google Ads accounts")

    if bool(matched.get("is_manager", False)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Manager (MCC) account is not allowed. Map a non-manager customer ID")

    account_name = str(matched.get("name") or normalized_customer_id)
    client_registry_service.upsert_platform_accounts(
        platform="google_ads",
        accounts=[{"id": normalized_customer_id, "name": account_name}],
    )

    updated = client_registry_service.attach_platform_account_to_client(
        platform="google_ads",
        client_id=client_id,
        account_id=normalized_customer_id,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    mapping = client_registry_service.get_google_mapping_details_for_client(client_id=client_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="agency_clients.google_ads.map",
        resource=f"client:{client_id}",
        details={"customer_id_masked": _mask_customer_id(normalized_customer_id)},
    )

    return {
        "status": "ok",
        "client_id": client_id,
        "mapped": True,
        "customer_id": normalized_customer_id,
        "customer_id_masked": _mask_customer_id(normalized_customer_id),
        "updated_at": mapping.get("updated_at") if mapping else None,
    }


@router.get("/{client_id}/integrations/google-ads")
def get_google_ads_mapping(
    client_id: int,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="agency_accounts")

    mapping = client_registry_service.get_google_mapping_details_for_client(client_id=client_id)
    if mapping is None:
        return {
            "mapped": False,
            "customer_id": None,
            "updated_at": None,
        }

    customer_id = str(mapping.get("customer_id") or "")
    return {
        "mapped": True,
        "customer_id": customer_id,
        "customer_id_masked": _mask_customer_id(customer_id),
        "updated_at": mapping.get("updated_at"),
    }
