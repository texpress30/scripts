"""Tests for the BigCommerce CRUD / claim / available / test-connection endpoints.

Each test calls the router function directly with a dummy ``AuthUser`` and
monkey-patches the repository + service helpers so the tests stay
hermetic (no DB, no live HTTP).
"""

from __future__ import annotations

import asyncio
import importlib
import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)


def _reload_router():
    import app.integrations.bigcommerce.config as cfg

    importlib.reload(cfg)
    import app.integrations.bigcommerce.service as svc

    importlib.reload(svc)
    import app.integrations.bigcommerce.client as client_mod

    importlib.reload(client_mod)
    from app.api.integrations import bigcommerce as bc_api

    importlib.reload(bc_api)
    return bc_api


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["BC_CLIENT_ID"] = "voxel-bc-client-id"
    os.environ["BC_CLIENT_SECRET"] = "voxel-bc-client-secret"
    os.environ["BC_CLIENT_UUID"] = "bc-account-uuid"
    os.environ["BC_REDIRECT_URI"] = "https://admin.example.com/integrations/bigcommerce/auth/callback"
    os.environ["FF_FEED_MANAGEMENT_ENABLED"] = "1"


def _now() -> datetime:
    return datetime(2026, 4, 8, 12, 0, 0, tzinfo=timezone.utc)


def _make_source(
    *,
    source_id: str = "src-1",
    subaccount_id: int = 42,
    source_type: FeedSourceType = FeedSourceType.bigcommerce,
    store_hash: str | None = "abc123",
    name: str = "My BC Store",
    connection_status: str = "pending",
) -> FeedSourceResponse:
    return FeedSourceResponse(
        id=source_id,
        subaccount_id=subaccount_id,
        source_type=source_type,
        name=name,
        config={},
        credentials_secret_id=None,
        is_active=True,
        bigcommerce_store_hash=store_hash,
        connection_status=connection_status,
        has_token=connection_status == "connected",
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


class ListAvailableStoresTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_returns_only_unclaimed_stores(self) -> None:
        installed = [
            {
                "store_hash": "abc123",
                "installed_at": _now(),
                "user_email": "owner@a.com",
                "scope": "store_v2_products_read_only",
            },
            {
                "store_hash": "def456",
                "installed_at": _now(),
                "user_email": "owner@b.com",
                "scope": "store_v2_products_read_only",
            },
        ]
        with patch.object(
            self.bc_api.bc_service,
            "list_installed_stores_with_metadata",
            return_value=installed,
        ), patch.object(
            self.bc_api._source_repo,
            "list_claimed_bigcommerce_store_hashes",
            return_value={"abc123"},
        ):
            response = self.bc_api.list_available_bigcommerce_stores(user=_user())

        self.assertEqual(response.total, 1)
        self.assertEqual(response.stores[0].store_hash, "def456")
        self.assertEqual(response.stores[0].user_email, "owner@b.com")

    def test_returns_empty_when_all_claimed(self) -> None:
        installed = [{"store_hash": "abc123", "installed_at": _now()}]
        with patch.object(
            self.bc_api.bc_service,
            "list_installed_stores_with_metadata",
            return_value=installed,
        ), patch.object(
            self.bc_api._source_repo,
            "list_claimed_bigcommerce_store_hashes",
            return_value={"abc123"},
        ):
            response = self.bc_api.list_available_bigcommerce_stores(user=_user())
        self.assertEqual(response.total, 0)


class ClaimSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _claim_payload(self) -> Any:
        return self.bc_api.BigCommerceClaimRequest(
            store_hash="abc123",
            source_name="My BC Store",
            catalog_type="product",
            catalog_variant="physical_products",
        )

    def test_claim_success(self) -> None:
        created = _make_source()
        connected = _make_source(connection_status="connected")

        with patch.object(
            self.bc_api.bc_service,
            "get_access_token_for_store",
            return_value="bc_TOKEN",
        ), patch.object(
            self.bc_api._source_repo, "create", return_value=created
        ), patch.object(
            self.bc_api.bc_service,
            "get_bigcommerce_credentials",
            return_value={
                "access_token": "bc_TOKEN",
                "scope": "store_v2_products_read_only",
            },
        ), patch.object(
            self.bc_api._source_repo,
            "mark_oauth_connected",
            return_value=connected,
        ):
            response = self.bc_api.claim_bigcommerce_source(
                payload=self._claim_payload(),
                subaccount_id=42,
                user=_user(),
            )

        self.assertEqual(response.store_hash, "abc123")
        self.assertEqual(response.connection_status, "connected")
        self.assertEqual(response.source_name, "My BC Store")

    def test_claim_not_installed_returns_404(self) -> None:
        with patch.object(
            self.bc_api.bc_service,
            "get_access_token_for_store",
            return_value=None,
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.claim_bigcommerce_source(
                    payload=self._claim_payload(),
                    subaccount_id=42,
                    user=_user(),
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_claim_already_claimed_returns_409(self) -> None:
        with patch.object(
            self.bc_api.bc_service,
            "get_access_token_for_store",
            return_value="bc_TOKEN",
        ), patch.object(
            self.bc_api._source_repo,
            "create",
            side_effect=FeedSourceAlreadyExistsError("abc123", 42),
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.claim_bigcommerce_source(
                    payload=self._claim_payload(),
                    subaccount_id=42,
                    user=_user(),
                )
        self.assertEqual(ctx.exception.status_code, 409)

    def test_claim_invalid_store_hash_returns_400(self) -> None:
        bad_payload = self.bc_api.BigCommerceClaimRequest(
            store_hash="abc/123",
            source_name="My BC Store",
        )
        with self.assertRaises(self.bc_api.HTTPException) as ctx:
            self.bc_api.claim_bigcommerce_source(
                payload=bad_payload, subaccount_id=42, user=_user()
            )
        self.assertEqual(ctx.exception.status_code, 400)


class ListSourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_list_returns_sources_from_subaccount(self) -> None:
        sources = [
            _make_source(source_id="src-1", store_hash="abc123"),
            _make_source(source_id="src-2", store_hash="def456"),
        ]
        with patch.object(
            self.bc_api._source_repo,
            "get_bigcommerce_sources_by_subaccount",
            return_value=sources,
        ):
            response = self.bc_api.list_bigcommerce_sources(
                subaccount_id=42, user=_user()
            )
        self.assertEqual(len(response), 2)
        self.assertEqual(response[0].store_hash, "abc123")
        self.assertEqual(response[1].store_hash, "def456")


class GetSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_get_source_happy_path(self) -> None:
        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=_make_source()
        ):
            response = self.bc_api.get_bigcommerce_source(
                source_id="src-1", subaccount_id=42, user=_user()
            )
        self.assertEqual(response.source_id, "src-1")
        self.assertEqual(response.store_hash, "abc123")

    def test_get_source_cross_tenant_returns_404(self) -> None:
        other_tenant = _make_source(subaccount_id=99)
        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=other_tenant
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.get_bigcommerce_source(
                    source_id="src-1", subaccount_id=42, user=_user()
                )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_get_source_wrong_type_returns_404(self) -> None:
        wrong_type = _make_source(source_type=FeedSourceType.shopify)
        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=wrong_type
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.get_bigcommerce_source(
                    source_id="src-1", subaccount_id=42, user=_user()
                )
        self.assertEqual(ctx.exception.status_code, 404)


class UpdateSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_update_renames_source(self) -> None:
        existing = _make_source()
        updated = _make_source(name="Renamed Store")
        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=existing
        ), patch.object(
            self.bc_api._source_repo, "update", return_value=updated
        ) as mock_update:
            payload = self.bc_api.BigCommerceSourceUpdateRequest(
                source_name="Renamed Store"
            )
            response = self.bc_api.update_bigcommerce_source(
                source_id="src-1",
                payload=payload,
                subaccount_id=42,
                user=_user(),
            )

        self.assertEqual(response.source_name, "Renamed Store")
        mock_update.assert_called_once()

    def test_update_no_op_when_no_fields_supplied(self) -> None:
        existing = _make_source()
        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=existing
        ), patch.object(self.bc_api._source_repo, "update") as mock_update:
            payload = self.bc_api.BigCommerceSourceUpdateRequest()
            response = self.bc_api.update_bigcommerce_source(
                source_id="src-1",
                payload=payload,
                subaccount_id=42,
                user=_user(),
            )
        mock_update.assert_not_called()
        self.assertEqual(response.source_id, "src-1")


class DeleteSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_delete_removes_row_but_preserves_credentials(self) -> None:
        existing = _make_source()
        delete_calls: list[str] = []

        def _fake_delete(source_id):
            delete_calls.append(source_id)

        with patch.object(
            self.bc_api._source_repo, "get_by_id", return_value=existing
        ), patch.object(
            self.bc_api._source_repo, "delete", side_effect=_fake_delete
        ), patch.object(
            self.bc_api.bc_service, "delete_bigcommerce_credentials"
        ) as mock_delete_creds:
            response = self.bc_api.delete_bigcommerce_source(
                source_id="src-1", subaccount_id=42, user=_user()
            )

        self.assertEqual(response, {"status": "ok", "id": "src-1"})
        self.assertEqual(delete_calls, ["src-1"])
        # Critical: the encrypted credentials must NOT be deleted by /sources DELETE.
        mock_delete_creds.assert_not_called()

    def test_delete_cross_tenant_returns_404(self) -> None:
        with patch.object(
            self.bc_api._source_repo,
            "get_by_id",
            return_value=_make_source(subaccount_id=99),
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.delete_bigcommerce_source(
                    source_id="src-1", subaccount_id=42, user=_user()
                )
        self.assertEqual(ctx.exception.status_code, 404)


class TestConnectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def _fake_client(self, store_payload: Any | None = None, *, raise_exc=None):
        client = AsyncMock()
        if raise_exc is not None:
            client.get = AsyncMock(side_effect=raise_exc)
        else:
            client.get = AsyncMock(return_value=store_payload)
        return client

    def test_test_connection_success_pre_claim(self) -> None:
        store_payload = {
            "name": "Test BC Store",
            "domain": "test-bc.example.com",
            "secure_url": "https://test-bc.example.com",
            "currency": "USD",
        }
        client = self._fake_client(store_payload)
        with patch.object(
            self.bc_api.bc_client_module,
            "create_bc_client_from_store_hash",
            return_value=client,
        ):
            payload = self.bc_api.BigCommerceTestConnectionRequest(
                store_hash="abc123"
            )
            result = self._run(
                self.bc_api.test_bigcommerce_connection_pre_claim(
                    payload=payload, user=_user()
                )
            )

        self.assertTrue(result.success)
        self.assertEqual(result.store_name, "Test BC Store")
        self.assertEqual(result.domain, "test-bc.example.com")
        self.assertEqual(result.currency, "USD")

    def test_test_connection_pre_claim_no_credentials(self) -> None:
        with patch.object(
            self.bc_api.bc_client_module,
            "create_bc_client_from_store_hash",
            side_effect=self.bc_api.BigCommerceAuthError("no creds"),
        ):
            payload = self.bc_api.BigCommerceTestConnectionRequest(
                store_hash="abc123"
            )
            result = self._run(
                self.bc_api.test_bigcommerce_connection_pre_claim(
                    payload=payload, user=_user()
                )
            )
        self.assertFalse(result.success)
        self.assertIn("no creds", result.error or "")

    def test_test_connection_pre_claim_invalid_store_hash(self) -> None:
        payload = self.bc_api.BigCommerceTestConnectionRequest(
            store_hash="abc/123"
        )
        result = self._run(
            self.bc_api.test_bigcommerce_connection_pre_claim(
                payload=payload, user=_user()
            )
        )
        self.assertFalse(result.success)

    def test_test_connection_pre_claim_bad_credentials_401(self) -> None:
        from app.integrations.bigcommerce.exceptions import (
            BigCommerceAuthError as ExcAuthError,
        )

        client = self._fake_client(
            raise_exc=ExcAuthError("Unauthorized", status_code=401)
        )
        with patch.object(
            self.bc_api.bc_client_module,
            "create_bc_client_from_store_hash",
            return_value=client,
        ):
            payload = self.bc_api.BigCommerceTestConnectionRequest(
                store_hash="abc123"
            )
            result = self._run(
                self.bc_api.test_bigcommerce_connection_pre_claim(
                    payload=payload, user=_user()
                )
            )
        self.assertFalse(result.success)
        self.assertIn("Invalid credentials", result.error or "")

    def test_test_connection_post_claim_success(self) -> None:
        store_payload = {
            "name": "BC Store 1",
            "domain": "bc.example.com",
            "currency": "EUR",
        }
        client = self._fake_client(store_payload)
        with patch.object(
            self.bc_api._source_repo,
            "get_by_id",
            return_value=_make_source(),
        ), patch.object(
            self.bc_api.bc_client_module,
            "create_bc_client_from_source",
            return_value=client,
        ), patch.object(
            self.bc_api._source_repo, "record_connection_check"
        ) as mock_record:
            result = self._run(
                self.bc_api.test_bigcommerce_source_connection(
                    source_id="src-1",
                    subaccount_id=42,
                    user=_user(),
                )
            )
        self.assertTrue(result.success)
        self.assertEqual(result.store_name, "BC Store 1")
        mock_record.assert_called_with("src-1", success=True)

    def test_test_connection_post_claim_no_credentials_marks_disconnected(self) -> None:
        with patch.object(
            self.bc_api._source_repo,
            "get_by_id",
            return_value=_make_source(),
        ), patch.object(
            self.bc_api.bc_client_module,
            "create_bc_client_from_source",
            side_effect=self.bc_api.BigCommerceAuthError("missing"),
        ), patch.object(
            self.bc_api._source_repo, "record_connection_check"
        ) as mock_record:
            result = self._run(
                self.bc_api.test_bigcommerce_source_connection(
                    source_id="src-1",
                    subaccount_id=42,
                    user=_user(),
                )
            )
        self.assertFalse(result.success)
        mock_record.assert_called_with(
            "src-1", success=False, error=result.error
        )


class RoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_all_crud_routes_registered(self) -> None:
        paths = {
            (getattr(r, "path", ""), tuple(sorted(r.methods)))
            for r in self.bc_api.router.routes
        }
        # claim
        self.assertIn(
            ("/integrations/bigcommerce/sources/claim", ("POST",)), paths
        )
        # available stores
        self.assertIn(
            ("/integrations/bigcommerce/stores/available", ("GET",)), paths
        )
        # CRUD
        self.assertIn(("/integrations/bigcommerce/sources", ("GET",)), paths)
        # /sources/{source_id} appears 3 times: GET / PUT / DELETE
        method_set = {
            tuple(sorted(r.methods))
            for r in self.bc_api.router.routes
            if getattr(r, "path", "") == "/integrations/bigcommerce/sources/{source_id}"
        }
        self.assertEqual(method_set, {("GET",), ("PUT",), ("DELETE",)})
        # test-connection
        self.assertIn(
            (
                "/integrations/bigcommerce/sources/{source_id}/test-connection",
                ("POST",),
            ),
            paths,
        )
        self.assertIn(
            ("/integrations/bigcommerce/test-connection", ("POST",)),
            paths,
        )


if __name__ == "__main__":
    unittest.main()
