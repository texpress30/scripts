"""Tests for catalog_schemas module."""

from __future__ import annotations

from app.services.feed_management.catalog_schemas import (
    CATALOG_SCHEMAS,
    CatalogType,
    get_all_fields,
    get_catalog_schema,
    get_required_fields,
    validate_mapping_completeness,
)


class TestCatalogType:
    def test_all_catalog_types_have_schemas(self):
        for ct in CatalogType:
            schema = get_catalog_schema(ct)
            assert "required" in schema
            assert "optional" in schema
            assert len(schema["required"]) > 0, f"{ct.value} should have at least one required field"

    def test_product_required_fields(self):
        fields = get_required_fields(CatalogType.product)
        assert "id" in fields
        assert "title" in fields
        assert "price" in fields
        assert "availability" in fields
        assert "image_link" in fields

    def test_vehicle_required_fields(self):
        fields = get_required_fields(CatalogType.vehicle)
        assert "vehicle_id" in fields
        assert "make" in fields
        assert "model" in fields
        assert "year" in fields
        assert "price" in fields

    def test_home_listing_required_fields(self):
        fields = get_required_fields(CatalogType.home_listing)
        assert "home_listing_id" in fields
        assert "address" in fields
        assert "city" in fields
        assert "price" in fields

    def test_hotel_required_fields(self):
        fields = get_required_fields(CatalogType.hotel)
        assert "hotel_id" in fields
        assert "name" in fields
        assert "city" in fields

    def test_get_all_fields_includes_required_and_optional(self):
        all_fields = get_all_fields(CatalogType.product)
        required = get_required_fields(CatalogType.product)
        schema = get_catalog_schema(CatalogType.product)
        optional_count = len(schema["optional"])
        assert len(all_fields) == len(required) + optional_count

    def test_each_field_has_required_keys(self):
        for ct in CatalogType:
            for field in get_all_fields(ct):
                assert "field" in field, f"Missing 'field' key in {ct.value}"
                assert "type" in field, f"Missing 'type' key in {ct.value} field {field.get('field')}"


class TestValidateMappingCompleteness:
    def test_complete_mapping(self):
        required = get_required_fields(CatalogType.product)
        result = validate_mapping_completeness(CatalogType.product, required)
        assert result["is_complete"] is True
        assert result["missing_required"] == []
        assert result["mapped_count"] == len(required)

    def test_incomplete_mapping(self):
        result = validate_mapping_completeness(CatalogType.product, ["id", "title"])
        assert result["is_complete"] is False
        assert len(result["missing_required"]) > 0
        assert "price" in result["missing_required"]

    def test_empty_mapping(self):
        result = validate_mapping_completeness(CatalogType.product, [])
        assert result["is_complete"] is False
        assert result["mapped_count"] == 0

    def test_extra_fields_dont_break(self):
        required = get_required_fields(CatalogType.product)
        extra = required + ["custom_field_1", "custom_field_2"]
        result = validate_mapping_completeness(CatalogType.product, extra)
        assert result["is_complete"] is True
