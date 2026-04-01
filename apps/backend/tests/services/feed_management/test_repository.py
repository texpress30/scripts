from __future__ import annotations

import json
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.feed_management.exceptions import (
    FeedImportInProgressError,
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedImportCreate,
    FeedImportStatus,
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceType,
)
from app.services.feed_management.repository import (
    FeedImportRepository,
    FeedSourceRepository,
)

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


class _FakeCursor:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn
        self._next_fetchone: tuple | None = None
        self._next_fetchall: list[tuple] = []
        self.rowcount: int = 0

    def execute(self, query: str, params: tuple | None = None) -> None:
        sql = str(query).strip()
        self.conn.executed.append((sql, params))

        # --- feed_sources queries ---
        if "SELECT id FROM feed_sources" in sql and "name" in sql:
            # Duplicate check: look up by subaccount_id + name
            subaccount_id, name = params[0], params[1]
            match = None
            for row in self.conn.feed_sources:
                if row[1] == subaccount_id and row[3] == name:
                    match = (row[0],)
                    break
            self._next_fetchone = match

        elif "INSERT INTO feed_sources" in sql:
            source_id = params[0]
            row = (
                source_id,
                params[1],       # subaccount_id
                params[2],       # source_type
                params[3],       # name
                json.loads(params[4]) if isinstance(params[4], str) else params[4],  # config
                params[5],       # credentials_secret_id
                True,            # is_active default
                _NOW,            # created_at
                _NOW,            # updated_at
            )
            self.conn.feed_sources.append(row)
            self._next_fetchone = row

        elif "DELETE FROM feed_sources" in sql:
            source_id = params[0]
            before = len(self.conn.feed_sources)
            self.conn.feed_sources = [r for r in self.conn.feed_sources if str(r[0]) != str(source_id)]
            self.rowcount = before - len(self.conn.feed_sources)

        elif "SELECT" in sql and "FROM feed_sources WHERE id" in sql:
            source_id = params[0]
            match = None
            for row in self.conn.feed_sources:
                if str(row[0]) == str(source_id):
                    match = row
                    break
            self._next_fetchone = match

        elif "FROM feed_sources WHERE subaccount_id" in sql:
            subaccount_id = params[0]
            self._next_fetchall = [row for row in self.conn.feed_sources if row[1] == subaccount_id]

        elif "UPDATE feed_sources" in sql:
            source_id = params[-1]
            for i, row in enumerate(self.conn.feed_sources):
                if str(row[0]) == str(source_id):
                    self._next_fetchone = row
                    break
            else:
                self._next_fetchone = None

        elif "FROM feed_sources ORDER BY" in sql:
            self._next_fetchall = list(self.conn.feed_sources)

        # --- feed_imports queries ---
        elif "SELECT id FROM feed_imports" in sql and "status" in sql:
            feed_source_id = params[0]
            match = None
            for row in self.conn.feed_imports:
                if str(row[1]) == str(feed_source_id) and row[2] in ("pending", "in_progress"):
                    match = (row[0],)
                    break
            self._next_fetchone = match

        elif "INSERT INTO feed_imports" in sql:
            import_id = params[0]
            row = (
                import_id,
                params[1],   # feed_source_id
                "pending",   # status default
                0,           # total_products
                0,           # imported_products
                [],          # errors
                None,        # started_at
                None,        # completed_at
                _NOW,        # created_at
            )
            self.conn.feed_imports.append(row)
            self._next_fetchone = row

        elif "FROM feed_imports WHERE id" in sql:
            import_id = params[0]
            match = None
            for row in self.conn.feed_imports:
                if str(row[0]) == str(import_id):
                    match = row
                    break
            self._next_fetchone = match

        elif "FROM feed_imports WHERE feed_source_id" in sql and "ORDER BY" in sql and "LIMIT 1" in sql:
            feed_source_id = params[0]
            matches = [r for r in self.conn.feed_imports if str(r[1]) == str(feed_source_id)]
            self._next_fetchone = matches[0] if matches else None

        elif "FROM feed_imports WHERE feed_source_id" in sql:
            feed_source_id = params[0]
            self._next_fetchall = [r for r in self.conn.feed_imports if str(r[1]) == str(feed_source_id)]

        elif "UPDATE feed_imports" in sql:
            import_id = params[-1]
            new_status = params[0]
            for i, row in enumerate(self.conn.feed_imports):
                if str(row[0]) == str(import_id):
                    updated = list(row)
                    updated[2] = new_status
                    if new_status == "in_progress":
                        updated[6] = updated[6] or _NOW
                    if new_status in ("completed", "failed"):
                        updated[7] = _NOW
                    # Check for extra params (total_products, imported_products, errors)
                    param_idx = 1
                    remaining_sql_parts = sql.split("status = %s")[1] if "status = %s" in sql else ""
                    if "total_products = %s" in remaining_sql_parts:
                        updated[3] = params[param_idx]
                        param_idx += 1
                    if "imported_products = %s" in remaining_sql_parts:
                        updated[4] = params[param_idx]
                        param_idx += 1
                    if "errors = %s" in remaining_sql_parts:
                        updated[5] = json.loads(params[param_idx]) if isinstance(params[param_idx], str) else params[param_idx]
                        param_idx += 1
                    updated_row = tuple(updated)
                    self.conn.feed_imports[i] = updated_row
                    self._next_fetchone = updated_row
                    break
            else:
                self._next_fetchone = None

    def fetchone(self) -> tuple | None:
        return self._next_fetchone

    def fetchall(self) -> list[tuple]:
        return list(self._next_fetchall)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self) -> None:
        self.feed_sources: list[tuple] = []
        self.feed_imports: list[tuple] = []
        self.executed: list[tuple[str, tuple | None]] = []

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        pass


@contextmanager
def _fake_connection():
    yield _shared_conn


_shared_conn = _FakeConn()


def _reset_conn():
    global _shared_conn
    _shared_conn = _FakeConn()


class TestFeedSourceRepository(unittest.TestCase):
    def setUp(self):
        _reset_conn()
        self.repo = FeedSourceRepository()
        self.patcher = patch(
            "app.services.feed_management.repository._connect",
            side_effect=_fake_connection,
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_create_feed_source(self):
        payload = FeedSourceCreate(
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="My Shopify Store",
            config=FeedSourceConfig(store_url="https://myshop.myshopify.com"),
        )
        result = self.repo.create(payload)

        self.assertEqual(result.subaccount_id, 42)
        self.assertEqual(result.source_type, FeedSourceType.shopify)
        self.assertEqual(result.name, "My Shopify Store")
        self.assertTrue(result.is_active)
        self.assertIsNotNone(result.id)

    def test_create_feed_source_duplicate_name_raises(self):
        payload = FeedSourceCreate(
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="Duplicate Store",
        )
        self.repo.create(payload)

        with self.assertRaises(FeedSourceAlreadyExistsError):
            self.repo.create(payload)

    def test_get_by_subaccount(self):
        for i in range(3):
            self.repo.create(FeedSourceCreate(
                subaccount_id=10,
                source_type=FeedSourceType.csv,
                name=f"Source {i}",
            ))
        # Different subaccount
        self.repo.create(FeedSourceCreate(
            subaccount_id=20,
            source_type=FeedSourceType.woocommerce,
            name="Other",
        ))

        results = self.repo.get_by_subaccount(10)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertEqual(r.subaccount_id, 10)

    def test_get_by_id_not_found_raises(self):
        with self.assertRaises(FeedSourceNotFoundError):
            self.repo.get_by_id("nonexistent-uuid")

    def test_delete_feed_source(self):
        payload = FeedSourceCreate(
            subaccount_id=42,
            source_type=FeedSourceType.json,
            name="To Delete",
        )
        created = self.repo.create(payload)
        self.repo.delete(created.id)

        with self.assertRaises(FeedSourceNotFoundError):
            self.repo.get_by_id(created.id)


class TestFeedImportRepository(unittest.TestCase):
    def setUp(self):
        _reset_conn()
        self.source_repo = FeedSourceRepository()
        self.import_repo = FeedImportRepository()
        self.patcher = patch(
            "app.services.feed_management.repository._connect",
            side_effect=_fake_connection,
        )
        self.patcher.start()

        # Create a source to use in import tests
        self.source = self.source_repo.create(FeedSourceCreate(
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="Import Test Store",
        ))

    def tearDown(self):
        self.patcher.stop()

    def test_create_import(self):
        result = self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))

        self.assertIsNotNone(result.id)
        self.assertEqual(result.feed_source_id, self.source.id)
        self.assertEqual(result.status, FeedImportStatus.pending)
        self.assertEqual(result.total_products, 0)
        self.assertEqual(result.imported_products, 0)

    def test_create_import_blocks_if_in_progress(self):
        self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))

        with self.assertRaises(FeedImportInProgressError):
            self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))

    def test_update_status(self):
        created = self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))
        updated = self.import_repo.update_status(
            created.id,
            status=FeedImportStatus.in_progress,
        )

        self.assertEqual(updated.status, FeedImportStatus.in_progress)
        self.assertIsNotNone(updated.started_at)

    def test_update_status_completed_with_counts(self):
        created = self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))

        # Move to in_progress first to clear the block
        self.import_repo.update_status(created.id, status=FeedImportStatus.in_progress)

        completed = self.import_repo.update_status(
            created.id,
            status=FeedImportStatus.completed,
            total_products=100,
            imported_products=95,
            errors=[{"sku": "ABC123", "reason": "missing price"}],
        )

        self.assertEqual(completed.status, FeedImportStatus.completed)
        self.assertEqual(completed.total_products, 100)
        self.assertEqual(completed.imported_products, 95)
        self.assertIsNotNone(completed.completed_at)

    def test_get_latest_by_source(self):
        self.import_repo.create(FeedImportCreate(feed_source_id=self.source.id))
        latest = self.import_repo.get_latest_by_source(self.source.id)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.feed_source_id, self.source.id)

    def test_get_latest_by_source_returns_none_when_empty(self):
        result = self.import_repo.get_latest_by_source("nonexistent-uuid")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
