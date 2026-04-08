"""Tests for the four BigCommerce callback endpoints.

Style mirrors ``tests/test_shopify_webhooks.py`` — no DB, no live HTTP, the
router functions are called directly with monkey-patched repository /
service methods so the tests remain hermetic.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import os
import time
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch


def _reload_bc_modules():
    import app.integrations.bigcommerce.config as cfg

    importlib.reload(cfg)
    import app.integrations.bigcommerce.auth as auth_mod

    importlib.reload(auth_mod)
    import app.integrations.bigcommerce.service as svc

    importlib.reload(svc)
    return cfg, auth_mod, svc


def _reload_router():
    _reload_bc_modules()
    from app.api.integrations import bigcommerce as bc_api

    importlib.reload(bc_api)
    return bc_api


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["BC_CLIENT_ID"] = "voxel-bc-client-id"
    os.environ["BC_CLIENT_SECRET"] = "voxel-bc-client-secret"
    os.environ["BC_CLIENT_UUID"] = "bc-account-uuid"
    os.environ["BC_REDIRECT_URI"] = "https://admin.example.com/agency/integrations/bigcommerce/callback"
    os.environ["BC_SCOPES"] = "store_v2_products_read_only"
    os.environ["FF_FEED_MANAGEMENT_ENABLED"] = "1"


def _b64url_nopad(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _build_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url_nopad(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_nopad(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_nopad(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _valid_jwt(secret: str = "voxel-bc-client-secret", **overrides) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "aud": "voxel-bc-client-id",
        "iss": "bc",
        "iat": now - 10,
        "nbf": now - 10,
        "exp": now + 3600,
        "jti": "deadbeef",
        "sub": "stores/abc123",
        "user": {"id": 9876543, "email": "user@example.com"},
        "owner": {"id": 7654321, "email": "owner@example.com"},
        "url": "/",
        "channel_id": None,
    }
    payload.update(overrides)
    return _build_jwt(payload, secret)


class _StubSource:
    """Stand-in for ``FeedSourceResponse`` — only the attrs the router touches."""

    def __init__(
        self,
        *,
        source_id: str = "src-1",
        subaccount_id: int = 42,
        shop_domain: str = "abc123",
    ) -> None:
        self.id = source_id
        self.subaccount_id = subaccount_id
        self.shop_domain = shop_domain


class AuthCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def _fake_exchange(self, **expected_scope_kwargs):
        def _impl(**kwargs):
            return {
                "access_token": "bc_TOKEN",
                "scope": kwargs.get("scope") or "store_v2_products_read_only",
                "user": {"id": 9876543, "email": "user@example.com"},
                "context": kwargs.get("context") or "stores/abc123",
                "account_uuid": "bc-account-uuid",
            }

        return _impl

    def test_callback_stores_credentials_and_creates_source(self) -> None:
        stored_creds: list[dict[str, Any]] = []
        created_sources: list[Any] = []
        marked_connected: list[str] = []

        def _fake_store(**kwargs):
            stored_creds.append(kwargs)

        def _fake_get_by_hash(store_hash):
            return []

        def _fake_create(payload):
            created_sources.append(payload)
            return _StubSource(
                source_id="new-src",
                subaccount_id=payload.subaccount_id,
                shop_domain=payload.shop_domain,
            )

        def _fake_mark(source_id, *, scopes):
            marked_connected.append(source_id)
            return _StubSource(source_id=source_id)

        with patch.object(
            self.bc_api.bc_auth, "exchange_code_for_token", side_effect=self._fake_exchange()
        ), patch.object(
            self.bc_api.bc_service, "store_bigcommerce_credentials", side_effect=_fake_store
        ), patch.object(
            self.bc_api._source_repo,
            "get_by_bigcommerce_store_hash",
            side_effect=_fake_get_by_hash,
        ), patch.object(
            self.bc_api._source_repo, "create", side_effect=_fake_create
        ), patch.object(
            self.bc_api._source_repo, "mark_oauth_connected", side_effect=_fake_mark
        ):
            response = self.bc_api.bigcommerce_auth_callback(
                code="code-xyz",
                scope="store_v2_products_read_only",
                context="stores/abc123",
                account_uuid="bc-account-uuid",
                subaccount_id=42,
            )

        self.assertTrue(response.success)
        self.assertEqual(response.store_hash, "abc123")
        self.assertEqual(response.scope, "store_v2_products_read_only")
        self.assertEqual(len(stored_creds), 1)
        self.assertEqual(stored_creds[0]["store_hash"], "abc123")
        self.assertEqual(stored_creds[0]["access_token"], "bc_TOKEN")
        self.assertEqual(len(created_sources), 1)
        self.assertEqual(marked_connected, ["new-src"])

    def test_callback_existing_store_refreshes_source(self) -> None:
        stored_creds: list[dict[str, Any]] = []
        created_sources: list[Any] = []
        marked_connected: list[str] = []

        existing = _StubSource(source_id="existing-src", subaccount_id=42, shop_domain="abc123")

        def _fake_store(**kwargs):
            stored_creds.append(kwargs)

        def _fake_get_by_hash(store_hash):
            return [existing]

        def _fake_create(payload):
            created_sources.append(payload)
            raise AssertionError("create() must NOT be called for existing stores")

        def _fake_mark(source_id, *, scopes):
            marked_connected.append(source_id)
            return _StubSource(source_id=source_id)

        with patch.object(
            self.bc_api.bc_auth, "exchange_code_for_token", side_effect=self._fake_exchange()
        ), patch.object(
            self.bc_api.bc_service, "store_bigcommerce_credentials", side_effect=_fake_store
        ), patch.object(
            self.bc_api._source_repo,
            "get_by_bigcommerce_store_hash",
            side_effect=_fake_get_by_hash,
        ), patch.object(
            self.bc_api._source_repo, "create", side_effect=_fake_create
        ), patch.object(
            self.bc_api._source_repo, "mark_oauth_connected", side_effect=_fake_mark
        ):
            response = self.bc_api.bigcommerce_auth_callback(
                code="code-xyz",
                scope="store_v2_products_read_only",
                context="stores/abc123",
                account_uuid=None,
                subaccount_id=42,
            )

        self.assertTrue(response.success)
        self.assertEqual(created_sources, [])
        self.assertEqual(marked_connected, ["existing-src"])
        self.assertEqual(len(stored_creds), 1)

    def test_callback_without_subaccount_hint_still_stores_credentials(self) -> None:
        stored_creds: list[dict[str, Any]] = []
        called_repo: list[None] = []

        def _fake_store(**kwargs):
            stored_creds.append(kwargs)

        def _unexpected(*args, **kwargs):
            called_repo.append(None)
            return []

        with patch.object(
            self.bc_api.bc_auth, "exchange_code_for_token", side_effect=self._fake_exchange()
        ), patch.object(
            self.bc_api.bc_service, "store_bigcommerce_credentials", side_effect=_fake_store
        ), patch.object(
            self.bc_api._source_repo,
            "get_by_bigcommerce_store_hash",
            side_effect=_unexpected,
        ):
            response = self.bc_api.bigcommerce_auth_callback(
                code="code-xyz",
                scope="store_v2_products_read_only",
                context="stores/abc123",
                account_uuid=None,
                subaccount_id=None,
            )

        self.assertTrue(response.success)
        self.assertEqual(len(stored_creds), 1)
        self.assertEqual(called_repo, [])  # repo lookup is skipped w/o subaccount

    def test_callback_invalid_context_returns_400(self) -> None:
        with patch.object(self.bc_api.bc_auth, "exchange_code_for_token"):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.bigcommerce_auth_callback(
                    code="code",
                    scope="",
                    context="not-a-context",
                    account_uuid=None,
                    subaccount_id=None,
                )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_callback_unconfigured_returns_503(self) -> None:
        for key in ("BC_CLIENT_ID", "BC_CLIENT_SECRET", "BC_REDIRECT_URI"):
            os.environ.pop(key, None)
        bc_api = _reload_router()
        with self.assertRaises(bc_api.HTTPException) as ctx:
            bc_api.bigcommerce_auth_callback(
                code="code",
                scope="",
                context="stores/abc123",
                account_uuid=None,
                subaccount_id=None,
            )
        self.assertEqual(ctx.exception.status_code, 503)
        _set_env()
        _reload_router()

    def test_callback_exchange_failure_surfaces_as_http_error(self) -> None:
        def _boom(**kwargs):
            raise self.bc_api.BigCommerceAuthError(
                "bad code", http_status=400
            )

        with patch.object(
            self.bc_api.bc_auth, "exchange_code_for_token", side_effect=_boom
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.bigcommerce_auth_callback(
                    code="bad",
                    scope="",
                    context="stores/abc123",
                    account_uuid=None,
                    subaccount_id=None,
                )
        self.assertEqual(ctx.exception.status_code, 400)


class LoadCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_valid_jwt_returns_session_info(self) -> None:
        token = _valid_jwt()
        response = self.bc_api.bigcommerce_load_callback(signed_payload_jwt=token)
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.store_hash, "abc123")
        self.assertEqual(response.user_email, "user@example.com")
        self.assertEqual(response.owner_email, "owner@example.com")

    def test_invalid_jwt_returns_401(self) -> None:
        # Tamper the signature segment.
        token = _valid_jwt() + "tampered"
        with self.assertRaises(self.bc_api.HTTPException) as ctx:
            self.bc_api.bigcommerce_load_callback(signed_payload_jwt=token)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_wrong_secret_returns_401(self) -> None:
        token = _valid_jwt(secret="other-secret")
        with self.assertRaises(self.bc_api.HTTPException) as ctx:
            self.bc_api.bigcommerce_load_callback(signed_payload_jwt=token)
        self.assertEqual(ctx.exception.status_code, 401)


class UninstallCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_valid_jwt_marks_sources_disconnected_and_deletes_token(self) -> None:
        marked: list[tuple[str, str]] = []
        deleted: list[str] = []

        def _fake_mark(store_hash, *, reason):
            marked.append((store_hash, reason))
            return 2

        def _fake_delete(store_hash):
            deleted.append(store_hash)

        with patch.object(
            self.bc_api._source_repo,
            "mark_disconnected_by_bigcommerce_store_hash",
            side_effect=_fake_mark,
        ), patch.object(
            self.bc_api.bc_service,
            "delete_bigcommerce_credentials",
            side_effect=_fake_delete,
        ):
            response = self.bc_api.bigcommerce_uninstall_callback(
                signed_payload_jwt=_valid_jwt()
            )

        self.assertEqual(response.status, "ok")
        self.assertEqual(response.store_hash, "abc123")
        self.assertEqual(response.sources_disconnected, 2)
        self.assertEqual(marked, [("abc123", "App uninstalled by merchant")])
        self.assertEqual(deleted, ["abc123"])

    def test_invalid_jwt_returns_401(self) -> None:
        called: list[None] = []

        def _unexpected(*args, **kwargs):
            called.append(None)
            return 0

        with patch.object(
            self.bc_api._source_repo,
            "mark_disconnected_by_bigcommerce_store_hash",
            side_effect=_unexpected,
        ):
            with self.assertRaises(self.bc_api.HTTPException) as ctx:
                self.bc_api.bigcommerce_uninstall_callback(
                    signed_payload_jwt="definitely.not.a.jwt"
                )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(called, [])

    def test_internal_cleanup_failure_still_returns_200(self) -> None:
        def _boom_mark(store_hash, *, reason):
            raise RuntimeError("db down")

        def _boom_delete(store_hash):
            raise RuntimeError("secrets store down")

        with patch.object(
            self.bc_api._source_repo,
            "mark_disconnected_by_bigcommerce_store_hash",
            side_effect=_boom_mark,
        ), patch.object(
            self.bc_api.bc_service,
            "delete_bigcommerce_credentials",
            side_effect=_boom_delete,
        ):
            response = self.bc_api.bigcommerce_uninstall_callback(
                signed_payload_jwt=_valid_jwt()
            )
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.sources_disconnected, 0)


class RemoveUserCallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_valid_jwt_returns_200_with_user_info(self) -> None:
        response = self.bc_api.bigcommerce_remove_user_callback(
            signed_payload_jwt=_valid_jwt()
        )
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.store_hash, "abc123")
        self.assertEqual(response.user_email, "user@example.com")

    def test_invalid_jwt_returns_401(self) -> None:
        with self.assertRaises(self.bc_api.HTTPException) as ctx:
            self.bc_api.bigcommerce_remove_user_callback(
                signed_payload_jwt="x.y.z"
            )
        self.assertEqual(ctx.exception.status_code, 401)


class CallbackRoutingTests(unittest.TestCase):
    """Smoke tests on the router wiring itself (no endpoint invocation)."""

    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.bc_api = _reload_router()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_router()

    def test_all_four_callbacks_are_registered(self) -> None:
        paths = {getattr(r, "path", "") for r in self.bc_api.router.routes}
        self.assertIn("/integrations/bigcommerce/auth/callback", paths)
        self.assertIn("/integrations/bigcommerce/auth/load", paths)
        self.assertIn("/integrations/bigcommerce/auth/uninstall", paths)
        self.assertIn("/integrations/bigcommerce/auth/remove-user", paths)

    def test_callbacks_do_not_require_authentication_dependency(self) -> None:
        from fastapi.dependencies.utils import get_dependant

        callback_paths = (
            "/integrations/bigcommerce/auth/callback",
            "/integrations/bigcommerce/auth/load",
            "/integrations/bigcommerce/auth/uninstall",
            "/integrations/bigcommerce/auth/remove-user",
        )
        for path in callback_paths:
            route = next(
                r for r in self.bc_api.router.routes if getattr(r, "path", "") == path
            )
            self.assertIn("GET", route.methods)
            dependant = get_dependant(path=route.path, call=route.endpoint)
            for sub in dependant.dependencies:
                call = getattr(sub, "call", None)
                self.assertNotEqual(
                    getattr(call, "__name__", ""),
                    "get_current_user",
                    f"{path} must not depend on get_current_user",
                )


if __name__ == "__main__":
    unittest.main()
