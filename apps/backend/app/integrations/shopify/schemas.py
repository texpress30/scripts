"""Pydantic schemas for the Shopify Feed Integration OAuth + claim flow."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ShopifyConnectRequest(BaseModel):
    shop: str = Field(min_length=1, description="Shopify shop domain (*.myshopify.com)")
    client_id: str | None = Field(default=None, description="Optional platform client id for callback association")


class ShopifyConnectResponse(BaseModel):
    authorize_url: str
    state: str


class ShopifyOAuthExchangeRequest(BaseModel):
    code: str = Field(min_length=1)
    shop: str = Field(min_length=1)
    state: str = Field(min_length=1)
    client_id: str | None = None


class ShopifyOAuthExchangeResponse(BaseModel):
    success: bool
    shop: str
    scope: str
    message: str | None = None


class ShopifyStatusResponse(BaseModel):
    oauth_configured: bool
    connected_shops: list[str]
    token_count: int


# ---------------------------------------------------------------------------
# Deferred-creation + claim flow (mirrors BigCommerce)
# ---------------------------------------------------------------------------


class ShopifyAvailableStore(BaseModel):
    """An installed but not-yet-claimed Shopify shop.

    Returned by ``GET /integrations/shopify/stores/available``. The
    ``installed_at`` timestamp is the ``updated_at`` of the
    ``integration_secrets`` row that holds the encrypted access token.
    """

    shop_domain: str
    installed_at: datetime | None = None
    scope: str | None = None


class ShopifyAvailableStoresResponse(BaseModel):
    stores: list[ShopifyAvailableStore]
    total: int


class ShopifyClaimRequest(BaseModel):
    """Body for ``POST /integrations/shopify/sources/claim``.

    The merchant has already installed VOXEL from the Shopify App Store
    (which stored an encrypted access token keyed by ``shop_domain``);
    this payload binds it to a subaccount + supplies the cosmetic source
    metadata.
    """

    shop_domain: str = Field(
        min_length=1,
        max_length=255,
        description="Shopify shop domain (*.myshopify.com)",
    )
    source_name: str = Field(
        min_length=1,
        max_length=255,
        description="Human-friendly name shown in the feed sources list",
    )
    catalog_type: str = Field(default="product", min_length=1, max_length=50)
    catalog_variant: str = Field(
        default="physical_products", min_length=1, max_length=50
    )


class ShopifySourceResponse(BaseModel):
    """Projection of a ``feed_sources`` row onto a Shopify-specific shape."""

    source_id: str
    subaccount_id: int
    source_name: str
    shop_domain: str
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    connection_status: str = "pending"
    has_token: bool = False
    token_scopes: str | None = None
    last_connection_check: datetime | None = None
    last_error: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ShopifyPreClaimTestRequest(BaseModel):
    """Body for ``POST /integrations/shopify/test-connection/by-shop``.

    Pre-claim probe by ``shop_domain`` — credentials are looked up from
    ``integration_secrets_store`` (the merchant has already completed
    OAuth via the App Store install). Used by the wizard "test before
    claim" button, mirroring the BigCommerce pre-claim endpoint.

    A separate endpoint path (``/test-connection/by-shop``) is used so
    the legacy ``POST /test-connection`` — which accepts raw
    ``access_token`` + ``shop_url`` for manual credential entry — stays
    untouched for backward compatibility.
    """

    shop_domain: str = Field(min_length=1, max_length=255)


class ShopifyPreClaimTestResponse(BaseModel):
    """Normalised pre-claim probe result.

    Populated by calling Shopify's ``GET /admin/api/{version}/shop.json``
    with the encrypted-at-rest access token. ``success=False`` responses
    always carry a human-readable ``error`` message.
    """

    success: bool
    store_name: str | None = None
    domain: str | None = None
    currency: str | None = None
    error: str | None = None