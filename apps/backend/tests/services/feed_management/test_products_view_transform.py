"""Tests for the products view transformation pipeline.

Verifies that:
- _merge_raw_data() merges raw_data fields into top-level data
- _transform_product() can resolve fields from both data and raw_data
- Column type detection works for image, url, and price columns
"""

from __future__ import annotations

import pytest

from app.services.feed_management.channels.feed_generator import FeedGenerator


class TestMergeRawData:
    """Verify that _merge_raw_data() makes raw_data fields accessible."""

    def test_merges_raw_data_into_top_level(self):
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN 2012",
            "price": "7500",
            "raw_data": {
                "brand": "Volkswagen",
                "model": "Touran",
                "combustibil": "Diesel",
                "caroserie": "VAN",
                "culoare": "Albastru",
                "attribute_vin": "UU1HSDAG548270631",
            },
        }
        merged = gen._merge_raw_data(data)

        assert merged["title"] == "VW TOURAN 2012"
        assert merged["brand"] == "Volkswagen"
        assert merged["model"] == "Touran"
        assert merged["combustibil"] == "Diesel"
        assert merged["caroserie"] == "VAN"
        assert merged["culoare"] == "Albastru"
        assert merged["attribute_vin"] == "UU1HSDAG548270631"
        # raw_data key itself should be removed
        assert "raw_data" not in merged

    def test_does_not_overwrite_existing_keys(self):
        gen = FeedGenerator()
        data = {
            "title": "Product Title",
            "raw_data": {
                "title": "Raw Title Should Not Overwrite",
                "brand": "BMW",
            },
        }
        merged = gen._merge_raw_data(data)

        assert merged["title"] == "Product Title"  # original preserved
        assert merged["brand"] == "BMW"  # new key added

    def test_no_raw_data(self):
        gen = FeedGenerator()
        data = {"title": "Product", "price": "100"}
        merged = gen._merge_raw_data(data)

        assert merged["title"] == "Product"
        assert merged["price"] == "100"

    def test_raw_data_not_dict(self):
        gen = FeedGenerator()
        data = {"title": "Product", "raw_data": "not a dict"}
        merged = gen._merge_raw_data(data)

        assert merged["title"] == "Product"


class TestTransformProductWithRawData:
    """End-to-end: verify that _transform_product resolves raw_data fields
    after _merge_raw_data has been called."""

    def _make_mapping(self, target: str, source: str | None, mtype: str = "direct",
                      static_value: str | None = None):
        """Create a mock mapping object."""
        from unittest.mock import MagicMock
        m = MagicMock()
        m.target_field = target
        m.source_field = source
        m.mapping_type = MagicMock()
        m.mapping_type.value = mtype
        m.static_value = static_value
        m.template_value = None
        return m

    def test_resolves_raw_data_fields(self):
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN 2012",
            "price": "7500",
            "image_src": "https://example.com/img.jpg",
            "raw_data": {
                "brand": "Volkswagen",
                "model": "Touran",
                "an_fabricatie": "2012",
                "combustibil": "Diesel",
                "meta_kilometraj": "285419",
            },
        }
        mappings = [
            self._make_mapping("title", "title"),
            self._make_mapping("make", "brand"),
            self._make_mapping("model", "model"),
            self._make_mapping("year", "an_fabricatie"),
            self._make_mapping("fuel_type", "combustibil"),
            self._make_mapping("mileage", "meta_kilometraj"),
            self._make_mapping("image_link", "image_src"),
        ]

        # Must merge raw_data first (as the fixed endpoint now does)
        merged = gen._merge_raw_data(data)
        row = gen._transform_product(merged, mappings, {})

        assert row["title"] == "VW TOURAN 2012"
        assert row["make"] == "Volkswagen"
        assert row["model"] == "Touran"
        assert row["year"] == "2012"
        assert row["fuel_type"] == "Diesel"
        assert row["mileage"] == "285419"
        assert row["image_link"] == "https://example.com/img.jpg"

    def test_without_merge_raw_data_fields_are_missing(self):
        """Demonstrates the bug: without _merge_raw_data, raw fields are not resolved."""
        gen = FeedGenerator()
        data = {
            "title": "VW TOURAN 2012",
            "raw_data": {
                "brand": "Volkswagen",
            },
        }
        mappings = [
            self._make_mapping("title", "title"),
            self._make_mapping("make", "brand"),
        ]

        # Without merge: brand is not found
        row = gen._transform_product(data, mappings, {})
        assert row.get("title") == "VW TOURAN 2012"
        assert "make" not in row  # brand not resolved — the bug

        # With merge: brand is found
        merged = gen._merge_raw_data(data)
        row = gen._transform_product(merged, mappings, {})
        assert row["make"] == "Volkswagen"  # now resolved

    def test_static_mapping(self):
        gen = FeedGenerator()
        data = {"title": "Some Product"}
        mappings = [
            self._make_mapping("dealership_name", None, "static", "ROC Automobile"),
        ]

        row = gen._transform_product(data, mappings, {})
        assert row["dealership_name"] == "ROC Automobile"

    def test_flattenated_image_fields(self):
        """Verify that flattened image fields (image_0_url, image_0_tag) are resolved."""
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "image_0_url": "https://example.com/img0.jpg",
            "image_0_tag": "Front",
            "image_1_url": "https://example.com/img1.jpg",
        }
        mappings = [
            self._make_mapping("image_link", "image_0_url"),
            self._make_mapping("image_0_tag_0", "image_0_tag"),
            self._make_mapping("additional_image_link", "image_1_url"),
        ]

        row = gen._transform_product(data, mappings, {})
        assert row["image_link"] == "https://example.com/img0.jpg"
        assert row["image_0_tag_0"] == "Front"
        assert row["additional_image_link"] == "https://example.com/img1.jpg"


class TestColumnTypeDetection:
    """Verify column type inference for the products endpoint."""

    def test_image_columns(self):
        """Columns with 'image' in the name should be type 'image'."""
        columns = [
            {"key": "image_link", "label": "Image Link", "type": "string"},
            {"key": "image_0_url", "label": "Image 0 Url", "type": "string"},
            {"key": "additional_image_link", "label": "Additional Image Link", "type": "string"},
        ]
        for col in columns:
            key = col["key"]
            if "image" in key:
                col["type"] = "image"
            elif key in ("link", "url") or key.endswith("_url") or key.endswith("_link"):
                col["type"] = "url"
            elif "price" in key:
                col["type"] = "price"

        assert all(c["type"] == "image" for c in columns)

    def test_url_columns(self):
        """Columns ending with _url or _link should be type 'url'."""
        columns = [
            {"key": "dealer_url", "label": "Dealer Url", "type": "string"},
            {"key": "video_0_url", "label": "Video 0 Url", "type": "string"},
            {"key": "link", "label": "Link", "type": "string"},
            {"key": "offer_disclaimer_url", "label": "Offer Disclaimer Url", "type": "string"},
        ]
        for col in columns:
            key = col["key"]
            if "image" in key:
                col["type"] = "image"
            elif key in ("link", "url") or key.endswith("_url") or key.endswith("_link"):
                col["type"] = "url"
            elif "price" in key:
                col["type"] = "price"

        assert all(c["type"] == "url" for c in columns)

    def test_price_columns(self):
        """Columns with 'price' in the name should be type 'price'."""
        columns = [
            {"key": "price", "label": "Price", "type": "string"},
            {"key": "sale_price", "label": "Sale Price", "type": "string"},
            {"key": "previous_price", "label": "Previous Price", "type": "string"},
        ]
        for col in columns:
            key = col["key"]
            if "image" in key:
                col["type"] = "image"
            elif key in ("link", "url") or key.endswith("_url") or key.endswith("_link"):
                col["type"] = "url"
            elif "price" in key:
                col["type"] = "price"

        assert all(c["type"] == "price" for c in columns)
