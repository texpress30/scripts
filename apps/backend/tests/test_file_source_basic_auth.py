"""Tests for the file source HTTP Basic Auth support (CSV / JSON / XML).

Covers:

* ``app.integrations.file_source.service`` — store / get / delete / mask
  helpers, with a monkey-patched ``integration_secrets_store`` so the
  tests stay hermetic (no DB, no Fernet round-trip).
* ``FileConnector`` + ``_resolve_basic_auth`` + ``_fetch_remote_content`` —
  verify that the connector forwards the ``auth=`` tuple to
  ``requests.get`` when both halves of the pair are set, and falls back
  to an unauthenticated fetch otherwise.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.integrations.file_source import service as fs_service
from app.services.feed_management.connectors import file_connector as fc_module
from app.services.feed_management.connectors.file_connector import (
    FileConnector,
    _resolve_basic_auth,
)
from app.services.integration_secrets_store import IntegrationSecretValue


_SOURCE_ID = "src-1"
_USERNAME = "feed_user"
_PASSWORD = "s3cr3t-pass"


# ---------------------------------------------------------------------------
# service.py
# ---------------------------------------------------------------------------


class FileSourceCredentialServiceTests(unittest.TestCase):
    """Exercise the store / get / delete cycle with a fake secrets store."""

    def setUp(self) -> None:
        self._stored: dict[tuple[str, str, str], str] = {}
        self._now = datetime(2026, 4, 9, tzinfo=timezone.utc)

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
                updated_at=self._now,
            )

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            self._stored.pop((provider, secret_key, scope), None)

        self._orig_upsert = fs_service.integration_secrets_store.upsert_secret
        self._orig_get = fs_service.integration_secrets_store.get_secret
        self._orig_delete = fs_service.integration_secrets_store.delete_secret
        fs_service.integration_secrets_store.upsert_secret = _fake_upsert  # type: ignore[assignment]
        fs_service.integration_secrets_store.get_secret = _fake_get  # type: ignore[assignment]
        fs_service.integration_secrets_store.delete_secret = _fake_delete  # type: ignore[assignment]

    def tearDown(self) -> None:
        fs_service.integration_secrets_store.upsert_secret = self._orig_upsert  # type: ignore[assignment]
        fs_service.integration_secrets_store.get_secret = self._orig_get  # type: ignore[assignment]
        fs_service.integration_secrets_store.delete_secret = self._orig_delete  # type: ignore[assignment]

    def test_store_and_get_round_trip(self) -> None:
        fs_service.store_file_source_credentials(
            source_id=_SOURCE_ID,
            username=_USERNAME,
            password=_PASSWORD,
        )

        self.assertEqual(
            self._stored[("file_source", "auth_username", _SOURCE_ID)],
            _USERNAME,
        )
        self.assertEqual(
            self._stored[("file_source", "auth_password", _SOURCE_ID)],
            _PASSWORD,
        )

        creds = fs_service.get_file_source_credentials(_SOURCE_ID)
        self.assertIsNotNone(creds)
        assert creds is not None
        self.assertEqual(creds["username"], _USERNAME)
        self.assertEqual(creds["password"], _PASSWORD)

    def test_store_rejects_empty_username(self) -> None:
        with self.assertRaises(ValueError):
            fs_service.store_file_source_credentials(
                source_id=_SOURCE_ID, username="", password=_PASSWORD
            )

    def test_store_rejects_empty_password(self) -> None:
        with self.assertRaises(ValueError):
            fs_service.store_file_source_credentials(
                source_id=_SOURCE_ID, username=_USERNAME, password=""
            )

    def test_store_rejects_empty_source_id(self) -> None:
        with self.assertRaises(ValueError):
            fs_service.store_file_source_credentials(
                source_id="", username=_USERNAME, password=_PASSWORD
            )

    def test_get_returns_none_when_missing(self) -> None:
        self.assertIsNone(fs_service.get_file_source_credentials(_SOURCE_ID))

    def test_get_returns_none_on_partial_row_set(self) -> None:
        """A stray username row without a matching password → treat as none."""
        self._stored[("file_source", "auth_username", _SOURCE_ID)] = _USERNAME
        self.assertIsNone(fs_service.get_file_source_credentials(_SOURCE_ID))

    def test_delete_is_idempotent(self) -> None:
        fs_service.store_file_source_credentials(
            source_id=_SOURCE_ID, username=_USERNAME, password=_PASSWORD
        )
        fs_service.delete_file_source_credentials(_SOURCE_ID)
        self.assertFalse(
            any(key[2] == _SOURCE_ID for key in self._stored.keys())
        )
        # Running it again on empty state is a no-op, not an error.
        fs_service.delete_file_source_credentials(_SOURCE_ID)

    def test_delete_silently_ignores_empty_source_id(self) -> None:
        fs_service.delete_file_source_credentials("")  # must not raise

    def test_mask_returns_no_auth_descriptor_for_none(self) -> None:
        masked = fs_service.mask_file_source_credentials(None)
        self.assertFalse(masked["has_auth"])
        self.assertIsNone(masked["username"])
        self.assertIsNone(masked["password_masked"])

    def test_mask_exposes_username_but_hides_password(self) -> None:
        masked = fs_service.mask_file_source_credentials(
            {"username": _USERNAME, "password": _PASSWORD}
        )
        self.assertTrue(masked["has_auth"])
        self.assertEqual(masked["username"], _USERNAME)
        # Password must never appear verbatim in the masked response.
        self.assertNotIn(_PASSWORD, masked["password_masked"])
        self.assertTrue(masked["password_masked"].startswith("*"))

    def test_mask_with_partial_pair_marks_has_auth_false(self) -> None:
        masked = fs_service.mask_file_source_credentials({"username": _USERNAME})
        self.assertFalse(masked["has_auth"])


# ---------------------------------------------------------------------------
# FileConnector HTTP fetch with Basic Auth
# ---------------------------------------------------------------------------


class ResolveBasicAuthTests(unittest.TestCase):
    def test_both_fields_set_returns_tuple(self) -> None:
        self.assertEqual(
            _resolve_basic_auth({"username": "u", "password": "p"}),
            ("u", "p"),
        )

    def test_missing_password_returns_none(self) -> None:
        self.assertIsNone(_resolve_basic_auth({"username": "u"}))

    def test_empty_password_returns_none(self) -> None:
        self.assertIsNone(_resolve_basic_auth({"username": "u", "password": ""}))

    def test_none_returns_none(self) -> None:
        self.assertIsNone(_resolve_basic_auth(None))

    def test_whitespace_only_returns_none(self) -> None:
        self.assertIsNone(
            _resolve_basic_auth({"username": "  ", "password": "  "})
        )


class FileConnectorBasicAuthTests(unittest.TestCase):
    """Exercise ``FileConnector.test_connection`` + ``fetch_products`` with
    a monkey-patched ``requests.get`` that captures the auth argument.
    """

    def setUp(self) -> None:
        import os

        # ``_fetch_remote_content`` calls ``load_settings()`` for the
        # timeout — make sure the required env vars are set so tests
        # don't fail with a RuntimeError on missing APP_AUTH_SECRET.
        self._env = os.environ.copy()
        os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")

    def tearDown(self) -> None:
        import os

        os.environ.clear()
        os.environ.update(self._env)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_fetch_without_auth_omits_auth_kwarg(self) -> None:
        captured: dict[str, Any] = {}

        def _fake_get(url, timeout=None, auth=None):
            captured["url"] = url
            captured["auth"] = auth
            resp = MagicMock()
            resp.content = b"id,title\n1,Shoes"
            resp.raise_for_status = MagicMock()
            return resp

        connector = FileConnector(
            config={"file_url": "https://example.com/feed.csv", "file_type": "csv"},
            credentials=None,
        )
        with patch.object(fc_module.requests, "get", side_effect=_fake_get):
            result = self._run(connector.test_connection())

        self.assertTrue(result.success)
        self.assertEqual(captured["url"], "https://example.com/feed.csv")
        self.assertIsNone(captured["auth"])

    def test_fetch_with_auth_forwards_tuple_to_requests(self) -> None:
        captured: dict[str, Any] = {}

        def _fake_get(url, timeout=None, auth=None):
            captured["auth"] = auth
            resp = MagicMock()
            resp.content = b"id,title\n1,Shoes"
            resp.raise_for_status = MagicMock()
            return resp

        connector = FileConnector(
            config={"file_url": "https://example.com/feed.csv", "file_type": "csv"},
            credentials={"username": _USERNAME, "password": _PASSWORD},
        )
        with patch.object(fc_module.requests, "get", side_effect=_fake_get):
            result = self._run(connector.test_connection())

        self.assertTrue(result.success)
        self.assertEqual(captured["auth"], (_USERNAME, _PASSWORD))

    def test_fetch_with_partial_credentials_still_unauthenticated(self) -> None:
        """Half-configured credentials (username only) fall back to public fetch."""
        captured: dict[str, Any] = {}

        def _fake_get(url, timeout=None, auth=None):
            captured["auth"] = auth
            resp = MagicMock()
            resp.content = b"id,title\n1,Shoes"
            resp.raise_for_status = MagicMock()
            return resp

        connector = FileConnector(
            config={"file_url": "https://example.com/feed.csv", "file_type": "csv"},
            credentials={"username": _USERNAME, "password": ""},
        )
        with patch.object(fc_module.requests, "get", side_effect=_fake_get):
            self._run(connector.test_connection())

        self.assertIsNone(captured["auth"])

    def test_fetch_products_threads_auth_through_csv_parse(self) -> None:
        """End-to-end: fetch_products with Basic Auth parses returned rows."""
        captured_auth: list[Any] = []

        def _fake_get(url, timeout=None, auth=None):
            captured_auth.append(auth)
            resp = MagicMock()
            resp.content = b"id,title,price\n1,Shoes,19.99\n2,Hat,9.50"
            resp.raise_for_status = MagicMock()
            return resp

        connector = FileConnector(
            config={"file_url": "https://example.com/feed.csv", "file_type": "csv"},
            credentials={"username": _USERNAME, "password": _PASSWORD},
        )

        async def _collect():
            out = []
            async for product in connector.fetch_products():
                out.append(product)
            return out

        with patch.object(fc_module.requests, "get", side_effect=_fake_get):
            products = self._run(_collect())

        self.assertEqual(captured_auth, [(_USERNAME, _PASSWORD)])
        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].id, "1")
        self.assertEqual(products[0].title, "Shoes")
        self.assertEqual(products[0].price, 19.99)

    def test_fetch_reraises_auth_failure_from_requests(self) -> None:
        """A 401 from the upstream propagates out of test_connection as
        ``success=False``, with a message the wizard can surface."""

        def _fake_get(url, timeout=None, auth=None):
            resp = MagicMock()

            class FakeHTTPError(Exception):
                pass

            def _raise():
                raise FakeHTTPError("401 Unauthorized")

            resp.raise_for_status = _raise
            return resp

        connector = FileConnector(
            config={"file_url": "https://example.com/feed.csv", "file_type": "csv"},
            credentials={"username": _USERNAME, "password": "wrong"},
        )
        with patch.object(fc_module.requests, "get", side_effect=_fake_get):
            result = self._run(connector.test_connection())

        self.assertFalse(result.success)
        self.assertIn("401", result.message)


# ---------------------------------------------------------------------------
# API — create / update / delete / response enrichment
# ---------------------------------------------------------------------------


class FileSourceApiAuthTests(unittest.TestCase):
    """End-to-end-ish tests that exercise the feed_sources router with
    ``_source_repo`` and ``file_source_service`` monkey-patched. Verifies:

    * create stores credentials after the row is created
    * create without credentials skips storage entirely
    * update adds / rotates / clears credentials
    * response enrichment surfaces ``has_file_auth`` + masked password
    * delete wipes credentials
    """

    def setUp(self) -> None:
        import os

        self._env = os.environ.copy()
        os.environ.setdefault("APP_AUTH_SECRET", "test-auth-secret")

        from app.api import feed_sources as feed_sources_api
        from app.services.auth import AuthUser
        from app.services.feed_management.models import (
            FeedSourceResponse,
            FeedSourceType,
        )

        self.feed_sources_api = feed_sources_api
        self._user = AuthUser(email="admin@example.com", role="agency_admin")

        now = datetime(2026, 4, 9, tzinfo=timezone.utc)
        self._sample_source = FeedSourceResponse(
            id=_SOURCE_ID,
            subaccount_id=42,
            source_type=FeedSourceType.csv,
            name="Test CSV Feed",
            config={
                "file_url": "https://example.com/products.csv",
                "file_type": "csv",
            },
            credentials_secret_id=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        self._feed_source_type_csv = FeedSourceType.csv

    def tearDown(self) -> None:
        import os

        os.environ.clear()
        os.environ.update(self._env)

    def _enable_feature_flag(self):
        return patch.object(self.feed_sources_api, "_enforce_feature_flag", lambda: None)

    def _fake_service(self):
        """Install a fake file_source service and return its storage dict.

        Only the I/O-bound helpers (store / get / delete) are patched —
        ``mask_file_source_credentials`` is a pure function with no
        backing store, so we let the real implementation run to avoid a
        recursive patch loop.
        """
        stored: dict[str, dict[str, str]] = {}

        def _fake_store(*, source_id, username, password):
            stored[source_id] = {"username": username, "password": password}

        def _fake_get(source_id):
            return stored.get(source_id)

        def _fake_delete(source_id):
            stored.pop(source_id, None)

        self._fs_patchers = [
            patch.object(self.feed_sources_api.file_source_service, "store_file_source_credentials", side_effect=_fake_store),
            patch.object(self.feed_sources_api.file_source_service, "get_file_source_credentials", side_effect=_fake_get),
            patch.object(self.feed_sources_api.file_source_service, "delete_file_source_credentials", side_effect=_fake_delete),
        ]
        for p in self._fs_patchers:
            p.start()
        return stored

    def _teardown_fake_service(self) -> None:
        for p in self._fs_patchers:
            p.stop()

    def _make_create_request(self, **overrides):
        payload = {
            "source_type": self._feed_source_type_csv,
            "name": "Test CSV Feed",
            "config": self.feed_sources_api.FeedSourceConfig(
                file_url="https://example.com/products.csv",
            ),
            "catalog_type": "product",
            "catalog_variant": "physical_products",
        }
        payload.update(overrides)
        return self.feed_sources_api.CreateFeedSourceRequest(**payload)

    def test_create_file_source_without_auth(self) -> None:
        """Creating a plain CSV source without auth skips credential storage."""
        stored = self._fake_service()
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "create",
                    return_value=self._sample_source,
                ):
                    req = self._make_create_request()
                    result = self.feed_sources_api.create_feed_source(
                        subaccount_id=42, payload=req, user=self._user
                    )

            self.assertEqual(stored, {})  # nothing stored
            self.assertFalse(result.source.has_file_auth)
            self.assertIsNone(result.source.file_auth_username)
        finally:
            self._teardown_fake_service()

    def test_create_file_source_with_auth_stores_credentials(self) -> None:
        """Creating a CSV source with both auth fields persists them."""
        stored = self._fake_service()
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "create",
                    return_value=self._sample_source,
                ):
                    req = self._make_create_request(
                        feed_auth_username=_USERNAME,
                        feed_auth_password=_PASSWORD,
                    )
                    result = self.feed_sources_api.create_feed_source(
                        subaccount_id=42, payload=req, user=self._user
                    )

            # Credentials stored under the source id.
            self.assertEqual(
                stored[_SOURCE_ID],
                {"username": _USERNAME, "password": _PASSWORD},
            )
            # Response is enriched with masked auth metadata.
            self.assertTrue(result.source.has_file_auth)
            self.assertEqual(result.source.file_auth_username, _USERNAME)
            self.assertIsNotNone(result.source.file_auth_password_masked)
            self.assertNotIn(_PASSWORD, result.source.file_auth_password_masked or "")
        finally:
            self._teardown_fake_service()

    def test_create_rolls_back_source_when_credential_store_fails(self) -> None:
        """If credential persistence fails, the feed_sources row is deleted."""
        deleted_ids: list[str] = []

        def _failing_store(*, source_id, username, password):
            raise RuntimeError("secrets store down")

        def _fake_delete(source_id):
            deleted_ids.append(source_id)

        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "create",
                    return_value=self._sample_source,
                ), patch.object(
                    self.feed_sources_api._source_repo,
                    "delete",
                    side_effect=_fake_delete,
                ), patch.object(
                    self.feed_sources_api.file_source_service,
                    "store_file_source_credentials",
                    side_effect=_failing_store,
                ):
                    req = self._make_create_request(
                        feed_auth_username=_USERNAME,
                        feed_auth_password=_PASSWORD,
                    )
                    with self.assertRaises(self.feed_sources_api.HTTPException) as ctx:
                        self.feed_sources_api.create_feed_source(
                            subaccount_id=42, payload=req, user=self._user
                        )

            self.assertEqual(ctx.exception.status_code, 500)
            self.assertEqual(deleted_ids, [_SOURCE_ID])
        finally:
            pass

    def test_update_source_add_auth(self) -> None:
        """Update without prior auth → store credentials."""
        stored = self._fake_service()
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "get_by_id",
                    return_value=self._sample_source,
                ), patch.object(
                    self.feed_sources_api._source_repo,
                    "update",
                    return_value=self._sample_source,
                ):
                    update_req = self.feed_sources_api.UpdateFeedSourceRequest(
                        feed_auth_username=_USERNAME,
                        feed_auth_password=_PASSWORD,
                    )
                    result = self.feed_sources_api.update_feed_source(
                        subaccount_id=42,
                        source_id=_SOURCE_ID,
                        payload=update_req,
                        user=self._user,
                    )

            self.assertEqual(stored[_SOURCE_ID]["username"], _USERNAME)
            self.assertEqual(stored[_SOURCE_ID]["password"], _PASSWORD)
            self.assertTrue(result.has_file_auth)
            self.assertEqual(result.file_auth_username, _USERNAME)
        finally:
            self._teardown_fake_service()

    def test_update_source_remove_auth(self) -> None:
        """``clear_file_auth=True`` wipes stored credentials."""
        stored = self._fake_service()
        stored[_SOURCE_ID] = {"username": _USERNAME, "password": _PASSWORD}
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "get_by_id",
                    return_value=self._sample_source,
                ), patch.object(
                    self.feed_sources_api._source_repo,
                    "update",
                    return_value=self._sample_source,
                ):
                    update_req = self.feed_sources_api.UpdateFeedSourceRequest(
                        clear_file_auth=True,
                    )
                    result = self.feed_sources_api.update_feed_source(
                        subaccount_id=42,
                        source_id=_SOURCE_ID,
                        payload=update_req,
                        user=self._user,
                    )

            self.assertEqual(stored, {})  # fully cleared
            self.assertFalse(result.has_file_auth)
            self.assertIsNone(result.file_auth_username)
        finally:
            self._teardown_fake_service()

    def test_update_with_half_credentials_returns_400(self) -> None:
        """Setting username alone (with no existing password row) → 400."""
        stored = self._fake_service()
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "get_by_id",
                    return_value=self._sample_source,
                ), patch.object(
                    self.feed_sources_api._source_repo,
                    "update",
                    return_value=self._sample_source,
                ):
                    update_req = self.feed_sources_api.UpdateFeedSourceRequest(
                        feed_auth_username=_USERNAME,
                    )
                    with self.assertRaises(self.feed_sources_api.HTTPException) as ctx:
                        self.feed_sources_api.update_feed_source(
                            subaccount_id=42,
                            source_id=_SOURCE_ID,
                            payload=update_req,
                            user=self._user,
                        )

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(stored, {})
        finally:
            self._teardown_fake_service()

    def test_response_masks_password(self) -> None:
        """GET a file source with auth → response has username but masked password."""
        stored = self._fake_service()
        stored[_SOURCE_ID] = {"username": _USERNAME, "password": _PASSWORD}
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "get_by_id",
                    return_value=self._sample_source,
                ):
                    result = self.feed_sources_api.get_feed_source(
                        subaccount_id=42,
                        source_id=_SOURCE_ID,
                        user=self._user,
                    )

            self.assertTrue(result.has_file_auth)
            self.assertEqual(result.file_auth_username, _USERNAME)
            self.assertIsNotNone(result.file_auth_password_masked)
            self.assertNotIn(_PASSWORD, result.file_auth_password_masked or "")
        finally:
            self._teardown_fake_service()

    def test_delete_wipes_credentials(self) -> None:
        """Deleting the source also wipes the stored file-auth credentials."""
        stored = self._fake_service()
        stored[_SOURCE_ID] = {"username": _USERNAME, "password": _PASSWORD}
        try:
            with self._enable_feature_flag():
                with patch.object(
                    self.feed_sources_api._source_repo,
                    "get_by_id",
                    return_value=self._sample_source,
                ), patch.object(
                    self.feed_sources_api._source_repo,
                    "delete",
                    return_value=None,
                ), patch.object(
                    self.feed_sources_api.feed_products_repository,
                    "delete_products_by_source",
                    return_value=0,
                ):
                    result = self.feed_sources_api.delete_feed_source(
                        subaccount_id=42,
                        source_id=_SOURCE_ID,
                        user=self._user,
                    )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(stored, {})  # credentials wiped
        finally:
            self._teardown_fake_service()


if __name__ == "__main__":
    unittest.main()
