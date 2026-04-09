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


# ---------------------------------------------------------------------------
# DB enum migration (0057) — guards against the Codex P1 review finding
# ---------------------------------------------------------------------------


class DbEnumMigrationTests(unittest.TestCase):
    """Verify the 0057 SQL migration covers every stub platform.

    Without this migration, ``feed_sources.source_type`` (a real
    PostgreSQL ENUM declared in 0033) would reject INSERTs of the new
    Python enum values with "invalid input value for enum" because the
    DB-side enum and the application-side enum are separate things.
    The test loads the migration file as text and asserts that an
    ``ALTER TYPE … ADD VALUE`` statement exists for each new platform
    so a refactor that drops one is caught immediately by CI.
    """

    def test_every_new_platform_has_an_alter_type_add_value(self) -> None:
        from pathlib import Path

        migration_path = (
            Path(__file__).resolve().parents[1]
            / "db"
            / "migrations"
            / "0057_feed_source_type_add_six_platforms.sql"
        )
        self.assertTrue(
            migration_path.exists(),
            f"Migration file missing: {migration_path}",
        )
        sql = migration_path.read_text(encoding="utf-8")

        for platform in (
            "prestashop",
            "opencart",
            "shopware",
            "lightspeed",
            "volusion",
            "shift4shop",
        ):
            with self.subTest(platform=platform):
                expected = f"ADD VALUE IF NOT EXISTS '{platform}'"
                self.assertIn(
                    expected,
                    sql,
                    f"Migration is missing the ADD VALUE for {platform!r}",
                )

    def test_uses_alter_type_on_feed_source_type_enum(self) -> None:
        from pathlib import Path

        sql = (
            Path(__file__).resolve().parents[1]
            / "db"
            / "migrations"
            / "0057_feed_source_type_add_six_platforms.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TYPE feed_source_type", sql)


# ---------------------------------------------------------------------------
# Sync gate — guards against the Codex P2 review finding
# ---------------------------------------------------------------------------


class SyncGateTests(unittest.TestCase):
    """``trigger_sync`` and ``FeedSyncService.run_sync`` must refuse to
    operate on the six stub source types so we never leave behind a
    ``feed_imports`` row stuck in ``pending`` or crash inside
    ``_get_connector`` (which raises ``ValueError`` for unknown types).
    """

    def setUp(self) -> None:
        _set_env()
        from app.services.feed_management.models import (
            SYNC_UNSUPPORTED_SOURCE_TYPES,
            is_sync_supported,
        )

        self._unsupported = SYNC_UNSUPPORTED_SOURCE_TYPES
        self._is_sync_supported = is_sync_supported

    def test_unsupported_set_includes_all_six_stub_platforms(self) -> None:
        for stub in (
            FeedSourceType.prestashop,
            FeedSourceType.opencart,
            FeedSourceType.shopware,
            FeedSourceType.lightspeed,
            FeedSourceType.volusion,
            FeedSourceType.shift4shop,
        ):
            with self.subTest(stub=stub.value):
                self.assertIn(stub, self._unsupported)
                self.assertFalse(self._is_sync_supported(stub))

    def test_supported_platforms_remain_supported(self) -> None:
        for platform in (
            FeedSourceType.shopify,
            FeedSourceType.woocommerce,
            FeedSourceType.magento,
            FeedSourceType.bigcommerce,
            FeedSourceType.csv,
            FeedSourceType.json,
            FeedSourceType.xml,
            FeedSourceType.google_sheets,
        ):
            with self.subTest(platform=platform.value):
                self.assertNotIn(platform, self._unsupported)
                self.assertTrue(self._is_sync_supported(platform))

    def test_trigger_sync_returns_400_for_stub_source(self) -> None:
        """The API endpoint must reject the request before it creates an import row."""
        from app.api import feed_sources as fs_api
        from app.services.auth import AuthUser

        source = _make_source(source_type=FeedSourceType.shopware)
        created_imports: list[Any] = []

        def _fake_create(payload):
            created_imports.append(payload)
            raise AssertionError(
                "import row must NOT be created when sync is gated"
            )

        with patch.object(fs_api, "_enforce_feature_flag", lambda: None), patch.object(
            fs_api._source_repo, "get_by_id", return_value=source
        ), patch.object(
            fs_api._import_repo, "create", side_effect=_fake_create
        ):
            from fastapi import BackgroundTasks

            user = AuthUser(
                email="admin@example.com",
                role="agency_admin",
                user_id=1,
                is_env_admin=True,
            )
            with self.assertRaises(fs_api.HTTPException) as ctx:
                fs_api.trigger_sync(
                    subaccount_id=_SUBACCOUNT_ID,
                    source_id=_SOURCE_ID,
                    background_tasks=BackgroundTasks(),
                    user=user,
                )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not yet available", ctx.exception.detail)
        self.assertIn("shopware", ctx.exception.detail)
        self.assertEqual(created_imports, [])  # no orphan import row

    def test_run_sync_marks_existing_pending_import_failed(self) -> None:
        """Defensive: if a stub source somehow reaches ``run_sync`` with a
        pending import (legacy / cron path), the import is marked failed
        instead of left stuck."""
        import asyncio

        from app.services.feed_management.models import FeedImportStatus
        from app.services.feed_management.sync_service import FeedSyncService

        source = _make_source(source_type=FeedSourceType.prestashop)

        from datetime import datetime, timezone

        from app.services.feed_management.models import FeedImportResponse

        existing_import = FeedImportResponse(
            id="imp-001",
            feed_source_id=_SOURCE_ID,
            status=FeedImportStatus.pending,
            total_products=0,
            imported_products=0,
            errors=[],
            started_at=None,
            completed_at=None,
            created_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
        )
        update_calls: list[dict[str, Any]] = []

        def _fake_update(import_id, **kwargs):
            update_calls.append({"id": import_id, **kwargs})
            return existing_import.model_copy(
                update={"status": kwargs.get("status", existing_import.status)}
            )

        svc = FeedSyncService()
        with patch.object(
            svc._source_repo, "get_by_id", return_value=source
        ), patch.object(
            svc._import_repo, "get_latest_by_source", return_value=existing_import
        ), patch.object(
            svc._import_repo, "update_status", side_effect=_fake_update
        ):
            result = asyncio.get_event_loop().run_until_complete(
                svc.run_sync(_SOURCE_ID)
            )

        self.assertEqual(result.status, FeedImportStatus.failed)
        self.assertEqual(len(update_calls), 1)
        self.assertEqual(update_calls[0]["status"], FeedImportStatus.failed)
        # Error message includes the source_type so logs / UI can surface
        # a clean reason instead of "ValueError".
        self.assertIn("prestashop", str(update_calls[0]["errors"]))

    def test_run_sync_raises_value_error_when_no_pending_import(self) -> None:
        """If there's no existing import row to mark failed, raising
        ``ValueError`` is fine — the cron's per-source try/except
        already handles it."""
        import asyncio

        from app.services.feed_management.sync_service import FeedSyncService

        source = _make_source(source_type=FeedSourceType.prestashop)
        svc = FeedSyncService()
        with patch.object(
            svc._source_repo, "get_by_id", return_value=source
        ), patch.object(
            svc._import_repo, "get_latest_by_source", return_value=None
        ):
            with self.assertRaises(ValueError) as ctx:
                asyncio.get_event_loop().run_until_complete(
                    svc.run_sync(_SOURCE_ID)
                )
        self.assertIn("prestashop", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
