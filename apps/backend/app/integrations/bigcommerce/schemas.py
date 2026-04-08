"""Pydantic schemas for the BigCommerce Feed Integration OAuth + CRUD flows."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BigCommerceCallbackResponse(BaseModel):
    """Minimal response returned by the BigCommerce ``auth_callback`` endpoint.

    The response is rendered as JSON when the app is called directly
    (e.g. by an API client), and used to drive the iFrame redirect HTML
    when the callback is loaded inside the BigCommerce control panel.
    """

    success: bool
    store_hash: str
    scope: str = ""
    account_uuid: str | None = None
    message: str | None = None


class BigCommerceStatusResponse(BaseModel):
    oauth_configured: bool
    connected_stores: list[str]
    token_count: int


class BigCommerceUninstallResponse(BaseModel):
    status: str = "ok"
    store_hash: str = ""
    sources_disconnected: int = 0


class BigCommerceRemoveUserResponse(BaseModel):
    status: str = "ok"
    store_hash: str = ""
    user_email: str = ""


class BigCommerceLoadResponse(BaseModel):
    status: str = "ok"
    store_hash: str
    user_email: str = ""
    owner_email: str = ""
    redirect_url: str = Field(
        default="",
        description="Optional frontend URL the iFrame should forward to",
    )


# ---------------------------------------------------------------------------
# CRUD / claim / test-connection (Task 2)
# ---------------------------------------------------------------------------


class BigCommerceClaimRequest(BaseModel):
    """Body for ``POST /integrations/bigcommerce/sources/claim``.

    The merchant has already installed the BigCommerce app (which stored an
    encrypted access token keyed by ``store_hash``); this payload binds it
    to a subaccount + supplies the cosmetic source metadata.
    """

    store_hash: str = Field(
        min_length=1,
        max_length=64,
        description="BigCommerce store hash returned in the install context",
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


class BigCommerceSourceUpdateRequest(BaseModel):
    """Body for ``PUT /integrations/bigcommerce/sources/{source_id}``.

    Every field is optional — only supplied keys are persisted. The
    ``store_hash`` itself is immutable post-claim (changing it would mean
    pointing the same source row at a different merchant store, which is
    never what the merchant wants).
    """

    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    catalog_type: str | None = Field(default=None, min_length=1, max_length=50)
    catalog_variant: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class BigCommerceSourceResponse(BaseModel):
    """Projection of a ``feed_sources`` row onto a BigCommerce-specific shape."""

    source_id: str
    subaccount_id: int
    source_name: str
    store_hash: str
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


class BigCommerceTestConnectionRequest(BaseModel):
    """Body for ``POST /integrations/bigcommerce/test-connection``.

    The pre-claim probe accepts only the ``store_hash`` — credentials are
    looked up from ``integration_secrets_store``. There is no "credentials
    in the body" variant for BigCommerce because the merchant flow is
    OAuth-only (no manual token entry path).
    """

    store_hash: str = Field(min_length=1, max_length=64)


class BigCommerceTestConnectionResponse(BaseModel):
    """Normalised probe result returned by both test-connection endpoints."""

    success: bool
    store_name: str | None = None
    domain: str | None = None
    secure_url: str | None = None
    currency: str | None = None
    error: str | None = None


class BigCommerceAvailableStore(BaseModel):
    """An installed but not-yet-claimed BigCommerce store.

    Returned by ``GET /integrations/bigcommerce/stores/available``. The
    ``installed_at`` timestamp is the ``updated_at`` of the
    ``integration_secrets`` row that holds the encrypted access token.
    """

    store_hash: str
    installed_at: datetime | None = None
    user_email: str | None = None
    scope: str | None = None


class BigCommerceAvailableStoresResponse(BaseModel):
    stores: list[BigCommerceAvailableStore]
    total: int
