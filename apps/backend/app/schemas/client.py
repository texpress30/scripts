from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


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


class SubaccountBusinessProfilePayload(BaseModel):
    general: dict[str, object] = Field(default_factory=dict)
    business: dict[str, object] = Field(default_factory=dict)
    address: dict[str, object] = Field(default_factory=dict)
    representative: dict[str, object] = Field(default_factory=dict)
    logo_url: str = ""
    logo_media_id: str | None = None


class SubaccountBusinessProfileResponse(BaseModel):
    client_id: int
    display_id: int
    client_name: str = ""
    general: dict[str, object]
    business: dict[str, object]
    address: dict[str, object]
    representative: dict[str, object]
    logo_url: str
    logo_media_id: str | None = None


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
    visible_columns: list[str] | None = None
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


class MediaTrackerWorksheetManualValueEntry(BaseModel):
    week_start: date
    field_key: str
    value: float | None = None


class MediaTrackerWorksheetManualValuesUpsertRequest(BaseModel):
    granularity: Literal["month", "quarter", "year"]
    anchor_date: date
    entries: list[MediaTrackerWorksheetManualValueEntry]


class MediaTrackerWorksheetEurRonRateUpsertRequest(BaseModel):
    granularity: Literal["month", "quarter", "year"]
    anchor_date: date
    value: float | None = None


class ClientDataDerivedField(BaseModel):
    key: str
    label: str
    value_kind: Literal["count", "amount"]


class ClientDataSourceItem(BaseModel):
    key: str
    label: str


class ClientDataCustomFieldItem(BaseModel):
    id: int
    field_key: str
    label: str
    value_kind: Literal["count", "amount"]
    sort_order: int
    is_active: bool


class ClientDataConfigResponse(BaseModel):
    client_id: int
    sources: list[ClientDataSourceItem]
    custom_fields: list[ClientDataCustomFieldItem]
    derived_fields: list[ClientDataDerivedField]


class ClientDataRowCustomValue(BaseModel):
    custom_field_id: int
    field_key: str
    label: str
    value_kind: Literal["count", "amount"]
    sort_order: int
    numeric_value: str


class ClientDataTableRow(BaseModel):
    daily_input_id: int
    metric_date: str
    source: str
    source_label: str
    leads: int
    phones: int
    custom_value_1_count: int
    custom_value_2_count: int
    custom_value_3_amount: str
    custom_value_5_amount: str
    notes: str | None = None
    sales_count: int
    revenue_amount: str
    cogs_amount: str
    custom_value_4_amount: str
    gross_profit_amount: str
    custom_values: list[ClientDataRowCustomValue]


class ClientDataTableResponse(BaseModel):
    client_id: int
    date_from: str
    date_to: str
    count: int
    rows: list[ClientDataTableRow]


class ClientDataDailyInputUpsertRequest(BaseModel):
    metric_date: date
    source: str
    leads: int | None = None
    phones: int | None = None
    custom_value_1_count: int | None = None
    custom_value_2_count: int | None = None
    custom_value_3_amount: float | int | str | None = None
    custom_value_5_amount: float | int | str | None = None
    notes: str | None = None


class ClientDataDailyInputWriteResponse(BaseModel):
    id: int
    client_id: int
    metric_date: str
    source: str
    leads: int
    phones: int
    custom_value_1_count: int
    custom_value_2_count: int
    custom_value_3_amount: str
    custom_value_5_amount: str
    notes: str | None = None


class ClientDataSaleEntryCreateRequest(BaseModel):
    daily_input_id: int
    sale_price_amount: float | int | str
    actual_price_amount: float | int | str
    brand: str | None = None
    model: str | None = None
    notes: str | None = None
    sort_order: int | None = None


class ClientDataSaleEntryUpdateRequest(BaseModel):
    sale_price_amount: float | int | str | None = None
    actual_price_amount: float | int | str | None = None
    brand: str | None = None
    model: str | None = None
    notes: str | None = None
    sort_order: int | None = None


class ClientDataSaleEntryWriteResponse(BaseModel):
    id: int
    daily_input_id: int
    brand: str | None = None
    model: str | None = None
    sale_price_amount: str
    actual_price_amount: str
    notes: str | None = None
    sort_order: int
    gross_profit_amount: str
