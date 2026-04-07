from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, get_current_user
from app.core.config import load_settings
from app.integrations.shopify import config as shopify_config
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
from app.services.feed_management.repository import FeedSourceRepository

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

    # Best-effort: register the app/uninstalled webhook so we get notified
    # when the merchant removes VOXEL. Failures are logged but never block the
    # OAuth flow — the access token is already persisted.
    webhook_registered = False
    try:
        webhook_registered = shopify_oauth_service.register_uninstall_webhook(
            shop_domain=exchange_result["shop"],
            access_token=exchange_result["access_token"],
        )
    except Exception:  # noqa: BLE001
        logger.exception("shopify_webhook_register_unexpected_error shop=%s", exchange_result["shop"])

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopify.connect.success",
        resource="integration:shopify",
        details={
            "shop": exchange_result["shop"],
            "scope": exchange_result.get("scope", ""),
            "uninstall_webhook_registered": webhook_registered,
        },
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


# ---------------------------------------------------------------------------
# Webhooks (PUBLIC — Shopify-authenticated via HMAC, no JWT/session required)
# ---------------------------------------------------------------------------

_source_repo = FeedSourceRepository()


@router.post("/webhooks/app-uninstalled")
async def shopify_webhook_app_uninstalled(request: Request) -> dict[str, str]:
    """Handle Shopify ``app/uninstalled`` webhook.

    Auth: ``X-Shopify-Hmac-Sha256`` (HMAC-SHA256 of the raw request body keyed
    on ``SHOPIFY_APP_CLIENT_SECRET``). No JWT/session — Shopify calls this
    endpoint directly when a merchant removes the VOXEL app.

    On success: deletes the encrypted access token, marks every Shopify
    feed source bound to the shop as ``disconnected`` and writes an audit
    log entry. Always returns 200 OK on a valid HMAC (Shopify retries 5x on
    non-2xx within 5 seconds, so internal cleanup errors must not surface).
    """
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "")
    shop_header = request.headers.get("X-Shopify-Shop-Domain", "")

    secret = shopify_config.SHOPIFY_APP_CLIENT_SECRET
    if not secret:
        # Misconfigured server — fail closed (don't accept un-verifiable webhooks).
        logger.error("shopify_webhook_secret_missing topic=%s shop=%s", topic, shop_header)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify webhook secret is not configured",
        )

    if not shopify_oauth_service.verify_shopify_webhook_hmac(body, hmac_header, secret):
        logger.warning(
            "shopify_webhook_hmac_invalid topic=%s shop=%s body_bytes=%d",
            topic,
            shop_header,
            len(body),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook HMAC")

    # HMAC is valid — every code path below MUST return 200.
    parsed: dict = {}
    try:
        parsed = json.loads(body.decode("utf-8")) if body else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = {}

    raw_shop = (
        shop_header
        or str(parsed.get("myshopify_domain") or "")
        or str(parsed.get("domain") or "")
    ).strip().lower()

    if not raw_shop:
        logger.warning("shopify_webhook_app_uninstalled_missing_shop topic=%s", topic)
        return {"status": "ok", "shop": "", "sources_disconnected": "0"}

    try:
        shop_domain = shopify_config.validate_shop_domain(raw_shop)
    except ValueError:
        logger.warning("shopify_webhook_app_uninstalled_invalid_shop shop=%s", raw_shop)
        return {"status": "ok", "shop": raw_shop, "sources_disconnected": "0"}

    sources_affected = 0
    try:
        sources_affected = _source_repo.mark_disconnected_by_shop_domain(
            shop_domain,
            reason="App uninstalled by merchant",
        )
    except Exception:  # noqa: BLE001
        logger.exception("shopify_webhook_mark_disconnected_failed shop=%s", shop_domain)

    try:
        shopify_oauth_service.delete_shopify_token(shop_domain)
    except Exception:  # noqa: BLE001
        logger.exception("shopify_webhook_delete_token_failed shop=%s", shop_domain)

    try:
        audit_log_service.log(
            actor_email="shopify-webhook",
            actor_role="system",
            action="shopify.app.uninstalled",
            resource="integration:shopify",
            details={
                "shop": shop_domain,
                "sources_disconnected": sources_affected,
                "topic": topic,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("shopify_webhook_audit_log_failed shop=%s", shop_domain)

    logger.info(
        "shopify_webhook_app_uninstalled_processed shop=%s sources_disconnected=%d",
        shop_domain,
        sources_affected,
    )
    return {
        "status": "ok",
        "shop": shop_domain,
        "sources_disconnected": str(sources_affected),
    }


# GDPR mandatory compliance webhooks (Shopify Public App requirement).
# VOXEL never stores customer PII — these endpoints only acknowledge receipt
# after verifying the HMAC. Shopify requires all three topics to be wired
# before an app can be reviewed/published.
_GDPR_COMPLIANCE_TOPICS = frozenset(
    {"customers/data_request", "customers/redact", "shop/redact"}
)


@router.post("/webhooks/compliance")
async def shopify_webhook_compliance(request: Request) -> dict[str, str]:
    """Handle Shopify GDPR compliance webhooks (no-op acknowledge).

    Accepts the three mandatory topics:

    * ``customers/data_request`` — merchant-initiated request for a customer's
      stored personal data.
    * ``customers/redact`` — Shopify-initiated request to delete a customer's
      personal data 48h after they request erasure.
    * ``shop/redact`` — Shopify-initiated request to delete shop data 48h
      after the merchant uninstalls the app.

    VOXEL does not store any customer PII (we only persist Shopify product
    catalog data + an encrypted offline token, both keyed on the shop
    domain). The token + per-shop sources are already wiped by the
    ``app/uninstalled`` webhook handler. There is therefore no further
    deletion to perform — we just verify the HMAC and acknowledge.

    Auth: same ``X-Shopify-Hmac-Sha256`` HMAC verification as the other
    webhook endpoints. No JWT/session.
    """
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "")
    shop_header = request.headers.get("X-Shopify-Shop-Domain", "")

    secret = shopify_config.SHOPIFY_APP_CLIENT_SECRET
    if not secret:
        logger.error("shopify_webhook_compliance_secret_missing topic=%s shop=%s", topic, shop_header)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify webhook secret is not configured",
        )

    if not shopify_oauth_service.verify_shopify_webhook_hmac(body, hmac_header, secret):
        logger.warning(
            "shopify_webhook_compliance_hmac_invalid topic=%s shop=%s body_bytes=%d",
            topic,
            shop_header,
            len(body),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook HMAC")

    # Resolve shop domain (best-effort, only used for log lines).
    parsed: dict = {}
    try:
        parsed = json.loads(body.decode("utf-8")) if body else {}
        if not isinstance(parsed, dict):
            parsed = {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = {}

    raw_shop = (
        shop_header
        or str(parsed.get("shop_domain") or "")
        or str(parsed.get("myshopify_domain") or "")
        or str(parsed.get("domain") or "")
    ).strip().lower()

    if topic not in _GDPR_COMPLIANCE_TOPICS:
        logger.warning(
            "shopify_webhook_compliance_unknown_topic topic=%s shop=%s",
            topic,
            raw_shop,
        )
    else:
        logger.info(
            "shopify_webhook_compliance_received topic=%s shop=%s action=acknowledge_no_pii_stored",
            topic,
            raw_shop,
        )

    # Best-effort audit trail — never blocks the 200 response Shopify expects.
    try:
        audit_log_service.log(
            actor_email="shopify-webhook",
            actor_role="system",
            action="shopify.compliance.received",
            resource="integration:shopify",
            details={"topic": topic, "shop": raw_shop},
        )
    except Exception:  # noqa: BLE001
        logger.exception("shopify_webhook_compliance_audit_log_failed topic=%s shop=%s", topic, raw_shop)

    return {"status": "ok", "topic": topic, "shop": raw_shop}
