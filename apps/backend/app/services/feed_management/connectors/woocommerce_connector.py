"""WooCommerce connector via REST API v3.

Uses HTTP Basic Auth over HTTPS with consumer_key / consumer_secret.
Handles pagination, variable products (variations), and maps
WooCommerce product JSON to the standardized ProductData model.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ProductVariant,
    ValidationResult,
)

logger = logging.getLogger(__name__)

_API_PREFIX = "/wp-json/wc/v3"
_PER_PAGE = 100
_REQUEST_TIMEOUT = 30.0
_DELAY_BETWEEN_PAGES = 0.25  # seconds


class WooCommerceConnector(BaseConnector):
    """Connector for WooCommerce stores via REST API v3."""

    def __init__(self, config: dict[str, Any], credentials: dict[str, str] | None = None) -> None:
        super().__init__(config, credentials)
        raw_url = str(config.get("store_url") or "").rstrip("/")
        self._store_url = raw_url
        self._consumer_key = credentials.get("consumer_key", "") if credentials else ""
        self._consumer_secret = credentials.get("consumer_secret", "") if credentials else ""
        self._currency = str(config.get("currency") or "USD")

    def _api_url(self, path: str) -> str:
        return f"{self._store_url}{_API_PREFIX}{path}"

    def _auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self._consumer_key, self._consumer_secret)

    # -- abstract implementations ---------------------------------------------

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        if not self._store_url:
            errors.append("store_url is required (e.g. https://mystore.com)")
        elif not self._store_url.startswith("https://"):
            errors.append("store_url must use HTTPS for Basic Auth")
        if not self._consumer_key:
            errors.append("consumer_key credential is required")
        if not self._consumer_secret:
            errors.append("consumer_secret credential is required")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        validation = await self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(success=False, message="Invalid config", details={"errors": validation.errors})
        try:
            async with httpx.AsyncClient(auth=self._auth(), timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.get(self._api_url(""))
                resp.raise_for_status()
                data = resp.json()

                # Try to fetch currency from settings
                currency = self._currency
                try:
                    settings_resp = await client.get(self._api_url("/settings/general"))
                    if settings_resp.status_code == 200:
                        for setting in settings_resp.json():
                            if setting.get("id") == "woocommerce_currency":
                                currency = str(setting.get("value") or currency)
                                self._currency = currency
                                break
                except Exception:
                    pass

                # Get product count
                count_resp = await client.get(self._api_url("/products"), params={"per_page": 1})
                total_products = int(count_resp.headers.get("X-WP-Total", 0))

                store_name = str(data.get("description") or data.get("name") or self._store_url)
                wc_routes = data.get("routes") or data.get("namespaces") or {}
                return ConnectionTestResult(
                    success=True,
                    message="Connected to WooCommerce store",
                    details={
                        "store_url": self._store_url,
                        "store_name": store_name,
                        "products_count": total_products,
                        "currency": currency,
                        "wc_version": "v3",
                    },
                )
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                return ConnectionTestResult(success=False, message="Authentication failed: invalid consumer_key or consumer_secret")
            return ConnectionTestResult(success=False, message=f"WooCommerce API returned HTTP {status}")
        except httpx.ConnectError:
            return ConnectionTestResult(success=False, message=f"Cannot connect to {self._store_url}")
        except Exception as exc:
            return ConnectionTestResult(success=False, message=f"Connection test failed: {exc}")

    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        params: dict[str, Any] = {"per_page": _PER_PAGE, "status": "publish", "orderby": "id", "order": "asc"}
        if since is not None:
            params["modified_after"] = since.isoformat()

        page = 1
        async with httpx.AsyncClient(auth=self._auth(), timeout=_REQUEST_TIMEOUT) as client:
            while True:
                params["page"] = page
                resp = await client.get(self._api_url("/products"), params=params)
                resp.raise_for_status()
                products = resp.json()
                if not products:
                    break

                for woo_product in products:
                    variations: list[dict[str, Any]] = []
                    if woo_product.get("type") == "variable":
                        variations = await self._fetch_variations(client, woo_product["id"])

                    for product_data in self._map_woo_product(woo_product, variations):
                        yield product_data

                total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1
                await asyncio.sleep(_DELAY_BETWEEN_PAGES)

    async def get_product_count(self) -> int:
        async with httpx.AsyncClient(auth=self._auth(), timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.get(self._api_url("/products"), params={"per_page": 1, "status": "publish"})
            resp.raise_for_status()
            return int(resp.headers.get("X-WP-Total", 0))

    # -- helpers --------------------------------------------------------------

    async def _fetch_variations(self, client: httpx.AsyncClient, product_id: int) -> list[dict[str, Any]]:
        all_variations: list[dict[str, Any]] = []
        page = 1
        while True:
            resp = await client.get(
                self._api_url(f"/products/{product_id}/variations"),
                params={"per_page": _PER_PAGE, "page": page},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            all_variations.extend(batch)
            total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
            if page >= total_pages:
                break
            page += 1
        return all_variations

    def _map_woo_product(self, woo: dict[str, Any], variations: list[dict[str, Any]] | None = None) -> list[ProductData]:
        """Map a WooCommerce product (and optional variations) to ProductData list."""
        images = [str(img.get("src") or "") for img in (woo.get("images") or []) if img.get("src")]
        categories = woo.get("categories") or []
        category = str(categories[0].get("name", "")) if categories else ""
        tags = [str(tag.get("name", "")) for tag in (woo.get("tags") or [])]
        currency = self._currency

        # For variable products with variations, emit one ProductData per variation
        if woo.get("type") == "variable" and variations:
            results: list[ProductData] = []
            for var in variations:
                attrs = var.get("attributes") or []
                attr_label = " / ".join(str(a.get("option", "")) for a in attrs)
                var_title = f"{woo.get('name', '')} - {attr_label}" if attr_label else str(woo.get("name", ""))
                var_images = [str(img.get("src", "")) for img in [var.get("image")] if img and img.get("src")]
                price = _safe_float(var.get("price"))
                regular = _safe_float(var.get("regular_price"))
                compare = regular if var.get("on_sale") and regular > price else None

                results.append(ProductData(
                    id=f"{woo['id']}_{var['id']}",
                    title=var_title,
                    description=str(woo.get("short_description") or woo.get("description") or ""),
                    price=price,
                    compare_at_price=compare,
                    currency=currency,
                    images=var_images or images,
                    variants=[],
                    category=category,
                    tags=tags,
                    inventory_quantity=int(var.get("stock_quantity") or 0),
                    sku=str(var.get("sku") or ""),
                    url=str(woo.get("permalink") or ""),
                ))
            return results

        # Simple / grouped / external product
        price = _safe_float(woo.get("price"))
        regular = _safe_float(woo.get("regular_price"))
        compare = regular if woo.get("on_sale") and regular > price else None

        return [ProductData(
            id=str(woo.get("id", "")),
            title=str(woo.get("name") or ""),
            description=str(woo.get("short_description") or woo.get("description") or ""),
            price=price,
            compare_at_price=compare,
            currency=currency,
            images=images,
            variants=[],
            category=category,
            tags=tags,
            inventory_quantity=int(woo.get("stock_quantity") or 0),
            sku=str(woo.get("sku") or ""),
            url=str(woo.get("permalink") or ""),
        )]


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0
