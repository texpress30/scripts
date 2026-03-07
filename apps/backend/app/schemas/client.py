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
