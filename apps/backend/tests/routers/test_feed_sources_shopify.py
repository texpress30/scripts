"""Tests for the Shopify-aware additions to the feed_sources router:
create-with-shop_domain, complete-oauth, reconnect, test-connection.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.api import feed_sources as feed_sources_api
from app.services.auth import AuthUser
from app.services.feed_management.models import (
    FeedSourceConfig,
    FeedSourceResponse,
    FeedSourceType,
)


_NOW = datetime(2026, 4, 7, tzinfo=timezone.utc)
_ADMIN = AuthUser(email="admin@example.com", role="agency_admin")


def _shopify_source(**overrides) -> FeedSourceResponse:
    base = dict(
        id="src-shop-1",
        subaccount_id=42,
        source_type=FeedSourceType.shopify,
        name="Main Shopify Store",
        config={},
        credentials_secret_id=None,
        is_active=True,
        catalog_type="product",
        catalog_variant="physical_products",
        shop_domain="my-store.myshopify.com",
        connection_status="pending",
        has_token=False,
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(overrides)
    return FeedSourceResponse(**base)


def _enable_ff():
    return patch.object(feed_sources_api, "_enforce_feature_flag", lambda: None)


def _set_oauth_env():
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["SHOPIFY_APP_CLIENT_ID"] = "voxel-id"
    os.environ["SHOPIFY_APP_CLIENT_SECRET"] = "voxel-secret"
    import importlib
    import app.integrations.shopify.config as cfg
    import app.integrations.shopify.service as svc
    importlib.reload(cfg)
    importlib.reload(svc)


class TestCreateShopifySource(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        _set_oauth_env()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        import importlib
        import app.integrations.shopify.config as cfg
        import app.integrations.shopify.service as svc
        importlib.reload(cfg)
        importlib.reload(svc)

    def test_creates_shopify_source_and_returns_authorize_url(self):
        with _enable_ff():
            original = feed_sources_api._source_repo.create
            try:
                feed_sources_api._source_repo.create = lambda payload: _shopify_source(
                    name=payload.name, shop_domain=payload.shop_domain
                )
                req = feed_sources_api.CreateFeedSourceRequest(
                    source_type=FeedSourceType.shopify,
                    name="Main Shopify Store",
                    shop_domain="My-Store.myshopify.com",
                )
                result = feed_sources_api.create_feed_source(subaccount_id=42, payload=req, user=_ADMIN)
            finally:
                feed_sources_api._source_repo.create = original

        self.assertEqual(result.source.shop_domain, "my-store.myshopify.com")
        self.assertIsNotNone(result.authorize_url)
        self.assertIn("my-store.myshopify.com/admin/oauth/authorize", result.authorize_url)
        self.assertIsNotNone(result.state)

    def test_shopify_without_shop_domain_returns_400(self):
        with _enable_ff():
            req = feed_sources_api.CreateFeedSourceRequest(
                source_type=FeedSourceType.shopify,
                name="Bad Shopify Source",
            )
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.create_feed_source(subaccount_id=42, payload=req, user=_ADMIN)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_shopify_with_invalid_shop_domain_returns_400(self):
        with _enable_ff():
            req = feed_sources_api.CreateFeedSourceRequest(
                source_type=FeedSourceType.shopify,
                name="Bad Shopify Source",
                shop_domain="evil.com",
            )
            with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                feed_sources_api.create_feed_source(subaccount_id=42, payload=req, user=_ADMIN)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_csv_source_unaffected_by_shopify_flow(self):
        with _enable_ff():
            csv_src = FeedSourceResponse(
                id="src-csv-1",
                subaccount_id=42,
                source_type=FeedSourceType.csv,
                name="CSV Feed",
                config={"file_url": "https://example.com/p.csv"},
                credentials_secret_id=None,
                is_active=True,
                created_at=_NOW,
                updated_at=_NOW,
            )
            original = feed_sources_api._source_repo.create
            try:
                feed_sources_api._source_repo.create = lambda payload: csv_src
                req = feed_sources_api.CreateFeedSourceRequest(
                    source_type=FeedSourceType.csv,
                    name="CSV Feed",
                    config=FeedSourceConfig(file_url="https://example.com/p.csv"),
                )
                result = feed_sources_api.create_feed_source(subaccount_id=42, payload=req, user=_ADMIN)
            finally:
                feed_sources_api._source_repo.create = original

        self.assertIsNone(result.authorize_url)
        self.assertEqual(result.source.source_type, FeedSourceType.csv)


class TestCompleteShopifyOAuth(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        _set_oauth_env()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        import importlib
        import app.integrations.shopify.config as cfg
        import app.integrations.shopify.service as svc
        importlib.reload(cfg)
        importlib.reload(svc)

    def test_complete_oauth_happy_path(self):
        from app.integrations.shopify import service as shopify_service

        # Generate a real HMAC-signed state so verify passes
        state = shopify_service.generate_oauth_state(shopify_service.OAUTH_STATE_PROVIDER)

        connected_source = _shopify_source(connection_status="connected", has_token=True, token_scopes="read_products")

        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            orig_mark = feed_sources_api._source_repo.mark_oauth_connected
            orig_exchange = shopify_service.exchange_code_for_token
            orig_store = shopify_service.store_shopify_token
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _shopify_source()
                feed_sources_api._source_repo.mark_oauth_connected = lambda source_id, *, scopes: connected_source
                shopify_service.exchange_code_for_token = lambda *, code, shop: {
                    "access_token": "shpua_TEST",
                    "scope": "read_products",
                    "shop": "my-store.myshopify.com",
                }
                shopify_service.store_shopify_token = lambda **kwargs: None

                payload = feed_sources_api.CompleteOAuthRequest(code="abc", state=state)
                result = feed_sources_api.complete_shopify_oauth(
                    subaccount_id=42, source_id="src-shop-1", payload=payload, user=_ADMIN
                )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
                feed_sources_api._source_repo.mark_oauth_connected = orig_mark
                shopify_service.exchange_code_for_token = orig_exchange
                shopify_service.store_shopify_token = orig_store

        self.assertEqual(result.connection_status, "connected")
        self.assertTrue(result.has_token)

    def test_complete_oauth_invalid_state_returns_400(self):
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _shopify_source()
                payload = feed_sources_api.CompleteOAuthRequest(code="abc", state="not-a-real-state")
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.complete_shopify_oauth(
                        subaccount_id=42, source_id="src-shop-1", payload=payload, user=_ADMIN
                    )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid OAuth state", ctx.exception.detail)

    def test_complete_oauth_rejects_non_shopify_source(self):
        non_shopify = FeedSourceResponse(
            id="src-csv-1",
            subaccount_id=42,
            source_type=FeedSourceType.csv,
            name="CSV",
            config={},
            credentials_secret_id=None,
            is_active=True,
            created_at=_NOW,
            updated_at=_NOW,
        )
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: non_shopify
                payload = feed_sources_api.CompleteOAuthRequest(code="abc", state="x.x.x.x")
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.complete_shopify_oauth(
                        subaccount_id=42, source_id="src-csv-1", payload=payload, user=_ADMIN
                    )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
        self.assertEqual(ctx.exception.status_code, 400)


class TestReconnectShopifySource(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        _set_oauth_env()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        import importlib
        import app.integrations.shopify.config as cfg
        import app.integrations.shopify.service as svc
        importlib.reload(cfg)
        importlib.reload(svc)

    def test_reconnect_returns_authorize_url_for_errored_source(self):
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _shopify_source(connection_status="error")
                result = feed_sources_api.reconnect_shopify_source(
                    subaccount_id=42, source_id="src-shop-1", user=_ADMIN
                )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
        self.assertIn("my-store.myshopify.com/admin/oauth/authorize", result["authorize_url"])
        self.assertIn("state", result)

    def test_reconnect_rejects_already_connected_source(self):
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _shopify_source(connection_status="connected")
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.reconnect_shopify_source(
                        subaccount_id=42, source_id="src-shop-1", user=_ADMIN
                    )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
        self.assertEqual(ctx.exception.status_code, 400)


class TestTestConnectionEndpoint(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.copy()
        _set_oauth_env()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        import importlib
        import app.integrations.shopify.config as cfg
        import app.integrations.shopify.service as svc
        importlib.reload(cfg)
        importlib.reload(svc)

    def test_test_connection_rejects_disconnected_source(self):
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: _shopify_source(connection_status="pending")
                with self.assertRaises(feed_sources_api.HTTPException) as ctx:
                    feed_sources_api.test_shopify_source_connection(
                        subaccount_id=42, source_id="src-shop-1", user=_ADMIN
                    )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
        self.assertEqual(ctx.exception.status_code, 400)

    def test_test_connection_returns_failure_when_no_token(self):
        connected = _shopify_source(connection_status="connected", has_token=True)
        with _enable_ff():
            orig_get = feed_sources_api._source_repo.get_by_id
            orig_record = feed_sources_api._source_repo.record_connection_check
            from app.integrations.shopify import service as shopify_service
            orig_token = shopify_service.get_access_token_for_shop
            try:
                feed_sources_api._source_repo.get_by_id = lambda source_id: connected
                feed_sources_api._source_repo.record_connection_check = (
                    lambda source_id, *, success, error=None: _shopify_source(
                        connection_status="error", last_error=error
                    )
                )
                shopify_service.get_access_token_for_shop = lambda shop: None

                result = feed_sources_api.test_shopify_source_connection(
                    subaccount_id=42, source_id="src-shop-1", user=_ADMIN
                )
            finally:
                feed_sources_api._source_repo.get_by_id = orig_get
                feed_sources_api._source_repo.record_connection_check = orig_record
                shopify_service.get_access_token_for_shop = orig_token

        self.assertFalse(result.success)
        self.assertEqual(result.message, "No stored token")


class TestMigrationFileExists(unittest.TestCase):
    def test_migration_file_present_and_idempotent(self):
        from pathlib import Path

        migrations_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
        target = migrations_dir / "0054_feed_sources_shopify_oauth.sql"
        self.assertTrue(target.exists(), f"missing migration: {target}")
        contents = target.read_text(encoding="utf-8")
        # Idempotency markers
        self.assertIn("ADD COLUMN IF NOT EXISTS shop_domain", contents)
        self.assertIn("ADD COLUMN IF NOT EXISTS connection_status", contents)
        self.assertIn("CREATE UNIQUE INDEX IF NOT EXISTS uq_feed_sources_subaccount_type_shop", contents)


if __name__ == "__main__":
    unittest.main()
