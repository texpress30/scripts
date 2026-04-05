"""Feed formatter: converts product lists to XML, JSON, CSV.

Includes channel-specific formats for Google Shopping (RSS 2.0 with g: namespace)
and Meta Catalog (CSV with required columns per catalog type).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring, register_namespace
from xml.sax.saxutils import escape as xml_escape

logger = logging.getLogger(__name__)

GOOGLE_NS = "http://base.google.com/ns/1.0"
register_namespace("g", GOOGLE_NS)

_XML_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_XML_TAG_INVALID_RE = re.compile(r"[^a-zA-Z0-9_\-]")
_MAX_XML_TEXT_LENGTH = 5000
_IMAGE_FIELD_PREFIX = "image_"


def _sanitize_xml_tag(name: str) -> str:
    tag = name.replace(" ", "_")
    tag = _XML_TAG_INVALID_RE.sub("_", tag)
    tag = re.sub(r"_+", "_", tag).strip("_")
    if tag and tag[0].isdigit():
        tag = f"n{tag}"
    return tag or "unknown"


def _sanitize_text(text: str) -> str:
    text = _XML_CONTROL_CHARS_RE.sub("", text)
    if len(text) > _MAX_XML_TEXT_LENGTH:
        text = text[:_MAX_XML_TEXT_LENGTH].rsplit(" ", 1)[0] + "..."
    return text

# ---------------------------------------------------------------------------
# Google Shopping required/optional fields
# ---------------------------------------------------------------------------

_GOOGLE_SHOPPING_FIELDS = [
    "id", "title", "description", "link", "image_link",
    "availability", "price", "brand", "condition", "gtin",
    "mpn", "google_product_category", "product_type",
    "additional_image_link", "sale_price", "sale_price_effective_date",
    "item_group_id", "color", "size", "gender", "age_group",
    "material", "pattern", "shipping", "tax",
    "custom_label_0", "custom_label_1", "custom_label_2",
    "custom_label_3", "custom_label_4",
]

# ---------------------------------------------------------------------------
# Meta Catalog fields per catalog type
# ---------------------------------------------------------------------------

_META_PRODUCT_FIELDS = [
    "id", "title", "description", "availability", "condition",
    "price", "link", "image_link", "brand", "additional_image_link",
    "age_group", "color", "gender", "item_group_id", "google_product_category",
    "material", "pattern", "product_type", "sale_price",
    "sale_price_effective_date", "shipping", "size",
    "custom_label_0", "custom_label_1", "custom_label_2",
    "custom_label_3", "custom_label_4",
]

_META_VEHICLE_FIELDS = [
    "vehicle_id", "title", "url", "image", "make", "model", "year",
    "mileage.value", "mileage.unit", "body_style", "drivetrain",
    "condition", "price", "exterior_color", "transmission",
    "fuel_type", "vin", "description", "availability",
    "state_of_vehicle", "sale_price",
]

_META_HOTEL_FIELDS = [
    "hotel_id", "name", "description", "brand", "url", "image",
    "address.addr1", "address.city", "address.region",
    "address.country", "address.postal_code",
    "latitude", "longitude", "star_rating", "phone", "price",
]

_META_HOME_LISTING_FIELDS = [
    "home_listing_id", "name", "availability", "description",
    "image", "url", "address.addr1", "address.city",
    "address.region", "address.country", "address.postal_code",
    "latitude", "longitude", "price", "num_beds", "num_baths",
    "area_size", "area_unit", "property_type", "listing_type",
]

_META_CATALOG_FIELDS: dict[str, list[str]] = {
    "product": _META_PRODUCT_FIELDS,
    "vehicle": _META_VEHICLE_FIELDS,
    "vehicle_offer": _META_VEHICLE_FIELDS,
    "hotel": _META_HOTEL_FIELDS,
    "hotel_room": _META_HOTEL_FIELDS,
    "home_listing": _META_HOME_LISTING_FIELDS,
}


class FeedFormatter:
    """Stateless formatter — all methods are pure functions on product lists."""

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def format_as_json(self, products: list[dict[str, Any]]) -> str:
        """Return pretty-printed JSON array of products."""
        return json.dumps(products, indent=2, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------
    # Generic XML
    # ------------------------------------------------------------------

    def format_as_xml(self, products: list[dict[str, Any]], catalog_type: str = "product") -> str:
        """Return a simple XML feed with <products> root."""
        root = Element("products")
        root.set("catalog_type", catalog_type)
        root.set("count", str(len(products)))
        for product in products:
            item_el = SubElement(root, "product")
            self._dict_to_xml(item_el, product)
        return self._xml_to_string(root)

    # ------------------------------------------------------------------
    # Generic CSV
    # ------------------------------------------------------------------

    def format_as_csv(self, products: list[dict[str, Any]]) -> str:
        """Return CSV with a header row derived from the union of all product keys."""
        if not products:
            return ""
        all_keys = self._collect_keys(products)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for product in products:
            flat = self._flatten_dict(product)
            writer.writerow(flat)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Meta Vehicle Offers: <listings><listing> — no namespace
    # ------------------------------------------------------------------

    def format_meta_listings_xml(
        self,
        products: list[dict[str, Any]],
        title: str = "Vehicle Offers Feed",
    ) -> str:
        """Generate Meta Vehicle Offers XML: <listings><listing>."""
        root = Element("listings")
        SubElement(root, "title").text = title

        _skip = {"image_link", "image_count"}
        for product in products:
            listing = SubElement(root, "listing")

            # 1. Nested <image> elements FIRST
            has_images = False
            for i in range(20):
                img_url = product.get(f"image_{i}_url")
                if not img_url:
                    break
                img_tag = product.get(f"image_{i}_tag", "")
                image_el = SubElement(listing, "image")
                SubElement(image_el, "url").text = _sanitize_text(str(img_url))
                if img_tag:
                    SubElement(image_el, "tag").text = _sanitize_text(str(img_tag))
                has_images = True

            if not has_images:
                img_link = product.get("image_link")
                if img_link:
                    image_el = SubElement(listing, "image")
                    SubElement(image_el, "url").text = _sanitize_text(str(img_link))

            # 2. Other fields — skip image flat fields
            for field_name, value in product.items():
                if value is None:
                    continue
                if field_name.startswith(_IMAGE_FIELD_PREFIX):
                    continue
                if field_name in _skip:
                    continue
                val_str = _sanitize_text(str(value))
                if not val_str.strip():
                    continue
                SubElement(listing, _sanitize_xml_tag(field_name)).text = val_str

        xml_str = '<?xml version="1.0" encoding="utf-8"?>\n' + tostring(root, encoding="unicode")
        fromstring(xml_str)
        return xml_str

    # ------------------------------------------------------------------
    # Google RSS 2.0: <rss><channel><item> with g: namespace
    # ------------------------------------------------------------------

    def format_rss_xml(
        self,
        products: list[dict[str, Any]],
        title: str = "Product Feed",
    ) -> str:
        """Generate RSS 2.0 XML feed with g: namespace (Google/TikTok)."""
        rss = Element("rss", {"version": "2.0"})
        ch_el = SubElement(rss, "channel")
        SubElement(ch_el, "title").text = title
        SubElement(ch_el, "link").text = "https://api.omarosa.ro"
        SubElement(ch_el, "description").text = "Automotive inventory feed"

        for product in products:
            item = SubElement(ch_el, "item")
            for field_name, value in product.items():
                if value is None:
                    continue
                val_str = _sanitize_text(str(value))
                if not val_str.strip():
                    continue
                SubElement(item, f"{{{GOOGLE_NS}}}{_sanitize_xml_tag(field_name)}").text = val_str

        xml_str = tostring(rss, encoding="unicode")
        fromstring(xml_str)
        return xml_str

    def format_google_shopping_xml(self, products: list[dict[str, Any]]) -> str:
        """Generate Google Shopping compliant RSS 2.0 XML feed."""
        return self.format_rss_xml(products, title="Google Shopping Feed")

    # ------------------------------------------------------------------
    # Meta Catalog CSV
    # ------------------------------------------------------------------

    def format_meta_catalog_csv(
        self,
        products: list[dict[str, Any]],
        catalog_type: str = "product",
    ) -> str:
        """Generate Meta (Facebook) catalog CSV for the given catalog type."""
        fields = _META_CATALOG_FIELDS.get(catalog_type, _META_PRODUCT_FIELDS)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for product in products:
            flat = self._flatten_dict(product)
            writer.writerow(flat)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _dict_to_xml(self, parent: Element, data: dict[str, Any]) -> None:
        """Recursively convert a dict to XML sub-elements."""
        for key, value in data.items():
            safe_key = _sanitize_xml_tag(str(key))
            if isinstance(value, dict):
                child = SubElement(parent, safe_key)
                self._dict_to_xml(child, value)
            elif isinstance(value, list):
                for item in value:
                    child = SubElement(parent, safe_key)
                    if isinstance(item, dict):
                        self._dict_to_xml(child, item)
                    else:
                        child.text = _sanitize_text(str(item))
            else:
                child = SubElement(parent, safe_key)
                child.text = _sanitize_text(str(value)) if value is not None else ""

    @staticmethod
    def _xml_to_string(root: Element) -> str:
        raw = tostring(root, encoding="unicode", xml_declaration=True)
        return raw

    @staticmethod
    def _collect_keys(products: list[dict[str, Any]]) -> list[str]:
        """Collect the union of all keys across products, preserving insertion order."""
        seen: dict[str, None] = {}
        for product in products:
            flat = FeedFormatter._flatten_dict(product)
            for key in flat:
                if key not in seen:
                    seen[key] = None
        return list(seen.keys())

    @staticmethod
    def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
        """Flatten nested dicts: {a: {b: 1}} -> {'a.b': 1}."""
        items: list[tuple[str, Any]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(FeedFormatter._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                items.append((new_key, ",".join(str(i) for i in v)))
            else:
                items.append((new_key, v))
        return dict(items)


feed_formatter = FeedFormatter()
