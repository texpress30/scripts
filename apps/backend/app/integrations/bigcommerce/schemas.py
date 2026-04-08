"""Pydantic schemas for the BigCommerce Feed Integration OAuth flow."""

from __future__ import annotations

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
