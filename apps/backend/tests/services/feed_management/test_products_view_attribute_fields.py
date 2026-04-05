"""Tests for attribute_* and image_0_tag fields in the products view pipeline.

Verifies that:
- _merge_raw_data() merges ALL raw_data fields including attribute_* prefixed ones
- _merge_raw_data() flattens images as safety net for stale data
- The full transform pipeline resolves attribute_* and image_0_tag fields
- Column type detection works for image, url, and price patterns
"""

from __future__ import annotations

import pytest

from app.services.feed_management.channels.feed_generator import FeedGenerator
from app.services.feed_management.connectors.base import flatten_images


# ---------------------------------------------------------------------------
# flatten_images tests
# ---------------------------------------------------------------------------

class TestFlattenImages:
    def test_basic_flatten(self):
        raw = {"images": ["https://img.test/0.jpg", "https://img.test/1.jpg"]}
        flatten_images(raw)
        assert raw["image_0_url"] == "https://img.test/0.jpg"
        assert raw["image_0_tag"] == "Față"
        assert raw["image_1_url"] == "https://img.test/1.jpg"
        assert raw["image_1_tag"] == "Spate"
        assert raw["image_count"] == 2
        assert raw["images"] == ["https://img.test/0.jpg", "https://img.test/1.jpg"]

    def test_empty_images(self):
        raw = {"images": []}
        flatten_images(raw)
        assert "image_0_url" not in raw
        assert "image_count" not in raw

    def test_no_images_key(self):
        raw = {"title": "test"}
        flatten_images(raw)
        assert "image_0_url" not in raw

    def test_idempotent(self):
        raw = {"images": ["https://img.test/0.jpg"]}
        flatten_images(raw)
        flatten_images(raw)
        assert raw["image_0_url"] == "https://img.test/0.jpg"
        assert raw["image_count"] == 1


# ---------------------------------------------------------------------------
# _merge_raw_data with attribute_* fields
# ---------------------------------------------------------------------------

class TestMergeRawDataAttributeFields:
    """Verify that _merge_raw_data merges ALL raw_data fields, including attribute_*."""

    def test_merges_attribute_fields(self):
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN 2012",
            "raw_data": {
                "attribute_vin": "UU1HSDAG548270631",
                "attribute_condition": "GOOD",
                "attribute_interior_color": "black",
                "attribute_drivetrain": "manual",
                "attribute_interior_upholstery": "textil",
                "caroserie": "VAN",
                "culoare": "Albastru",
            },
        }
        merged = gen._merge_raw_data(data)

        assert merged["attribute_vin"] == "UU1HSDAG548270631"
        assert merged["attribute_condition"] == "GOOD"
        assert merged["attribute_interior_color"] == "black"
        assert merged["attribute_drivetrain"] == "manual"
        assert merged["attribute_interior_upholstery"] == "textil"
        assert merged["caroserie"] == "VAN"
        assert merged["culoare"] == "Albastru"
        assert "raw_data" not in merged

    def test_merges_meta_fields(self):
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "raw_data": {
                "meta_kilometraj": "285419",
                "meta_brand": "Volkswagen",
            },
        }
        merged = gen._merge_raw_data(data)
        assert merged["meta_kilometraj"] == "285419"
        assert merged["meta_brand"] == "Volkswagen"

    def test_data_takes_priority_over_raw_data(self):
        gen = FeedGenerator()
        data = {
            "description": "Clean text",
            "raw_data": {
                "description": "<p>HTML text</p>",
                "attribute_vin": "ABC123",
            },
        }
        merged = gen._merge_raw_data(data)
        assert merged["description"] == "Clean text"
        assert merged["attribute_vin"] == "ABC123"

    def test_flattens_images_on_merge(self):
        """images array is flattened into image_N_url/tag fields."""
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "raw_data": {
                "images": [
                    "https://img.test/front.jpg",
                    "https://img.test/back.jpg",
                ],
                "attribute_vin": "ABC123",
            },
        }
        merged = gen._merge_raw_data(data)

        # Images flattened
        assert merged["image_0_url"] == "https://img.test/front.jpg"
        assert merged["image_0_tag"] == "Față"
        assert merged["image_1_url"] == "https://img.test/back.jpg"
        assert merged["image_1_tag"] == "Spate"
        # Other fields still merged
        assert merged["attribute_vin"] == "ABC123"

    def test_preserves_existing_image_fields(self):
        """If image_0_url already exists (from sync), don't re-flatten."""
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "raw_data": {
                "images": ["https://img.test/0.jpg"],
                "image_0_url": "https://img.test/original.jpg",
                "image_0_tag": "Custom Tag",
            },
        }
        merged = gen._merge_raw_data(data)

        # Existing image fields preserved (merge adds them, then flatten skips)
        assert merged["image_0_url"] == "https://img.test/original.jpg"
        assert merged["image_0_tag"] == "Custom Tag"

    def test_image_tag_from_data(self):
        """image_0_tag in data (not raw_data) is preserved after merge."""
        gen = FeedGenerator()
        data = {
            "image_0_tag": "Față",
            "image_0_url": "https://img.test/0.jpg",
            "raw_data": {
                "brand": "Volkswagen",
            },
        }
        merged = gen._merge_raw_data(data)

        assert merged["image_0_tag"] == "Față"
        assert merged["image_0_url"] == "https://img.test/0.jpg"
        assert merged["brand"] == "Volkswagen"


# ---------------------------------------------------------------------------
# Full transform pipeline
# ---------------------------------------------------------------------------

class TestTransformWithAttributeFields:
    """End-to-end: transform products with attribute_* and image fields."""

    def _make_mapping(self, target: str, source: str | None, mtype: str = "direct",
                      static_value: str | None = None):
        from unittest.mock import MagicMock
        m = MagicMock()
        m.target_field = target
        m.source_field = source
        m.mapping_type = MagicMock()
        m.mapping_type.value = mtype
        m.static_value = static_value
        m.template_value = None
        return m

    def test_resolves_attribute_fields_after_merge(self):
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN 2012",
            "price": 7500.0,
            "url": "https://example.com/product/60837",
            "raw_data": {
                "attribute_vin": "UU1HSDAG548270631",
                "attribute_condition": "GOOD",
                "attribute_interior_color": "black",
                "attribute_drivetrain": "manual",
                "attribute_interior_upholstery": "textil",
                "caroserie": "VAN",
                "culoare": "Albastru",
                "capacitate_motor": "2.0L",
                "brand": "Volkswagen",
                "model": "Touran",
                "an_fabricatie": "2012",
                "combustibil": "Diesel",
                "meta_kilometraj": "285419",
                "stock_status": "instock",
                "image_src": "https://example.com/img.jpg",
                "images": ["https://example.com/img0.jpg", "https://example.com/img1.jpg"],
            },
        }
        mappings = [
            self._make_mapping("title", "title"),
            self._make_mapping("vin", "attribute_vin"),
            self._make_mapping("vehicle_condition", "attribute_condition"),
            self._make_mapping("interior_color", "attribute_interior_color"),
            self._make_mapping("drivetrain", "attribute_drivetrain"),
            self._make_mapping("interior_upholstery", "attribute_interior_upholstery"),
            self._make_mapping("body_style", "caroserie"),
            self._make_mapping("exterior_color", "culoare"),
            self._make_mapping("engine", "capacitate_motor"),
            self._make_mapping("make", "brand"),
            self._make_mapping("model", "model"),
            self._make_mapping("year", "an_fabricatie"),
            self._make_mapping("fuel_type", "combustibil"),
            self._make_mapping("mileage", "meta_kilometraj"),
            self._make_mapping("availability", "stock_status"),
            self._make_mapping("image_link", "image_src"),
            self._make_mapping("image_0_tag_0", "image_0_tag"),
            self._make_mapping("dealership_name", None, "static", "ROC Automobile"),
        ]

        merged = gen._merge_raw_data(data)
        row = gen._transform_product(merged, mappings, {})

        # attribute_* fields
        assert row["vin"] == "UU1HSDAG548270631"
        assert row["vehicle_condition"] == "GOOD"
        assert row["interior_color"] == "black"
        assert row["drivetrain"] == "manual"
        assert row["interior_upholstery"] == "textil"

        # Regular raw_data fields
        assert row["body_style"] == "VAN"
        assert row["exterior_color"] == "Albastru"
        assert row["engine"] == "2.0L"
        assert row["make"] == "Volkswagen"
        assert row["model"] == "Touran"
        assert row["year"] == "2012"
        assert row["fuel_type"] == "Diesel"
        assert row["mileage"] == "285419"
        assert row["availability"] == "instock"

        # Image fields (from raw_data images flatten)
        assert row["image_link"] == "https://example.com/img.jpg"
        assert row["image_0_tag_0"] == "Față"  # from flatten_images safety net

        # Static mapping
        assert row["dealership_name"] == "ROC Automobile"

    def test_without_merge_attribute_fields_missing(self):
        """Demonstrates the bug: without _merge_raw_data, attribute fields not resolved."""
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN",
            "raw_data": {
                "attribute_vin": "UU1HSDAG548270631",
                "caroserie": "VAN",
            },
        }
        mappings = [
            self._make_mapping("vin", "attribute_vin"),
            self._make_mapping("body_style", "caroserie"),
        ]

        # Without merge: raw_data fields are not found
        row = gen._transform_product(data, mappings, {})
        assert "vin" not in row
        assert "body_style" not in row

        # With merge: all fields resolved
        merged = gen._merge_raw_data(data)
        row = gen._transform_product(merged, mappings, {})
        assert row["vin"] == "UU1HSDAG548270631"
        assert row["body_style"] == "VAN"


# ---------------------------------------------------------------------------
# Column type detection
# ---------------------------------------------------------------------------

class TestColumnTypeDetection:

    @staticmethod
    def _detect(key: str) -> str:
        col = {"key": key, "type": "string"}
        if "image" in key:
            col["type"] = "image"
        elif key in ("link", "url") or key.endswith("_url") or key.endswith("_link"):
            col["type"] = "url"
        elif "price" in key:
            col["type"] = "price"
        return col["type"]

    def test_image_columns(self):
        assert self._detect("image_link") == "image"
        assert self._detect("image_0_url") == "image"
        assert self._detect("additional_image_link") == "image"

    def test_url_columns(self):
        assert self._detect("dealer_url") == "url"
        assert self._detect("video_0_url") == "url"
        assert self._detect("link") == "url"
        assert self._detect("url") == "url"

    def test_price_columns(self):
        assert self._detect("price") == "price"
        assert self._detect("sale_price") == "price"
        assert self._detect("previous_price") == "price"

    def test_string_columns(self):
        assert self._detect("title") == "string"
        assert self._detect("vin") == "string"
        assert self._detect("body_style") == "string"
