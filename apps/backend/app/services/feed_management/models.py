from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FeedSourceType(str, enum.Enum):
    shopify = "shopify"
    woocommerce = "woocommerce"
    magento = "magento"
    bigcommerce = "bigcommerce"
    csv = "csv"
    json = "json"
    xml = "xml"
    google_sheets = "google_sheets"


class FeedImportStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class FeedSourceConfig(BaseModel):
    """Flexible config for different platform types stored as JSONB."""
    store_url: str | None = None
    api_version: str | None = None
    sync_interval_minutes: int | None = None
    file_url: str | None = None
    delimiter: str | None = None
    sheet_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class FeedSourceCreate(BaseModel):
    subaccount_id: int
    source_type: FeedSourceType
    name: str
    config: FeedSourceConfig = Field(default_factory=FeedSourceConfig)
    credentials_secret_id: str | None = None
    catalog_type: str = "product"


class FeedSourceUpdate(BaseModel):
    name: str | None = None
    config: FeedSourceConfig | None = None
    credentials_secret_id: str | None = None
    is_active: bool | None = None


class FeedSourceResponse(BaseModel):
    id: str
    subaccount_id: int
    source_type: FeedSourceType
    name: str
    config: dict[str, Any]
    credentials_secret_id: str | None
    is_active: bool
    catalog_type: str = "product"
    created_at: datetime
    updated_at: datetime


class FeedImportCreate(BaseModel):
    feed_source_id: str


class FeedImportResponse(BaseModel):
    id: str
    feed_source_id: str
    status: FeedImportStatus
    total_products: int
    imported_products: int
    errors: list[dict[str, Any]]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class ProductListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int


class ProductStatsResponse(BaseModel):
    total: int
    by_category: dict[str, int]
    last_sync: datetime | None
