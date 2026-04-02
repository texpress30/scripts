"""Tests for field mapping presets."""

from __future__ import annotations

from app.services.feed_management.catalog_schemas import CatalogType
from app.services.feed_management.field_mapping.models import TargetChannel
from app.services.feed_management.field_mapping.presets import (
    get_preset,
    list_available_presets,
)


class TestPresets:
    def test_product_google_preset_exists(self):
        rules = get_preset(CatalogType.product, TargetChannel.google_shopping)
        assert len(rules) > 0
        target_fields = [r.target_field for r in rules]
        assert "id" in target_fields
        assert "title" in target_fields
        assert "price" in target_fields

    def test_product_meta_preset_exists(self):
        rules = get_preset(CatalogType.product, TargetChannel.meta_catalog)
        assert len(rules) > 0

    def test_vehicle_google_preset_exists(self):
        rules = get_preset(CatalogType.vehicle, TargetChannel.google_shopping)
        assert len(rules) > 0
        target_fields = [r.target_field for r in rules]
        assert "vehicle_id" in target_fields
        assert "make" in target_fields

    def test_home_listing_preset_exists(self):
        rules = get_preset(CatalogType.home_listing, TargetChannel.google_shopping)
        assert len(rules) > 0
        target_fields = [r.target_field for r in rules]
        assert "home_listing_id" in target_fields

    def test_unknown_combination_returns_fallback(self):
        rules = get_preset(CatalogType.flight, TargetChannel.tiktok_catalog)
        assert isinstance(rules, list)

    def test_list_available_presets(self):
        presets = list_available_presets()
        assert len(presets) > 0
        assert all("catalog_type" in p and "target_channel" in p for p in presets)

    def test_preset_rules_have_valid_fields(self):
        rules = get_preset(CatalogType.product, TargetChannel.google_shopping)
        for rule in rules:
            assert rule.target_field
            assert rule.transformation_type is not None
