"""Tests for the field transformer engine."""

from __future__ import annotations

import pytest

from app.services.feed_management.catalog_schemas import CatalogType
from app.services.feed_management.field_mapping.models import (
    FieldMappingRuleResponse,
    TransformationType,
)
from app.services.feed_management.field_mapping.transformer import FieldTransformer


def _rule(
    target: str,
    source: str | None = None,
    tt: TransformationType = TransformationType.direct,
    required: bool = False,
    order: int = 0,
    **config,
) -> FieldMappingRuleResponse:
    return FieldMappingRuleResponse(
        id="r1",
        field_mapping_id="m1",
        target_field=target,
        source_field=source,
        transformation_type=tt,
        transformation_config=dict(config) if config else {},
        is_required=required,
        sort_order=order,
    )


SAMPLE_PRODUCT = {
    "product_id": "p123",
    "data": {
        "id": "p123",
        "title": "Blue Running Shoes",
        "description": "Comfortable shoes for running",
        "price": 79.99,
        "compare_at_price": 99.99,
        "currency": "USD",
        "images": ["https://img.com/1.jpg", "https://img.com/2.jpg"],
        "category": "Shoes > Running",
        "tags": ["running", "blue"],
        "inventory_quantity": 25,
        "sku": "SKU-BLUE-42",
        "url": "https://shop.com/blue-shoes",
    },
}


class TestDirectTransform:
    def test_direct_simple(self):
        t = FieldTransformer()
        rules = [_rule("id", "data.id")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["id"] == "p123"

    def test_direct_nested(self):
        t = FieldTransformer()
        rules = [_rule("image", "data.images.0")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["image"] == "https://img.com/1.jpg"

    def test_direct_missing_field_returns_none(self):
        t = FieldTransformer()
        rules = [_rule("brand", "data.brand")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert "brand" not in result  # None values are skipped


class TestStaticTransform:
    def test_static_value(self):
        t = FieldTransformer()
        rules = [_rule("condition", tt=TransformationType.static, value="new")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["condition"] == "new"


class TestTemplateTransform:
    def test_template_interpolation(self):
        t = FieldTransformer()
        rules = [_rule("price_str", tt=TransformationType.template, template="{data.price} {data.currency}")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["price_str"] == "79.99 USD"

    def test_template_missing_field(self):
        t = FieldTransformer()
        rules = [_rule("label", tt=TransformationType.template, template="{data.brand} - {data.title}")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["label"] == " - Blue Running Shoes"


class TestConcatenateTransform:
    def test_concatenate_fields(self):
        t = FieldTransformer()
        rules = [_rule("full", tt=TransformationType.concatenate, fields=["data.title", "data.sku"], separator=" | ")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["full"] == "Blue Running Shoes | SKU-BLUE-42"


class TestTextTransforms:
    def test_uppercase(self):
        t = FieldTransformer()
        rules = [_rule("title_upper", "data.title", tt=TransformationType.uppercase)]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["title_upper"] == "BLUE RUNNING SHOES"

    def test_lowercase(self):
        t = FieldTransformer()
        rules = [_rule("title_lower", "data.title", tt=TransformationType.lowercase)]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["title_lower"] == "blue running shoes"

    def test_prefix(self):
        t = FieldTransformer()
        rules = [_rule("prefixed", "data.id", tt=TransformationType.prefix, prefix="PROD-")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["prefixed"] == "PROD-p123"

    def test_suffix(self):
        t = FieldTransformer()
        rules = [_rule("suffixed", "data.id", tt=TransformationType.suffix, suffix="-US")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["suffixed"] == "p123-US"

    def test_replace(self):
        t = FieldTransformer()
        rules = [_rule("replaced", "data.category", tt=TransformationType.replace, search=" > ", replacement=" / ")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["replaced"] == "Shoes / Running"

    def test_truncate(self):
        t = FieldTransformer()
        rules = [_rule("short_title", "data.title", tt=TransformationType.truncate, max_length=10)]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["short_title"] == "Blue Runni"
        assert len(result["short_title"]) == 10

    def test_truncate_shorter_string(self):
        t = FieldTransformer()
        rules = [_rule("title", "data.id", tt=TransformationType.truncate, max_length=100)]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["title"] == "p123"


class TestConditionalTransform:
    def test_conditional_match(self):
        t = FieldTransformer()
        zero_product = {**SAMPLE_PRODUCT, "data": {**SAMPLE_PRODUCT["data"], "inventory_quantity": 0}}
        rules = [_rule("availability", tt=TransformationType.conditional,
                       condition_field="data.inventory_quantity",
                       condition_value="0",
                       then_value="out_of_stock",
                       else_value="in_stock")]
        result = t.apply_mapping(zero_product, rules)
        assert result["availability"] == "out_of_stock"

    def test_conditional_no_match(self):
        t = FieldTransformer()
        rules = [_rule("availability", tt=TransformationType.conditional,
                       condition_field="data.inventory_quantity",
                       condition_value="0",
                       then_value="out_of_stock",
                       else_value="in_stock")]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result["availability"] == "in_stock"


class TestMultipleRules:
    def test_multiple_rules_ordered(self):
        t = FieldTransformer()
        rules = [
            _rule("id", "data.id", order=0),
            _rule("title", "data.title", order=1),
            _rule("price", "data.price", tt=TransformationType.template, template="{data.price} {data.currency}", order=2),
            _rule("condition", tt=TransformationType.static, value="new", order=3),
        ]
        result = t.apply_mapping(SAMPLE_PRODUCT, rules)
        assert result == {
            "id": "p123",
            "title": "Blue Running Shoes",
            "price": "79.99 USD",
            "condition": "new",
        }


class TestValidateOutput:
    def test_validate_complete(self):
        t = FieldTransformer()
        transformed = {
            "id": "p123",
            "title": "Test",
            "description": "Desc",
            "link": "https://test.com",
            "image_link": "https://img.com/1.jpg",
            "price": "10.00 USD",
            "availability": "in_stock",
        }
        result = t.validate_output(transformed, CatalogType.product)
        assert result["is_complete"] is True

    def test_validate_incomplete(self):
        t = FieldTransformer()
        transformed = {"id": "p123", "title": "Test"}
        result = t.validate_output(transformed, CatalogType.product)
        assert result["is_complete"] is False
        assert "price" in result["missing_required"]
