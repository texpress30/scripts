"""Feed generator: transforms products through master mappings + channel
overrides, formats them as XML/CSV/JSON, and uploads to S3."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring, register_namespace
from xml.sax.saxutils import escape as xml_escape

# Regex to strip XML-invalid control characters (keeps \t, \n, \r)
_XML_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Regex for characters invalid in XML element names
_XML_TAG_INVALID_RE = re.compile(r"[^a-zA-Z0-9_.\-]")


def _sanitize_xml_value(value: Any) -> str:
    """Convert a value to an XML-safe escaped string."""
    if value is None:
        return ""
    text = str(value)
    text = _XML_CONTROL_CHARS_RE.sub("", text)
    return xml_escape(text)


def _sanitize_xml_tag(name: str) -> str:
    """Convert a field name to a valid XML element name."""
    tag = name.replace(" ", "_")
    tag = _XML_TAG_INVALID_RE.sub("_", tag)
    if tag and tag[0].isdigit():
        tag = f"_{tag}"
    return tag or "_unknown"

from pydantic import BaseModel


# Regex to strip XML-invalid control characters (keeps \t, \n, \r)
_XML_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Regex for valid XML element name: starts with letter or _, then letters/digits/_/-/.
_XML_TAG_INVALID_RE = re.compile(r"[^a-zA-Z0-9_.\-]")


def _sanitize_xml_value(value: Any) -> str:
    """Convert a value to an XML-safe escaped string.

    - Converts to string
    - Strips control characters invalid in XML
    - Escapes &, <, >
    """
    if value is None:
        return ""
    text = str(value)
    text = _XML_CONTROL_CHARS_RE.sub("", text)
    return xml_escape(text)


def _sanitize_xml_tag(name: str) -> str:
    """Convert a field name to a valid XML element name.

    - Replaces spaces with underscores
    - Strips characters invalid in XML element names
    - Prepends underscore if name starts with a digit
    """
    tag = name.replace(" ", "_")
    tag = _XML_TAG_INVALID_RE.sub("_", tag)
    if tag and tag[0].isdigit():
        tag = f"_{tag}"
    return tag or "_unknown"

from app.services.feed_management.channels.models import (
    ChannelType,
    FeedFormat,
)

logger = logging.getLogger(__name__)

# Google namespace for RSS feeds (Google Shopping, TikTok, etc.)
GOOGLE_NS = "http://base.google.com/ns/1.0"
register_namespace("g", GOOGLE_NS)

_XML_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_XML_TAG_INVALID_RE = re.compile(r"[^a-zA-Z0-9_\-]")
_MAX_XML_TEXT_LENGTH = 5000

# Channel types that use Meta's <listings><listing> format
_META_LISTINGS_TYPES = frozenset({
    ChannelType.facebook_product_ads,
    ChannelType.facebook_catalog_vehicles,
    ChannelType.facebook_catalog_vehicle_offer,
    ChannelType.facebook_automotive,  # legacy
    ChannelType.facebook_country,
    ChannelType.facebook_language,
    ChannelType.facebook_marketplace,
    ChannelType.facebook_hotel,
    ChannelType.facebook_streaming_ads,
    ChannelType.facebook_destination_ads,
    ChannelType.facebook_professional_services,
    ChannelType.meta_catalog,
})

# Channel types that use Google's RSS 2.0 with g: namespace
_GOOGLE_RSS_TYPES = frozenset({
    ChannelType.google_shopping,
    ChannelType.google_vehicle_ads_v3,
    ChannelType.google_vehicle_listings,
    ChannelType.google_local_inventory,
    ChannelType.google_product_reviews,
    ChannelType.google_regional_inventory,
    ChannelType.google_manufacturers,
    ChannelType.google_hotel_ads,
    ChannelType.google_real_estate,
    ChannelType.google_jobs,
    ChannelType.google_things_to_do,
})

# Mapping between ChannelType enum values and schema registry channel_slugs.
# The schema registry may store fields under a different slug than the enum value
# (e.g. templates imported as "facebook_catalog_vehicles" but enum is "facebook_automotive").
# _load_field_specs tries each slug in order and returns the first match.
_CHANNEL_TYPE_SLUG_MAP: dict[str, list[str]] = {
    # Meta Vehicles catalog (new + legacy)
    "facebook_catalog_vehicles": ["facebook_catalog_vehicles"],
    "facebook_automotive": ["facebook_catalog_vehicles", "facebook_automotive"],
    # Meta Vehicle Offers catalog
    "facebook_catalog_vehicle_offer": ["facebook_catalog_vehicle_offer"],
    # facebook_product_ads NOT in map — stays e-commerce only, direct slug lookup
    # TikTok slugs match directly — no mapping needed
    # tiktok_automotive_inventory, tiktok_automotive_model use direct slug lookup
}

# Pattern matching image URL/tag fields: image_0_url, image[0].url, image_0_tag, etc.
# After _apply_field_specs, keys may be raw channel_field_names like "image[0].url"
# or sanitized canonical names like "image_0_url". Match both.
_IMAGE_URL_RE = re.compile(r"^image[^a-zA-Z0-9]*(\d+)[^a-zA-Z0-9]*(?:url|link)", re.IGNORECASE)
_IMAGE_TAG_RE = re.compile(r"^image[^a-zA-Z0-9]*(\d+)[^a-zA-Z0-9]*tag", re.IGNORECASE)
_IMAGE_FIELD_RE = re.compile(r"^image", re.IGNORECASE)

# Matches indexed nested fields like video[0].url, features[1].value
_INDEXED_NESTED_RE = re.compile(r"^(\w+)\[(\d+)\]\.(.+)$")


def _sanitize_xml_value(value: Any) -> str:
    """Strip control chars and truncate for XML text content."""
    if value is None:
        return ""
    text = _XML_CONTROL_CHARS_RE.sub("", str(value))
    if len(text) > _MAX_XML_TEXT_LENGTH:
        text = text[:_MAX_XML_TEXT_LENGTH].rsplit(" ", 1)[0] + "..."
    return text


def _sanitize_xml_tag(name: str) -> str:
    """Convert a field name to a valid XML element name."""
    tag = name.replace(" ", "_")
    tag = _XML_TAG_INVALID_RE.sub("_", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    if tag and tag[0].isdigit():
        tag = f"n{tag}"
    return tag or "unknown"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

class FeedResult(BaseModel):
    channel_id: str
    status: str  # "ok" | "error"
    included_products: int = 0
    excluded_products: int = 0
    s3_key: str | None = None
    feed_url: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Feed Generator
# ---------------------------------------------------------------------------

class FeedGenerator:

    def generate(self, channel_id: str) -> FeedResult:
        """Full pipeline: fetch → transform → format → upload → update metadata."""
        from app.services.feed_management.channels.repository import (
            feed_channel_repository,
        )
        from app.services.feed_management.master_fields.repository import (
            master_field_mapping_repository,
        )
        from app.services.feed_management.products_repository import (
            feed_products_repository,
        )

        try:
            # 1. Load channel + overrides
            channel = feed_channel_repository.get_by_id(channel_id)
            overrides = feed_channel_repository.get_overrides(channel_id)

            # 2. Load master mappings
            master_mappings = master_field_mapping_repository.get_by_source(
                channel.feed_source_id,
            )

            # 2b. Load schema registry field specs for this channel
            field_specs = self._load_field_specs(
                channel.channel_type.value, channel.feed_source_id,
            )

            # 3. Fetch all products from MongoDB
            raw_products = feed_products_repository.list_products(
                channel.feed_source_id, limit=200,
            )

            # 4. Transform each product
            override_map = {o.target_field: o for o in overrides}
            transformed: list[dict[str, Any]] = []
            excluded = 0

            for product in raw_products:
                data = product.get("data", {})
                if not isinstance(data, dict):
                    excluded += 1
                    continue
                data = self._merge_raw_data(data)

                row = self._transform_product(data, master_mappings, override_map)
                if row:
                    row = self._apply_field_specs(row, field_specs, product.get("product_id"))
                    transformed.append(row)
                else:
                    excluded += 1

            # 4b. Apply Meta-specific value transforms (mileage, price, etc.)
            #     so both XML and CSV outputs get correct formatting.
            if channel.channel_type in _META_LISTINGS_TYPES:
                transformed = [self._format_meta_values(row) for row in transformed]

            # 5. Format feed
            content = self._format_feed(
                transformed, channel.channel_type, channel.feed_format,
                channel=channel,
            )

            # 6. Upload to S3
            ext = channel.feed_format.value
            s3_key = f"channel-feeds/{channel.feed_source_id}/{channel_id}/feed.{ext}"
            if channel.feed_format == FeedFormat.xml and channel.channel_type != ChannelType.custom:
                content_type = "application/rss+xml; charset=utf-8"
            else:
                content_type = self._content_type(channel.feed_format)
            self._upload_to_s3(s3_key, content, content_type)

            # 7. Build public feed URL
            feed_url = f"/feeds/{channel.public_token}.{ext}"

            # 8. Update channel metadata
            feed_channel_repository.update_metadata(channel_id, {
                "status": "active",
                "s3_key": s3_key,
                "feed_url": feed_url,
                "included_products": len(transformed),
                "excluded_products": excluded,
                "last_generated_at": _utcnow(),
                "error_message": None,
            })

            return FeedResult(
                channel_id=channel_id,
                status="ok",
                included_products=len(transformed),
                excluded_products=excluded,
                s3_key=s3_key,
                feed_url=feed_url,
            )

        except Exception as exc:
            logger.exception("Feed generation failed for channel %s", channel_id)
            try:
                from app.services.feed_management.channels.repository import (
                    feed_channel_repository as repo,
                )
                repo.update_metadata(channel_id, {
                    "status": "error",
                    "error_message": str(exc)[:500],
                })
            except Exception:
                logger.exception("Failed to update channel error status")

            return FeedResult(
                channel_id=channel_id,
                status="error",
                error_message=str(exc)[:500],
            )

    # ------------------------------------------------------------------
    # Schema registry integration
    # ------------------------------------------------------------------

    @staticmethod
    def _load_field_specs(
        channel_slug: str,
        feed_source_id: str,
    ) -> list[dict[str, Any]] | None:
        """Load field specs from schema registry.  Returns None on fallback."""
        try:
            from app.services.feed_management.schema_registry.repository import (
                schema_registry_repository,
            )
            from app.services.feed_management.repository import FeedSourceRepository

            source = FeedSourceRepository().get_by_id(feed_source_id)
            catalog_type = source.catalog_type if hasattr(source, "catalog_type") else "product"

            # Try mapped slugs first (e.g. facebook_automotive → facebook_catalog_vehicles),
            # then fall back to the direct channel_slug.
            slugs_to_try = _CHANNEL_TYPE_SLUG_MAP.get(channel_slug, [channel_slug])
            for slug in slugs_to_try:
                specs = schema_registry_repository.get_channel_field_specs(
                    slug, catalog_type,
                )
                if specs:
                    logger.info(
                        "Loaded %d field specs for channel=%s (resolved slug=%s, catalog=%s)",
                        len(specs), channel_slug, slug, catalog_type,
                    )
                    return specs

            logger.warning(
                "No schema registry data for channel=%s (tried slugs=%s, catalog_type=%s). "
                "Using hardcoded fields.",
                channel_slug, slugs_to_try, catalog_type,
            )
            return None
        except Exception:
            logger.debug("Schema registry lookup failed, using fallback", exc_info=True)
            return None

    @staticmethod
    def _apply_field_specs(
        row: dict[str, Any],
        field_specs: list[dict[str, Any]] | None,
        product_id: Any = None,
    ) -> dict[str, Any]:
        """Rename keys from field_key → channel_field_name, validate, and
        filter to only channel-registered fields.

        If *field_specs* is None (fallback mode) the row is returned unchanged.
        """
        if field_specs is None:
            return row

        spec_map = {s["field_key"]: s for s in field_specs}
        result: dict[str, Any] = {}

        for spec in field_specs:
            fk = spec["field_key"]
            out_name = spec["channel_field_name"]
            value = row.get(fk)

            # Default value for required fields with no value
            if value is None and spec.get("is_required") and spec.get("default_value"):
                value = spec["default_value"]

            # Log missing required field (info-level — data quality, not app error)
            if value is None and spec.get("is_required"):
                logger.info(
                    "Required field %s is empty for product %s", fk, product_id,
                )

            # Enum validation
            allowed = spec.get("allowed_values")
            if value is not None and allowed and isinstance(allowed, list):
                if str(value) not in [str(a) for a in allowed]:
                    logger.info(
                        "Field %s value '%s' not in allowed_values %s for product %s",
                        fk, value, allowed, product_id,
                    )

            # Regex validation
            pattern = spec.get("format_pattern")
            if value is not None and pattern:
                try:
                    if not re.match(pattern, str(value)):
                        logger.info(
                            "Field %s value '%s' does not match pattern '%s' for product %s",
                            fk, value, pattern, product_id,
                        )
                except re.error:
                    pass  # invalid regex — skip validation

            if value is not None:
                result[out_name] = value

        # Also include any extra mapped fields not in spec (from master_mappings)
        # so we don't lose data that the user explicitly mapped.
        # Skip keys already in result — spec-renamed fields take precedence.
        for key, value in row.items():
            if key not in spec_map and key not in result and value is not None:
                result[key] = value

        return result

    @staticmethod
    def _format_meta_values(row: dict[str, Any]) -> dict[str, Any]:
        """Apply Meta-specific value transforms so both XML and CSV are correct.

        - mileage.value → integer (no decimals)
        - mileage.unit → uppercase (KM not km)
        - price/sale_price/etc. → append currency if numeric-only
        """
        result = dict(row)
        # Mileage transforms
        if "mileage.value" in result and result["mileage.value"] is not None:
            try:
                result["mileage.value"] = str(int(float(result["mileage.value"])))
            except (ValueError, TypeError):
                pass
        if "mileage.unit" in result and result["mileage.unit"] is not None:
            result["mileage.unit"] = str(result["mileage.unit"]).upper()
        # Price transforms — append currency if missing
        currency = str(result.get("currency", "EUR"))
        for price_key in ("price", "sale_price", "previous_price", "msrp"):
            if price_key in result and result[price_key] is not None:
                val = str(result[price_key])
                if re.match(r"^\d+\.?\d*$", val):
                    result[price_key] = f"{val} {currency}"
        return result

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    def _transform_product(
        self,
        data: dict[str, Any],
        master_mappings: list,
        override_map: dict[str, Any],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for mapping in master_mappings:
            target = mapping.target_field
            # Check override first
            override = override_map.get(target)
            if override:
                value = self._apply_mapping(
                    data,
                    override.source_field,
                    override.mapping_type.value,
                    override.static_value,
                    override.template_value,
                )
            else:
                value = self._apply_mapping(
                    data,
                    mapping.source_field,
                    mapping.mapping_type.value,
                    mapping.static_value,
                    mapping.template_value,
                )

            if value is not None:
                result[target] = value

        return result

    def _apply_mapping(
        self,
        data: dict[str, Any],
        source_field: str | None,
        mapping_type: str,
        static_value: str | None,
        template_value: str | None,
    ) -> Any:
        if mapping_type == "static":
            return static_value

        if mapping_type == "template" and template_value:
            return self._render_template(data, template_value)

        # direct
        if not source_field:
            return None
        return self._resolve_source(data, source_field)

    @staticmethod
    def _merge_raw_data(data: dict[str, Any]) -> dict[str, Any]:
        """Merge raw_data fields into the top-level data dict.

        Raw fields are added only when they don't conflict with an existing
        standardized key, so mappings can reference both standardized names
        (``title``) and raw source names (``body_html``, ``vendor``, …).

        Safety nets applied during merge:
        - HTML stripped from description fields (stale data from before strip fix)
        - Images array flattened into image_N_url/tag fields (stale data
          or data synced before flatten feature; always re-applies current
          tag rules so updated defaults take effect immediately)
        """
        from app.services.feed_management.connectors.base import flatten_images, strip_html

        raw = data.get("raw_data")
        if not isinstance(raw, dict):
            return data
        merged = dict(data)
        # Strip HTML from descriptions (safety net for data synced before strip fix)
        for dk in ("description", "short_description"):
            if dk in merged and isinstance(merged[dk], str) and "<" in merged[dk]:
                merged[dk] = strip_html(merged[dk])
        for key, value in raw.items():
            if key not in merged:
                merged[key] = value
        merged.pop("raw_data", None)
        # Flatten images — always re-apply to ensure current tag rules are used
        if "images" in merged:
            flatten_images(merged)
        return merged

    @staticmethod
    def _resolve_source(data: dict[str, Any], source_field: str) -> Any:
        parts = source_field.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if current is None:
                return None
        return current

    @staticmethod
    def _render_template(data: dict[str, Any], template: str) -> str:
        """Replace ``{{field_name}}`` placeholders with values from data."""
        def _replacer(match: re.Match) -> str:
            field = match.group(1).strip()
            value = data.get(field)
            return str(value) if value is not None else ""

        return re.sub(r"\{\{(.+?)\}\}", _replacer, template)

    # ------------------------------------------------------------------
    # Format
    # ------------------------------------------------------------------

    def _format_feed(
        self,
        products: list[dict[str, Any]],
        channel_type: ChannelType,
        feed_format: FeedFormat,
        channel: Any = None,
    ) -> str:
        if feed_format == FeedFormat.csv:
            return self._format_csv(products)
        if feed_format == FeedFormat.tsv:
            return self._format_csv(products, delimiter="\t")
        if feed_format == FeedFormat.json:
            return json.dumps({"items": products}, ensure_ascii=False, indent=2)

        # XML routing by channel type:
        # - Meta channels → <listings><listing> (no namespace)
        # - Google channels → RSS 2.0 <rss><channel><item> with g: namespace
        # - Everything else → RSS 2.0 (safe default for TikTok, Bing, etc.)
        # - Custom → generic <feed><entry>
        logger.info(
            "feed.format_xml: channel_type=%s (%s) → %s",
            channel_type, type(channel_type).__name__,
            "meta_listings" if channel_type in _META_LISTINGS_TYPES
            else "rss" if channel_type != ChannelType.custom
            else "generic",
        )
        if channel_type in _META_LISTINGS_TYPES:
            return self._format_meta_listings_xml(products, channel)
        if channel_type == ChannelType.custom:
            return self._format_xml(products)
        return self._format_rss_xml(products, channel)

    # ------------------------------------------------------------------
    # Meta Vehicle Offers: <listings><listing> — no namespace
    # ------------------------------------------------------------------

    def _format_meta_listings_xml(
        self,
        products: list[dict[str, Any]],
        channel: Any = None,
    ) -> str:
        """Generate Meta Vehicle Offers XML: <listings><listing>."""
        root = Element("listings")
        SubElement(root, "title").text = (channel.name if channel else None) or "Vehicle Offers Feed"

        for product in products:
            listing = SubElement(root, "listing")

            # 1. Collect image URL/tag pairs from product dict.
            #    Keys may be canonical (image_0_url) or raw channel names
            #    (image[0].url) — match by regex, pair by index.
            image_urls: dict[int, str] = {}
            image_tags: dict[int, str] = {}
            image_keys: set[str] = set()

            for key, val in product.items():
                if val is None:
                    continue
                m_url = _IMAGE_URL_RE.match(key)
                m_tag = _IMAGE_TAG_RE.match(key)
                if m_url:
                    image_urls[int(m_url.group(1))] = str(val)
                    image_keys.add(key)
                elif m_tag:
                    image_tags[int(m_tag.group(1))] = str(val)
                    image_keys.add(key)
                elif _IMAGE_FIELD_RE.match(key):
                    image_keys.add(key)

            # Render nested <image> elements FIRST (Meta template order)
            for idx in sorted(image_urls.keys()):
                image_el = SubElement(listing, "image")
                SubElement(image_el, "url").text = _sanitize_xml_value(image_urls[idx])
                tag_val = image_tags.get(idx)
                if tag_val:
                    SubElement(image_el, "tag").text = _sanitize_xml_value(tag_val)

            # Fallback: use image_link if no indexed images found
            if not image_urls:
                img_link = product.get("image_link")
                if img_link:
                    image_el = SubElement(listing, "image")
                    SubElement(image_el, "url").text = _sanitize_xml_value(img_link)

            # 2. Group dot-notation keys into nested structures.
            #    e.g. {"address.addr1": "X", "address.city": "Y"}
            #      → <address><addr1>X</addr1><city>Y</city></address>
            nested_groups: dict[str, dict[str, str]] = {}
            nested_keys: set[str] = set()

            # 3. Group indexed nested fields (e.g. video[0].url, features[1].value)
            indexed_groups: dict[str, dict[int, dict[str, str]]] = {}
            indexed_keys: set[str] = set()

            for field_name, value in product.items():
                if value is None or field_name in image_keys:
                    continue
                # Check indexed nested first (e.g. video[0].url)
                m = _INDEXED_NESTED_RE.match(field_name)
                if m:
                    parent, idx, child = m.group(1), int(m.group(2)), m.group(3)
                    if parent.lower() != "image":  # images handled above
                        indexed_groups.setdefault(parent, {}).setdefault(idx, {})[child] = str(value)
                        indexed_keys.add(field_name)
                    continue
                # Check dot-notation nested (e.g. address.city)
                if "." in field_name:
                    parts = field_name.split(".", 1)
                    nested_groups.setdefault(parts[0], {})[parts[1]] = str(value)
                    nested_keys.add(field_name)

            # Render dot-notation nested elements
            for parent, children in nested_groups.items():
                parent_el = SubElement(listing, _sanitize_xml_tag(parent))
                for child_key, child_val in children.items():
                    val_str = _sanitize_xml_value(child_val)
                    if val_str.strip():
                        SubElement(parent_el, _sanitize_xml_tag(child_key)).text = val_str

            # Render indexed nested elements
            for parent, indices in indexed_groups.items():
                for idx in sorted(indices.keys()):
                    parent_el = SubElement(listing, _sanitize_xml_tag(parent))
                    for child_key, child_val in indices[idx].items():
                        val_str = _sanitize_xml_value(child_val)
                        if val_str.strip():
                            SubElement(parent_el, _sanitize_xml_tag(child_key)).text = val_str

            # Collect nested parent tag names to avoid flat duplicates (A1)
            nested_parents = {_sanitize_xml_tag(p) for p in nested_groups}
            nested_parents |= {_sanitize_xml_tag(p) for p in indexed_groups}

            # 4. Flat fields — skip image, nested, indexed keys, and
            #    flat keys whose tag collides with a nested parent.
            for field_name, value in product.items():
                if value is None:
                    continue
                if field_name in image_keys or field_name in nested_keys or field_name in indexed_keys:
                    continue
                tag = _sanitize_xml_tag(str(field_name))
                # Skip flat field if a nested parent with same tag exists
                if tag in nested_parents:
                    continue
                val_str = _sanitize_xml_value(value)
                if not val_str.strip():
                    continue
                SubElement(listing, tag).text = val_str

        xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(root, encoding="unicode")
        self._validate_xml(xml_str)
        return xml_str

    # ------------------------------------------------------------------
    # Google RSS 2.0: <rss><channel><item> with g: namespace
    # ------------------------------------------------------------------

    def _format_rss_xml(
        self,
        products: list[dict[str, Any]],
        channel: Any = None,
    ) -> str:
        """Generate RSS 2.0 XML with g: namespace (Google/TikTok/Bing)."""
        rss = Element("rss", {"version": "2.0"})
        ch_el = SubElement(rss, "channel")
        SubElement(ch_el, "title").text = (channel.name if channel else None) or "Product Feed"
        SubElement(ch_el, "link").text = "https://api.omarosa.ro"
        SubElement(ch_el, "description").text = "Automotive inventory feed"

        for product in products:
            item = SubElement(ch_el, "item")
            for field_name, value in product.items():
                if value is None:
                    continue
                val_str = _sanitize_xml_value(value)
                if not val_str.strip():
                    continue
                tag = _sanitize_xml_tag(str(field_name))
                SubElement(item, f"{{{GOOGLE_NS}}}{tag}").text = val_str

        xml_str = tostring(rss, encoding="unicode")
        self._validate_xml(xml_str)
        return xml_str

    # ------------------------------------------------------------------
    # Generic XML: <feed><entry> — only for custom channels
    # ------------------------------------------------------------------

    def _format_xml(self, products: list[dict[str, Any]]) -> str:
        """Generic XML feed — only used for custom channels."""
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<feed count="{len(products)}">',
        ]
        for product in products:
            lines.append("  <entry>")
            for field, value in product.items():
                if value is None:
                    continue
                tag = _sanitize_xml_tag(str(field))
                lines.append(f"    <{tag}>{xml_escape(_sanitize_xml_value(value))}</{tag}>")
            lines.append("  </entry>")
        lines.append("</feed>")
        return "\n".join(lines)

    @staticmethod
    def _validate_xml(xml_str: str) -> None:
        """Validate XML with fromstring — raises on invalid."""
        try:
            fromstring(xml_str)
        except Exception as exc:
            logger.error("Generated XML is invalid: %s", exc)
            raise ValueError(f"Generated XML is invalid: {exc}") from exc

    def _format_csv(
        self, products: list[dict[str, Any]], delimiter: str = ","
    ) -> str:
        if not products:
            return ""
        all_keys: list[str] = []
        seen: set[str] = set()
        for p in products:
            for k in p:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=all_keys, delimiter=delimiter, extrasaction="ignore",
        )
        writer.writeheader()
        for product in products:
            row = {k: str(v) if v is not None else "" for k, v in product.items()}
            writer.writerow(row)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # S3
    # ------------------------------------------------------------------

    @staticmethod
    def _upload_to_s3(s3_key: str, content: str, content_type: str) -> None:
        from app.services.s3_provider import get_s3_bucket_name, get_s3_client

        client = get_s3_client()
        bucket = get_s3_bucket_name()
        client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
            CacheControl="no-cache, must-revalidate",
        )

    @staticmethod
    def _content_type(fmt: FeedFormat) -> str:
        return {
            FeedFormat.xml: "application/xml; charset=utf-8",
            FeedFormat.csv: "text/csv; charset=utf-8",
            FeedFormat.tsv: "text/tab-separated-values; charset=utf-8",
            FeedFormat.json: "application/json; charset=utf-8",
        }.get(fmt, "application/octet-stream")

    # ------------------------------------------------------------------
    # Preview (no S3 upload)
    # ------------------------------------------------------------------

    def preview(self, channel_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Transform a few products without uploading — for UI preview."""
        from app.services.feed_management.channels.repository import (
            feed_channel_repository,
        )
        from app.services.feed_management.master_fields.repository import (
            master_field_mapping_repository,
        )
        from app.services.feed_management.products_repository import (
            feed_products_repository,
        )

        channel = feed_channel_repository.get_by_id(channel_id)
        overrides = feed_channel_repository.get_overrides(channel_id)
        master_mappings = master_field_mapping_repository.get_by_source(
            channel.feed_source_id,
        )
        field_specs = self._load_field_specs(
            channel.channel_type.value, channel.feed_source_id,
        )
        raw_products = feed_products_repository.list_products(
            channel.feed_source_id, limit=limit,
        )

        override_map = {o.target_field: o for o in overrides}
        results: list[dict[str, Any]] = []
        for product in raw_products[:limit]:
            data = product.get("data", {})
            if not isinstance(data, dict):
                continue
            data = self._merge_raw_data(data)
            transformed = self._transform_product(data, master_mappings, override_map)
            transformed = self._apply_field_specs(transformed, field_specs, product.get("product_id"))
            results.append({"original": data, "transformed": transformed})
        return results


feed_generator = FeedGenerator()
