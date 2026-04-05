"""Tests for _apply_field_specs: extra mapped fields must not overwrite spec-renamed fields.

Root cause: If a master mapping has target_field="offer_description" (the channel
name) and the spec renames "description" → "offer_description", the extra fields
loop at the end of _apply_field_specs overwrote the spec value with the raw value.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.feed_management.channels.feed_generator import FeedGenerator


def _make_mapping(target: str, source: str | None, mtype: str = "direct",
                  static_value: str | None = None):
    m = MagicMock()
    m.target_field = target
    m.source_field = source
    m.mapping_type = MagicMock()
    m.mapping_type.value = mtype
    m.static_value = static_value
    m.template_value = None
    return m


class TestApplyFieldSpecsOverwrite:
    """Verify that spec-renamed fields are not overwritten by extra mapped fields."""

    def _make_specs(self):
        """Simulate schema registry specs for facebook_product_ads vehicle."""
        return [
            {"field_key": "description", "channel_field_name": "offer_description",
             "data_type": "string", "is_required": True, "default_value": None,
             "allowed_values": None, "format_pattern": None},
            {"field_key": "title", "channel_field_name": "title",
             "data_type": "string", "is_required": True, "default_value": None,
             "allowed_values": None, "format_pattern": None},
            {"field_key": "price", "channel_field_name": "price",
             "data_type": "price", "is_required": True, "default_value": None,
             "allowed_values": None, "format_pattern": None},
        ]

    def test_static_mapping_not_overwritten_by_extra_field(self):
        """The exact production bug: offer_description static value overwritten by raw description."""
        gen = FeedGenerator()

        # Product data
        data = {
            "title": "DACIA DUSTER 2013",
            "description": "DACIA DUSTER 2013\n*1.5 DIESEL\n*EURO 5\n...hundreds of lines...",
            "price": "6990",
        }
        data = gen._merge_raw_data(data)

        # Master mappings: description → static, offer_description → direct from description
        master_mappings = [
            _make_mapping("title", "title"),
            _make_mapping("description", None, "static", "RATE FIXE, 0 % AVANS, 12 LUNI GARANTIE"),
            _make_mapping("offer_description", "description"),  # maps raw description to offer_description
            _make_mapping("price", "price"),
        ]

        row = gen._transform_product(data, master_mappings, {})
        # After transform: row has both "description" (static) and "offer_description" (raw)
        assert row["description"] == "RATE FIXE, 0 % AVANS, 12 LUNI GARANTIE"
        assert "DACIA DUSTER 2013" in row["offer_description"]  # raw description

        # Apply field specs: description → offer_description
        specs = self._make_specs()
        result = gen._apply_field_specs(row, specs, "product-1")

        # offer_description MUST be the static value, NOT the raw description
        assert result["offer_description"] == "RATE FIXE, 0 % AVANS, 12 LUNI GARANTIE"
        assert "DACIA DUSTER 2013\n*1.5 DIESEL" not in result.get("offer_description", "")

    def test_spec_renamed_field_takes_precedence(self):
        """When spec renames A→B and there's also a direct mapping B, spec wins."""
        gen = FeedGenerator()

        row = {
            "description": "CORRECT VALUE (from static mapping)",
            "offer_description": "WRONG VALUE (from direct mapping to raw data)",
            "title": "Test",
        }

        specs = self._make_specs()
        result = gen._apply_field_specs(row, specs, "product-1")

        assert result["offer_description"] == "CORRECT VALUE (from static mapping)"

    def test_extra_fields_still_included_when_no_conflict(self):
        """Extra mapped fields that don't conflict with specs are included."""
        gen = FeedGenerator()

        row = {
            "title": "Test Car",
            "description": "Static desc",
            "price": "6990",
            "dealership_name": "ROC Automobile",  # not in specs
        }

        specs = self._make_specs()
        result = gen._apply_field_specs(row, specs, "product-1")

        assert result["title"] == "Test Car"
        assert result["offer_description"] == "Static desc"
        assert result["dealership_name"] == "ROC Automobile"

    def test_field_specs_none_returns_row_as_is(self):
        """When field_specs is None (fallback), row is returned unchanged."""
        gen = FeedGenerator()
        row = {"title": "Test", "description": "Desc"}
        result = gen._apply_field_specs(row, None, "product-1")
        assert result == row

    def test_full_pipeline_with_static_mapping(self):
        """End-to-end: product → transform → apply_specs → correct output."""
        gen = FeedGenerator()

        data = {
            "title": "BMW X1 2013",
            "description": "Long raw WooCommerce description with *bullets and\nnewlines",
            "price": "9990",
            "url": "https://rocautomobile.ro/produs/bmw-x1",
        }
        data = gen._merge_raw_data(data)

        master_mappings = [
            _make_mapping("title", "title"),
            _make_mapping("description", None, "static", "RATE FIXE, 0 % AVANS"),
            _make_mapping("price", "price"),
        ]

        row = gen._transform_product(data, master_mappings, {})
        assert row["description"] == "RATE FIXE, 0 % AVANS"

        specs = self._make_specs()
        result = gen._apply_field_specs(row, specs, "product-1")

        # offer_description should have the static value
        assert result["offer_description"] == "RATE FIXE, 0 % AVANS"
        assert "Long raw WooCommerce" not in result.get("offer_description", "")
