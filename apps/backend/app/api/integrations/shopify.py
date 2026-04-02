from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/shopify", tags=["shopify", "integrations"])


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed management is not enabled")


class TestConnectionRequest(BaseModel):
    shop_url: str = Field(min_length=1)
    access_token: str | None = None
    api_key: str | None = None
    api_secret_key: str | None = None


class TestConnectionResponse(BaseModel):
    success: bool
    shop_name: str = ""
    currency: str = ""
    products_count: int = 0
    message: str = ""


@router.post("/test-connection", response_model=TestConnectionResponse)
def test_shopify_connection(
    payload: TestConnectionRequest,
    user: AuthUser = Depends(get_current_user),
) -> TestConnectionResponse:
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="clients:create", scope="subaccount")

    from app.services.feed_management.connectors.shopify_connector import ShopifyConnector

    credentials: dict[str, str] = {}
    if payload.access_token:
        credentials["access_token"] = payload.access_token
    if payload.api_key:
        credentials["api_key"] = payload.api_key
    if payload.api_secret_key:
        credentials["api_secret_key"] = payload.api_secret_key

    connector = ShopifyConnector(
        config={"store_url": payload.shop_url},
        credentials=credentials,
    )

    result = asyncio.get_event_loop().run_until_complete(connector.test_connection())

    if not result.success:
        return TestConnectionResponse(success=False, message=result.message)

    try:
        products_count = asyncio.get_event_loop().run_until_complete(connector.get_product_count())
    except Exception:
        products_count = 0

    details = result.details or {}
    return TestConnectionResponse(
        success=True,
        shop_name=details.get("shop_name", ""),
        currency=details.get("currency", ""),
        products_count=products_count,
        message=result.message,
    )
