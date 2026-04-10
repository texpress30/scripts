"""Tests for the dedicated Shopware integration.

Covers:

* ``app.integrations.shopware.config`` — bridge endpoint validation.
* ``app.integrations.shopware.router`` — full CRUD cycle with credential
  storage (Store Key + API Access Key encrypted) and Bridge Endpoint in
  config JSONB.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from app.integrations.shopware import router as sw_router
from app.integrations.shopware import service as sw_service
from app.integrations.shopware.config import validate_bridge_endpoint
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)
from app.services.integration_secrets_store import IntegrationSecretValue


_NOW = datetime(2026, 4, 10, tzinfo=timezone.utc)
_SOURCE_ID = "sw-src-001"
_SUBACCOUNT_ID = 42


def _set_env() -> None:
    os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")
    os.environ.setdefault("FF_FEED_MANAGEMENT_ENABLED", "1")


def _make_source(
    *,
    config: dict | None = None,
) -> FeedSourceResponse:
    return FeedSourceResponse(
        id=_SOURCE_ID,
        subaccount_id=_SUBACCOUNT_ID,
        source_type=FeedSourceType.shopware,
        name="Test Shopware Store",
        config=config or {
            "store_url": "https://store.example.com",
            "extra": {"bridge_endpoint": "https://store.example.com/bridge/abc"},
        },
        credentials_secret_id=None,
        is_active=True,
        connection_status="pending",
        last_connection_check=None,
        last_error=None,
        has_token=False,
        token_scopes=None,
        last_import_at=None,
        last_sync_at=None,
        product_count=0,
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_user():
    from app.services.auth import AuthUser
    return AuthUser(
        email="admin@example.com",
        role="agency_admin",
        user_id=1,
        is_env_admin=True,
    )


# ---------------------------------------------------------------------------
# config.py — validation
# ---------------------------------------------------------------------------


class ShopwareConfigTests(unittest.TestCase):

    def test_validate_bridge_endpoint_strips_whitespace(self) -> None:
        self.assertEqual(
            validate_bridge_endpoint("  https://bridge.example.com  "),
            "https://bridge.example.com",
        )

    def test_validate_bridge_endpoint_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_bridge_endpoint("")
        with self.assertRaises(ValueError):
            validate_bridge_endpoint("   ")


# ---------------------------------------------------------------------------
# router.py — CRUD cycle
# ---------------------------------------------------------------------------


class ShopwareRouterCrudTests(unittest.TestCase):

    def setUp(self) -> None:
        _set_env()
        self._stored: dict[tuple[str, str, str], str] = {}

        def _fake_upsert(*, provider: str, secret_key: str, value: str, scope: str = "agency_default") -> None:
            self._stored[(provider, secret_key, scope)] = value

        def _fake_get(*, provider: str, secret_key: str, scope: str = "agency_default"):
            value = self._stored.get((provider, secret_key, scope))
            if value is None:
                return None
            return IntegrationSecretValue(
                provider=provider, secret_key=secret_key, scope=scope,
                value=value, updated_at=_NOW,
            )

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            self._stored.pop((provider, secret_key, scope), None)

        self._patches = [
            patch.object(sw_service.integration_secrets_store, "upsert_secret", _fake_upsert),
            patch.object(sw_service.integration_secrets_store, "get_secret", _fake_get),
            patch.object(sw_service.integration_secrets_store, "delete_secret", _fake_delete),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def _find_endpoint(self, path_suffix: str, method: str, *, exact: bool = False):
        for r in sw_router.router.routes:
            full_path = getattr(r, "path", "")
            match = (full_path == path_suffix) if exact else full_path.endswith(path_suffix)
            if match and method in (getattr(r, "methods", set()) or set()):
                return r.endpoint
        raise AssertionError(f"Endpoint not found: {path_suffix} {method}")

    def test_create_source_stores_credentials(self) -> None:
        source = _make_source()
        payload = sw_router.ShopwareSourceCreateRequest(
            source_name="My Shopware",
            store_url="https://store.example.com",
            store_key="sk-12345",
            bridge_endpoint="https://store.example.com/bridge/abc",
            api_access_key="ak-67890",
        )
        with patch.object(sw_router._source_repo, "create", return_value=source):
            endpoint = self._find_endpoint("/sources", "POST")
            response = endpoint(
                payload=payload,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(response.platform, "shopware")
        self.assertTrue(response.has_credentials)
        self.assertIsNotNone(response.store_key_masked)
        self.assertNotIn("sk-12345", response.store_key_masked or "")
        self.assertIsNotNone(response.api_access_key_masked)
        self.assertNotIn("ak-67890", response.api_access_key_masked or "")
        # Credentials stored in the fake store
        self.assertEqual(self._stored[("shopware", "api_key", _SOURCE_ID)], "sk-12345")
        self.assertEqual(self._stored[("shopware", "api_secret", _SOURCE_ID)], "ak-67890")

    def test_create_rejects_empty_bridge_endpoint(self) -> None:
        from fastapi import HTTPException

        payload = sw_router.ShopwareSourceCreateRequest(
            source_name="My Shopware",
            store_url="https://store.example.com",
            store_key="sk-12345",
            bridge_endpoint="   ",
            api_access_key="ak-67890",
        )
        endpoint = self._find_endpoint("/sources", "POST")
        with self.assertRaises(HTTPException) as ctx:
            endpoint(
                payload=payload,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Bridge Endpoint", ctx.exception.detail)

    def test_get_source_returns_bridge_endpoint(self) -> None:
        source = _make_source()
        self._stored[("shopware", "api_key", _SOURCE_ID)] = "sk-12345"
        self._stored[("shopware", "api_secret", _SOURCE_ID)] = "ak-67890"

        with patch.object(sw_router._source_repo, "get_by_id", return_value=source):
            endpoint = self._find_endpoint("/sources/{source_id}", "GET")
            response = endpoint(
                source_id=_SOURCE_ID,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(response.bridge_endpoint, "https://store.example.com/bridge/abc")
        self.assertTrue(response.has_credentials)

    def test_delete_source_wipes_credentials(self) -> None:
        source = _make_source()
        self._stored[("shopware", "api_key", _SOURCE_ID)] = "sk-12345"
        self._stored[("shopware", "api_secret", _SOURCE_ID)] = "ak-67890"

        with patch.object(sw_router._source_repo, "get_by_id", return_value=source), \
             patch.object(sw_router._source_repo, "delete"):
            endpoint = self._find_endpoint("/sources/{source_id}", "DELETE")
            result = endpoint(
                source_id=_SOURCE_ID,
                subaccount_id=_SUBACCOUNT_ID,
                user=_make_user(),
            )

        self.assertEqual(result["status"], "ok")
        self.assertNotIn(("shopware", "api_key", _SOURCE_ID), self._stored)
        self.assertNotIn(("shopware", "api_secret", _SOURCE_ID), self._stored)

    def test_list_filters_by_shopware_type(self) -> None:
        sw_source = _make_source()
        other_source = FeedSourceResponse(
            id="other",
            subaccount_id=_SUBACCOUNT_ID,
            source_type=FeedSourceType.shopify,
            name="Shopify Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            connection_status="connected",
            created_at=_NOW,
            updated_at=_NOW,
        )
        with patch.object(
            sw_router._source_repo, "get_by_subaccount",
            return_value=[sw_source, other_source],
        ):
            endpoint = self._find_endpoint("/sources", "GET")
            result = endpoint(subaccount_id=_SUBACCOUNT_ID, user=_make_user())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].platform, "shopware")

    def test_cross_tenant_returns_404(self) -> None:
        from fastapi import HTTPException

        source = _make_source()
        with patch.object(sw_router._source_repo, "get_by_id", return_value=source):
            endpoint = self._find_endpoint("/sources/{source_id}", "GET")
            with self.assertRaises(HTTPException) as ctx:
                endpoint(source_id=_SOURCE_ID, subaccount_id=999, user=_make_user())
        self.assertEqual(ctx.exception.status_code, 404)

    def test_test_connection_pre_save(self) -> None:
        with patch(
            "app.integrations.shopware.router.probe_store_url",
            return_value={"success": True, "message": "OK", "details": {"status_code": 200}},
        ):
            endpoint = self._find_endpoint(
                "/integrations/shopware/test-connection", "POST", exact=True
            )
            response = endpoint(store_url="https://store.example.com", user=_make_user())

        self.assertTrue(response.success)


if __name__ == "__main__":
    unittest.main()
