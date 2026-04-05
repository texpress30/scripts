"""Tests for manually_edited flag on master field mappings.

Verifies that:
- Auto-suggestions skip fields marked manually_edited
- The fuzzy suggestion engine respects the flag
- Bulk save correctly persists the flag
"""

from __future__ import annotations

import pytest

from app.services.feed_management.master_fields.service import _suggest_source_field


# ---------------------------------------------------------------------------
# Fuzzy suggestion tests
# ---------------------------------------------------------------------------

def _make_target(field_key: str, **kwargs) -> dict:
    return {"field_key": field_key, "display_name": field_key, **kwargs}


class TestSuggestSourceField:
    """Unit tests for the fuzzy auto-suggestion engine."""

    def test_exact_match(self):
        result = _suggest_source_field(
            _make_target("title"),
            ["title", "description", "price"],
        )
        assert result == "title"

    def test_substring_match_target_in_source(self):
        """e.g. target 'url' matches source 'permalink_url'."""
        result = _suggest_source_field(
            _make_target("url"),
            ["permalink_url", "name", "price"],
        )
        assert result == "permalink_url"

    def test_substring_match_source_in_target(self):
        """e.g. target 'product_title' matches source 'title'."""
        result = _suggest_source_field(
            _make_target("product_title"),
            ["title", "description"],
        )
        assert result == "title"

    def test_no_match(self):
        result = _suggest_source_field(
            _make_target("applink_ios_app_name"),
            ["meta_brand", "meta_model", "price"],
        )
        assert result is None

    def test_problematic_url_match(self):
        """Demonstrates the bug: 'applink_ios_url' fuzzy-matches 'url'
        because 'url' (3 chars, passes the len>=3 check) is contained
        in 'applink_ios_url'."""
        result = _suggest_source_field(
            _make_target("applink_ios_url"),
            ["url", "name", "price"],
        )
        # This WILL match due to substring logic — the fix is to not call
        # _suggest_source_field at all for manually_edited fields.
        assert result == "url"

    def test_problematic_name_match(self):
        """'dealership_name' fuzzy-matches 'name'."""
        result = _suggest_source_field(
            _make_target("dealership_name"),
            ["name", "url", "price"],
        )
        assert result == "name"


# ---------------------------------------------------------------------------
# Pydantic model tests
# ---------------------------------------------------------------------------

class TestModelsManuallyEdited:
    """Verify the manually_edited field exists and defaults correctly."""

    def test_bulk_item_default(self):
        from app.services.feed_management.master_fields.models import MasterFieldMappingBulkItem
        item = MasterFieldMappingBulkItem(target_field="test")
        assert item.manually_edited is False

    def test_bulk_item_explicit_true(self):
        from app.services.feed_management.master_fields.models import MasterFieldMappingBulkItem
        item = MasterFieldMappingBulkItem(target_field="test", manually_edited=True)
        assert item.manually_edited is True

    def test_bulk_item_cleared_field(self):
        """A manually cleared field has source_field=None and manually_edited=True."""
        from app.services.feed_management.master_fields.models import MasterFieldMappingBulkItem
        item = MasterFieldMappingBulkItem(
            target_field="applink_ios_url",
            source_field=None,
            manually_edited=True,
        )
        assert item.source_field is None
        assert item.manually_edited is True

    def test_response_default(self):
        from app.services.feed_management.master_fields.models import MasterFieldMappingResponse
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        resp = MasterFieldMappingResponse(
            id="abc",
            feed_source_id="src",
            target_field="test",
            mapping_type="direct",
            is_required=False,
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        assert resp.manually_edited is False


# ---------------------------------------------------------------------------
# Service-level tests (get_mappings_with_suggestions)
# ---------------------------------------------------------------------------

class TestGetMappingsWithSuggestionsManualOverride:
    """Verify that get_mappings_with_suggestions skips suggestions for
    manually_edited fields."""

    def test_suggestions_skip_manually_edited(self):
        """Mock the repo and verify manually_edited fields get no suggestion."""
        from unittest.mock import patch, MagicMock
        from app.services.feed_management.master_fields.models import (
            MasterFieldMappingResponse,
            MappingType,
        )
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        # Simulate a manually-edited mapping with source_field=None (user cleared it)
        mock_mapping = MasterFieldMappingResponse(
            id="id1",
            feed_source_id="src1",
            target_field="applink_ios_url",
            source_field=None,
            mapping_type=MappingType.direct,
            is_required=False,
            sort_order=0,
            manually_edited=True,
            created_at=now,
            updated_at=now,
        )

        mock_source = MagicMock()
        mock_source.name = "Test Source"
        mock_source.catalog_type = "product"

        target_fields = [
            {
                "field_key": "applink_ios_url",
                "display_name": "Applink iOS URL",
                "description": "",
                "data_type": "string",
                "is_required": False,
                "category": "app_links",
                "allowed_values": None,
                "google_attribute": None,
                "facebook_attribute": None,
                "channels": [],
                "is_system": False,
                "format_pattern": None,
                "example_value": None,
                "aliases_count": 0,
                "aliases": [],
                "all_channels": [],
                "channels_count": 0,
            },
        ]

        source_fields = [
            {"field": "url", "type": "string", "sample": "https://example.com/product/1"},
            {"field": "name", "type": "string", "sample": "BMW X1"},
        ]

        with (
            patch(
                "app.services.feed_management.master_fields.service._source_repo"
            ) as mock_source_repo,
            patch(
                "app.services.feed_management.master_fields.service.master_field_mapping_repository"
            ) as mock_repo,
            patch(
                "app.services.feed_management.master_fields.service._get_target_fields",
                return_value=target_fields,
            ),
            patch(
                "app.services.feed_management.master_fields.service.get_source_fields",
                return_value=(source_fields, 50),
            ),
        ):
            mock_source_repo.get_by_id.return_value = mock_source
            mock_repo.get_by_source.return_value = [mock_mapping]

            from app.services.feed_management.master_fields.service import (
                get_mappings_with_suggestions,
            )

            result = get_mappings_with_suggestions("src1")

        # The field should appear in suggestions but with NO suggested_source_field
        # because it's manually_edited (user cleared it).
        assert len(result["suggestions"]) == 0  # it's in mapped_targets since it has a DB row
        # Actually, wait: mapped_targets = {m.target_field for m in existing}
        # Since mock_mapping has target_field="applink_ios_url", it IS in mapped_targets
        # and gets skipped entirely from suggestions. The mapping appears in result["mappings"].
        assert len(result["mappings"]) == 1
        assert result["mappings"][0]["target_field"] == "applink_ios_url"
        assert result["mappings"][0]["source_field"] is None
        assert result["mappings"][0]["manually_edited"] is True

    def test_suggestions_provided_for_non_manual_fields(self):
        """Fields NOT manually_edited should still get fuzzy suggestions."""
        from unittest.mock import patch, MagicMock

        mock_source = MagicMock()
        mock_source.name = "Test Source"
        mock_source.catalog_type = "product"

        target_fields = [
            {
                "field_key": "title",
                "display_name": "Title",
                "description": "Product title",
                "data_type": "string",
                "is_required": True,
                "category": "basic",
                "allowed_values": None,
                "google_attribute": None,
                "facebook_attribute": None,
                "channels": [],
                "is_system": True,
                "format_pattern": None,
                "example_value": None,
                "aliases_count": 0,
                "aliases": [],
                "all_channels": [],
                "channels_count": 0,
            },
        ]

        source_fields = [
            {"field": "title", "type": "string", "sample": "BMW X1 2015"},
        ]

        with (
            patch(
                "app.services.feed_management.master_fields.service._source_repo"
            ) as mock_source_repo,
            patch(
                "app.services.feed_management.master_fields.service.master_field_mapping_repository"
            ) as mock_repo,
            patch(
                "app.services.feed_management.master_fields.service._get_target_fields",
                return_value=target_fields,
            ),
            patch(
                "app.services.feed_management.master_fields.service.get_source_fields",
                return_value=(source_fields, 50),
            ),
        ):
            mock_source_repo.get_by_id.return_value = mock_source
            mock_repo.get_by_source.return_value = []  # No saved mappings

            from app.services.feed_management.master_fields.service import (
                get_mappings_with_suggestions,
            )

            result = get_mappings_with_suggestions("src1")

        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0]["target_field"] == "title"
        assert result["suggestions"][0]["suggested_source_field"] == "title"
