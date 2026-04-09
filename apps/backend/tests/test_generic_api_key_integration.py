"""Tests for the generic-API-key e-commerce platform integration.

Covers:

* ``app.integrations.generic_api_key.config`` — PLATFORM_DEFINITIONS,
  ``get_platform``, ``validate_store_url``.
* ``app.integrations.generic_api_key.service`` — store / get / delete /
  mask helpers, with a monkey-patched ``integration_secrets_store`` so
  the tests stay hermetic. Plus the ``probe_store_url`` reachability
  helper with a monkey-patched ``httpx.Client``.
* ``app.integrations.generic_api_key.router.build_router`` — full CRUD
  cycle for one platform, exercised through the FastAPI test client
  with monkey-patched repo + service. The platform is parametrised so
  one test class covers all six platforms by re-running the same suite
  per platform via ``subTest``.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.integrations.generic_api_key import config as gak_config
from app.integrations.generic_api_key import router as gak_router
from app.integrations.generic_api_key import service as gak_service
from app.integrations.generic_api_key.config import (
    PLATFORM_DEFINITIONS,
    PlatformDefinition,
    get_platform,
    validate_store_url,
)
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)
from app.services.integration_secrets_store import IntegrationSecretValue


_NOW = datetime(2026, 4, 9, tzinfo=timezone.utc)
_SOURCE_ID = "src-001"
_SUBACCOUNT_ID = 42


def _set_env() -> None:
    os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")
    os.environ.setdefault("FF_FEED_MANAGEMENT_ENABLED", "1")


# ---------------------------------------------------------------------------
# config.py — PlatformDefinition + lookups + URL validation
# ---------------------------------------------------------------------------


class PlatformDefinitionsTests(unittest.TestCase):
    def test_six_platforms_registered(self) -> None:
        self.assertEqual(
            sorted(PLATFORM_DEFINITIONS.keys()),
            [
                "lightspeed",
                "opencart",
                "prestashop",
                "shift4shop",
                "shopware",
                "volusion",
            ],
        )

    def test_each_definition_maps_to_a_feed_source_type(self) -> None:
        for key, definition in PLATFORM_DEFINITIONS.items():
            with self.subTest(platform=key):
                self.assertEqual(definition.key, key)
                self.assertEqual(definition.feed_source_type.value, key)
                self.assertIsInstance(definition.has_api_secret, bool)

    def test_get_platform_normalises_input(self) -> None:
        self.assertEqual(get_platform("PRESTASHOP").key, "prestashop")
        self.assertEqual(get_platform("  Shopware  ").key, "shopware")

    def test_get_platform_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_platform("nonsense")

    def test_secret_flag_split(self) -> None:
        self.assertFalse(get_platform("prestashop").has_api_secret)
        self.assertFalse(get_platform("volusion").has_api_secret)
        self.assertTrue(get_platform("shopware").has_api_secret)
        self.assertTrue(get_platform("opencart").has_api_secret)
        self.assertTrue(get_platform("lightspeed").has_api_secret)
        self.assertTrue(get_platform("shift4shop").has_api_secret)


class ValidateStoreUrlTests(unittest.TestCase):
    def test_https_url_passes_through(self) -> None:
        self.assertEqual(
            validate_store_url("https://store.example.com"),
            "https://store.example.com",
        )

    def test_http_url_passes_through(self) -> None:
        self.assertEqual(
            validate_store_url("http://store.example.com"),
            "http://store.example.com",
        )

    def test_strips_trailing_slash(self) -> None:
        self.assertEqual(
            validate_store_url("https://store.example.com/"),
            "https://store.example.com",
        )

    def test_preserves_subpath(self) -> None:
        self.assertEqual(
            validate_store_url("https://example.com/shop"),
            "https://example.com/shop",
        )

    def test_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            validate_store_url("")
        with self.assertRaises(ValueError):
            validate_store_url("   ")

    def test_rejects_non_http_scheme(self) -> None:
        with self.assertRaises(ValueError):
            validate_store_url("ftp://example.com")
        with self.assertRaises(ValueError):
            validate_store_url("javascript:alert(1)")

    def test_rejects_missing_host(self) -> None:
        with self.assertRaises(ValueError):
            validate_store_url("https://")


# ---------------------------------------------------------------------------
# service.py — credential round-trip + URL probe
# ---------------------------------------------------------------------------


class GenericApiKeyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._stored: dict[tuple[str, str, str], str] = {}

        def _fake_upsert(*, provider: str, secret_key: str, value: str, scope: str = "agency_default") -> None:
            self._stored[(provider, secret_key, scope)] = value

        def _fake_get(*, provider: str, secret_key: str, scope: str = "agency_default"):
            value = self._stored.get((provider, secret_key, scope))
            if value is None:
                return None
            return IntegrationSecretValue(
                provider=provider,
                secret_key=secret_key,
                scope=scope,
                value=value,
                updated_at=_NOW,
            )

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            self._stored.pop((provider, secret_key, scope), None)

        self._patches = [
            patch.object(
                gak_service.integration_secrets_store,
                "upsert_secret",
                _fake_upsert,
            ),
            patch.object(
                gak_service.integration_secrets_store,
                "get_secret",
                _fake_get,
            ),
            patch.object(
                gak_service.integration_secrets_store,
                "delete_secret",
                _fake_delete,
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def test_store_and_get_for_key_only_platform(self) -> None:
        gak_service.store_credentials(
            platform="prestashop",
            source_id=_SOURCE_ID,
            api_key="psk-12345",
        )
        self.assertEqual(
            self._stored[("prestashop", "api_key", _SOURCE_ID)],
            "psk-12345",
        )
        # No api_secret row for a key-only platform.
        self.assertNotIn(
            ("prestashop", "api_secret", _SOURCE_ID),
            self._stored,
        )
        creds = gak_service.get_credentials(
            platform="prestashop", source_id=_SOURCE_ID
        )
        self.assertEqual(creds, {"api_key": "psk-12345"})

    def test_store_and_get_for_key_plus_secret_platform(self) -> None:
        gak_service.store_credentials(
            platform="shopware",
            source_id=_SOURCE_ID,
            api_key="SWIA-key",
            api_secret="SW1-secret",
        )
        creds = gak_service.get_credentials(
            platform="shopware", source_id=_SOURCE_ID
        )
        self.assertEqual(creds, {"api_key": "SWIA-key", "api_secret": "SW1-secret"})

    def test_store_rejects_missing_api_key(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            gak_service.store_credentials(
                platform="prestashop",
                source_id=_SOURCE_ID,
                api_key="",
            )
        self.assertIn("Webservice Key", str(ctx.exception))

    def test_store_rejects_missing_secret_for_secret_platform(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            gak_service.store_credentials(
                platform="shopware",
                source_id=_SOURCE_ID,
                api_key="SWIA-key",
                api_secret=None,
            )
        self.assertIn("Integration Secret Key", str(ctx.exception))

    def test_store_rejects_missing_source_id(self) -> None:
        with self.assertRaises(ValueError):
            gak_service.store_credentials(
                platform="prestashop", source_id="", api_key="x"
            )

    def test_get_returns_none_when_missing(self) -> None:
        self.assertIsNone(
            gak_service.get_credentials(platform="prestashop", source_id=_SOURCE_ID)
        )

    def test_get_returns_none_for_partial_secret_pair(self) -> None:
        """Shopware needs both api_key + api_secret rows; api_key alone → None."""
        self._stored[("shopware", "api_key", _SOURCE_ID)] = "SWIA-key"
        self.assertIsNone(
            gak_service.get_credentials(platform="shopware", source_id=_SOURCE_ID)
        )

    def test_delete_is_idempotent(self) -> None:
        gak_service.store_credentials(
            platform="prestashop", source_id=_SOURCE_ID, api_key="psk"
        )
        gak_service.delete_credentials(platform="prestashop", source_id=_SOURCE_ID)
        self.assertFalse(
            any(key[2] == _SOURCE_ID for key in self._stored.keys())
        )
        gak_service.delete_credentials(platform="prestashop", source_id=_SOURCE_ID)

    def test_mask_credentials_hides_full_key(self) -> None:
        masked = gak_service.mask_credentials(
            "shopware",
            {"api_key": "SWIAOABCDEFGHIJKLMNOPQRSTUVWXYZ", "api_secret": "SW1XYZ"},
        )
        self.assertTrue(masked["has_credentials"])
        self.assertNotIn(
            "SWIAOABCDEFGHIJKLMNOPQRSTUVWXYZ", masked["api_key_masked"]
        )
        # Last 4 chars only — defensive check, no full plaintext leak.
        self.assertTrue(masked["api_key_masked"].startswith("*"))

    def test_mask_credentials_for_no_credentials(self) -> None:
        masked = gak_service.mask_credentials("prestashop", None)
        self.assertFalse(masked["has_credentials"])
        self.assertIsNone(masked["api_key_masked"])
        self.assertIsNone(masked["api_secret_masked"])


class ProbeStoreUrlTests(unittest.TestCase):
    def test_returns_success_on_2xx_response(self) -> None:
        fake_resp = MagicMock(status_code=200)
        fake_client = MagicMock()
        fake_client.get.return_value = fake_resp
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)

        with patch.object(gak_service.httpx, "Client", return_value=fake_client):
            result = gak_service.probe_store_url("https://example.com")

        self.assertTrue(result["success"])
        self.assertIn("reachable", result["message"])
        self.assertEqual(result["details"]["status_code"], 200)

    def test_returns_success_on_non_5xx_status(self) -> None:
        fake_resp = MagicMock(status_code=403)
        fake_client = MagicMock()
        fake_client.get.return_value = fake_resp
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)

        with patch.object(gak_service.httpx, "Client", return_value=fake_client):
            result = gak_service.probe_store_url("https://example.com")

        # 403 still counts as "reachable" — the URL responded.
        self.assertTrue(result["success"])

    def test_returns_failure_on_5xx(self) -> None:
        fake_resp = MagicMock(status_code=503)
        fake_client = MagicMock()
        fake_client.get.return_value = fake_resp
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)

        with patch.object(gak_service.httpx, "Client", return_value=fake_client):
            result = gak_service.probe_store_url("https://example.com")

        self.assertFalse(result["success"])
        self.assertIn("503", result["message"])

    def test_returns_failure_on_transport_error(self) -> None:
        import httpx

        fake_client = MagicMock()
        fake_client.get.side_effect = httpx.ConnectError("DNS failed")
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)

        with patch.object(gak_service.httpx, "Client", return_value=fake_client):
            result = gak_service.probe_store_url("https://nonsense.invalid")

        self.assertFalse(result["success"])
        self.assertIn("Could not reach", result["message"])

    def test_returns_failure_on_empty_url(self) -> None:
        result = gak_service.probe_store_url("")
        self.assertFalse(result["success"])


# ---------------------------------------------------------------------------
# router.py — full CRUD cycle (parametrised across all 6 platforms)
# ---------------------------------------------------------------------------


def _make_source(*, source_type: FeedSourceType) -> FeedSourceResponse:
    return FeedSourceResponse(
        id=_SOURCE_ID,
        subaccount_id=_SUBACCOUNT_ID,
        source_type=source_type,
        name="Test Store",
        config={"store_url": "https://store.example.com"},
        credentials_secret_id=None,
        is_active=True,
        connection_status="pending",
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


class GenericApiKeyRouterCrudTests(unittest.TestCase):
    """Drives the full CRUD cycle for every platform via subTest."""

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
                provider=provider,
                secret_key=secret_key,
                scope=scope,
                value=value,
                updated_at=_NOW,
            )

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            self._stored.pop((provider, secret_key, scope), None)

        self._patches = [
            patch.object(
                gak_service.integration_secrets_store,
                "upsert_secret",
                _fake_upsert,
            ),
            patch.object(
                gak_service.integration_secrets_store,
                "get_secret",
                _fake_get,
            ),
            patch.object(
                gak_service.integration_secrets_store,
                "delete_secret",
                _fake_delete,
            ),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def _build_router_for(self, platform_key: str):
        return gak_router.build_router(platform_key)

    def _find_endpoint(self, router, path_suffix: str, method: str):
        """Locate the bound function for a route by path suffix + method."""
        for r in router.routes:
            full_path = getattr(r, "path", "")
            if full_path.endswith(path_suffix) and method in (getattr(r, "methods", set()) or set()):
                return r.endpoint
        raise AssertionError(
            f"Endpoint not found: {path_suffix} {method} on router"
        )

    def test_full_crud_cycle_for_each_platform(self) -> None:
        for platform_key, definition in PLATFORM_DEFINITIONS.items():
            with self.subTest(platform=platform_key):
                self._stored.clear()
                router = self._build_router_for(platform_key)
                source = _make_source(source_type=definition.feed_source_type)

                # ---- create ----------------------------------------------
                payload = gak_router.GenericApiKeySourceCreate(
                    source_name="My Store",
                    store_url="https://store.example.com",
                    api_key="api-key-12345",
                    api_secret="api-secret-67890" if definition.has_api_secret else None,
                )
                with patch.object(
                    gak_router._source_repo, "create", return_value=source
                ):
                    create_endpoint = self._find_endpoint(
                        router, "/sources", "POST"
                    )
                    response = create_endpoint(
                        payload=payload,
                        subaccount_id=_SUBACCOUNT_ID,
                        user=_make_user(),
                    )

                self.assertEqual(response.platform, platform_key)
                # The response carries the row's stored name, not the
                # request payload — _make_source seeds it as "Test Store".
                self.assertEqual(response.source_name, "Test Store")
                self.assertEqual(response.store_url, "https://store.example.com")
                self.assertTrue(response.has_credentials)
                self.assertIsNotNone(response.api_key_masked)
                self.assertNotIn(
                    "api-key-12345", response.api_key_masked or ""
                )
                if definition.has_api_secret:
                    self.assertIsNotNone(response.api_secret_masked)
                    self.assertNotIn(
                        "api-secret-67890", response.api_secret_masked or ""
                    )
                # Credentials persisted in the fake store
                self.assertEqual(
                    self._stored[(platform_key, "api_key", _SOURCE_ID)],
                    "api-key-12345",
                )
                if definition.has_api_secret:
                    self.assertEqual(
                        self._stored[(platform_key, "api_secret", _SOURCE_ID)],
                        "api-secret-67890",
                    )

                # ---- list ------------------------------------------------
                with patch.object(
                    gak_router._source_repo,
                    "get_by_subaccount",
                    return_value=[source],
                ):
                    list_endpoint = self._find_endpoint(router, "/sources", "GET")
                    items = list_endpoint(
                        subaccount_id=_SUBACCOUNT_ID, user=_make_user()
                    )
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0].source_id, _SOURCE_ID)

                # ---- read ------------------------------------------------
                with patch.object(
                    gak_router._source_repo, "get_by_id", return_value=source
                ):
                    get_endpoint = self._find_endpoint(
                        router, "/sources/{source_id}", "GET"
                    )
                    detail = get_endpoint(
                        source_id=_SOURCE_ID,
                        subaccount_id=_SUBACCOUNT_ID,
                        user=_make_user(),
                    )
                self.assertEqual(detail.source_id, _SOURCE_ID)
                self.assertTrue(detail.has_credentials)

                # ---- update (rename only — no credential rotation) ------
                renamed = source.model_copy(update={"name": "Renamed Store"})
                with patch.object(
                    gak_router._source_repo, "get_by_id", return_value=source
                ), patch.object(
                    gak_router._source_repo, "update", return_value=renamed
                ):
                    put_endpoint = self._find_endpoint(
                        router, "/sources/{source_id}", "PUT"
                    )
                    updated = put_endpoint(
                        source_id=_SOURCE_ID,
                        payload=gak_router.GenericApiKeySourceUpdate(
                            source_name="Renamed Store"
                        ),
                        subaccount_id=_SUBACCOUNT_ID,
                        user=_make_user(),
                    )
                self.assertEqual(updated.source_name, "Renamed Store")
                # Credentials still in the store after a cosmetic update
                self.assertIn(
                    (platform_key, "api_key", _SOURCE_ID), self._stored
                )

                # ---- delete ----------------------------------------------
                with patch.object(
                    gak_router._source_repo, "get_by_id", return_value=source
                ), patch.object(
                    gak_router._source_repo, "delete", return_value=None
                ):
                    delete_endpoint = self._find_endpoint(
                        router, "/sources/{source_id}", "DELETE"
                    )
                    result = delete_endpoint(
                        source_id=_SOURCE_ID,
                        subaccount_id=_SUBACCOUNT_ID,
                        user=_make_user(),
                    )
                self.assertEqual(result, {"status": "ok", "id": _SOURCE_ID})
                # Credentials wiped on delete
                self.assertFalse(
                    any(k[0] == platform_key for k in self._stored.keys())
                )

    def test_create_rolls_back_source_when_credential_store_fails(self) -> None:
        deleted_ids: list[str] = []
        router = self._build_router_for("shopware")
        source = _make_source(source_type=FeedSourceType.shopware)

        def _failing_store(**kwargs):
            raise RuntimeError("secrets store down")

        with patch.object(
            gak_router._source_repo, "create", return_value=source
        ), patch.object(
            gak_router._source_repo,
            "delete",
            side_effect=lambda sid: deleted_ids.append(sid),
        ), patch.object(
            gak_service, "store_credentials", side_effect=_failing_store
        ):
            create_endpoint = self._find_endpoint(router, "/sources", "POST")
            with self.assertRaises(gak_router.HTTPException) as ctx:
                create_endpoint(
                    payload=gak_router.GenericApiKeySourceCreate(
                        source_name="x",
                        store_url="https://store.example.com",
                        api_key="key",
                        api_secret="secret",
                    ),
                    subaccount_id=_SUBACCOUNT_ID,
                    user=_make_user(),
                )

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertEqual(deleted_ids, [_SOURCE_ID])

    def test_create_rejects_missing_api_secret_for_secret_platform(self) -> None:
        """Shopware requires both api_key + api_secret → 400 on missing secret."""
        deleted_ids: list[str] = []
        router = self._build_router_for("shopware")
        source = _make_source(source_type=FeedSourceType.shopware)

        with patch.object(
            gak_router._source_repo, "create", return_value=source
        ), patch.object(
            gak_router._source_repo,
            "delete",
            side_effect=lambda sid: deleted_ids.append(sid),
        ):
            create_endpoint = self._find_endpoint(router, "/sources", "POST")
            with self.assertRaises(gak_router.HTTPException) as ctx:
                create_endpoint(
                    payload=gak_router.GenericApiKeySourceCreate(
                        source_name="x",
                        store_url="https://store.example.com",
                        api_key="SWIA-key",
                        api_secret=None,
                    ),
                    subaccount_id=_SUBACCOUNT_ID,
                    user=_make_user(),
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(deleted_ids, [_SOURCE_ID])  # rolled back

    def test_get_returns_404_for_cross_tenant_lookup(self) -> None:
        router = self._build_router_for("prestashop")
        other_tenant = _make_source(source_type=FeedSourceType.prestashop)
        other_tenant = other_tenant.model_copy(update={"subaccount_id": 99})

        with patch.object(
            gak_router._source_repo, "get_by_id", return_value=other_tenant
        ):
            get_endpoint = self._find_endpoint(
                router, "/sources/{source_id}", "GET"
            )
            with self.assertRaises(gak_router.HTTPException) as ctx:
                get_endpoint(
                    source_id=_SOURCE_ID,
                    subaccount_id=_SUBACCOUNT_ID,
                    user=_make_user(),
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_returns_404_for_wrong_platform(self) -> None:
        """A Shopware source isn't visible through the PrestaShop router."""
        router = self._build_router_for("prestashop")
        wrong_type = _make_source(source_type=FeedSourceType.shopware)

        with patch.object(
            gak_router._source_repo, "get_by_id", return_value=wrong_type
        ):
            get_endpoint = self._find_endpoint(
                router, "/sources/{source_id}", "GET"
            )
            with self.assertRaises(gak_router.HTTPException) as ctx:
                get_endpoint(
                    source_id=_SOURCE_ID,
                    subaccount_id=_SUBACCOUNT_ID,
                    user=_make_user(),
                )
        self.assertEqual(ctx.exception.status_code, 404)


class FeedSourceTypeEnumTests(unittest.TestCase):
    """Sanity check that the new enum values reach the canonical model."""

    def test_enum_includes_all_six_new_platforms(self) -> None:
        values = {item.value for item in FeedSourceType}
        for platform in (
            "prestashop",
            "opencart",
            "shopware",
            "lightspeed",
            "volusion",
            "shift4shop",
        ):
            self.assertIn(platform, values)

    def test_existing_enum_values_unchanged(self) -> None:
        values = {item.value for item in FeedSourceType}
        for platform in (
            "shopify",
            "woocommerce",
            "magento",
            "bigcommerce",
            "csv",
            "json",
            "xml",
            "google_sheets",
        ):
            self.assertIn(platform, values)


if __name__ == "__main__":
    unittest.main()
