"""Tests for destination + service catalog types across all layers.

Validates that the new catalog types (destination, service) are correctly
wired in: CatalogType enum, CATALOG_SCHEMAS, ChannelType, _VALID_CATALOG_TYPES,
and catalog_field_schemas fallback.
"""

from __future__ import annotations

import pytest

from app.services.feed_management.catalog_schemas import (
    CATALOG_SCHEMAS,
    CatalogType,
    get_all_fields,
    get_catalog_schema,
    get_required_fields,
    validate_mapping_completeness,
)
from app.services.feed_management.channels.models import ChannelType
from app.services.feed_management.schema_registry.service import (
    validate_catalog_type,
)


# ---------------------------------------------------------------------------
# CatalogType enum
# ---------------------------------------------------------------------------

class TestCatalogTypeEnum:
    def test_enum_contains_destination(self):
        assert CatalogType.destination.value == "destination"

    def test_enum_contains_service(self):
        assert CatalogType.service.value == "service"

    def test_enum_has_11_values(self):
        assert len(CatalogType) == 11

    def test_all_expected_values(self):
        expected = {
            "product", "vehicle", "vehicle_offer", "home_listing",
            "hotel", "hotel_room", "flight", "trip", "media",
            "destination", "service",
        }
        actual = {ct.value for ct in CatalogType}
        assert actual == expected


# ---------------------------------------------------------------------------
# CATALOG_SCHEMAS
# ---------------------------------------------------------------------------

class TestCatalogSchemas:
    def test_schemas_has_destination(self):
        assert CatalogType.destination in CATALOG_SCHEMAS

    def test_schemas_has_service(self):
        assert CatalogType.service in CATALOG_SCHEMAS

    def test_all_catalog_types_have_schemas(self):
        for ct in CatalogType:
            assert ct in CATALOG_SCHEMAS, f"{ct.value} missing from CATALOG_SCHEMAS"

    def test_destination_required_fields(self):
        fields = get_required_fields(CatalogType.destination)
        assert len(fields) == 5
        assert set(fields) == {"id", "name", "url", "image_link", "description"}

    def test_destination_optional_fields(self):
        schema = get_catalog_schema(CatalogType.destination)
        optional = [f["field"] for f in schema["optional"]]
        assert len(optional) == 11
        assert "address" in optional
        assert "city" in optional
        assert "country" in optional
        assert "latitude" in optional
        assert "longitude" in optional
        assert "neighborhood" in optional

    def test_destination_total_fields(self):
        all_fields = get_all_fields(CatalogType.destination)
        assert len(all_fields) == 16

    def test_service_required_fields(self):
        fields = get_required_fields(CatalogType.service)
        assert len(fields) == 4
        assert set(fields) == {"id", "title", "url", "image_link"}

    def test_service_optional_fields(self):
        schema = get_catalog_schema(CatalogType.service)
        optional = [f["field"] for f in schema["optional"]]
        assert len(optional) == 9
        assert "description" in optional
        assert "category" in optional
        assert "price" in optional
        assert "availability" in optional
        assert "area_served" in optional

    def test_service_total_fields(self):
        all_fields = get_all_fields(CatalogType.service)
        assert len(all_fields) == 13

    def test_destination_mapping_completeness(self):
        required = get_required_fields(CatalogType.destination)
        result = validate_mapping_completeness(CatalogType.destination, required)
        assert result["is_complete"] is True

    def test_service_mapping_completeness(self):
        required = get_required_fields(CatalogType.service)
        result = validate_mapping_completeness(CatalogType.service, required)
        assert result["is_complete"] is True


# ---------------------------------------------------------------------------
# _VALID_CATALOG_TYPES (API validation)
# ---------------------------------------------------------------------------

class TestValidCatalogTypes:
    def test_destination_accepted(self):
        validate_catalog_type("destination")  # should not raise

    def test_service_accepted(self):
        validate_catalog_type("service")  # should not raise

    def test_invalid_rejected(self):
        with pytest.raises(ValueError, match="Invalid catalog_type"):
            validate_catalog_type("fake_type")

    def test_all_enum_values_accepted(self):
        for ct in CatalogType:
            validate_catalog_type(ct.value)  # should not raise


# ---------------------------------------------------------------------------
# ChannelType enum — new channels
# ---------------------------------------------------------------------------

class TestChannelType:
    def test_facebook_streaming_ads(self):
        assert ChannelType.facebook_streaming_ads.value == "facebook_streaming_ads"

    def test_facebook_destination_ads(self):
        assert ChannelType.facebook_destination_ads.value == "facebook_destination_ads"

    def test_tiktok_destination(self):
        assert ChannelType.tiktok_destination.value == "tiktok_destination"

    def test_facebook_professional_services(self):
        assert ChannelType.facebook_professional_services.value == "facebook_professional_services"


# ---------------------------------------------------------------------------
# catalog_field_schemas fallback
# ---------------------------------------------------------------------------

class TestCatalogFieldSchemasFallback:
    def test_destination_fields_importable(self):
        from app.services.feed_management.catalog_field_schemas import DESTINATION_FIELDS
        assert len(DESTINATION_FIELDS) == 16

    def test_service_fields_importable(self):
        from app.services.feed_management.catalog_field_schemas import SERVICE_FIELDS
        assert len(SERVICE_FIELDS) == 13

    def test_catalog_field_schemas_dict_has_destination(self):
        from app.services.feed_management.catalog_field_schemas import CATALOG_FIELD_SCHEMAS
        assert "destination" in CATALOG_FIELD_SCHEMAS
        assert len(CATALOG_FIELD_SCHEMAS["destination"]) == 16

    def test_catalog_field_schemas_dict_has_service(self):
        from app.services.feed_management.catalog_field_schemas import CATALOG_FIELD_SCHEMAS
        assert "service" in CATALOG_FIELD_SCHEMAS
        assert len(CATALOG_FIELD_SCHEMAS["service"]) == 13

    def test_destination_required_count(self):
        from app.services.feed_management.catalog_field_schemas import DESTINATION_FIELDS
        required = [f for f in DESTINATION_FIELDS if f.required]
        assert len(required) == 5

    def test_service_required_count(self):
        from app.services.feed_management.catalog_field_schemas import SERVICE_FIELDS
        required = [f for f in SERVICE_FIELDS if f.required]
        assert len(required) == 4
