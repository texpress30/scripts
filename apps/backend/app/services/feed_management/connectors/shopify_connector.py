"""Shopify connector — imports products via the Shopify Admin REST API.

Uses cursor-based pagination (Link header) and maps Shopify products
(including variants) to the standardised ProductData model.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator

import requests

from app.core.config import load_settings
from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ProductVariant,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_API_VERSION = "2024-01"
_PAGE_LIMIT = 250
_SHOPIFY_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", str(text))
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _normalize_shop_url(raw: str) -> str:
    """Normalize store_url to 'mystore.myshopify.com' format."""
    url = str(raw).strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = url.rstrip("/")
    if "." not in url:
        url = f"{url}.myshopify.com"
    return url


def _build_base_url(shop_url: str) -> str:
    return f"https://{_normalize_shop_url(shop_url)}/admin/api/{_API_VERSION}"


def _auth_headers(credentials: dict[str, str]) -> dict[str, str]:
    """Build auth headers — supports access_token (preferred) or api_key+password."""
    access_token = credentials.get("access_token") or ""
    if access_token:
        return {"X-Shopify-Access-Token": access_token}
    # Fallback: basic auth via api_key + api_secret_key is handled at request level
    return {}


def _auth_tuple(credentials: dict[str, str]) -> tuple[str, str] | None:
    """Return (api_key, password) for HTTP basic auth if no access_token."""
    if credentials.get("access_token"):
        return None
    api_key = credentials.get("api_key", "")
    api_secret = credentials.get("api_secret_key", "")
    if api_key and api_secret:
        return (api_key, api_secret)
    return None


def _request(
    method: str,
    url: str,
    credentials: dict[str, str],
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """Make an authenticated request to the Shopify Admin API."""
    timeout = load_settings().storage_media_remote_fetch_timeout_seconds
    resp = requests.request(
        method,
        url,
        headers=_auth_headers(credentials),
        auth=_auth_tuple(credentials),
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp


def _parse_next_page_url(link_header: str | None) -> str | None:
    """Extract the next-page URL from a Shopify Link header."""
    if not link_header:
        return None
    for part in link_header.split(","):
        part = part.strip()
        if 'rel="next"' in part:
            match = re.search(r"<([^>]+)>", part)
            if match:
                return match.group(1)
    return None


class ShopifyConnector(BaseConnector):
    """Connector for Shopify stores via Admin REST API."""

    def __init__(self, config: dict[str, Any], credentials: dict[str, str] | None = None) -> None:
        super().__init__(config, credentials)
        self._shop_currency: str = "USD"

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        store_url = self.config.get("store_url", "")
        if not store_url:
            errors.append("store_url is required (e.g. myshop.myshopify.com)")
        else:
            normalized = _normalize_shop_url(store_url)
            if not _SHOPIFY_DOMAIN_RE.match(normalized):
                errors.append(f"Invalid store_url format: {store_url} (expected myshop.myshopify.com)")

        has_access_token = bool(self.credentials.get("access_token"))
        has_api_keys = bool(self.credentials.get("api_key")) and bool(self.credentials.get("api_secret_key"))
        if not has_access_token and not has_api_keys:
            errors.append("Either access_token or (api_key + api_secret_key) credentials are required")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        validation = await self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(success=False, message="Invalid config", details={"errors": validation.errors})

        base_url = _build_base_url(self.config["store_url"])
        try:
            resp = _request("GET", f"{base_url}/shop.json", self.credentials)
            shop = resp.json().get("shop", {})
            self._shop_currency = shop.get("currency", "USD")
            return ConnectionTestResult(
                success=True,
                message=f"Connected to {shop.get('name', 'Shopify store')}",
                details={
                    "shop_name": shop.get("name", ""),
                    "domain": shop.get("domain", ""),
                    "currency": self._shop_currency,
                    "plan": shop.get("plan_display_name", ""),
                },
            )
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else 0
            if status_code == 401:
                return ConnectionTestResult(success=False, message="Authentication failed — check your credentials")
            if status_code == 404:
                return ConnectionTestResult(success=False, message="Store not found — check your store URL")
            return ConnectionTestResult(success=False, message=f"Shopify API error (HTTP {status_code})")
        except requests.RequestException as exc:
            return ConnectionTestResult(success=False, message=f"Connection failed: {type(exc).__name__}")

    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        base_url = _build_base_url(self.config["store_url"])

        # Fetch shop currency if we haven't already
        try:
            resp = _request("GET", f"{base_url}/shop.json", self.credentials)
            self._shop_currency = resp.json().get("shop", {}).get("currency", "USD")
        except Exception:
            logger.warning("Could not fetch shop currency, defaulting to USD")

        params: dict[str, Any] = {"limit": _PAGE_LIMIT}
        if since:
            params["updated_at_min"] = since.isoformat()

        url: str | None = f"{base_url}/products.json"

        while url:
            resp = _request("GET", url, self.credentials, params=params if "products.json" in url and "page_info" not in url else None)
            data = resp.json()
            products = data.get("products", [])

            for shopify_product in products:
                for product_data in self._map_shopify_product(shopify_product):
                    yield product_data

            url = _parse_next_page_url(resp.headers.get("Link"))
            params = {}  # params only for first request; pagination URL includes everything

    async def get_product_count(self) -> int:
        base_url = _build_base_url(self.config["store_url"])
        resp = _request("GET", f"{base_url}/products/count.json", self.credentials)
        return int(resp.json().get("count", 0))

    def _map_shopify_product(self, product: dict[str, Any]) -> list[ProductData]:
        """Map a Shopify product (with variants) to ProductData instances."""
        product_id = str(product.get("id", ""))
        title = str(product.get("title", ""))
        description = _strip_html(product.get("body_html") or "")
        category = str(product.get("product_type", ""))
        handle = str(product.get("handle", ""))
        shop_url = _normalize_shop_url(self.config.get("store_url", ""))
        product_url = f"https://{shop_url}/products/{handle}" if handle else ""

        images = [str(img.get("src", "")) for img in product.get("images", []) if img.get("src")]

        tags_raw = product.get("tags", "")
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()] if tags_raw else []

        variants = product.get("variants") or []

        if not variants:
            return [ProductData(
                id=product_id,
                title=title,
                description=description,
                price=0.0,
                currency=self._shop_currency,
                images=images,
                variants=[],
                category=category,
                tags=tags,
                inventory_quantity=0,
                sku="",
                url=product_url,
            )]

        # Build ProductVariant list for all variants
        all_variants = []
        for v in variants:
            all_variants.append(ProductVariant(
                sku=str(v.get("sku") or ""),
                title=str(v.get("title") or ""),
                price=_safe_float(v.get("price")),
                compare_at_price=_safe_float(v.get("compare_at_price")),
                inventory_quantity=int(v.get("inventory_quantity") or 0),
            ))

        results: list[ProductData] = []
        for v in variants:
            variant_id = str(v.get("id", ""))
            variant_title = str(v.get("title") or "")
            display_title = f"{title} - {variant_title}" if variant_title and variant_title != "Default Title" else title

            compare_at = _safe_float(v.get("compare_at_price"))

            results.append(ProductData(
                id=f"{product_id}_{variant_id}",
                title=display_title,
                description=description,
                price=_safe_float(v.get("price")),
                compare_at_price=compare_at,
                currency=self._shop_currency,
                images=images,
                variants=all_variants,
                category=category,
                tags=tags,
                inventory_quantity=int(v.get("inventory_quantity") or 0),
                sku=str(v.get("sku") or ""),
                url=product_url,
            ))

        return results


def _safe_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
