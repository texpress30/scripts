from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import enforce_action_scope, get_current_user
from app.schemas.company import CompanySettingsResponse, UpdateCompanySettingsRequest
from app.services.auth import AuthUser
from app.services.company_settings import company_settings_service

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/settings", response_model=CompanySettingsResponse)
def get_company_settings(user: AuthUser = Depends(get_current_user)) -> CompanySettingsResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    payload = company_settings_service.get_settings(owner_email=user.email.strip().lower())
    return CompanySettingsResponse(**payload)


@router.patch("/settings", response_model=CompanySettingsResponse)
def update_company_settings(payload: UpdateCompanySettingsRequest, user: AuthUser = Depends(get_current_user)) -> CompanySettingsResponse:
    enforce_action_scope(user=user, action="clients:create", scope="agency")

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
        },
    )
    return CompanySettingsResponse(**updated)
