from datetime import date
from typing import Literal

from pydantic import BaseModel


class CreateClientRequest(BaseModel):
    name: str


class AttachGoogleAccountRequest(BaseModel):
    customer_id: str


class DetachGoogleAccountRequest(BaseModel):
    customer_id: str


class AttachPlatformAccountRequest(BaseModel):
    platform: Literal["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads", "reddit_ads"]
    account_id: str


class DetachPlatformAccountRequest(BaseModel):
    platform: Literal["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads", "reddit_ads"]
    account_id: str


class UpdateClientProfileRequest(BaseModel):
    name: str | None = None
    client_logo_url: str | None = None
    client_type: str | None = None
    account_manager: str | None = None
    currency: str | None = None
    platform: str | None = None
    account_id: str | None = None


class BusinessInputsImportRequest(BaseModel):
    period_grain: str | None = None
    source: str | None = None
    rows: list[dict[str, object]]


class BusinessInputsImportResponse(BaseModel):
    processed: int
    succeeded: int
    failed: int
    errors: list[dict[str, object]]
    rows: list[dict[str, object]] | None = None


class MediaBuyingConfigUpdateRequest(BaseModel):
    template_type: Literal["lead", "ecommerce", "programmatic"] | None = None
    display_currency: str | None = None
    custom_label_1: str | None = None
    custom_label_2: str | None = None
    custom_label_3: str | None = None
    custom_label_4: str | None = None
    custom_label_5: str | None = None
    custom_rate_label_1: str | None = None
    custom_rate_label_2: str | None = None
    custom_cost_label_1: str | None = None
    custom_cost_label_2: str | None = None
    enabled: bool | None = None


class MediaBuyingLeadDailyValueUpsertRequest(BaseModel):
    date: date
    leads: int
    phones: int
    custom_value_1_count: int
    custom_value_2_count: int
    custom_value_3_amount_ron: float
    custom_value_4_amount_ron: float
    custom_value_5_amount_ron: float
    sales_count: int
