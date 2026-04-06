"""Shopify Feed Integration configuration (VOXEL app - OAuth)."""

from __future__ import annotations

import os
import re
from urllib.parse import quote, urlencode


_MYSHOPIFY_SUFFIX = ".myshopify.com"
_SHOP_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*\.myshopify\.com$")

SHOPIFY_APP_CLIENT_ID: str = os.environ.get("SHOPIFY_APP_CLIENT_ID", "")
SHOPIFY_APP_CLIENT_SECRET: str = os.environ.get("SHOPIFY_APP_CLIENT_SECRET", "")
SHOPIFY_REDIRECT_URI: str = os.environ.get(
    "SHOPIFY_REDIRECT_URI",
    "https://admin.omarosa.ro/agency/integrations/shopify/callback",
)
SHOPIFY_API_VERSION: str = os.environ.get("SHOPIFY_API_VERSION", "2026-04")
SHOPIFY_SCOPES: str = os.environ.get(
    "SHOPIFY_SCOPES",
    "read_products,read_product_listings,read_inventory,read_locations",
)


def oauth_configured() -> bool:
    """Return ``True`` when both OAuth credentials are present and non-empty."""
    return bool(SHOPIFY_APP_CLIENT_ID.strip() and SHOPIFY_APP_CLIENT_SECRET.strip())


def validate_shop_domain(shop: str) -> str:
    """Sanitise and validate a Shopify shop domain.

    Returns the cleaned domain (lowercase, trimmed) or raises ``ValueError``.
    """
    cleaned = shop.strip().lower()

    if "/" in cleaned:
        raise ValueError(f"Invalid shop domain (contains path): {shop}")

    if not cleaned.endswith(_MYSHOPIFY_SUFFIX):
        raise ValueError(
            f"Invalid shop domain (must end with {_MYSHOPIFY_SUFFIX}): {shop}"
        )

    if not _SHOP_DOMAIN_RE.match(cleaned):
        raise ValueError(f"Invalid shop domain (illegal characters): {shop}")

    return cleaned


def get_shopify_authorize_url(shop_domain: str, state: str) -> str:
    """Build the Shopify OAuth authorize URL."""
    params = urlencode(
        {
            "client_id": SHOPIFY_APP_CLIENT_ID,
            "scope": SHOPIFY_SCOPES,
            "redirect_uri": SHOPIFY_REDIRECT_URI,
            "state": state,
        },
        quote_via=quote,
    )
    return f"https://{shop_domain}/admin/oauth/authorize?{params}"


def get_shopify_access_token_url(shop_domain: str) -> str:
    """Return the Shopify OAuth access-token exchange endpoint."""
    return f"https://{shop_domain}/admin/oauth/access_token"


def get_shopify_api_base_url(shop_domain: str) -> str:
    """Return the versioned Shopify Admin API base URL."""
    return f"https://{shop_domain}/admin/api/{SHOPIFY_API_VERSION}"
