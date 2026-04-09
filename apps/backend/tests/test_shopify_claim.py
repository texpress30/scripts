"""Tests for the Shopify deferred-creation + claim flow.

Covers the new endpoints added by the deferred-claim refactor (PR
``feat/shopify-deferred-claim-flow``):

* ``GET /integrations/shopify/stores/available`` — list installed shops
  not yet claimed.
* ``POST /integrations/shopify/sources/claim`` — bind an installed shop
  to a subaccount.
* ``POST /integrations/shopify/test-connection/by-shop`` — pre-claim
  probe by ``shop_domain`` using the stored access token.

Also exercises the service-layer additions
(``get_shopify_credentials``, ``list_installed_shops_with_metadata``)
and asserts that the legacy Shopify OAuth endpoints keep working.

The tests monkey-patch the repository + service + urllib layer so
every case stays hermetic (no DB, no live HTTP).
"""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from urllib import error as urllib_error

from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)
from app.services.integration_secrets_store import IntegrationSecretValue


def _reload_router():
    import app.integrations.shopify.config as cfg

    importlib.reload(cfg)
    import app.integrations.shopify.service as svc

    importlib.reload(svc)
    from app.api.integrations import shopify as shopify_api

    importlib.reload(shopify_api)
    return shopify_api


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["SHOPIFY_APP_CLIENT_ID"] = "voxel-shopify-client-id"
    os.environ["SHOPIFY_APP_CLIENT_SECRET"] = "voxel-shopify-client-secret"
    os.environ["SHOPIFY_REDIRECT_URI"] = "https://admin.example.com/agency/integrations/shopify/callback"
    os.environ["SHOPIFY_API_VERSION"] = "2026-04"
    os.environ["SHOPIFY_SCOPES"] = "read_products,read_inventory"
    os.environ["FF_FEED_MANAGEMENT_ENABLED"] = "1"


def _now() -> datetime:
    return datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)


def _make_shopify_source(
    *,
    source_id: str = "src-1",
    subaccount_id: int = 42,
    shop_domain: str | None = "my-store.myshopify.com",
    name: str = "My Shopify Store",
    connection_status: str = "pending",
) -> FeedSourceResponse:
    return FeedSourceResponse(
        id=source_id,
        subaccount_id=subaccount_id,
        source_type=FeedSourceType.shopify,
        name=name,
        config={"store_url": f"https://{shop_domain}"} if shop_domain else {},
        credentials_secret_id=None,
        is_active=True,
        shop_domain=shop_domain,
        connection_status=connection_status,
        has_token=connection_status == "connected",
        token_scopes="read_products,read_inventory" if connection_status == "connected" else None,
        created_at=_now(),
        updated_at=_now(),
    )


def _user(role: str = "agency_admin") -> AuthUser:
    return AuthUser(
        email="admin@example.com",
        role=role,
        user_id=1,
        subaccount_id=42,
        is_env_admin=True,  # bypass per-user enforcement
    )


# ---------------------------------------------------------------------------
# Service-layer additions
# ---------------------------------------------------------------------------


class ShopifyServiceCredentialsTests(unittest.TestCase):
    """``get_shopify_credentials`` + ``list_installed_shops_with_metadata``."""

    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.shopify_api = _reload_router()
        self.svc = self.shopify_api.shopify_oauth_service

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _fake_secret(self, value: str, updated: datetime | None = None) -> IntegrationSecretValue:
        return IntegrationSecretValue(
            provider="shopify",
            secret_key="access_token",
            scope="my-store.myshopify.com",
            value=value,
            updated_at=updated or _now(),
        )

    def test_get_credentials_returns_token_and_scope(self) -> None:
        token_row = self._fake_secret("shpua_abc123")
        scope_row = IntegrationSecretValue(
            provider="shopify",
            secret_key="scope",
            scope="my-store.myshopify.com",
            value="read_products,read_inventory",
            updated_at=_now(),
        )

        def _fake_get(*, provider: str, secret_key: str, scope: str):
            if secret_key == "access_token":
                return token_row
            if secret_key == "scope":
                return scope_row
            return None

        with patch.object(
            self.svc.integration_secrets_store,
            "get_secret",
            side_effect=_fake_get,
        ):
            creds = self.svc.get_shopify_credentials("my-store.myshopify.com")

        self.assertIsNotNone(creds)
        assert creds is not None  # mypy hint
        self.assertEqual(creds["access_token"], "shpua_abc123")
        self.assertEqual(creds["scope"], "read_products,read_inventory")

    def test_get_credentials_returns_none_when_token_missing(self) -> None:
        with patch.object(
            self.svc.integration_secrets_store, "get_secret", return_value=None
        ):
            self.assertIsNone(
                self.svc.get_shopify_credentials("my-store.myshopify.com")
            )

    def test_get_credentials_returns_none_for_invalid_domain(self) -> None:
        self.assertIsNone(self.svc.get_shopify_credentials("not-a-shop.com"))

    def test_list_installed_shops_returns_metadata(self) -> None:
        token_row = self._fake_secret("shpua_abc123")

        def _fake_get(*, provider: str, secret_key: str, scope: str):
            if secret_key == "access_token":
                return token_row
            if secret_key == "scope":
                return IntegrationSecretValue(
                    provider="shopify",
                    secret_key="scope",
                    scope=scope,
                    value="read_products",
                    updated_at=_now(),
                )
            return None

        with patch.object(
            self.svc,
            "_list_connected_shops",
            return_value=["my-store.myshopify.com"],
        ), patch.object(
            self.svc.integration_secrets_store,
            "get_secret",
            side_effect=_fake_get,
        ):
            result = self.svc.list_installed_shops_with_metadata()

        self.assertEqual(len(result), 1)
        entry = result[0]
        self.assertEqual(entry["shop_domain"], "my-store.myshopify.com")
        self.assertEqual(entry["scope"], "read_products")
        self.assertEqual(entry["installed_at"], _now())

    def test_list_installed_shops_returns_empty_when_no_tokens(self) -> None:
        with patch.object(
            self.svc, "_list_connected_shops", return_value=[]
        ):
            self.assertEqual(self.svc.list_installed_shops_with_metadata(), [])


# ---------------------------------------------------------------------------
# GET /integrations/shopify/stores/available
# ---------------------------------------------------------------------------


class ListAvailableStoresTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.shopify_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_returns_only_unclaimed_shops(self) -> None:
        installed = [
            {
                "shop_domain": "store-a.myshopify.com",
                "installed_at": _now(),
                "scope": "read_products",
            },
            {
                "shop_domain": "store-b.myshopify.com",
                "installed_at": _now(),
                "scope": "read_products",
            },
        ]
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "list_installed_shops_with_metadata",
            return_value=installed,
        ), patch.object(
            self.shopify_api._source_repo,
            "list_claimed_shop_domains",
            return_value={"store-a.myshopify.com"},
        ):
            response = self.shopify_api.list_available_shopify_stores(user=_user())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.stores[0].shop_domain, "store-b.myshopify.com")
        self.assertEqual(response.stores[0].scope, "read_products")

    def test_returns_empty_when_all_claimed(self) -> None:
        installed = [{"shop_domain": "store-a.myshopify.com", "installed_at": _now()}]
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "list_installed_shops_with_metadata",
            return_value=installed,
        ), patch.object(
            self.shopify_api._source_repo,
            "list_claimed_shop_domains",
            return_value={"store-a.myshopify.com"},
        ):
            response = self.shopify_api.list_available_shopify_stores(user=_user())
        self.assertEqual(response.total, 0)

    def test_returns_empty_when_no_shops_installed(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "list_installed_shops_with_metadata",
            return_value=[],
        ), patch.object(
            self.shopify_api._source_repo,
            "list_claimed_shop_domains",
            return_value=set(),
        ):
            response = self.shopify_api.list_available_shopify_stores(user=_user())
        self.assertEqual(response.total, 0)
        self.assertEqual(response.stores, [])


# ---------------------------------------------------------------------------
# POST /integrations/shopify/sources/claim
# ---------------------------------------------------------------------------


class ClaimSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.shopify_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _claim_payload(self) -> Any:
        return self.shopify_api.ShopifyClaimRequest(
            shop_domain="my-store.myshopify.com",
            source_name="Main Shopify Store",
            catalog_type="product",
            catalog_variant="physical_products",
        )

    def test_claim_success_marks_connected_immediately(self) -> None:
        created = _make_shopify_source(name="Main Shopify Store")
        connected = _make_shopify_source(
            name="Main Shopify Store", connection_status="connected"
        )

        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_shopify_credentials",
            return_value={"access_token": "shpua_abc", "scope": "read_products"},
        ), patch.object(
            self.shopify_api._source_repo, "create", return_value=created
        ), patch.object(
            self.shopify_api._source_repo,
            "mark_oauth_connected",
            return_value=connected,
        ):
            response = self.shopify_api.claim_shopify_source(
                payload=self._claim_payload(),
                subaccount_id=42,
                user=_user(),
            )

        self.assertEqual(response.shop_domain, "my-store.myshopify.com")
        self.assertEqual(response.connection_status, "connected")
        self.assertEqual(response.source_name, "Main Shopify Store")
        self.assertTrue(response.has_token)

    def test_claim_not_installed_returns_404(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_shopify_credentials",
            return_value=None,
        ):
            with self.assertRaises(self.shopify_api.HTTPException) as ctx:
                self.shopify_api.claim_shopify_source(
                    payload=self._claim_payload(),
                    subaccount_id=42,
                    user=_user(),
                )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("installed", ctx.exception.detail.lower())

    def test_claim_already_claimed_returns_409(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_shopify_credentials",
            return_value={"access_token": "shpua_abc"},
        ), patch.object(
            self.shopify_api._source_repo,
            "create",
            side_effect=FeedSourceAlreadyExistsError("my-store.myshopify.com", 42),
        ):
            with self.assertRaises(self.shopify_api.HTTPException) as ctx:
                self.shopify_api.claim_shopify_source(
                    payload=self._claim_payload(),
                    subaccount_id=42,
                    user=_user(),
                )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("already claimed", ctx.exception.detail.lower())

    def test_claim_invalid_shop_domain_returns_400(self) -> None:
        bad_payload = self.shopify_api.ShopifyClaimRequest(
            shop_domain="evil.com",
            source_name="Bad",
        )
        with self.assertRaises(self.shopify_api.HTTPException) as ctx:
            self.shopify_api.claim_shopify_source(
                payload=bad_payload, subaccount_id=42, user=_user()
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_claim_survives_mark_oauth_connected_failure(self) -> None:
        """If ``mark_oauth_connected`` raises, we still return the row
        as-is (pending) rather than 500 — the credentials are already
        stored and the next ``test-connection`` call will fix the status."""
        created = _make_shopify_source()

        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_shopify_credentials",
            return_value={"access_token": "shpua_abc"},
        ), patch.object(
            self.shopify_api._source_repo, "create", return_value=created
        ), patch.object(
            self.shopify_api._source_repo,
            "mark_oauth_connected",
            side_effect=FeedSourceNotFoundError("src-1"),
        ):
            response = self.shopify_api.claim_shopify_source(
                payload=self._claim_payload(),
                subaccount_id=42,
                user=_user(),
            )
        self.assertEqual(response.connection_status, "pending")


# ---------------------------------------------------------------------------
# POST /integrations/shopify/test-connection/by-shop
# ---------------------------------------------------------------------------


class PreClaimTestConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.shopify_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _payload(self) -> Any:
        return self.shopify_api.ShopifyPreClaimTestRequest(
            shop_domain="my-store.myshopify.com",
        )

    def test_happy_path_returns_store_metadata(self) -> None:
        body = json.dumps(
            {
                "shop": {
                    "name": "My Store",
                    "domain": "my-store.myshopify.com",
                    "currency": "USD",
                }
            }
        ).encode("utf-8")

        fake_resp = MagicMock(status=200)
        fake_resp.read.return_value = body
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_access_token_for_shop",
            return_value="shpua_abc",
        ), patch.object(
            self.shopify_api.request, "urlopen", return_value=fake_resp
        ):
            response = self.shopify_api.test_shopify_connection_pre_claim(
                payload=self._payload(), user=_user()
            )

        self.assertTrue(response.success)
        self.assertEqual(response.store_name, "My Store")
        self.assertEqual(response.currency, "USD")
        self.assertEqual(response.domain, "my-store.myshopify.com")
        self.assertIsNone(response.error)

    def test_no_credentials_returns_error(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_access_token_for_shop",
            return_value=None,
        ):
            response = self.shopify_api.test_shopify_connection_pre_claim(
                payload=self._payload(), user=_user()
            )
        self.assertFalse(response.success)
        self.assertIn("No Shopify credentials", response.error or "")

    def test_invalid_shop_domain_returns_error(self) -> None:
        bad_payload = self.shopify_api.ShopifyPreClaimTestRequest(
            shop_domain="not-shopify.com",
        )
        response = self.shopify_api.test_shopify_connection_pre_claim(
            payload=bad_payload, user=_user()
        )
        self.assertFalse(response.success)

    def test_http_error_returns_shopify_http_message(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_access_token_for_shop",
            return_value="shpua_abc",
        ), patch.object(
            self.shopify_api.request,
            "urlopen",
            side_effect=urllib_error.HTTPError(
                url="https://my-store.myshopify.com/admin/api/2026-04/shop.json",
                code=401,
                msg="Unauthorized",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            ),
        ):
            response = self.shopify_api.test_shopify_connection_pre_claim(
                payload=self._payload(), user=_user()
            )
        self.assertFalse(response.success)
        self.assertIn("401", response.error or "")

    def test_network_error_returns_unreachable_message(self) -> None:
        with patch.object(
            self.shopify_api.shopify_oauth_service,
            "get_access_token_for_shop",
            return_value="shpua_abc",
        ), patch.object(
            self.shopify_api.request,
            "urlopen",
            side_effect=urllib_error.URLError("DNS failed"),
        ):
            response = self.shopify_api.test_shopify_connection_pre_claim(
                payload=self._payload(), user=_user()
            )
        self.assertFalse(response.success)
        self.assertIn("Could not reach", response.error or "")


# ---------------------------------------------------------------------------
# Backward compatibility: legacy endpoints still work
# ---------------------------------------------------------------------------


class BackwardCompatibilityTests(unittest.TestCase):
    """The legacy agency-initiated OAuth flow must stay intact."""

    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.shopify_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_legacy_connect_endpoint_still_registered(self) -> None:
        """``GET /integrations/shopify/connect`` remains for legacy callers."""
        paths = {getattr(r, "path", "") for r in self.shopify_api.router.routes}
        self.assertIn("/integrations/shopify/connect", paths)

    def test_legacy_oauth_exchange_endpoint_still_registered(self) -> None:
        paths = {getattr(r, "path", "") for r in self.shopify_api.router.routes}
        self.assertIn("/integrations/shopify/oauth/exchange", paths)

    def test_legacy_test_connection_endpoint_still_registered(self) -> None:
        """The original manual-credentials ``/test-connection`` endpoint
        must stay — the new deferred-claim probe lives at a different path
        (``/test-connection/by-shop``) on purpose."""
        paths = {getattr(r, "path", "") for r in self.shopify_api.router.routes}
        self.assertIn("/integrations/shopify/test-connection", paths)

    def test_legacy_webhook_routes_still_registered(self) -> None:
        paths = {getattr(r, "path", "") for r in self.shopify_api.router.routes}
        self.assertIn("/integrations/shopify/webhooks/app-uninstalled", paths)
        self.assertIn("/integrations/shopify/webhooks/compliance", paths)

    def test_new_routes_are_mounted(self) -> None:
        paths = {getattr(r, "path", "") for r in self.shopify_api.router.routes}
        self.assertIn("/integrations/shopify/stores/available", paths)
        self.assertIn("/integrations/shopify/sources/claim", paths)
        self.assertIn("/integrations/shopify/test-connection/by-shop", paths)


if __name__ == "__main__":
    unittest.main()
