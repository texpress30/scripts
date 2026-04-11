"""Render cache logic checks that don't require a real Postgres connection.

The render_cache module is mostly SQL plumbing — we exercise the query shape
by monkeypatching ``get_connection`` with a fake cursor that records the
statements the module would execute.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.enriched_catalog import render_cache


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed: list[tuple[str, tuple]] = []
        self.rowcount = 0

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        # Return value for DELETE statements.
        self.rowcount = len(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _patch_pool(monkeypatch, cursor: FakeCursor) -> FakeConnection:
    connection = FakeConnection(cursor)

    class _Pool:
        def __enter__(self_inner):
            return connection

        def __exit__(self_inner, *args):
            return False

    import app.db.pool as pool_module

    monkeypatch.setattr(pool_module, "get_connection", lambda: _Pool())
    return connection


class TestGetResult:
    def test_cache_miss_returns_none(self, monkeypatch):
        cursor = FakeCursor(rows=[])
        _patch_pool(monkeypatch, cursor)

        result = render_cache.get_result(
            template_id="tpl-1",
            template_version=3,
            output_feed_id="00000000-0000-0000-0000-000000000001",
            product_id="p-1",
        )
        assert result is None
        assert len(cursor.executed) == 1
        sql, params = cursor.executed[0]
        assert "template_render_results" in sql
        assert params == ("tpl-1", 3, "00000000-0000-0000-0000-000000000001", "p-1")

    def test_cache_hit_builds_record(self, monkeypatch):
        row = (
            "tpl-1",
            3,
            "00000000-0000-0000-0000-000000000001",
            "p-1",
            "enriched-catalog/feed/previews/tpl-1/3/p-1.png",
            "https://cdn/p-1.png",
            "media-abc",
            "ready",
        )
        cursor = FakeCursor(rows=[row])
        _patch_pool(monkeypatch, cursor)

        result = render_cache.get_result(
            template_id="tpl-1",
            template_version=3,
            output_feed_id="00000000-0000-0000-0000-000000000001",
            product_id="p-1",
        )
        assert result is not None
        assert result.status == "ready"
        assert result.s3_key.endswith("p-1.png")
        assert result.media_id == "media-abc"


class TestInvalidateByOutputFeed:
    def test_delete_by_feed(self, monkeypatch):
        cursor = FakeCursor(rows=[(1,), (2,)])
        _patch_pool(monkeypatch, cursor)

        deleted = render_cache.invalidate_by_output_feed(
            "00000000-0000-0000-0000-000000000001"
        )
        assert deleted == 2
        sql, params = cursor.executed[-1]
        assert "DELETE FROM template_render_results" in sql
        assert params == ("00000000-0000-0000-0000-000000000001",)
