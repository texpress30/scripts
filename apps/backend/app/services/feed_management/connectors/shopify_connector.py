"""Shopify connector — imports products via the Shopify Admin REST API.

Uses cursor-based pagination (Link header) and maps Shopify products
(including variants) to the standardised ProductData model.
"""

from __future__ import annotations

import json as _json
import logging
import re
import time
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
    flatten_images,
    strip_html as _strip_html,
)

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 250
_SHOPIFY_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")
_RATE_LIMIT_SOFT_THRESHOLD = 35  # of 40 — sleep 1s when bucket >= 35/40
_RATE_LIMIT_MAX_RETRIES = 3
_DEFAULT_RETRY_AFTER_SECONDS = 2.0


def _resolve_api_version() -> str:
    """Read the Shopify Admin API version from the integration config.

    Falls back to ``2024-01`` for environments where the Shopify integration
    module isn't initialised (e.g. legacy/test paths).
    """
    try:
        from app.integrations.shopify import config as shopify_config

        version = (shopify_config.SHOPIFY_API_VERSION or "").strip()
        return version or "2024-01"
    except Exception:
        return "2024-01"


def _normalize_shop_url(raw: str) -> str:
    """Normalize store_url to 'mystore.myshopify.com' format."""
    url = str(raw).strip().lower()
    url = re.sub(r"^https?://", "", url)
    url = url.rstrip("/")
    if "." not in url:
        url = f"{url}.myshopify.com"
    return url


def _build_base_url(shop_url: str) -> str:
    return f"https://{_normalize_shop_url(shop_url)}/admin/api/{_resolve_api_version()}"


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


def _throttle_for_bucket(api_call_limit_header: str | None) -> None:
    """Sleep briefly when Shopify's leaky bucket is close to full.

    Header format: ``"32/40"`` — numerator is current usage, denominator
    is the bucket size. We back off proactively before Shopify returns 429.
    """
    if not api_call_limit_header:
        return
    try:
        used_str, _capacity_str = api_call_limit_header.split("/", 1)
        used = int(used_str)
    except (ValueError, IndexError):
        return
    if used >= _RATE_LIMIT_SOFT_THRESHOLD:
        logger.info("shopify_rate_limit_soft_throttle bucket=%s sleeping=1s", api_call_limit_header)
        time.sleep(1.0)


def _request(
    method: str,
    url: str,
    credentials: dict[str, str],
    params: dict[str, Any] | None = None,
) -> requests.Response:
    """Make an authenticated request with retry-on-429 + soft throttle."""
    timeout = load_settings().storage_media_remote_fetch_timeout_seconds
    attempts = 0
    while True:
        attempts += 1
        resp = requests.request(
            method,
            url,
            headers=_auth_headers(credentials),
            auth=_auth_tuple(credentials),
            params=params,
            timeout=timeout,
        )
        if resp.status_code == 429 and attempts <= _RATE_LIMIT_MAX_RETRIES:
            retry_after_raw = resp.headers.get("Retry-After")
            try:
                retry_after = float(retry_after_raw) if retry_after_raw else _DEFAULT_RETRY_AFTER_SECONDS
            except ValueError:
                retry_after = _DEFAULT_RETRY_AFTER_SECONDS
            logger.warning(
                "shopify_rate_limit_429 url=%s attempt=%d retry_after=%.1fs",
                url, attempts, retry_after,
            )
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        _throttle_for_bucket(resp.headers.get("X-Shopify-Shop-Api-Call-Limit"))
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
        """Map a Shopify product (with variants) to ProductData instances.

        Each variant becomes its own ``ProductData`` row. Standard feed fields
        (additional_image_links, size, color, material, gtin, weight, availability,
        sale_price, brand, condition, mpn) are placed in ``raw_data`` under
        well-known keys so downstream channel exporters (Google Shopping,
        Meta Catalog) can read them by name.
        """
        product_id = str(product.get("id", ""))
        title = str(product.get("title", ""))
        description = _strip_html(product.get("body_html") or "")
        category = str(product.get("product_type", ""))
        handle = str(product.get("handle", ""))
        shop_url = _normalize_shop_url(self.config.get("store_url", ""))
        product_url = f"https://{shop_url}/products/{handle}" if handle else ""
        is_active = str(product.get("status", "active")).lower() == "active"

        images = [str(img.get("src", "")) for img in product.get("images", []) if img.get("src")]
        additional_images = images[1:] if len(images) > 1 else []

        tags_raw = product.get("tags", "")
        tags = [t.strip() for t in str(tags_raw).split(",") if t.strip()] if tags_raw else []

        # Map option position (1-based) → option name lower-cased so we can pull
        # size/color/material out of variant.option1/option2/option3.
        option_position_to_name: dict[int, str] = {}
        for opt in product.get("options") or []:
            try:
                pos = int(opt.get("position") or 0)
            except (TypeError, ValueError):
                pos = 0
            name = str(opt.get("name") or "").strip().lower()
            if pos and name:
                option_position_to_name[pos] = name

        def _extract_named_option(variant: dict[str, Any], target_names: set[str]) -> str:
            for pos in (1, 2, 3):
                opt_name = option_position_to_name.get(pos)
                if opt_name and opt_name in target_names:
                    val = variant.get(f"option{pos}")
                    if val:
                        return str(val)
            return ""

        variants = product.get("variants") or []
        raw_base = _flatten_shopify_raw(product)
        raw_base["product_status"] = product.get("status", "")
        raw_base["additional_image_links"] = _json.dumps(additional_images)
        raw_base["brand"] = product.get("vendor", "") or ""
        raw_base["condition"] = "new"
        raw_base["link"] = product_url
        if images:
            raw_base["image_link"] = images[0]

        if not variants:
            availability = "out_of_stock"
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
                raw_data={**raw_base, "availability": availability, "is_active": is_active},
            )]

        # Shared variants list (each ProductData carries the full set for context)
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
            display_title = (
                f"{title} - {variant_title}"
                if variant_title and variant_title != "Default Title"
                else title
            )

            inventory_qty = int(v.get("inventory_quantity") or 0)
            inventory_policy = str(v.get("inventory_policy") or "").lower()
            availability = (
                "in_stock" if inventory_qty > 0 or inventory_policy == "continue" else "out_of_stock"
            )

            price_value = _safe_float(v.get("price"))
            compare_at = _safe_float(v.get("compare_at_price"))
            sale_price_str = ""
            if compare_at is not None and price_value is not None and compare_at > price_value:
                # Shopify uses ``compare_at_price`` as the original price; the
                # *current* (lower) price is the sale price for feed purposes.
                sale_price_str = f"{price_value:.2f}"

            sku_value = str(v.get("sku") or "")
            barcode_value = str(v.get("barcode") or "")
            weight_value = v.get("weight")
            weight_unit = str(v.get("weight_unit") or "")

            size_value = _extract_named_option(v, {"size"})
            color_value = _extract_named_option(v, {"color", "colour"})
            material_value = _extract_named_option(v, {"material"})

            variant_raw = dict(raw_base)
            variant_raw.update({
                "variant_id": variant_id,
                "availability": availability,
                "sku": sku_value,
                "mpn": sku_value,
                "gtin": barcode_value,
                "size": size_value,
                "color": color_value,
                "material": material_value,
                "weight": f"{weight_value} {weight_unit}".strip() if weight_value else "",
                "weight_value": weight_value,
                "weight_unit": weight_unit,
                "sale_price": sale_price_str,
                "is_active": is_active,
            })
            for key in ("price", "compare_at_price", "inventory_quantity", "grams", "inventory_policy"):
                if key in v and v[key] is not None:
                    variant_raw[f"variant_{key}"] = v[key]

            results.append(ProductData(
                id=f"{product_id}_{variant_id}",
                title=display_title,
                description=description,
                price=price_value,
                compare_at_price=compare_at,
                currency=self._shop_currency,
                images=images,
                variants=all_variants,
                category=category,
                tags=tags,
                inventory_quantity=inventory_qty,
                sku=sku_value,
                url=product_url,
                raw_data=variant_raw,
            ))

        return results


def _flatten_shopify_raw(product: dict[str, Any]) -> dict[str, Any]:
    """Extract a flat dict of presentable raw fields from a Shopify product."""
    raw: dict[str, Any] = {}
    _SCALAR_KEYS = (
        "id", "title", "body_html", "vendor", "product_type", "handle",
        "status", "published_scope", "template_suffix", "created_at",
        "updated_at", "published_at",
    )
    for key in _SCALAR_KEYS:
        if key in product:
            raw[key] = product[key]

    tags_raw = product.get("tags", "")
    if tags_raw:
        raw["tags"] = tags_raw

    images = product.get("images") or []
    if images:
        raw["image_src"] = images[0].get("src", "")
        raw["image_alt"] = images[0].get("alt", "")
        raw["images"] = [img.get("src", "") for img in images if img.get("src")]
        flatten_images(raw)

    options = product.get("options") or []
    for opt in options:
        opt_name = str(opt.get("name", "")).lower().replace(" ", "_")
        if opt_name:
            raw[f"option_{opt_name}"] = ", ".join(str(v) for v in (opt.get("values") or []))

    variants = product.get("variants") or []
    if variants:
        first = variants[0]
        for key in ("price", "compare_at_price", "sku", "inventory_quantity", "weight", "grams"):
            if key in first and first[key] is not None:
                raw[f"variant_{key}"] = first[key]

    return raw


def _safe_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
