from pydantic import BaseModel


class CompanySettingsResponse(BaseModel):
    company_name: str
    company_email: str
    company_phone_prefix: str
    company_phone: str
    company_website: str
    business_category: str
    business_niche: str
    platform_primary_use: str
    address_line1: str
    city: str
    postal_code: str
    region: str
    country: str
    timezone: str
    logo_url: str
    logo_media_id: str | None = None
    logo_storage_client_id: int | None = None


class UpdateCompanySettingsRequest(BaseModel):
    company_name: str
    company_email: str
    company_phone_prefix: str = "+40"
    company_phone: str = ""
    company_website: str = ""
    business_category: str = ""
    business_niche: str = ""
    platform_primary_use: str = ""
    address_line1: str
    city: str
    postal_code: str
    region: str
    country: str
    timezone: str
    logo_url: str = ""
    logo_media_id: str | None = None
