"""Tests for sync lifecycle: reconciliation of stale products.

Verifies that:
- Stale products (no longer in source) are removed after sync
- New products from source are added
- Zero-product response skips reconciliation (safety net)
- Large deletions are allowed but logged
- WooCommerce connector only fetches published products
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feed_management.sync_service import FeedSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(product_id: str, title: str = "Test", price: float = 100.0):
    """Create a mock ProductData."""
    from app.services.feed_management.connectors.base import ProductData
    return ProductData(
        id=product_id,
        title=title,
        price=price,
    )


def _make_source():
    """Create a mock FeedSourceResponse."""
    m = MagicMock()
    m.id = "source-1"
    m.source_type = MagicMock()
    m.source_type.value = "woocommerce"
    m.config = {"store_url": "https://test.example.com"}
    m.credentials_secret_id = None
    return m


def _make_import():
    """Create a mock FeedImportResponse."""
    m = MagicMock()
    m.id = "import-1"
    m.status = MagicMock()
    m.status.value = "pending"
    return m


# ---------------------------------------------------------------------------
# _reconcile_stale_products tests
# ---------------------------------------------------------------------------

class TestReconcileStaleProducts:

    def test_removes_stale_products(self):
        """Products absent from source are removed from MongoDB."""
        service = FeedSyncService()
        errors: list = []

        with patch.object(
            service, "_source_repo"
        ), patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            mock_repo.get_product_ids.return_value = {"1", "2", "3"}
            mock_repo.remove_stale_products.return_value = 1

            removed = service._reconcile_stale_products(
                "source-1", {"1", "2"}, errors,
            )

        assert removed == 1
        mock_repo.remove_stale_products.assert_called_once_with("source-1", {"3"})
        assert not errors

    def test_adds_new_products_no_stale(self):
        """When source has new products and none removed, nothing deleted."""
        service = FeedSyncService()
        errors: list = []

        with patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            mock_repo.get_product_ids.return_value = {"1", "2"}
            mock_repo.remove_stale_products.return_value = 0

            removed = service._reconcile_stale_products(
                "source-1", {"1", "2", "3"}, errors,
            )

        assert removed == 0

    def test_skips_reconciliation_on_empty_sync(self):
        """If source returned 0 products, don't delete anything (API may be down)."""
        service = FeedSyncService()
        errors: list = []

        with patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            removed = service._reconcile_stale_products(
                "source-1", set(), errors,
            )

        assert removed == 0
        mock_repo.get_product_ids.assert_not_called()
        mock_repo.remove_stale_products.assert_not_called()

    def test_handles_get_product_ids_error(self):
        """Reconciliation errors are logged but don't crash sync."""
        service = FeedSyncService()
        errors: list = []

        with patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            mock_repo.get_product_ids.side_effect = Exception("MongoDB down")

            removed = service._reconcile_stale_products(
                "source-1", {"1"}, errors,
            )

        assert removed == 0
        assert len(errors) == 1
        assert "reconciliation_error" in errors[0]

    def test_handles_remove_stale_error(self):
        """Deletion errors are logged but don't crash sync."""
        service = FeedSyncService()
        errors: list = []

        with patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            mock_repo.get_product_ids.return_value = {"1", "2", "3"}
            mock_repo.remove_stale_products.side_effect = Exception("Delete failed")

            removed = service._reconcile_stale_products(
                "source-1", {"1"}, errors,
            )

        assert removed == 0
        assert len(errors) == 1

    def test_large_deletion_proceeds_with_warning(self):
        """Large deletions (>50%) proceed but are logged."""
        service = FeedSyncService()
        errors: list = []

        with patch(
            "app.services.feed_management.sync_service.feed_products_repository"
        ) as mock_repo:
            # 10 existing, only 2 synced → 8 to delete (80%)
            mock_repo.get_product_ids.return_value = {str(i) for i in range(10)}
            mock_repo.remove_stale_products.return_value = 8

            removed = service._reconcile_stale_products(
                "source-1", {"0", "1"}, errors,
            )

        assert removed == 8
        mock_repo.remove_stale_products.assert_called_once()


# ---------------------------------------------------------------------------
# WooCommerce connector tests
# ---------------------------------------------------------------------------

class TestWooCommercePublishFilter:

    def test_fetch_params_include_publish_status(self):
        """WooCommerce connector should only fetch published products."""
        from app.services.feed_management.connectors.woocommerce_connector import (
            WooCommerceConnector,
        )
        connector = WooCommerceConnector(
            config={"store_url": "https://test.example.com"},
            credentials={"consumer_key": "ck_test", "consumer_secret": "cs_test"},
        )
        # The params are set in fetch_products — verify via code inspection
        # (actual HTTP call would require mocking httpx)
        import inspect
        source = inspect.getsource(connector.fetch_products)
        assert '"status": "publish"' in source or "'status': 'publish'" in source


# ---------------------------------------------------------------------------
# Integration: run_sync collects IDs and reconciles
# ---------------------------------------------------------------------------

class TestRunSyncReconciliation:

    def test_run_sync_collects_ids_and_reconciles(self):
        """run_sync should collect synced product IDs and call reconciliation."""
        service = FeedSyncService()

        products = [_make_product("p1"), _make_product("p2")]

        async def _mock_fetch_products(since=None):
            for p in products:
                yield p

        mock_connector = MagicMock()
        mock_connector.fetch_products = _mock_fetch_products

        mock_import = _make_import()

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
            ) as mock_reconcile,
            patch.object(service, "_update_source_after_sync"),
        ):
            mock_source_repo.get_by_id.return_value = _make_source()
            mock_import_repo.get_latest_by_source.return_value = None
            mock_import_repo.create.return_value = mock_import
            mock_import_repo.update_status.return_value = mock_import
            mock_products_repo.upsert_products_batch.return_value = 2

            result = asyncio.run(service.run_sync("source-1"))

        # Reconcile was called with the correct synced IDs
        mock_reconcile.assert_called_once()
        call_args = mock_reconcile.call_args
        assert call_args[0][0] == "source-1"  # feed_source_id
        assert call_args[0][1] == {"p1", "p2"}  # synced_product_ids
