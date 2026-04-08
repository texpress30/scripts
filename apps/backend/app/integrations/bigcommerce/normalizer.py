"""Pure normalization helpers for BigCommerce V3 catalog product payloads.

These functions live in their own module (separate from ``connector.py``) so
they can be unit-tested without instantiating any HTTP client, DB connection
or Mongo provider. ``normalize_bigcommerce_product`` is a pure function:

    raw_product + context → ProductData

The caller (``BigCommerceConnector``) is responsible for collecting the
context (currency, store domain, categories map, brands map) and stitching
everything together.

Pricing model
-------------
BigCommerce and Shopify use opposite conventions for sale pricing:

* **Shopify**: ``price`` is the *current* selling price, ``compare_at_price``
  is the higher original price (the strikethrough).
* **BigCommerce**: ``price`` is the *base* (regular) price; ``sale_price``
  is the lower discounted price.

The normalised :class:`ProductData` shape mirrors Shopify semantics, so we
flip the BC fields:

* If BC ``sale_price`` is in ``(0, price)``: normalised ``price`` becomes
  the BC ``sale_price`` and ``compare_at_price`` becomes the BC ``price``.
* Otherwise: normalised ``price`` is the BC ``price`` and
  ``compare_at_price`` is ``None``.

This matches the Magento normalizer's ``resolve_special_price`` semantics
and the WooCommerce / Shopify connectors so downstream channels (Google,
Meta, TikTok feeds) see one consistent shape across every platform.
"""

from __future__ import annotations

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
    """Parse a BigCommerce price value (string / int / float / None) to float."""
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


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


def normalize_price(
    price: Any, sale_price: Any
) -> tuple[float, float | None]:
    """Map BigCommerce ``(price, sale_price)`` onto ``(display_price, compare_at)``.

    Returns ``(display_price, compare_at_price)``:

    * If ``sale_price`` is a positive value strictly less than ``price``,
      we treat the listing as on sale: ``display_price = sale_price``,
      ``compare_at_price = price``.
    * Otherwise (no sale, sale_price == 0, sale_price >= price), we
      surface the regular price with no comparison: ``display_price =
      price``, ``compare_at_price = None``.
    """
    base = _safe_float(price)
    sale = _safe_float(sale_price)
    if sale > 0 and sale < base:
        return sale, base
    return base, None


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def extract_image_urls(images: list[dict[str, Any]] | None) -> list[str]:
    """Sort BigCommerce ``images`` by ``sort_order`` and pull the public URL.

    Each entry exposes ``url_zoom`` (high-res), ``url_standard`` (catalog),
    ``url_thumbnail`` and ``url_tiny``. We prefer ``url_standard`` because
    it's the size catalog feeds expect; ``url_zoom`` is the fallback when
    standard is missing (rare). Thumbnails first via the ``is_thumbnail``
    flag, then by ``sort_order``.
    """
    if not images or not isinstance(images, list):
        return []

    def _sort_key(entry: dict[str, Any]) -> tuple[int, int, int]:
        is_thumb = 0 if entry.get("is_thumbnail") else 1
        sort_order = _safe_int(entry.get("sort_order"), default=9999)
        image_id = _safe_int(entry.get("id"), default=9999)
        return (is_thumb, sort_order, image_id)

    sorted_entries = sorted(
        (e for e in images if isinstance(e, dict)),
        key=_sort_key,
    )

    urls: list[str] = []
    for entry in sorted_entries:
        url = (
            entry.get("url_standard")
            or entry.get("url_zoom")
            or entry.get("url_thumbnail")
            or ""
        )
        if isinstance(url, str) and url.strip():
            urls.append(url.strip())
    return urls


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------


def build_product_url(
    store_domain: str | None,
    custom_url: dict[str, Any] | None,
) -> str:
    """Stitch the storefront base URL onto a BigCommerce ``custom_url`` slug.

    BigCommerce delivers ``custom_url = {"url": "/winter-jacket/", ...}``.
    Returns an empty string when either input is missing — the caller can
    fall back to the bare slug or a search URL if needed.
    """
    if not custom_url or not isinstance(custom_url, dict):
        return ""
    slug_raw = str(custom_url.get("url") or "").strip()
    if not slug_raw:
        return ""

    domain_raw = str(store_domain or "").strip()
    if not domain_raw:
        return slug_raw

    # Domain may arrive as "store.example.com" or "https://store.example.com".
    if not domain_raw.startswith(("http://", "https://")):
        domain_raw = f"https://{domain_raw}"
    base = domain_raw.rstrip("/")

    if not slug_raw.startswith("/"):
        slug_raw = "/" + slug_raw
    return f"{base}{slug_raw}"


# ---------------------------------------------------------------------------
# Categories + brand
# ---------------------------------------------------------------------------


def resolve_primary_category(
    raw: dict[str, Any], categories_map: dict[int, str] | None
) -> str:
    """Resolve the first category id on a BC product to its display name.

    BigCommerce returns ``categories: [18, 23, 41]`` (a list of category
    ids). We pick the first id that resolves through ``categories_map``
    (built once during the connector bootstrap from ``GET /v3/catalog/
    categories``); duplicates and unresolved ids are silently skipped.
    """
    cats_map = categories_map or {}
    raw_ids = raw.get("categories") or []
    if not isinstance(raw_ids, list):
        return ""
    for cat_id in raw_ids:
        try:
            key = int(cat_id)
        except (TypeError, ValueError):
            continue
        name = cats_map.get(key)
        if name:
            return str(name)
    return ""


def resolve_brand_name(
    raw: dict[str, Any], brands_map: dict[int, str] | None
) -> str:
    brands = brands_map or {}
    brand_id = raw.get("brand_id")
    if brand_id in (None, 0):
        return ""
    try:
        key = int(brand_id)
    except (TypeError, ValueError):
        return ""
    return str(brands.get(key) or "")


# ---------------------------------------------------------------------------
# Tags — search_keywords + custom_fields
# ---------------------------------------------------------------------------


def extract_tags(raw: dict[str, Any]) -> list[str]:
    """Build a deduped tag list from ``search_keywords`` + ``custom_fields``.

    BigCommerce stores ``search_keywords`` as a comma-separated string and
    exposes a separate ``custom_fields`` array of ``{name, value}`` rows.
    Both are surfaced verbatim — channel-specific tag mapping happens
    further down the pipeline.
    """
    tags: list[str] = []

    raw_keywords = raw.get("search_keywords")
    if isinstance(raw_keywords, str) and raw_keywords.strip():
        for token in raw_keywords.split(","):
            cleaned = token.strip()
            if cleaned and cleaned not in tags:
                tags.append(cleaned)

    custom_fields = raw.get("custom_fields") or []
    if isinstance(custom_fields, list):
        for field in custom_fields:
            if not isinstance(field, dict):
                continue
            name = str(field.get("name") or "").strip()
            value = str(field.get("value") or "").strip()
            if not name or not value:
                continue
            tag = f"{name}:{value}"
            if tag not in tags:
                tags.append(tag)
    return tags


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def normalize_variants(
    variants: list[dict[str, Any]] | None,
    *,
    fallback_price: float = 0.0,
) -> list[ProductVariant]:
    """Project BigCommerce V3 variants onto :class:`ProductVariant`.

    Variants inherit pricing from the parent when their own ``price`` field
    is null or zero (BC's "use product price" convention). The same
    BC-vs-Shopify price flip from :func:`normalize_price` applies per
    variant.
    """
    if not variants or not isinstance(variants, list):
        return []

    out: list[ProductVariant] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue

        raw_price = variant.get("price")
        # When the variant doesn't override price, BC returns null/0.0; the
        # caller's parent price is the effective base.
        base_price = (
            _safe_float(raw_price)
            if raw_price not in (None, "", 0, 0.0)
            else _safe_float(fallback_price)
        )
        display_price, compare_at = normalize_price(
            base_price, variant.get("sale_price")
        )

        title_parts: list[str] = []
        for option in variant.get("option_values") or []:
            if not isinstance(option, dict):
                continue
            label = str(option.get("label") or "").strip()
            if label:
                title_parts.append(label)
        title = " / ".join(title_parts)

        out.append(
            ProductVariant(
                sku=str(variant.get("sku") or ""),
                title=title,
                price=display_price,
                compare_at_price=compare_at,
                inventory_quantity=_safe_int(variant.get("inventory_level")),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Raw-data flattener (symmetry with WooCommerce / Magento / Shopify pattern)
# ---------------------------------------------------------------------------


_SCALAR_KEYS_TO_COPY = (
    "id",
    "sku",
    "name",
    "type",
    "price",
    "sale_price",
    "retail_price",
    "cost_price",
    "weight",
    "width",
    "depth",
    "height",
    "is_visible",
    "is_featured",
    "availability",
    "inventory_level",
    "inventory_tracking",
    "brand_id",
    "date_created",
    "date_modified",
    "mpn",
    "gtin",
    "upc",
    "ean",
    "isbn",
    "condition",
)


def flatten_raw(
    raw: dict[str, Any],
    *,
    brand_name: str | None = None,
    category_name: str | None = None,
) -> dict[str, Any]:
    """Extract a flat presentable dict of raw BigCommerce fields.

    Used to populate ``ProductData.raw_data``. Mirrors the ``flatten_raw``
    helpers in the Magento / Shopify connectors — scalar top-level fields
    copy through verbatim, while a few resolved derivations (brand and
    category names) are hoisted in for easier channel export mapping.
    """
    flat: dict[str, Any] = {}
    for key in _SCALAR_KEYS_TO_COPY:
        if key in raw:
            flat[key] = raw[key]

    description = raw.get("description")
    if isinstance(description, str) and description:
        flat["description"] = strip_html(description)

    if brand_name:
        flat["brand"] = brand_name
    if category_name:
        flat["category"] = category_name

    images = raw.get("images")
    if isinstance(images, list) and images:
        flat["image_count"] = len(images)

    custom_url = raw.get("custom_url")
    if isinstance(custom_url, dict) and custom_url.get("url"):
        flat["custom_url"] = str(custom_url.get("url") or "")

    return flat


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def normalize_bigcommerce_product(
    raw: dict[str, Any],
    *,
    store_domain: str,
    currency: str,
    categories_map: dict[int, str] | None = None,
    brands_map: dict[int, str] | None = None,
) -> ProductData:
    """Convert a BigCommerce V3 product payload into a :class:`ProductData` row.

    The connector should fetch products with ``?include=variants,images,
    custom_fields`` so the variants/images/custom_fields arrays are
    populated inline — that's where the call savings vs. Magento come
    from (no per-product follow-up requests).
    """
    categories_map = categories_map or {}
    brands_map = brands_map or {}

    product_id = str(raw.get("id") or raw.get("sku") or "")
    title = str(raw.get("name") or "")

    description_raw = raw.get("description") or ""
    description = (
        strip_html(str(description_raw)) if description_raw else ""
    )

    display_price, compare_at = normalize_price(
        raw.get("price"), raw.get("sale_price")
    )

    images = extract_image_urls(raw.get("images"))
    category = resolve_primary_category(raw, categories_map)
    brand_name = resolve_brand_name(raw, brands_map)
    tags = extract_tags(raw)
    if brand_name and brand_name not in tags:
        tags.insert(0, brand_name)

    variants = normalize_variants(
        raw.get("variants"),
        fallback_price=display_price,
    )

    inventory = _safe_int(raw.get("inventory_level"))
    sku = str(raw.get("sku") or "")
    url = build_product_url(store_domain, raw.get("custom_url"))

    return ProductData(
        id=product_id,
        title=title,
        description=description,
        price=display_price,
        compare_at_price=compare_at,
        currency=str(currency or "USD"),
        images=images,
        variants=variants,
        category=category,
        tags=tags,
        inventory_quantity=inventory,
        sku=sku,
        url=url,
        raw_data=flatten_raw(raw, brand_name=brand_name, category_name=category),
    )
