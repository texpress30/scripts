from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.integrations.shopify import service as shopify_oauth_service
from app.integrations.shopify.schemas import (
    ShopifyConnectResponse,
    ShopifyOAuthExchangeRequest,
    ShopifyOAuthExchangeResponse,
    ShopifyStatusResponse,
)
from app.integrations.shopify.service import ShopifyIntegrationError
from app.services.audit import audit_log_service
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


# ---------------------------------------------------------------------------
# OAuth flow (VOXEL Public App): connect → exchange → status
# ---------------------------------------------------------------------------


def _raise_if_oauth_unconfigured() -> None:
    from app.integrations.shopify import config as shopify_config

    if not shopify_config.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify OAuth is not configured. Set SHOPIFY_APP_CLIENT_ID and SHOPIFY_APP_CLIENT_SECRET.",
        )


def _shopify_error_to_http(exc: ShopifyIntegrationError) -> HTTPException:
    code = exc.http_status or status.HTTP_400_BAD_REQUEST
    if code not in {400, 403, 502}:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/connect", response_model=ShopifyConnectResponse)
def shopify_oauth_connect(
    shop: str = Query(..., min_length=1, description="Shopify shop domain (*.myshopify.com)"),
    client_id: str | None = Query(default=None, description="Optional platform client id"),
    user: AuthUser = Depends(get_current_user),
) -> ShopifyConnectResponse:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    _raise_if_oauth_unconfigured()

    try:
        payload = shopify_oauth_service.generate_connect_url(shop=shop, client_id=client_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShopifyIntegrationError as exc:
        raise _shopify_error_to_http(exc) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopify.connect.start",
        resource="integration:shopify",
        details={"shop": shop, "client_id": client_id, "state": payload.get("state")},
    )
    return ShopifyConnectResponse(authorize_url=payload["authorize_url"], state=payload["state"])


@router.post("/oauth/exchange", response_model=ShopifyOAuthExchangeResponse)
def shopify_oauth_exchange(
    payload: ShopifyOAuthExchangeRequest,
    user: AuthUser = Depends(get_current_user),
) -> ShopifyOAuthExchangeResponse:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    _raise_if_oauth_unconfigured()

    state_valid, state_reason = shopify_oauth_service.verify_shopify_oauth_state(payload.state)
    if not state_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state for Shopify connect callback: {state_reason}",
        )

    try:
        exchange_result = shopify_oauth_service.exchange_code_for_token(
            code=payload.code,
            shop=payload.shop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShopifyIntegrationError as exc:
        raise _shopify_error_to_http(exc) from exc

    try:
        shopify_oauth_service.store_shopify_token(
            shop=exchange_result["shop"],
            access_token=exchange_result["access_token"],
            scope=exchange_result.get("scope", ""),
            client_id=payload.client_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("shopify_token_store_failed shop=%s", exchange_result.get("shop"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist Shopify access token",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopify.connect.success",
        resource="integration:shopify",
        details={"shop": exchange_result["shop"], "scope": exchange_result.get("scope", "")},
    )

    return ShopifyOAuthExchangeResponse(
        success=True,
        shop=exchange_result["shop"],
        scope=exchange_result.get("scope", ""),
        message="Shopify OAuth connected. Access token stored securely.",
    )


@router.get("/status", response_model=ShopifyStatusResponse)
def shopify_oauth_status(
    user: AuthUser = Depends(get_current_user),
) -> ShopifyStatusResponse:
    enforce_action_scope(user=user, action="integrations:status", scope="agency")
    payload = shopify_oauth_service.get_shopify_status()
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopify.status",
        resource="integration:shopify",
        details={"oauth_configured": payload["oauth_configured"], "token_count": payload["token_count"]},
    )
    return ShopifyStatusResponse(
        oauth_configured=bool(payload["oauth_configured"]),
        connected_shops=list(payload["connected_shops"]),
        token_count=int(payload["token_count"]),
    )
