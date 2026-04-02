from __future__ import annotations

import enum
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


class SyncSchedule(str, enum.Enum):
    manual = "manual"
    hourly = "hourly"
    every_6h = "every_6h"
    every_12h = "every_12h"
    daily = "daily"
    weekly = "weekly"


SCHEDULE_INTERVALS: dict[SyncSchedule, timedelta] = {
    SyncSchedule.hourly: timedelta(hours=1),
    SyncSchedule.every_6h: timedelta(hours=6),
    SyncSchedule.every_12h: timedelta(hours=12),
    SyncSchedule.daily: timedelta(days=1),
    SyncSchedule.weekly: timedelta(weeks=1),
}


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
    model_config = {"extra": "allow"}

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
    sync_schedule: str = "manual"
    next_scheduled_sync: datetime | None = None
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
