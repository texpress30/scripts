"""Pure normalization helpers for Magento 2 product payloads.

These functions live in their own module (separate from ``connector.py``) so
they can be unit-tested without instantiating any HTTP client, DB connection
or Mongo provider. ``normalize_magento_product`` is a pure function:

    raw_product + context → ProductData

The caller (``MagentoConnector``) is responsible for collecting the context
(currency, base URL, categories map, resolved children) and stitching
everything together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.feed_management.connectors.base import (
    ProductData,
    ProductVariant,
    strip_html,
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Parse a Magento price value (string / int / float / None) to float."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def extract_custom_attribute(raw: dict[str, Any], key: str, default: Any = None) -> Any:
    """Pull a single ``custom_attributes`` entry out of a Magento product payload.

    Magento 2 shapes most interesting fields as a list of
    ``{"attribute_code": str, "value": Any}`` objects rather than as top-level
    keys. This helper is tolerant of the list being missing / empty.
    """
    attrs = raw.get("custom_attributes") or []
    if not isinstance(attrs, list):
        return default
    for entry in attrs:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("attribute_code", "")) == key:
            return entry.get("value", default)
    return default


def _is_special_price_active(
    raw: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return True when ``special_price`` is within its [from, to] window.

    Either bound may be missing — a missing ``from`` means "started in the
    past", a missing ``to`` means "never expires". A parse error on either
    date is treated as "no constraint" (safer to show a sale than hide it).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    from_raw = extract_custom_attribute(raw, "special_from_date")
    to_raw = extract_custom_attribute(raw, "special_to_date")

    def _parse(value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Magento emits "YYYY-MM-DD HH:MM:SS" (store timezone) — we fall back
        # to date-only parsing for robustness.
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    from_dt = _parse(from_raw)
    to_dt = _parse(to_raw)
    if from_dt is not None and now < from_dt:
        return False
    if to_dt is not None and now > to_dt:
        return False
    return True


def resolve_special_price(
    raw: dict[str, Any],
    *,
    price: float,
    now: datetime | None = None,
) -> float | None:
    """Return ``compare_at_price`` (original) when a valid sale is active.

    In Magento 2, ``price`` is the regular price and ``special_price`` (in
    ``custom_attributes``) is the sale price. When a sale is running we
    surface ``compare_at_price = regular_price`` and keep ``price`` on the
    sale value — mirroring WooCommerce / Shopify semantics in the
    normalized ``ProductData`` shape.
    """
    special_raw = extract_custom_attribute(raw, "special_price")
    if special_raw in (None, ""):
        return None
    special_price = _safe_float(special_raw, default=0.0)
    if special_price <= 0 or special_price >= price:
        return None
    if not _is_special_price_active(raw, now=now):
        return None
    return price


# ---------------------------------------------------------------------------
# Media gallery → absolute image URLs
# ---------------------------------------------------------------------------


def build_media_base_url(storefront_base_url: str) -> str:
    """Build the public media prefix for product images.

    Magento 2 serves product images under ``<storefront>/media/catalog/product``
    by default. Callers can override by passing an absolute prefix.
    """
    return f"{storefront_base_url.rstrip('/')}/media/catalog/product"


def build_image_urls(raw: dict[str, Any], media_base_url: str) -> list[str]:
    """Return the absolute URLs for every enabled image in ``media_gallery_entries``.

    The primary image is surfaced first regardless of ``position``; the rest
    follow in Magento's own ``position`` order so the caller sees the
    merchant-configured gallery order.
    """
    entries = raw.get("media_gallery_entries") or []
    if not isinstance(entries, list):
        return []

    def _is_disabled(entry: dict[str, Any]) -> bool:
        value = entry.get("disabled")
        if isinstance(value, bool):
            return value
        if value in (1, "1", "true", "True"):
            return True
        return False

    enabled = [e for e in entries if isinstance(e, dict) and not _is_disabled(e)]

    def _sort_key(entry: dict[str, Any]) -> tuple[int, int]:
        types = entry.get("types") or []
        is_primary = 0 if "image" in types else 1
        position = _safe_int(entry.get("position"), default=9999)
        return (is_primary, position)

    enabled.sort(key=_sort_key)

    urls: list[str] = []
    prefix = media_base_url.rstrip("/")
    for entry in enabled:
        file_path = str(entry.get("file") or "").lstrip("/")
        if not file_path:
            continue
        urls.append(f"{prefix}/{file_path}")
    return urls


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def flatten_category_tree(tree: dict[str, Any] | None) -> dict[str, str]:
    """Walk Magento's ``GET /categories`` tree and return ``{id: name}``.

    The tree payload is recursive (``children_data`` at every level). We
    skip the root category 1 ("Default Category") and the global root 2
    ("Root Catalog") because neither ever appears on a real product.
    """
    if not tree or not isinstance(tree, dict):
        return {}
    out: dict[str, str] = {}

    def _walk(node: dict[str, Any]) -> None:
        cid = node.get("id")
        name = str(node.get("name", "")).strip()
        if cid is not None and name:
            out[str(cid)] = name
        children = node.get("children_data") or []
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    _walk(child)

    _walk(tree)
    return out


def resolve_category_name(
    raw: dict[str, Any], categories_map: dict[str, str]
) -> str:
    """Return the first resolvable category name from ``category_ids``.

    Magento stores category ids as a comma-separated string inside
    ``custom_attributes`` — we split, resolve against the map passed in
    by the connector, and return the first hit.
    """
    ids_raw = extract_custom_attribute(raw, "category_ids")
    if not ids_raw:
        return ""
    ids: list[str] = []
    if isinstance(ids_raw, list):
        ids = [str(x) for x in ids_raw if x not in (None, "")]
    else:
        ids = [p.strip() for p in str(ids_raw).split(",") if p.strip()]
    for cid in ids:
        name = categories_map.get(cid)
        if name:
            return name
    return ""


# ---------------------------------------------------------------------------
# URL + tags
# ---------------------------------------------------------------------------


def build_product_url(
    raw: dict[str, Any],
    storefront_base_url: str,
    *,
    url_suffix: str = ".html",
) -> str:
    """Return the canonical storefront URL for a product.

    Magento 2 stores the pretty handle as ``url_key`` in custom attributes.
    The default URL rewrite appends ``.html``; callers can override via
    ``url_suffix`` when a store uses a different suffix.
    """
    url_key = extract_custom_attribute(raw, "url_key")
    if not url_key:
        return ""
    base = storefront_base_url.rstrip("/")
    return f"{base}/{str(url_key).lstrip('/')}{url_suffix}"


def extract_tags(raw: dict[str, Any]) -> list[str]:
    """Return a best-effort list of tags from ``meta_keywords``."""
    keywords = extract_custom_attribute(raw, "meta_keywords")
    if not keywords:
        return []
    return [token.strip() for token in str(keywords).split(",") if token.strip()]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def extract_inventory_quantity(raw: dict[str, Any]) -> int:
    """Return the on-hand stock quantity from ``extension_attributes.stock_item.qty``."""
    ext = raw.get("extension_attributes") or {}
    if not isinstance(ext, dict):
        return 0
    stock = ext.get("stock_item") or {}
    if not isinstance(stock, dict):
        return 0
    return _safe_int(stock.get("qty"), default=0)


def extract_is_in_stock(raw: dict[str, Any]) -> bool:
    ext = raw.get("extension_attributes") or {}
    if not isinstance(ext, dict):
        return False
    stock = ext.get("stock_item") or {}
    if not isinstance(stock, dict):
        return False
    value = stock.get("is_in_stock")
    if isinstance(value, bool):
        return value
    return value in (1, "1", "true", "True")


# ---------------------------------------------------------------------------
# Raw-data flattener (symmetry with WooCommerce / Shopify pattern)
# ---------------------------------------------------------------------------


_SCALAR_KEYS_TO_COPY = (
    "id",
    "sku",
    "name",
    "type_id",
    "price",
    "status",
    "visibility",
    "weight",
    "created_at",
    "updated_at",
)


def flatten_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract a flat presentable dict of raw Magento fields.

    Used to populate ``ProductData.raw_data``. Mirrors the ``_flatten_raw``
    helpers in the WooCommerce/Shopify connectors — scalar top-level fields
    copy through verbatim, while a handful of well-known custom attributes
    are hoisted to top-level keys for easier channel export mapping.
    """
    flat: dict[str, Any] = {}
    for key in _SCALAR_KEYS_TO_COPY:
        if key in raw:
            flat[key] = raw[key]

    for attr_code in (
        "description",
        "short_description",
        "url_key",
        "meta_keywords",
        "meta_description",
        "brand",
        "manufacturer",
        "color",
        "size",
        "material",
        "mpn",
        "gtin",
        "special_price",
        "special_from_date",
        "special_to_date",
    ):
        value = extract_custom_attribute(raw, attr_code)
        if value not in (None, ""):
            if attr_code in ("description", "short_description") and isinstance(value, str):
                value = strip_html(value)
            flat[attr_code] = value

    ext = raw.get("extension_attributes") or {}
    if isinstance(ext, dict):
        stock = ext.get("stock_item") or {}
        if isinstance(stock, dict):
            if "qty" in stock:
                flat["stock_quantity"] = _safe_int(stock.get("qty"))
            if "is_in_stock" in stock:
                flat["is_in_stock"] = bool(stock.get("is_in_stock"))

    media = raw.get("media_gallery_entries") or []
    if isinstance(media, list) and media:
        flat["image_count"] = len(media)

    return flat


# ---------------------------------------------------------------------------
# Variants — configurable product children
# ---------------------------------------------------------------------------


def build_variants(
    children: list[dict[str, Any]] | None,
) -> list[ProductVariant]:
    """Project Magento configurable ``children`` onto :class:`ProductVariant`."""
    if not children:
        return []
    out: list[ProductVariant] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        price = _safe_float(child.get("price"))
        special = resolve_special_price(child, price=price)
        out.append(
            ProductVariant(
                sku=str(child.get("sku") or ""),
                title=str(child.get("name") or ""),
                price=price,
                compare_at_price=special,
                inventory_quantity=extract_inventory_quantity(child),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def normalize_magento_product(
    raw: dict[str, Any],
    *,
    storefront_base_url: str,
    currency: str,
    categories_map: dict[str, str] | None = None,
    media_base_url: str | None = None,
    children: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> ProductData:
    """Convert a Magento 2 product payload into a :class:`ProductData` row.

    ``children`` should be supplied for ``configurable`` products; they are
    projected into ``ProductData.variants``. For ``simple`` products callers
    can omit it entirely.
    """
    categories_map = categories_map or {}
    media_prefix = media_base_url or build_media_base_url(storefront_base_url)

    product_id = str(raw.get("id") or raw.get("sku") or "")
    title = str(raw.get("name") or "")
    description_raw = extract_custom_attribute(raw, "description") or extract_custom_attribute(
        raw, "short_description"
    ) or ""
    description = strip_html(str(description_raw)) if description_raw else ""

    price = _safe_float(raw.get("price"))
    compare_at_price = resolve_special_price(raw, price=price, now=now)

    images = build_image_urls(raw, media_prefix)
    category = resolve_category_name(raw, categories_map)
    tags = extract_tags(raw)
    variants = build_variants(children)
    inventory = extract_inventory_quantity(raw)
    sku = str(raw.get("sku") or "")
    url = build_product_url(raw, storefront_base_url)

    return ProductData(
        id=product_id,
        title=title,
        description=description,
        price=price,
        compare_at_price=compare_at_price,
        currency=str(currency or "USD"),
        images=images,
        variants=variants,
        category=category,
        tags=tags,
        inventory_quantity=inventory,
        sku=sku,
        url=url,
        raw_data=flatten_raw(raw),
    )
