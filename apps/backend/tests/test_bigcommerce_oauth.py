"""Tests for the BigCommerce OAuth 2.0 flow: JWT verification + token exchange + service helpers.

Mirrors the style of ``tests/test_shopify_oauth.py``:

* No DB, no live HTTP — every external call is monkey-patched.
* Module-level env reads are refreshed via ``importlib.reload`` per test.
* JWT helpers are validated end-to-end against ``verify_signed_payload_jwt``
  to make sure the stdlib HS256 implementation matches what BigCommerce
  actually emits.
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

from app.services.integration_secrets_store import IntegrationSecretValue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_bigcommerce_modules():
    """Reload config + auth + service so module-level env reads refresh."""
    import app.integrations.bigcommerce.config as cfg

    importlib.reload(cfg)
    import app.integrations.bigcommerce.auth as auth_mod

    importlib.reload(auth_mod)
    import app.integrations.bigcommerce.service as svc

    importlib.reload(svc)
    return cfg, auth_mod, svc


def _b64url_nopad(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _build_jwt(
    payload: dict,
    secret: str,
    *,
    alg: str = "HS256",
    typ: str | None = "JWT",
) -> str:
    header: dict = {"alg": alg}
    if typ is not None:
        header["typ"] = typ
    header_b64 = _b64url_nopad(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_nopad(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_nopad(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _valid_payload(**overrides) -> dict:
    now = int(time.time())
    payload: dict = {
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
    return payload


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["BC_CLIENT_ID"] = "voxel-bc-client-id"
    os.environ["BC_CLIENT_SECRET"] = "voxel-bc-client-secret"
    os.environ["BC_CLIENT_UUID"] = "bc-account-uuid"
    os.environ["BC_REDIRECT_URI"] = "https://admin.example.com/agency/integrations/bigcommerce/callback"
    os.environ["BC_SCOPES"] = "store_v2_products_read_only store_v2_information_read_only"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class BigCommerceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bigcommerce_modules()

    def test_oauth_configured_false_when_missing(self) -> None:
        for key in ("BC_CLIENT_ID", "BC_CLIENT_SECRET", "BC_REDIRECT_URI"):
            os.environ.pop(key, None)
        cfg, _, _ = _reload_bigcommerce_modules()
        self.assertFalse(cfg.oauth_configured())

    def test_oauth_configured_true_when_all_set(self) -> None:
        _set_env()
        cfg, _, _ = _reload_bigcommerce_modules()
        self.assertTrue(cfg.oauth_configured())

    def test_require_oauth_configured_raises_with_list(self) -> None:
        # BC_CLIENT_ID + BC_CLIENT_SECRET have no default; BC_REDIRECT_URI
        # falls back to the admin.omarosa.ro URL so it's not in the "missing"
        # list unless we explicitly blank it.
        for key in ("BC_CLIENT_ID", "BC_CLIENT_SECRET"):
            os.environ.pop(key, None)
        cfg, _, _ = _reload_bigcommerce_modules()
        with self.assertRaises(RuntimeError) as ctx:
            cfg.require_oauth_configured()
        self.assertIn("BC_CLIENT_ID", str(ctx.exception))
        self.assertIn("BC_CLIENT_SECRET", str(ctx.exception))

    def test_validate_store_hash_normalizes_case(self) -> None:
        cfg, _, _ = _reload_bigcommerce_modules()
        self.assertEqual(cfg.validate_store_hash("ABC123"), "abc123")

    def test_validate_store_hash_rejects_invalid(self) -> None:
        cfg, _, _ = _reload_bigcommerce_modules()
        with self.assertRaises(ValueError):
            cfg.validate_store_hash("abc/123")
        with self.assertRaises(ValueError):
            cfg.validate_store_hash("")

    def test_get_store_api_base_url(self) -> None:
        cfg, _, _ = _reload_bigcommerce_modules()
        self.assertEqual(
            cfg.get_bigcommerce_store_api_base_url("abc123"),
            "https://api.bigcommerce.com/stores/abc123/v3",
        )


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------


class VerifySignedPayloadJwtTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.cfg, self.auth_mod, _ = _reload_bigcommerce_modules()
        self.secret = "voxel-bc-client-secret"

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bigcommerce_modules()

    def test_verify_returns_claims_for_valid_jwt(self) -> None:
        payload = _valid_payload()
        token = _build_jwt(payload, self.secret)
        claims = self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertEqual(claims["sub"], "stores/abc123")
        self.assertEqual(claims["user"]["email"], "user@example.com")
        self.assertEqual(claims["iss"], "bc")

    def test_verify_rejects_expired_jwt(self) -> None:
        now = int(time.time())
        payload = _valid_payload(iat=now - 7200, nbf=now - 7200, exp=now - 120)
        token = _build_jwt(payload, self.secret)
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_verify_rejects_wrong_secret(self) -> None:
        token = _build_jwt(_valid_payload(), "other-secret")
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertIn("signature", str(ctx.exception).lower())

    def test_verify_rejects_wrong_audience(self) -> None:
        token = _build_jwt(_valid_payload(aud="other-client-id"), self.secret)
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(
                token, self.secret, client_id="voxel-bc-client-id"
            )
        self.assertIn("audience", str(ctx.exception).lower())

    def test_verify_rejects_wrong_issuer(self) -> None:
        token = _build_jwt(_valid_payload(iss="not-bc"), self.secret)
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertIn("issuer", str(ctx.exception).lower())

    def test_verify_rejects_non_hs256_algorithm(self) -> None:
        token = _build_jwt(_valid_payload(), self.secret, alg="none")
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertIn("alg", str(ctx.exception).lower())

    def test_verify_rejects_malformed_jwt(self) -> None:
        with self.assertRaises(self.auth_mod.BigCommerceAuthError):
            self.auth_mod.verify_signed_payload_jwt("not.a.jwt.extra", self.secret)
        with self.assertRaises(self.auth_mod.BigCommerceAuthError):
            self.auth_mod.verify_signed_payload_jwt("single-segment", self.secret)

    def test_verify_requires_client_secret(self) -> None:
        with self.assertRaises(self.auth_mod.BigCommerceAuthError):
            self.auth_mod.verify_signed_payload_jwt("a.b.c", "")

    def test_verify_rejects_future_nbf(self) -> None:
        now = int(time.time())
        payload = _valid_payload(nbf=now + 3600, exp=now + 7200)
        token = _build_jwt(payload, self.secret)
        with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
            self.auth_mod.verify_signed_payload_jwt(token, self.secret)
        self.assertIn("not yet valid", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# extract_store_hash
# ---------------------------------------------------------------------------


class ExtractStoreHashTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.auth_mod, _ = _reload_bigcommerce_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bigcommerce_modules()

    def test_extract_happy_path(self) -> None:
        self.assertEqual(self.auth_mod.extract_store_hash("stores/abc123"), "abc123")

    def test_extract_normalizes_case(self) -> None:
        self.assertEqual(self.auth_mod.extract_store_hash("stores/ABC123"), "abc123")

    def test_extract_rejects_missing_prefix(self) -> None:
        with self.assertRaises(ValueError):
            self.auth_mod.extract_store_hash("abc123")

    def test_extract_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            self.auth_mod.extract_store_hash("")

    def test_extract_rejects_invalid_hash_chars(self) -> None:
        with self.assertRaises(ValueError):
            self.auth_mod.extract_store_hash("stores/abc-123")


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


class ExchangeCodeForTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.cfg, self.auth_mod, _ = _reload_bigcommerce_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bigcommerce_modules()

    def test_exchange_happy_path(self) -> None:
        captured: dict = {}

        def _fake_post(url: str, body: dict):
            captured["url"] = url
            captured["body"] = body
            return {
                "access_token": "bc_TESTTOKEN",
                "scope": "store_v2_products_read_only",
                "user": {"id": 9876543, "email": "user@example.com"},
                "context": "stores/abc123",
                "account_uuid": "bc-account-uuid",
            }

        original = self.auth_mod._http_post_form
        try:
            self.auth_mod._http_post_form = _fake_post
            result = self.auth_mod.exchange_code_for_token(
                code="code-xyz",
                scope="store_v2_products_read_only",
                context="stores/abc123",
            )
        finally:
            self.auth_mod._http_post_form = original

        self.assertEqual(result["access_token"], "bc_TESTTOKEN")
        self.assertEqual(result["context"], "stores/abc123")
        self.assertEqual(captured["url"], "https://login.bigcommerce.com/oauth2/token")
        self.assertEqual(captured["body"]["client_id"], "voxel-bc-client-id")
        self.assertEqual(captured["body"]["client_secret"], "voxel-bc-client-secret")
        self.assertEqual(captured["body"]["code"], "code-xyz")
        self.assertEqual(captured["body"]["grant_type"], "authorization_code")
        self.assertEqual(captured["body"]["context"], "stores/abc123")
        self.assertEqual(
            captured["body"]["redirect_uri"],
            "https://admin.example.com/agency/integrations/bigcommerce/callback",
        )

    def test_exchange_raises_when_missing_access_token(self) -> None:
        def _fake_post(url: str, body: dict):
            return {"scope": "x"}

        original = self.auth_mod._http_post_form
        try:
            self.auth_mod._http_post_form = _fake_post
            with self.assertRaises(self.auth_mod.BigCommerceAuthError) as ctx:
                self.auth_mod.exchange_code_for_token(
                    code="code",
                    scope="x",
                    context="stores/abc",
                )
        finally:
            self.auth_mod._http_post_form = original
        self.assertIn("access token", str(ctx.exception).lower())

    def test_exchange_requires_configured_credentials(self) -> None:
        for key in ("BC_CLIENT_ID", "BC_CLIENT_SECRET", "BC_REDIRECT_URI"):
            os.environ.pop(key, None)
        _, auth_mod, _ = _reload_bigcommerce_modules()
        with self.assertRaises(auth_mod.BigCommerceAuthError):
            auth_mod.exchange_code_for_token(
                code="code",
                scope="",
                context="stores/abc",
            )


# ---------------------------------------------------------------------------
# Service (credential persistence)
# ---------------------------------------------------------------------------


class BigCommerceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, _, self.svc = _reload_bigcommerce_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bigcommerce_modules()

    def _install_fake_store(self) -> dict[tuple[str, str, str], str]:
        stored: dict[tuple[str, str, str], str] = {}

        def _fake_upsert(*, provider: str, secret_key: str, value: str, scope: str = "agency_default") -> None:
            stored[(provider, secret_key, scope)] = value

        def _fake_get(*, provider: str, secret_key: str, scope: str = "agency_default"):
            value = stored.get((provider, secret_key, scope))
            if value is None:
                return None
            return IntegrationSecretValue(
                provider=provider,
                secret_key=secret_key,
                scope=scope,
                value=value,
                updated_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
            )

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            stored.pop((provider, secret_key, scope), None)

        self.svc.integration_secrets_store.upsert_secret = _fake_upsert  # type: ignore[assignment]
        self.svc.integration_secrets_store.get_secret = _fake_get  # type: ignore[assignment]
        self.svc.integration_secrets_store.delete_secret = _fake_delete  # type: ignore[assignment]
        return stored

    def test_store_and_get_round_trip(self) -> None:
        stored = self._install_fake_store()

        self.svc.store_bigcommerce_credentials(
            store_hash="abc123",
            access_token="bc_TOKEN",
            scope="store_v2_products_read_only",
            user_info={"id": 9876543, "email": "user@example.com"},
        )

        self.assertEqual(
            stored[("bigcommerce", "access_token", "abc123")], "bc_TOKEN"
        )
        self.assertEqual(
            stored[("bigcommerce", "scope", "abc123")], "store_v2_products_read_only"
        )
        self.assertEqual(
            stored[("bigcommerce", "user_email", "abc123")], "user@example.com"
        )
        self.assertEqual(
            stored[("bigcommerce", "user_id", "abc123")], "9876543"
        )

        creds = self.svc.get_bigcommerce_credentials("abc123")
        self.assertIsNotNone(creds)
        assert creds is not None
        self.assertEqual(creds["access_token"], "bc_TOKEN")
        self.assertEqual(creds["scope"], "store_v2_products_read_only")
        self.assertEqual(creds["user_email"], "user@example.com")
        self.assertEqual(creds["user_id"], "9876543")

        token = self.svc.get_access_token_for_store("ABC123")  # case-insensitive
        self.assertEqual(token, "bc_TOKEN")

    def test_store_requires_access_token(self) -> None:
        self._install_fake_store()
        with self.assertRaises(ValueError):
            self.svc.store_bigcommerce_credentials(
                store_hash="abc123",
                access_token="",
                scope="",
            )

    def test_store_rejects_invalid_store_hash(self) -> None:
        self._install_fake_store()
        with self.assertRaises(ValueError):
            self.svc.store_bigcommerce_credentials(
                store_hash="abc/123",
                access_token="bc_TOKEN",
                scope="",
            )

    def test_get_returns_none_when_missing(self) -> None:
        self._install_fake_store()
        self.assertIsNone(self.svc.get_bigcommerce_credentials("unknown"))

    def test_delete_removes_all_keys(self) -> None:
        stored = self._install_fake_store()
        self.svc.store_bigcommerce_credentials(
            store_hash="abc123",
            access_token="bc_TOKEN",
            scope="store_v2_products_read_only",
            user_info={"id": 1, "email": "a@b.com"},
        )
        self.assertTrue(
            any(key[2] == "abc123" for key in stored.keys())
        )
        self.svc.delete_bigcommerce_credentials("abc123")
        self.assertFalse(
            any(key[2] == "abc123" for key in stored.keys())
        )

    def test_delete_silently_ignores_invalid_hash(self) -> None:
        self._install_fake_store()
        # Must not raise
        self.svc.delete_bigcommerce_credentials("abc/123")

    def test_status_when_not_configured(self) -> None:
        for key in ("BC_CLIENT_ID", "BC_CLIENT_SECRET", "BC_REDIRECT_URI"):
            os.environ.pop(key, None)
        _, _, svc = _reload_bigcommerce_modules()
        payload = svc.get_bigcommerce_status()
        self.assertFalse(payload["oauth_configured"])
        self.assertEqual(payload["token_count"], 0)
        self.assertEqual(payload["connected_stores"], [])

    def test_status_when_configured_no_stores(self) -> None:
        original = self.svc._list_connected_stores
        try:
            self.svc._list_connected_stores = lambda: []
            payload = self.svc.get_bigcommerce_status()
        finally:
            self.svc._list_connected_stores = original
        self.assertTrue(payload["oauth_configured"])
        self.assertEqual(payload["token_count"], 0)


if __name__ == "__main__":
    unittest.main()
