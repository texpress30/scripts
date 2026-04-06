from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChannelType(str, enum.Enum):
    # Google
    google_shopping = "google_shopping"
    google_vehicle_ads_v3 = "google_vehicle_ads_v3"
    google_vehicle_listings = "google_vehicle_listings"
    google_local_inventory = "google_local_inventory"
    google_product_reviews = "google_product_reviews"
    google_regional_inventory = "google_regional_inventory"
    google_manufacturers = "google_manufacturers"
    google_hotel_ads = "google_hotel_ads"
    google_real_estate = "google_real_estate"
    google_jobs = "google_jobs"
    google_things_to_do = "google_things_to_do"
    # Meta
    facebook_product_ads = "facebook_product_ads"
    facebook_catalog_vehicles = "facebook_catalog_vehicles"
    facebook_catalog_vehicle_offer = "facebook_catalog_vehicle_offer"
    facebook_country = "facebook_country"
    facebook_language = "facebook_language"
    facebook_marketplace = "facebook_marketplace"
    facebook_automotive = "facebook_automotive"  # legacy — maps to facebook_catalog_vehicles
    facebook_hotel = "facebook_hotel"
    facebook_streaming_ads = "facebook_streaming_ads"
    facebook_destination_ads = "facebook_destination_ads"
    facebook_professional_services = "facebook_professional_services"
    meta_catalog = "meta_catalog"
    # TikTok
    tiktok_automotive_inventory = "tiktok_automotive_inventory"
    tiktok = "tiktok"
    tiktok_catalog = "tiktok_catalog"
    tiktok_destination = "tiktok_destination"
    # Bing
    bing = "bing"
    # Social & Ads
    pinterest = "pinterest"
    snapchat = "snapchat"
    linkedin = "linkedin"
    twitter = "twitter"
    reddit_catalog = "reddit_catalog"
    criteo = "criteo"
    trade_desk = "trade_desk"
    perplexity = "perplexity"
    gpt_shopping = "gpt_shopping"
    # Marketplaces RO
    compari_ro = "compari_ro"
    okazii_ro = "okazii_ro"
    price_ro = "price_ro"
    shopmania_ro = "shopmania_ro"
    glami_ro = "glami_ro"
    # Affiliate
    daisycon = "daisycon"
    klarna = "klarna"
    awin = "awin"
    shareasale = "shareasale"
    # Custom
    custom = "custom"


class ChannelStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    error = "error"


class FeedFormat(str, enum.Enum):
    xml = "xml"
    csv = "csv"
    tsv = "tsv"
    json = "json"


class OverrideMappingType(str, enum.Enum):
    direct = "direct"
    static = "static"
    template = "template"


# ---------------------------------------------------------------------------
# Feed Channel request models
# ---------------------------------------------------------------------------

class FeedChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    channel_type: ChannelType
    feed_format: FeedFormat = FeedFormat.xml
    settings: dict[str, Any] = Field(default_factory=dict)


class FeedChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    channel_type: ChannelType | None = None
    status: ChannelStatus | None = None
    feed_format: FeedFormat | None = None
    settings: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Feed Channel response models
# ---------------------------------------------------------------------------

class FeedChannelResponse(BaseModel):
    id: str
    feed_source_id: str
    name: str
    channel_type: ChannelType
    status: ChannelStatus
    feed_format: FeedFormat
    public_token: str
    feed_url: str | None = None
    s3_key: str | None = None
    included_products: int
    excluded_products: int
    last_generated_at: datetime | None = None
    error_message: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Channel Field Override request models
# ---------------------------------------------------------------------------

class ChannelFieldOverrideCreate(BaseModel):
    target_field: str = Field(min_length=1, max_length=100)
    source_field: str | None = None
    mapping_type: OverrideMappingType = OverrideMappingType.direct
    static_value: str | None = None
    template_value: str | None = None


class ChannelFieldOverrideUpdate(BaseModel):
    source_field: str | None = None
    mapping_type: OverrideMappingType | None = None
    static_value: str | None = None
    template_value: str | None = None


# ---------------------------------------------------------------------------
# Channel Field Override response models
# ---------------------------------------------------------------------------

class ChannelFieldOverrideResponse(BaseModel):
    id: str
    channel_id: str
    target_field: str
    source_field: str | None = None
    mapping_type: OverrideMappingType
    static_value: str | None = None
    template_value: str | None = None
    created_at: datetime
    updated_at: datetime
