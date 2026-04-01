from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, get_current_user
from app.services.rbac import normalize_role
from app.schemas.company import CompanySettingsResponse, UpdateCompanySettingsRequest
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.company_settings import company_settings_service

router = APIRouter(prefix="/company", tags=["company"])


def _resolve_logo_storage_client_id(*, owner_email: str) -> int | None:
    records = client_registry_service.list_clients()
    normalized_owner = str(owner_email or "").strip().lower()
    for item in records:
        if str(item.get("owner_email") or "").strip().lower() == normalized_owner:
            candidate = int(item.get("id") or 0)
            if candidate > 0:
                return candidate
    for item in records:
        candidate = int(item.get("id") or 0)
        if candidate > 0:
            return candidate
    # No clients exist yet — auto-create an internal agency client for storage
    try:
        created = client_registry_service.create_client(
            name="Agency Storage",
            owner_email=normalized_owner or "admin@example.com",
        )
        return int(created.get("id") or 0) or None
    except Exception:  # noqa: BLE001
        return None


@router.get("/settings", response_model=CompanySettingsResponse)
def get_company_settings(user: AuthUser = Depends(get_current_user)) -> CompanySettingsResponse:
    role = normalize_role(user.role)
    if role.startswith("subaccount_"):
        enforce_action_scope(user=user, action="clients:list", scope="subaccount")
    else:
        enforce_action_scope(user=user, action="clients:list", scope="agency")
        enforce_agency_navigation_access(user=user, permission_key="settings_company")
    logo_storage_client_id = _resolve_logo_storage_client_id(owner_email=user.email.strip().lower())
    payload = company_settings_service.get_settings(
        owner_email=user.email.strip().lower(),
        logo_storage_client_id=logo_storage_client_id,
    )
    return CompanySettingsResponse(**payload)


@router.patch("/settings", response_model=CompanySettingsResponse)
def update_company_settings(payload: UpdateCompanySettingsRequest, user: AuthUser = Depends(get_current_user)) -> CompanySettingsResponse:
    enforce_action_scope(user=user, action="clients:create", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_company")

    if payload.company_name.strip() == "":
        raise HTTPException(status_code=400, detail="Numele companiei este obligatoriu")
    if payload.company_email.strip() == "":
        raise HTTPException(status_code=400, detail="Emailul companiei este obligatoriu")
    if payload.address_line1.strip() == "":
        raise HTTPException(status_code=400, detail="Adresa este obligatorie")
    if payload.city.strip() == "":
        raise HTTPException(status_code=400, detail="Orașul este obligatoriu")
    if payload.postal_code.strip() == "":
        raise HTTPException(status_code=400, detail="Codul poștal este obligatoriu")
    if payload.region.strip() == "":
        raise HTTPException(status_code=400, detail="Regiunea este obligatorie")
    if payload.country.strip() == "":
        raise HTTPException(status_code=400, detail="Țara este obligatorie")
    if payload.timezone.strip() == "":
        raise HTTPException(status_code=400, detail="Fusul orar este obligatoriu")

    logo_storage_client_id = _resolve_logo_storage_client_id(owner_email=user.email.strip().lower())
    updated = company_settings_service.update_settings(
        owner_email=user.email.strip().lower(),
        payload={
            "company_name": payload.company_name.strip(),
            "company_email": payload.company_email.strip(),
            "company_phone_prefix": payload.company_phone_prefix.strip() or "+40",
            "company_phone": payload.company_phone.strip(),
            "company_website": payload.company_website.strip(),
            "business_category": payload.business_category.strip(),
            "business_niche": payload.business_niche.strip(),
            "platform_primary_use": payload.platform_primary_use.strip(),
            "address_line1": payload.address_line1.strip(),
            "city": payload.city.strip(),
            "postal_code": payload.postal_code.strip(),
            "region": payload.region.strip(),
            "country": payload.country.strip(),
            "timezone": payload.timezone.strip(),
            "logo_url": payload.logo_url.strip(),
            "logo_media_id": str(payload.logo_media_id or "").strip() or None,
        },
        logo_storage_client_id=logo_storage_client_id,
    )
    return CompanySettingsResponse(**updated)
