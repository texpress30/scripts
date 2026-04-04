"""Tests for AI-powered field mapping suggestions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.feed_management.master_fields.service import suggest_mappings_ai

# Patch targets: the actual module where the functions live
_AI_MOD = "app.services.feed_management.schema_registry.ai_suggestions"


def _source_fields():
    return [
        {"field": "meta_brand", "type": "string", "sample": "BMW"},
        {"field": "meta_model", "type": "string", "sample": "X1"},
        {"field": "meta_kilometraj", "type": "string", "sample": "236116"},
        {"field": "meta_combustibil", "type": "string", "sample": "Diesel"},
        {"field": "meta_transmisie", "type": "string", "sample": "Automata"},
        {"field": "meta_an_fabricatie", "type": "string", "sample": "2015"},
        {"field": "name", "type": "string", "sample": "BMW X1 2015"},
        {"field": "price", "type": "number", "sample": "7500"},
        {"field": "image_src", "type": "url", "sample": "https://img.test/1.jpg"},
    ]


def _target_fields():
    return [
        {"field_key": "make", "display_name": "Make", "description": "Vehicle manufacturer", "is_required": True},
        {"field_key": "model", "display_name": "Model", "description": "Vehicle model", "is_required": True},
        {"field_key": "mileage", "display_name": "Mileage", "description": "Odometer reading", "is_required": True},
        {"field_key": "fuel_type", "display_name": "Fuel Type", "description": "Type of fuel", "is_required": False},
        {"field_key": "transmission", "display_name": "Transmission", "description": "Transmission type", "is_required": False},
        {"field_key": "year", "display_name": "Year", "description": "Manufacturing year", "is_required": True},
    ]


_MOCK_AI_RESPONSE = """[
  {"target_field": "make", "source_field": "meta_brand", "confidence": "high", "reason": "brand = make"},
  {"target_field": "model", "source_field": "meta_model", "confidence": "high", "reason": "direct match"},
  {"target_field": "mileage", "source_field": "meta_kilometraj", "confidence": "high", "reason": "kilometraj = mileage in Romanian"},
  {"target_field": "fuel_type", "source_field": "meta_combustibil", "confidence": "medium", "reason": "combustibil = fuel type in Romanian"},
  {"target_field": "transmission", "source_field": "meta_transmisie", "confidence": "medium", "reason": "transmisie = transmission"},
  {"target_field": "year", "source_field": "meta_an_fabricatie", "confidence": "high", "reason": "an_fabricatie = manufacturing year"}
]"""


class TestSuggestMappingsAi:
    def test_returns_validated_suggestions(self):
        with patch(f"{_AI_MOD}._call_claude", return_value=_MOCK_AI_RESPONSE), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert len(result) == 6
        assert result[0]["target_field"] == "make"
        assert result[0]["source_field"] == "meta_brand"
        assert result[0]["confidence"] == "high"
        assert result[0]["reason"] == "brand = make"

    def test_returns_empty_when_ai_disabled(self):
        with patch(f"{_AI_MOD}.is_ai_enabled", return_value=False):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert result == []

    def test_returns_empty_on_ai_error(self):
        with patch(f"{_AI_MOD}._call_claude", return_value=None), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert result == []

    def test_filters_invalid_field_names(self):
        bad_response = """[
          {"target_field": "make", "source_field": "meta_brand", "confidence": "high", "reason": "ok"},
          {"target_field": "nonexistent_target", "source_field": "meta_brand", "confidence": "high", "reason": "bad"},
          {"target_field": "make", "source_field": "nonexistent_source", "confidence": "high", "reason": "bad"}
        ]"""
        with patch(f"{_AI_MOD}._call_claude", return_value=bad_response), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert len(result) == 1
        assert result[0]["target_field"] == "make"
        assert result[0]["source_field"] == "meta_brand"

    def test_normalizes_invalid_confidence(self):
        response = '[{"target_field": "make", "source_field": "meta_brand", "confidence": "super_high", "reason": "ok"}]'
        with patch(f"{_AI_MOD}._call_claude", return_value=response), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert result[0]["confidence"] == "medium"

    def test_handles_markdown_wrapped_json(self):
        response = "```json\n" + _MOCK_AI_RESPONSE + "\n```"
        with patch(f"{_AI_MOD}._call_claude", return_value=response), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(_source_fields(), _target_fields(), "vehicle")

        assert len(result) == 6

    def test_works_for_product_catalog_type(self):
        product_sources = [
            {"field": "title", "type": "string", "sample": "Blue T-Shirt"},
            {"field": "meta_brand", "type": "string", "sample": "Nike"},
        ]
        product_targets = [
            {"field_key": "brand", "display_name": "Brand", "description": "Product brand", "is_required": False},
        ]
        response = '[{"target_field": "brand", "source_field": "meta_brand", "confidence": "high", "reason": "direct"}]'
        with patch(f"{_AI_MOD}._call_claude", return_value=response), \
             patch(f"{_AI_MOD}.is_ai_enabled", return_value=True):
            result = suggest_mappings_ai(product_sources, product_targets, "product")

        assert len(result) == 1
        assert result[0]["target_field"] == "brand"
