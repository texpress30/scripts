"""Shopify Feed Integration OAuth service.

Mirrors the Meta Ads OAuth pattern: stdlib ``urllib.request`` for HTTP,
HMAC-signed state via ``integration_secrets_store``, encrypted token storage
in the shared ``integration_secrets`` table.

Tokens are scoped per shop domain so multiple Shopify stores can be connected
under the same agency.
"""

from __future__ import annotations

import json
import logging
from urllib import error, request

from app.integrations.shopify import config as shopify_config
from app.services.integration_secrets_store import (
    generate_oauth_state,
    integration_secrets_store,
    verify_oauth_state,
)


logger = logging.getLogger(__name__)


PROVIDER = "shopify"
SECRET_KEY_ACCESS_TOKEN = "access_token"
SECRET_KEY_SCOPE = "scope"
OAUTH_STATE_PROVIDER = "shopify"


class ShopifyIntegrationError(RuntimeError):
    """Raised when a Shopify OAuth operation fails."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        provider_error: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = int(http_status) if http_status is not None else None
        self.provider_error = provider_error
        self.retryable = retryable


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if token.startswith("shpua_") or token.startswith("shpat_"):
        return f"{token[:6]}***"
    return "***"


def generate_connect_url(shop: str, client_id: str | None = None) -> dict[str, str]:
    """Validate the shop and build a Shopify OAuth authorize URL.

    ``client_id`` is the platform-side client identifier (not the Shopify app
    client id) and is currently passed through unchanged for symmetry with the
    request payload — the actual association happens at exchange time.
    """
    if not shopify_config.oauth_configured():
        raise ShopifyIntegrationError(
            "Shopify OAuth is not configured. Set SHOPIFY_APP_CLIENT_ID and SHOPIFY_APP_CLIENT_SECRET.",
        )

    shop_domain = shopify_config.validate_shop_domain(shop)
    state = generate_oauth_state(OAUTH_STATE_PROVIDER)
    authorize_url = shopify_config.get_shopify_authorize_url(shop_domain, state)
    logger.info(
        "shopify_connect_url_generated shop=%s client_id=%s state_prefix=%s",
        shop_domain,
        client_id or "-",
        state[:20],
    )
    return {"authorize_url": authorize_url, "state": state}


def _http_post_json(url: str, body: dict[str, str]) -> dict[str, object]:
    """POST a JSON body using stdlib ``urllib.request`` (no extra dependencies)."""
    encoded = json.dumps(body).encode("utf-8")
    req = request.Request(
        url=url,
        data=encoded,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            data = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_body = ""
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw_body = ""
        provider_error = None
        try:
            parsed_err = json.loads(raw_body) if raw_body else {}
            if isinstance(parsed_err, dict):
                provider_error = (
                    parsed_err.get("error_description")
                    or parsed_err.get("error")
                    or None
                )
        except Exception:
            provider_error = None

        if exc.code == 400:
            raise ShopifyIntegrationError(
                "Shopify rejected the OAuth code (invalid or expired).",
                http_status=400,
                provider_error=str(provider_error) if provider_error else None,
                retryable=False,
            ) from exc
        if exc.code == 403:
            raise ShopifyIntegrationError(
                "Shopify app is not installed on this shop.",
                http_status=403,
                provider_error=str(provider_error) if provider_error else None,
                retryable=False,
            ) from exc
        raise ShopifyIntegrationError(
            f"Shopify OAuth exchange failed: status={exc.code}",
            http_status=exc.code,
            provider_error=str(provider_error) if provider_error else None,
            retryable=exc.code >= 500,
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise ShopifyIntegrationError(
            "Could not reach Shopify",
            http_status=502,
            retryable=True,
        ) from exc

    try:
        parsed = json.loads(data) if data else {}
    except json.JSONDecodeError as exc:
        raise ShopifyIntegrationError("Shopify returned invalid JSON") from exc

    if not isinstance(parsed, dict):
        raise ShopifyIntegrationError("Shopify response shape is invalid")
    return parsed


def exchange_code_for_token(code: str, shop: str) -> dict[str, str]:
    """Exchange an authorization ``code`` for a permanent Shopify offline token."""
    if not shopify_config.oauth_configured():
        raise ShopifyIntegrationError(
            "Shopify OAuth is not configured. Set SHOPIFY_APP_CLIENT_ID and SHOPIFY_APP_CLIENT_SECRET.",
        )

    shop_domain = shopify_config.validate_shop_domain(shop)
    url = shopify_config.get_shopify_access_token_url(shop_domain)
    payload = _http_post_json(
        url,
        {
            "client_id": shopify_config.SHOPIFY_APP_CLIENT_ID,
            "client_secret": shopify_config.SHOPIFY_APP_CLIENT_SECRET,
            "code": code,
        },
    )

    access_token = str(payload.get("access_token") or "").strip()
    scope = str(payload.get("scope") or "").strip()
    if access_token == "":
        raise ShopifyIntegrationError("Shopify OAuth callback did not return an access token")

    logger.info(
        "shopify_token_exchange_ok shop=%s scope=%s token=%s",
        shop_domain,
        scope,
        _mask_token(access_token),
    )
    return {"access_token": access_token, "scope": scope, "shop": shop_domain}


def store_shopify_token(
    *,
    shop: str,
    access_token: str,
    scope: str,
    client_id: str | None = None,  # noqa: ARG001 - reserved for future client linking
) -> None:
    """Persist the Shopify access token (encrypted) keyed by shop domain."""
    shop_domain = shopify_config.validate_shop_domain(shop)
    integration_secrets_store.upsert_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN,
        value=access_token,
        scope=shop_domain,
    )
    if scope:
        integration_secrets_store.upsert_secret(
            provider=PROVIDER,
            secret_key=SECRET_KEY_SCOPE,
            value=scope,
            scope=shop_domain,
        )
    logger.info("shopify_token_stored shop=%s token=%s", shop_domain, _mask_token(access_token))


def get_access_token_for_shop(shop: str) -> str | None:
    """Return the decrypted Shopify access token for ``shop`` (or ``None``)."""
    shop_domain = shopify_config.validate_shop_domain(shop)
    secret = integration_secrets_store.get_secret(
        provider=PROVIDER,
        secret_key=SECRET_KEY_ACCESS_TOKEN,
        scope=shop_domain,
    )
    if secret is None or not secret.value.strip():
        return None
    return secret.value.strip()


def _list_connected_shops() -> list[str]:
    """List all shop domains that have a stored Shopify access token."""
    try:
        with integration_secrets_store._connect() as conn:  # noqa: SLF001
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT scope
                    FROM integration_secrets
                    WHERE provider = %s AND secret_key = %s
                    ORDER BY scope ASC
                    """,
                    (PROVIDER, SECRET_KEY_ACCESS_TOKEN),
                )
                rows = cur.fetchall() or []
        return [str(row[0]) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("shopify_list_connected_shops_failed error=%s", exc)
        return []


def get_shopify_status() -> dict[str, object]:
    """Return integration status (configured + currently connected shops)."""
    configured = shopify_config.oauth_configured()
    shops = _list_connected_shops() if configured else []
    return {
        "oauth_configured": configured,
        "connected_shops": shops,
        "token_count": len(shops),
    }


def verify_shopify_oauth_state(state: str) -> tuple[bool, str]:
    """Verify an HMAC-signed Shopify OAuth state token."""
    return verify_oauth_state(OAUTH_STATE_PROVIDER, state)