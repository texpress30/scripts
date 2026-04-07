"""Pydantic schemas for the Shopify Feed Integration OAuth flow."""

from __future__ import annotations

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