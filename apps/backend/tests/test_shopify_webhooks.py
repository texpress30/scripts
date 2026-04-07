"""Tests for the Shopify ``app/uninstalled`` webhook handler and helpers.

Covers:
* ``verify_shopify_webhook_hmac`` (timing-safe, edge cases)
* ``register_uninstall_webhook`` (success / 422 already-taken / network error)
* ``delete_shopify_token`` cleanup
* ``POST /integrations/shopify/webhooks/app-uninstalled`` end-to-end via the
  router function (HMAC valid → 200 + cleanup, HMAC invalid → 401, missing
  shop → graceful 200, idempotent re-delivery).

Style mirrors ``tests/test_shopify_oauth.py`` and
``tests/routers/test_feed_sources_shopify.py`` — no DB, no live HTTP, async
endpoints driven via ``asyncio.run``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import importlib
import json
import os
import unittest
from typing import Any
from unittest.mock import patch


def _reload_shopify_modules():
    import app.integrations.shopify.config as cfg

    importlib.reload(cfg)
    import app.integrations.shopify.service as svc

    importlib.reload(svc)
    return cfg, svc


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["SHOPIFY_APP_CLIENT_ID"] = "voxel-client-id"
    os.environ["SHOPIFY_APP_CLIENT_SECRET"] = "voxel-client-secret"
    os.environ["SHOPIFY_API_VERSION"] = "2026-04"
    os.environ["SHOPIFY_REDIRECT_URI"] = "https://example.com/agency/integrations/shopify/callback"
    os.environ["SHOPIFY_SCOPES"] = "read_products"
    os.environ["SHOPIFY_WEBHOOK_BASE_URL"] = "https://admin.example.com"


def _shopify_hmac(body: bytes, secret: str) -> str:
    return base64.b64encode(hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()).decode("utf-8")


class _FakeRequest:
    """Minimal stand-in for ``starlette.requests.Request`` covering ``.body()``
    and ``.headers``. The webhook handler only touches these two fields."""

    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body = body
        self.headers = headers

    async def body(self) -> bytes:
        return self._body


class VerifyHmacTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.svc = _reload_shopify_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()

    def test_verify_returns_true_for_matching_signature(self) -> None:
        body = b'{"shop_id": 1, "name": "test"}'
        secret = "voxel-client-secret"
        signature = _shopify_hmac(body, secret)
        self.assertTrue(self.svc.verify_shopify_webhook_hmac(body, signature, secret))

    def test_verify_returns_false_for_tampered_body(self) -> None:
        body = b'{"shop_id": 1}'
        secret = "voxel-client-secret"
        signature = _shopify_hmac(body, secret)
        self.assertFalse(self.svc.verify_shopify_webhook_hmac(b'{"shop_id": 2}', signature, secret))

    def test_verify_returns_false_for_wrong_secret(self) -> None:
        body = b"payload"
        signature = _shopify_hmac(body, "voxel-client-secret")
        self.assertFalse(self.svc.verify_shopify_webhook_hmac(body, signature, "other-secret"))

    def test_verify_returns_false_for_empty_body(self) -> None:
        signature = _shopify_hmac(b"x", "voxel-client-secret")
        self.assertFalse(self.svc.verify_shopify_webhook_hmac(b"", signature, "voxel-client-secret"))

    def test_verify_returns_false_for_missing_header(self) -> None:
        self.assertFalse(self.svc.verify_shopify_webhook_hmac(b"payload", "", "voxel-client-secret"))

    def test_verify_uses_compare_digest_timing_safe(self) -> None:
        # Sanity check: ``hmac.compare_digest`` is the comparison primitive.
        # We monkey-patch it to a sentinel and ensure the helper invokes it.
        called: list[tuple[str, str]] = []

        def _spy(a: str, b: str) -> bool:
            called.append((a, b))
            return False

        with patch.object(self.svc.hmac, "compare_digest", side_effect=_spy):
            self.svc.verify_shopify_webhook_hmac(b"payload", "header", "secret")
        self.assertEqual(len(called), 1)


class RegisterUninstallWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.svc = _reload_shopify_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()

    def test_returns_true_on_201(self) -> None:
        captured: dict[str, Any] = {}

        def _fake_request(*, method: str, shop_domain: str, path: str, access_token: str, body: dict | None = None, timeout: int = 15):
            captured.update(method=method, shop_domain=shop_domain, path=path, access_token=access_token, body=body)
            return 201, {"webhook": {"id": 1}}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            ok = self.svc.register_uninstall_webhook("My-Store.myshopify.com", "shpua_TEST")

        self.assertTrue(ok)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["shop_domain"], "my-store.myshopify.com")
        self.assertEqual(captured["path"], "/webhooks.json")
        self.assertEqual(captured["body"]["webhook"]["topic"], "app/uninstalled")
        self.assertEqual(
            captured["body"]["webhook"]["address"],
            "https://admin.example.com/api/integrations/shopify/webhooks/app-uninstalled",
        )

    def test_returns_true_when_already_registered_422(self) -> None:
        def _fake_request(**kwargs):
            return 422, {"errors": {"address": ["for this topic has already been taken"]}}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            ok = self.svc.register_uninstall_webhook("store.myshopify.com", "shpua_TEST")
        self.assertTrue(ok)

    def test_returns_false_on_network_error(self) -> None:
        with patch.object(self.svc, "_shop_admin_request", side_effect=lambda **kw: (0, {})):
            self.assertFalse(self.svc.register_uninstall_webhook("store.myshopify.com", "shpua_TEST"))

    def test_returns_false_on_other_422_validation_errors(self) -> None:
        def _fake_request(**kwargs):
            return 422, {"errors": {"address": ["is not https"]}}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            self.assertFalse(self.svc.register_uninstall_webhook("store.myshopify.com", "shpua_TEST"))

    def test_returns_false_for_invalid_shop_domain_without_calling_api(self) -> None:
        called: list[None] = []

        def _spy(**kwargs):
            called.append(None)
            return 201, {}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_spy):
            self.assertFalse(self.svc.register_uninstall_webhook("evil.com", "shpua_TEST"))
        self.assertEqual(called, [])


class RegisterComplianceWebhooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.svc = _reload_shopify_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()

    def test_registers_all_three_topics_on_201(self) -> None:
        captured: list[dict[str, Any]] = []

        def _fake_request(*, method: str, shop_domain: str, path: str, access_token: str, body: dict | None = None, timeout: int = 15):
            captured.append({"method": method, "shop_domain": shop_domain, "path": path, "body": body})
            return 201, {"webhook": {"id": len(captured)}}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            results = self.svc.register_compliance_webhooks("My-Store.myshopify.com", "shpua_TEST")

        self.assertEqual(
            results,
            {"customers/data_request": True, "customers/redact": True, "shop/redact": True},
        )
        self.assertEqual(len(captured), 3)
        topics_called = [c["body"]["webhook"]["topic"] for c in captured]
        self.assertEqual(
            topics_called,
            ["customers/data_request", "customers/redact", "shop/redact"],
        )
        for c in captured:
            self.assertEqual(c["method"], "POST")
            self.assertEqual(c["path"], "/webhooks.json")
            self.assertEqual(c["shop_domain"], "my-store.myshopify.com")
            self.assertEqual(
                c["body"]["webhook"]["address"],
                "https://admin.example.com/api/integrations/shopify/webhooks/compliance",
            )
            self.assertEqual(c["body"]["webhook"]["format"], "json")

    def test_returns_true_when_already_registered_422(self) -> None:
        def _fake_request(**kwargs):
            return 422, {"errors": {"address": ["for this topic has already been taken"]}}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            results = self.svc.register_compliance_webhooks("store.myshopify.com", "shpua_TEST")
        self.assertEqual(
            results,
            {"customers/data_request": True, "customers/redact": True, "shop/redact": True},
        )

    def test_partial_failure_marks_only_failing_topic_false(self) -> None:
        # First two succeed, third returns 422 with a non-"taken" error
        responses = iter([
            (201, {"webhook": {"id": 1}}),
            (201, {"webhook": {"id": 2}}),
            (422, {"errors": {"address": ["is invalid"]}}),
        ])

        def _fake_request(**kwargs):
            return next(responses)

        with patch.object(self.svc, "_shop_admin_request", side_effect=_fake_request):
            results = self.svc.register_compliance_webhooks("store.myshopify.com", "shpua_TEST")

        self.assertTrue(results["customers/data_request"])
        self.assertTrue(results["customers/redact"])
        self.assertFalse(results["shop/redact"])

    def test_network_error_returns_all_false(self) -> None:
        with patch.object(self.svc, "_shop_admin_request", side_effect=lambda **kw: (0, {})):
            results = self.svc.register_compliance_webhooks("store.myshopify.com", "shpua_TEST")
        self.assertEqual(set(results.values()), {False})
        self.assertEqual(set(results.keys()), set(self.svc.GDPR_COMPLIANCE_WEBHOOK_TOPICS))

    def test_invalid_shop_returns_all_false_without_calling_api(self) -> None:
        called: list[None] = []

        def _spy(**kwargs):
            called.append(None)
            return 201, {}

        with patch.object(self.svc, "_shop_admin_request", side_effect=_spy):
            results = self.svc.register_compliance_webhooks("evil.com", "shpua_TEST")
        self.assertEqual(set(results.values()), {False})
        self.assertEqual(called, [])

    def test_compliance_webhook_address_uses_env_override(self) -> None:
        try:
            os.environ["SHOPIFY_WEBHOOK_BASE_URL"] = "https://custom.example.org/"
            _, svc = _reload_shopify_modules()
            self.assertEqual(
                svc.get_compliance_webhook_address(),
                "https://custom.example.org/api/integrations/shopify/webhooks/compliance",
            )
        finally:
            os.environ["SHOPIFY_WEBHOOK_BASE_URL"] = "https://admin.example.com"
            _reload_shopify_modules()


class DeleteShopifyTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.svc = _reload_shopify_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()

    def test_delete_calls_secrets_store_for_token_and_scope(self) -> None:
        deleted: list[tuple[str, str, str]] = []

        def _fake_delete(*, provider: str, secret_key: str, scope: str = "agency_default") -> None:
            deleted.append((provider, secret_key, scope))

        with patch.object(self.svc.integration_secrets_store, "delete_secret", side_effect=_fake_delete):
            self.svc.delete_shopify_token("My-Store.myshopify.com")

        self.assertIn(("shopify", "access_token", "my-store.myshopify.com"), deleted)
        self.assertIn(("shopify", "scope", "my-store.myshopify.com"), deleted)

    def test_delete_silently_ignores_invalid_shop(self) -> None:
        with patch.object(self.svc.integration_secrets_store, "delete_secret") as mock_delete:
            self.svc.delete_shopify_token("evil.com")
            mock_delete.assert_not_called()


class WebhookEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _reload_shopify_modules()
        # Import after env reload so module-level config is fresh
        from app.api.integrations import shopify as shopify_api

        importlib.reload(shopify_api)
        self.shopify_api = shopify_api

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()
        from app.api.integrations import shopify as shopify_api

        importlib.reload(shopify_api)

    def _build_request(self, body: dict[str, Any], *, shop: str = "my-store.myshopify.com", topic: str = "app/uninstalled", secret: str | None = None, override_signature: str | None = None) -> _FakeRequest:
        raw = json.dumps(body).encode("utf-8")
        sig_secret = secret if secret is not None else "voxel-client-secret"
        signature = override_signature if override_signature is not None else _shopify_hmac(raw, sig_secret)
        return _FakeRequest(
            body=raw,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Shopify-Topic": topic,
                "X-Shopify-Shop-Domain": shop,
            },
        )

    def _run(self, request: _FakeRequest):
        return asyncio.get_event_loop().run_until_complete(
            self.shopify_api.shopify_webhook_app_uninstalled(request)  # type: ignore[arg-type]
        )

    def test_valid_hmac_marks_sources_disconnected_and_clears_token(self) -> None:
        marked: list[tuple[str, str]] = []
        deleted_tokens: list[str] = []

        def _fake_mark(shop_domain: str, *, reason: str) -> int:
            marked.append((shop_domain, reason))
            return 2

        def _fake_delete(shop_domain: str) -> None:
            deleted_tokens.append(shop_domain)

        with patch.object(self.shopify_api._source_repo, "mark_disconnected_by_shop_domain", side_effect=_fake_mark), patch.object(
            self.shopify_api.shopify_oauth_service, "delete_shopify_token", side_effect=_fake_delete
        ):
            request = self._build_request({"id": 1, "myshopify_domain": "my-store.myshopify.com"})
            result = self._run(request)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["shop"], "my-store.myshopify.com")
        self.assertEqual(result["sources_disconnected"], "2")
        self.assertEqual(marked, [("my-store.myshopify.com", "App uninstalled by merchant")])
        self.assertEqual(deleted_tokens, ["my-store.myshopify.com"])

    def test_invalid_hmac_returns_401_and_skips_cleanup(self) -> None:
        with patch.object(self.shopify_api._source_repo, "mark_disconnected_by_shop_domain") as mock_mark, patch.object(
            self.shopify_api.shopify_oauth_service, "delete_shopify_token"
        ) as mock_delete:
            request = self._build_request(
                {"id": 1},
                override_signature="not-a-valid-base64-signature",
            )
            with self.assertRaises(self.shopify_api.HTTPException) as ctx:
                self._run(request)
        self.assertEqual(ctx.exception.status_code, 401)
        mock_mark.assert_not_called()
        mock_delete.assert_not_called()

    def test_missing_secret_returns_503(self) -> None:
        os.environ["SHOPIFY_APP_CLIENT_SECRET"] = ""
        _reload_shopify_modules()
        from app.api.integrations import shopify as shopify_api_reloaded

        importlib.reload(shopify_api_reloaded)
        try:
            request = _FakeRequest(
                body=b'{}',
                headers={"X-Shopify-Hmac-Sha256": "x", "X-Shopify-Topic": "app/uninstalled", "X-Shopify-Shop-Domain": "store.myshopify.com"},
            )
            with self.assertRaises(shopify_api_reloaded.HTTPException) as ctx:
                asyncio.get_event_loop().run_until_complete(
                    shopify_api_reloaded.shopify_webhook_app_uninstalled(request)  # type: ignore[arg-type]
                )
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            _set_env()
            _reload_shopify_modules()
            importlib.reload(shopify_api_reloaded)

    def test_unknown_shop_returns_200_gracefully(self) -> None:
        with patch.object(self.shopify_api._source_repo, "mark_disconnected_by_shop_domain", return_value=0) as mock_mark, patch.object(
            self.shopify_api.shopify_oauth_service, "delete_shopify_token"
        ) as mock_delete:
            request = self._build_request({"id": 99}, shop="ghost-store.myshopify.com")
            result = self._run(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sources_disconnected"], "0")
        mock_mark.assert_called_once()
        mock_delete.assert_called_once()

    def test_idempotent_re_delivery_does_not_raise(self) -> None:
        # Simulate Shopify retry: a second call after the row is already
        # disconnected and the token already gone.
        with patch.object(self.shopify_api._source_repo, "mark_disconnected_by_shop_domain", return_value=0), patch.object(
            self.shopify_api.shopify_oauth_service, "delete_shopify_token"
        ):
            request = self._build_request({"id": 1, "myshopify_domain": "my-store.myshopify.com"})
            first = self._run(request)
            second = self._run(request)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")

    def test_internal_cleanup_failure_still_returns_200(self) -> None:
        def _explode_mark(shop_domain: str, *, reason: str) -> int:
            raise RuntimeError("db down")

        def _explode_delete(shop_domain: str) -> None:
            raise RuntimeError("secrets store down")

        with patch.object(self.shopify_api._source_repo, "mark_disconnected_by_shop_domain", side_effect=_explode_mark), patch.object(
            self.shopify_api.shopify_oauth_service, "delete_shopify_token", side_effect=_explode_delete
        ):
            request = self._build_request({"id": 1, "myshopify_domain": "my-store.myshopify.com"})
            result = self._run(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sources_disconnected"], "0")

    def test_endpoint_does_not_require_authentication_dependency(self) -> None:
        # Sanity check the FastAPI route signature: zero ``Depends(get_current_user)``
        # entries on the webhook route.
        from fastapi import APIRouter

        route = next(
            r for r in self.shopify_api.router.routes if getattr(r, "path", "").endswith("/webhooks/app-uninstalled")
        )
        # The endpoint is the bound function — inspect it for any FastAPI Depends
        # markers (Depends params would surface in the dependant info).
        self.assertIn("POST", route.methods)
        # Use FastAPI's parameter resolution to confirm no Depends(get_current_user)
        from fastapi.dependencies.utils import get_dependant

        dependant = get_dependant(path=route.path, call=route.endpoint)
        for sub in dependant.dependencies:
            call = getattr(sub, "call", None)
            self.assertNotEqual(getattr(call, "__name__", ""), "get_current_user")


class ComplianceWebhookEndpointTests(unittest.TestCase):
    """GDPR compliance webhooks (customers/data_request, customers/redact, shop/redact).

    VOXEL stores no customer PII, so the handler is a no-op acknowledge — but it
    still must verify the HMAC and reject invalid signatures.
    """

    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _reload_shopify_modules()
        from app.api.integrations import shopify as shopify_api

        importlib.reload(shopify_api)
        self.shopify_api = shopify_api

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_shopify_modules()
        from app.api.integrations import shopify as shopify_api

        importlib.reload(shopify_api)

    def _build_request(
        self,
        body: dict[str, Any],
        *,
        topic: str,
        shop: str = "my-store.myshopify.com",
        override_signature: str | None = None,
    ) -> _FakeRequest:
        raw = json.dumps(body).encode("utf-8")
        signature = override_signature if override_signature is not None else _shopify_hmac(raw, "voxel-client-secret")
        return _FakeRequest(
            body=raw,
            headers={
                "X-Shopify-Hmac-Sha256": signature,
                "X-Shopify-Topic": topic,
                "X-Shopify-Shop-Domain": shop,
            },
        )

    def _run(self, request: _FakeRequest):
        return asyncio.get_event_loop().run_until_complete(
            self.shopify_api.shopify_webhook_compliance(request)  # type: ignore[arg-type]
        )

    def test_customers_data_request_returns_200(self) -> None:
        request = self._build_request(
            {"shop_domain": "my-store.myshopify.com", "customer": {"id": 1}},
            topic="customers/data_request",
        )
        result = self._run(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["topic"], "customers/data_request")
        self.assertEqual(result["shop"], "my-store.myshopify.com")

    def test_customers_redact_returns_200(self) -> None:
        request = self._build_request(
            {"shop_domain": "my-store.myshopify.com", "customer": {"id": 1}},
            topic="customers/redact",
        )
        result = self._run(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["topic"], "customers/redact")

    def test_shop_redact_returns_200(self) -> None:
        request = self._build_request(
            {"shop_domain": "my-store.myshopify.com", "shop_id": 1},
            topic="shop/redact",
        )
        result = self._run(request)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["topic"], "shop/redact")

    def test_invalid_hmac_returns_401(self) -> None:
        request = self._build_request(
            {"shop_domain": "my-store.myshopify.com"},
            topic="customers/data_request",
            override_signature="not-a-valid-signature",
        )
        with self.assertRaises(self.shopify_api.HTTPException) as ctx:
            self._run(request)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_secret_returns_503(self) -> None:
        os.environ["SHOPIFY_APP_CLIENT_SECRET"] = ""
        _reload_shopify_modules()
        from app.api.integrations import shopify as shopify_api_reloaded

        importlib.reload(shopify_api_reloaded)
        try:
            request = _FakeRequest(
                body=b'{}',
                headers={
                    "X-Shopify-Hmac-Sha256": "x",
                    "X-Shopify-Topic": "customers/redact",
                    "X-Shopify-Shop-Domain": "store.myshopify.com",
                },
            )
            with self.assertRaises(shopify_api_reloaded.HTTPException) as ctx:
                asyncio.get_event_loop().run_until_complete(
                    shopify_api_reloaded.shopify_webhook_compliance(request)  # type: ignore[arg-type]
                )
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            _set_env()
            _reload_shopify_modules()
            importlib.reload(shopify_api_reloaded)

    def test_unknown_topic_still_returns_200(self) -> None:
        # Shopify only sends one of the three GDPR topics here, but if anything
        # else slips through with a valid HMAC we still ack with 200 (and log).
        request = self._build_request(
            {"shop_domain": "my-store.myshopify.com"},
            topic="customers/unknown_topic",
        )
        result = self._run(request)
        self.assertEqual(result["status"], "ok")

    def test_endpoint_does_not_require_authentication_dependency(self) -> None:
        from fastapi.dependencies.utils import get_dependant

        route = next(
            r for r in self.shopify_api.router.routes if getattr(r, "path", "").endswith("/webhooks/compliance")
        )
        self.assertIn("POST", route.methods)
        dependant = get_dependant(path=route.path, call=route.endpoint)
        for sub in dependant.dependencies:
            call = getattr(sub, "call", None)
            self.assertNotEqual(getattr(call, "__name__", ""), "get_current_user")


if __name__ == "__main__":
    unittest.main()
