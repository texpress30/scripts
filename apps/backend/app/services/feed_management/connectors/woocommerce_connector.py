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
    strip_html,
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
            status_code = exc.response.status_code
            logger.warning("WooCommerce HTTP %s from %s: %s", status_code, self._store_url, exc.response.text[:500])
            if status_code == 401:
                return ConnectionTestResult(success=False, message="Autentificare eșuată — Consumer Key sau Consumer Secret invalid.")
            if status_code == 403:
                return ConnectionTestResult(success=False, message="Acces interzis — verifică permisiunile API Key (Read access necesar).")
            if status_code == 404:
                return ConnectionTestResult(success=False, message="WooCommerce REST API nu este accesibil. Verifică că URL-ul este corect și WooCommerce este activ.")
            return ConnectionTestResult(success=False, message=f"WooCommerce API a returnat eroare HTTP {status_code}.")
        except httpx.ConnectError as exc:
            logger.warning("WooCommerce ConnectError for %s: %s", self._store_url, exc)
            return ConnectionTestResult(success=False, message=f"Nu se poate conecta la {self._store_url}. Verifică URL-ul și că site-ul este online.")
        except httpx.ConnectTimeout:
            return ConnectionTestResult(success=False, message=f"Timeout la conectare — {self._store_url} nu răspunde. Încearcă din nou.")
        except httpx.ReadTimeout:
            return ConnectionTestResult(success=False, message="Site-ul a răspuns prea lent. Încearcă din nou mai târziu.")
        except Exception as exc:
            logger.exception("WooCommerce test_connection unexpected error for %s", self._store_url)
            return ConnectionTestResult(success=False, message=f"Eroare la testarea conexiunii: {type(exc).__name__}: {exc}")

    async def _fetch_currency(self, client: httpx.AsyncClient) -> None:
        """Fetch store currency from WooCommerce Settings API."""
        try:
            resp = await client.get(self._api_url("/settings/general"))
            if resp.status_code == 200:
                for setting in resp.json():
                    if setting.get("id") == "woocommerce_currency":
                        value = setting.get("value")
                        if value:
                            self._currency = str(value)
                        break
        except Exception:
            pass  # keep existing self._currency as fallback

    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        params: dict[str, Any] = {"per_page": _PER_PAGE, "status": "publish", "orderby": "id", "order": "asc"}
        if since is not None:
            params["modified_after"] = since.isoformat()

        page = 1
        async with httpx.AsyncClient(auth=self._auth(), timeout=_REQUEST_TIMEOUT) as client:
            # Fetch real currency before processing products
            await self._fetch_currency(client)
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
                    description=strip_html(woo.get("short_description") or woo.get("description") or ""),
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
                    raw_data=_flatten_raw(woo, var),
                ))
            return results

        # Simple / grouped / external product
        price = _safe_float(woo.get("price"))
        regular = _safe_float(woo.get("regular_price"))
        compare = regular if woo.get("on_sale") and regular > price else None

        return [ProductData(
            id=str(woo.get("id", "")),
            title=str(woo.get("name") or ""),
            description=strip_html(woo.get("short_description") or woo.get("description") or ""),
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
            raw_data=_flatten_raw(woo),
        )]


def _flatten_raw(woo: dict[str, Any], variation: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract a flat dict of presentable raw fields from a WooCommerce product."""
    raw: dict[str, Any] = {}
    # Scalar fields from the parent product
    _SCALAR_KEYS = (
        "id", "name", "slug", "permalink", "status", "featured", "description",
        "short_description", "sku", "price", "regular_price", "sale_price",
        "on_sale", "manage_stock", "stock_quantity", "stock_status", "weight",
        "purchase_note", "menu_order", "type",
    )
    for key in _SCALAR_KEYS:
        if key in woo:
            value = woo[key]
            # Strip HTML from description fields in raw_data too
            if key in ("description", "short_description") and isinstance(value, str):
                value = strip_html(value)
            raw[key] = value

    # Useful nested data flattened
    categories = woo.get("categories") or []
    if categories:
        raw["category"] = categories[0].get("name", "")
        if len(categories) > 1:
            raw["all_categories"] = ", ".join(c.get("name", "") for c in categories)
    tags = woo.get("tags") or []
    if tags:
        raw["tags"] = ", ".join(t.get("name", "") for t in tags)
    images = woo.get("images") or []
    if images:
        raw["image_src"] = images[0].get("src", "")
        raw["image_alt"] = images[0].get("alt", "")
        raw["images"] = [img.get("src", "") for img in images]
    dims = woo.get("dimensions") or {}
    for dim_key in ("length", "width", "height"):
        if dims.get(dim_key):
            raw[f"dimension_{dim_key}"] = dims[dim_key]
    attrs = woo.get("attributes") or []
    for attr in attrs:
        attr_name = str(attr.get("name", "")).lower().replace(" ", "_")
        if not attr_name:
            continue
        # WooCommerce uses "options" (array) for product attributes,
        # and "option" (string) for variation attributes
        options = attr.get("options") or []
        option_single = attr.get("option", "")
        if options:
            value = ", ".join(str(o) for o in options) if len(options) > 1 else str(options[0])
        elif option_single:
            value = str(option_single)
        else:
            continue
        raw[f"attribute_{attr_name}"] = value

    # meta_data — custom fields (e.g. auto dealer plugins: kilometraj, brand, model)
    _WP_INTERNAL_META_PREFIXES = (
        "_edit_", "_wp_", "_thumbnail", "_oembed", "_wc_",
        "_product_image_gallery", "_product_url", "_product_button_text",
        "_sku", "_price", "_regular_price", "_sale_price", "_stock",
        "_manage_stock", "_backorders", "_sold_individually", "_virtual",
        "_downloadable", "_download_", "_purchase_note", "_variation_",
        "_crosssell_", "_upsell_",
    )
    for meta in woo.get("meta_data") or []:
        key = str(meta.get("key") or "")
        value = meta.get("value")
        if not key or value is None or value == "":
            continue
        # Skip complex nested values (serialized objects, arrays of objects)
        if isinstance(value, (dict, list)):
            continue
        # Skip WordPress/WooCommerce internal meta
        key_lower = key.lower()
        if any(key_lower.startswith(p) for p in _WP_INTERNAL_META_PREFIXES):
            continue
        # Normalize: strip leading underscores, lowercase
        clean_key = key.lstrip("_").lower().replace(" ", "_")
        # Don't overwrite fields already extracted (name, price, etc.)
        if clean_key not in raw:
            raw[f"meta_{clean_key}"] = str(value) if not isinstance(value, str) else value

    # Variation overrides
    if variation:
        for key in ("sku", "price", "regular_price", "sale_price", "stock_quantity", "weight"):
            if key in variation and variation[key] is not None:
                raw[f"variant_{key}"] = variation[key]

    # meta_box — JetEngine and similar plugins expose custom fields here
    # Contains taxonomy terms as dicts, arrays of terms, and scalar values
    # e.g. {"brand": {"name": "BMW", ...}, "tip_oferta": [{"name": "Stoc intern"}], "rata": ""}
    meta_box = woo.get("meta_box")
    if isinstance(meta_box, dict):
        for key, value in meta_box.items():
            clean_key = key.lower().replace("-", "_").replace(" ", "_")
            if clean_key in raw:
                continue
            if isinstance(value, dict) and "name" in value:
                raw[clean_key] = str(value["name"])
            elif isinstance(value, list) and value and isinstance(value[0], dict) and "name" in value[0]:
                names = [str(t["name"]) for t in value if t.get("name")]
                if names:
                    raw[clean_key] = ", ".join(names)
            elif isinstance(value, str) and value:
                raw[clean_key] = value
            elif isinstance(value, (int, float)) and value is not None:
                raw[clean_key] = str(value)

    # Top-level taxonomy objects (auto dealer plugins like JetEngine inject these)
    # e.g. "brand": {"term_id": 17, "name": "BMW", "taxonomy": "product_cat"}
    # e.g. "norma_de_poluare": [{"name": "EURO 5", ...}]
    _KNOWN_COMPLEX_KEYS = frozenset({
        "categories", "tags", "images", "attributes", "dimensions",
        "meta_data", "downloads", "related_ids", "grouped_products",
        "_links", "default_attributes",
    })
    for key, value in woo.items():
        if key in _KNOWN_COMPLEX_KEYS:
            continue
        clean_key = key.lower().replace(" ", "_")
        if clean_key in raw:
            continue
        if isinstance(value, dict) and "name" in value:
            raw[clean_key] = str(value["name"])
        elif isinstance(value, list) and value and isinstance(value[0], dict) and "name" in value[0]:
            names = [str(t["name"]) for t in value if t.get("name")]
            if names:
                raw[clean_key] = ", ".join(names)

    return raw


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0
