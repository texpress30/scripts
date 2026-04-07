from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.api import feed_sources as feed_sources_api
from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedImportInProgressError,
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedImportResponse,
    FeedImportStatus,
    FeedSourceConfig,
    FeedSourceResponse,
    FeedSourceType,
)

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

_ADMIN_USER = AuthUser(email="admin@example.com", role="agency_admin")
_VIEWER_USER = AuthUser(email="viewer@example.com", role="agency_viewer")

_SAMPLE_SOURCE = FeedSourceResponse(
    id="src-001",
    subaccount_id=42,
    source_type=FeedSourceType.csv,
    name="Test CSV Feed",
    config={"file_url": "https://example.com/products.csv", "file_type": "csv"},
    credentials_secret_id=None,
    is_active=True,
    created_at=_NOW,
    updated_at=_NOW,
)

_SAMPLE_IMPORT = FeedImportResponse(
    id="imp-001",
    feed_source_id="src-001",
    status=FeedImportStatus.pending,
    total_products=0,
    imported_products=0,
    errors=[],
    started_at=None,
    completed_at=None,
    created_at=_NOW,
)


def _enable_feature_flag():
    return patch.object(
        feed_sources_api,
        "_enforce_feature_flag",
        lambda: None,
    )


def _disable_feature_flag():
    def _raise():
        raise feed_sources_api.HTTPException(status_code=404, detail="Feed management is not enabled")
    return patch.object(feed_sources_api, "_enforce_feature_flag", _raise)


class TestListFeedSources(unittest.TestCase):
    def test_returns_empty_list(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.get_by_subaccount
            try:
                feed_sources_api._source_repo.get_by_subaccount = lambda subaccount_id: []
                result = feed_sources_api.list_feed_sources(subaccount_id=42, user=_ADMIN_USER)
                self.assertEqual(result.items, [])
            finally:
                feed_sources_api._source_repo.get_by_subaccount = original

    def test_returns_sources(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.get_by_subaccount
            try:
                feed_sources_api._source_repo.get_by_subaccount = lambda subaccount_id: [_SAMPLE_SOURCE]
                result = feed_sources_api.list_feed_sources(subaccount_id=42, user=_ADMIN_USER)
                self.assertEqual(len(result.items), 1)
                self.assertEqual(result.items[0].name, "Test CSV Feed")
            finally:
                feed_sources_api._source_repo.get_by_subaccount = original


class TestCreateFeedSource(unittest.TestCase):
    def test_creates_csv_source(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.create
            try:
                feed_sources_api._source_repo.create = lambda payload: _SAMPLE_SOURCE
                payload = feed_sources_api.CreateFeedSourceRequest(
                    source_type=FeedSourceType.csv,
                    name="Test CSV Feed",
                    config=FeedSourceConfig(file_url="https://example.com/products.csv"),
                )
                result = feed_sources_api.create_feed_source(subaccount_id=42, payload=payload, user=_ADMIN_USER)
                self.assertEqual(result.source.source_type, FeedSourceType.csv)
                self.assertEqual(result.source.name, "Test CSV Feed")
                self.assertIsNone(result.authorize_url)
            finally:
                feed_sources_api._source_repo.create = original

    def test_duplicate_raises_409(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.create
            try:
                def _raise(payload):
                    raise FeedSourceAlreadyExistsError("Dup", 42)
                feed_sources_api._source_repo.create = _raise
                payload = feed_sources_api.CreateFeedSourceRequest(
                    source_type=FeedSourceType.csv,
                    name="Dup",
                )
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.create_feed_source(subaccount_id=42, payload=payload, user=_ADMIN_USER)
                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                feed_sources_api._source_repo.create = original

    def test_forbidden_for_viewer(self):
        with _enable_feature_flag():
            payload = feed_sources_api.CreateFeedSourceRequest(
                source_type=FeedSourceType.csv,
                name="Test",
            )
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.create_feed_source(subaccount_id=42, payload=payload, user=_VIEWER_USER)
            self.assertEqual(ctx.exception.status_code, 403)


class TestGetFeedSource(unittest.TestCase):
    def test_get_by_id(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _SAMPLE_SOURCE
                result = feed_sources_api.get_feed_source(subaccount_id=42, source_id="src-001", user=_ADMIN_USER)
                self.assertEqual(result.id, "src-001")
            finally:
                feed_sources_api._source_repo.get_by_id = original

    def test_not_found_raises_404(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.get_by_id
            try:
                def _raise(source_id):
                    raise FeedSourceNotFoundError(source_id)
                feed_sources_api._source_repo.get_by_id = _raise
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.get_feed_source(subaccount_id=42, source_id="nope", user=_ADMIN_USER)
                self.assertEqual(ctx.exception.status_code, 404)
            finally:
                feed_sources_api._source_repo.get_by_id = original

    def test_wrong_subaccount_raises_404(self):
        with _enable_feature_flag():
            original = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _SAMPLE_SOURCE
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.get_feed_source(subaccount_id=999, source_id="src-001", user=_ADMIN_USER)
                self.assertEqual(ctx.exception.status_code, 404)
            finally:
                feed_sources_api._source_repo.get_by_id = original


class TestTriggerSync(unittest.TestCase):
    def test_creates_import_and_queues_background(self):
        with _enable_feature_flag():
            orig_get = feed_sources_api._source_repo.get_by_id
            orig_create = feed_sources_api._import_repo.create
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _SAMPLE_SOURCE
                feed_sources_api._import_repo.create = lambda payload: _SAMPLE_IMPORT
                bg = MagicMock()
                result = feed_sources_api.trigger_sync(
                    subaccount_id=42, source_id="src-001", background_tasks=bg, user=_ADMIN_USER,
                )
                self.assertEqual(result.import_id, "imp-001")
                self.assertEqual(result.status, "pending")
                bg.add_task.assert_called_once()
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
                feed_sources_api._import_repo.create = orig_create

    def test_blocks_if_import_in_progress(self):
        with _enable_feature_flag():
            orig_get = feed_sources_api._source_repo.get_by_id
            orig_create = feed_sources_api._import_repo.create
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _SAMPLE_SOURCE
                def _raise(payload):
                    raise FeedImportInProgressError("src-001")
                feed_sources_api._import_repo.create = _raise
                bg = MagicMock()
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.trigger_sync(
                        subaccount_id=42, source_id="src-001", background_tasks=bg, user=_ADMIN_USER,
                    )
                self.assertEqual(ctx.exception.status_code, 409)
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
                feed_sources_api._import_repo.create = orig_create


class TestFeatureFlagDisabled(unittest.TestCase):
    def test_list_returns_404(self):
        with _disable_feature_flag():
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.list_feed_sources(subaccount_id=42, user=_ADMIN_USER)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_create_returns_404(self):
        with _disable_feature_flag():
            payload = feed_sources_api.CreateFeedSourceRequest(source_type=FeedSourceType.csv, name="Test")
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.create_feed_source(subaccount_id=42, payload=payload, user=_ADMIN_USER)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_get_returns_404(self):
        with _disable_feature_flag():
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.get_feed_source(subaccount_id=42, source_id="src-001", user=_ADMIN_USER)
            self.assertEqual(ctx.exception.status_code, 404)


class TestListImports(unittest.TestCase):
    def test_list_imports_for_source(self):
        with _enable_feature_flag():
            orig_get = feed_sources_api._source_repo.get_by_id
            orig_imports = feed_sources_api._import_repo.get_by_source
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _SAMPLE_SOURCE
                feed_sources_api._import_repo.get_by_source = lambda source_id: [_SAMPLE_IMPORT]
                result = feed_sources_api.list_imports(subaccount_id=42, source_id="src-001", user=_ADMIN_USER)
                self.assertEqual(len(result.items), 1)
                self.assertEqual(result.items[0].id, "imp-001")
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
                feed_sources_api._import_repo.get_by_source = orig_imports


if __name__ == "__main__":
    unittest.main()
