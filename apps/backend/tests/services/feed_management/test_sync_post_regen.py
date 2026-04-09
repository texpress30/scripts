"""Tests for post-sync feed regeneration.

Verifies that after a successful sync, every active channel's S3 feed
artifact is regenerated so `GET /feeds/{token}.{ext}` serves fresh data
without requiring a manual "Generate Feed" click.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feed_management.models import FeedImportStatus
from app.services.feed_management.sync_service import FeedSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(product_id: str, title: str = "Test", price: float = 100.0):
    from app.services.feed_management.connectors.base import ProductData
    return ProductData(id=product_id, title=title, price=price)


def _make_source():
    m = MagicMock()
    m.id = "source-1"
    m.source_type = MagicMock()
    m.source_type.value = "woocommerce"
    m.config = {"store_url": "https://test.example.com"}
    m.credentials_secret_id = None
    return m


def _make_completed_import():
    """Mock a FeedImportResponse with real FeedImportStatus.completed."""
    m = MagicMock()
    m.id = "import-1"
    m.status = FeedImportStatus.completed
    return m


def _make_failed_import():
    m = MagicMock()
    m.id = "import-1"
    m.status = FeedImportStatus.failed
    return m


def _make_channel(channel_id: str):
    m = MagicMock()
    m.id = channel_id
    return m


def _make_feed_result(status: str = "ok", included: int = 10, excluded: int = 0):
    m = MagicMock()
    m.status = status
    m.included_products = included
    m.excluded_products = excluded
    return m


# ---------------------------------------------------------------------------
# _regenerate_channels_after_sync direct tests
# ---------------------------------------------------------------------------

class TestRegenerateChannelsAfterSync:

    def test_calls_generate_for_each_active_channel(self):
        """Every active channel gets generate() called exactly once."""
        service = FeedSyncService()
        channels = [_make_channel("ch-1"), _make_channel("ch-2")]

        with (
            patch(
                "app.services.feed_management.channels.repository.feed_channel_repository",
            ) as mock_repo,
            patch(
                "app.services.feed_management.channels.feed_generator.feed_generator",
            ) as mock_gen,
        ):
            mock_repo.list_active_by_source.return_value = channels
            mock_gen.generate.return_value = _make_feed_result()

            asyncio.run(service._regenerate_channels_after_sync("source-1"))

        mock_repo.list_active_by_source.assert_called_once_with("source-1")
        assert mock_gen.generate.call_count == 2
        called_ids = {c.args[0] for c in mock_gen.generate.call_args_list}
        assert called_ids == {"ch-1", "ch-2"}

    def test_one_channel_failure_does_not_block_others(self):
        """A raising generate() on one channel must not stop the loop."""
        service = FeedSyncService()
        channels = [
            _make_channel("ch-1"),
            _make_channel("ch-2"),
            _make_channel("ch-3"),
        ]

        def _fake_generate(channel_id):
            if channel_id == "ch-2":
                raise RuntimeError("S3 upload failed")
            return _make_feed_result()

        with (
            patch(
                "app.services.feed_management.channels.repository.feed_channel_repository",
            ) as mock_repo,
            patch(
                "app.services.feed_management.channels.feed_generator.feed_generator",
            ) as mock_gen,
        ):
            mock_repo.list_active_by_source.return_value = channels
            mock_gen.generate.side_effect = _fake_generate

            # Must not raise.
            asyncio.run(service._regenerate_channels_after_sync("source-1"))

        assert mock_gen.generate.call_count == 3

    def test_no_active_channels_is_a_noop(self):
        """Empty channel list logs and returns cleanly."""
        service = FeedSyncService()

        with (
            patch(
                "app.services.feed_management.channels.repository.feed_channel_repository",
            ) as mock_repo,
            patch(
                "app.services.feed_management.channels.feed_generator.feed_generator",
            ) as mock_gen,
        ):
            mock_repo.list_active_by_source.return_value = []

            asyncio.run(service._regenerate_channels_after_sync("source-1"))

        mock_gen.generate.assert_not_called()

    def test_list_channels_failure_is_swallowed(self):
        """If listing active channels raises, we log and return."""
        service = FeedSyncService()

        with (
            patch(
                "app.services.feed_management.channels.repository.feed_channel_repository",
            ) as mock_repo,
            patch(
                "app.services.feed_management.channels.feed_generator.feed_generator",
            ) as mock_gen,
        ):
            mock_repo.list_active_by_source.side_effect = Exception("DB down")

            # Must not raise.
            asyncio.run(service._regenerate_channels_after_sync("source-1"))

        mock_gen.generate.assert_not_called()


# ---------------------------------------------------------------------------
# run_sync integration: regeneration gate
# ---------------------------------------------------------------------------

class TestRunSyncTriggersRegeneration:

    def _run_sync_with_mocks(self, *, final_import, connector_raises=False):
        """Run run_sync with all external collaborators mocked out.

        Returns (result, mock_regenerate) so callers can assert on both.
        """
        service = FeedSyncService()
        products = [_make_product("p1"), _make_product("p2")]

        async def _mock_fetch_products(since=None):
            if connector_raises:
                raise RuntimeError("connector boom")
            for p in products:
                yield p

        mock_connector = MagicMock()
        mock_connector.fetch_products = _mock_fetch_products

        with (
            patch.object(service, "_source_repo") as mock_source_repo,
            patch.object(service, "_import_repo") as mock_import_repo,
            patch(
                "app.services.feed_management.sync_service._get_connector",
                return_value=mock_connector,
            ),
            patch(
                "app.services.feed_management.sync_service.feed_products_repository",
            ) as mock_products_repo,
            patch.object(
                service, "_reconcile_stale_products", return_value=0,
            ),
            patch.object(service, "_update_source_after_sync"),
            patch.object(
                service,
                "_regenerate_channels_after_sync",
                new_callable=AsyncMock,
            ) as mock_regenerate,
        ):
            mock_source_repo.get_by_id.return_value = _make_source()
            mock_import_repo.get_latest_by_source.return_value = None
            mock_import_repo.create.return_value = final_import
            mock_import_repo.update_status.return_value = final_import
            mock_products_repo.upsert_products_batch.return_value = 2

            result = asyncio.run(service.run_sync("source-1"))

        return result, mock_regenerate

    def test_successful_sync_triggers_regeneration(self):
        """A sync that completes cleanly must call _regenerate_channels_after_sync."""
        result, mock_regenerate = self._run_sync_with_mocks(
            final_import=_make_completed_import(),
        )

        assert result.status == FeedImportStatus.completed
        mock_regenerate.assert_awaited_once_with("source-1")

    def test_failed_sync_does_not_trigger_regeneration(self):
        """A sync that ends up as `failed` must NOT regenerate the feed."""
        result, mock_regenerate = self._run_sync_with_mocks(
            final_import=_make_failed_import(),
            connector_raises=True,
        )

        assert result.status == FeedImportStatus.failed
        mock_regenerate.assert_not_awaited()

    def test_regeneration_crash_does_not_break_sync(self):
        """If _regenerate_channels_after_sync raises, sync still returns cleanly."""
        service = FeedSyncService()
        products = [_make_product("p1")]

        async def _mock_fetch_products(since=None):
            for p in products:
                yield p

        mock_connector = MagicMock()
        mock_connector.fetch_products = _mock_fetch_products
        final_import = _make_completed_import()

        with (
            patch.object(service, "_source_repo") as mock_source_repo,
            patch.object(service, "_import_repo") as mock_import_repo,
            patch(
                "app.services.feed_management.sync_service._get_connector",
                return_value=mock_connector,
            ),
            patch(
                "app.services.feed_management.sync_service.feed_products_repository",
            ) as mock_products_repo,
            patch.object(
                service, "_reconcile_stale_products", return_value=0,
            ),
            patch.object(service, "_update_source_after_sync"),
            patch.object(
                service,
                "_regenerate_channels_after_sync",
                new_callable=AsyncMock,
                side_effect=RuntimeError("regen boom"),
            ),
        ):
            mock_source_repo.get_by_id.return_value = _make_source()
            mock_import_repo.get_latest_by_source.return_value = None
            mock_import_repo.create.return_value = final_import
            mock_import_repo.update_status.return_value = final_import
            mock_products_repo.upsert_products_batch.return_value = 1

            # Must not raise — regeneration failure is a safety-net logged exc.
            result = asyncio.run(service.run_sync("source-1"))

        assert result.status == FeedImportStatus.completed
