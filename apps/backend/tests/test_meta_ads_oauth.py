import os
import unittest
from datetime import datetime, timezone

from app.api import meta_ads as meta_ads_api
from app.services.auth import AuthUser
from app.services.integration_secrets_store import IntegrationSecretValue
from app.services.meta_ads import MetaAdsIntegrationError, MetaAdsService


class MetaAdsOauthTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def _configure_base_env(self):
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["META_APP_ID"] = "meta-app-id"
        os.environ["META_APP_SECRET"] = "meta-app-secret"
        os.environ["META_REDIRECT_URI"] = "https://example.com/meta/callback"
        os.environ["META_API_VERSION"] = "v20.0"

    def test_connect_start_happy_path(self):
        self._configure_base_env()
        service = MetaAdsService()
        payload = service.build_oauth_authorize_url()

        self.assertIn("authorize_url", payload)
        self.assertIn("state", payload)
        self.assertIn("facebook.com", payload["authorize_url"])
        self.assertIn("dialog/oauth", payload["authorize_url"])

    def test_oauth_exchange_happy_path_with_http_mock(self):
        self._configure_base_env()
        service = MetaAdsService()
        service._oauth_state_cache.add("valid-state")

        calls = []

        def _fake_http_json(*, method: str, url: str):
            calls.append((method, url))
            if "code=" in url:
                return {"access_token": "short-lived-token"}
            return {"access_token": "long-lived-token", "expires_in": 3600}

        stored: dict[str, str] = {}

        def _fake_upsert_secret(*, provider: str, secret_key: str, value: str, scope: str = "agency_default"):
            self.assertEqual(provider, "meta_ads")
            self.assertEqual(scope, "agency_default")
            stored[secret_key] = value

        def _fake_get_secret(*, provider: str, secret_key: str, scope: str = "agency_default"):
            self.assertEqual(provider, "meta_ads")
            self.assertEqual(scope, "agency_default")
            value = stored.get(secret_key)
            if value is None:
                return None
            return IntegrationSecretValue(
                provider="meta_ads",
                secret_key=secret_key,
                scope="agency_default",
                value=value,
                updated_at=datetime(2026, 3, 7, tzinfo=timezone.utc),
            )

        original_http_json = service._http_json
        original_service_upsert = None
        original_service_get = None
        try:
            service._http_json = _fake_http_json
            # patch global store used in both modules
            import app.services.meta_ads as meta_ads_service_module

            original_service_upsert = meta_ads_service_module.integration_secrets_store.upsert_secret
            original_service_get = meta_ads_service_module.integration_secrets_store.get_secret
            meta_ads_service_module.integration_secrets_store.upsert_secret = _fake_upsert_secret
            meta_ads_service_module.integration_secrets_store.get_secret = _fake_get_secret

            payload = service.exchange_oauth_code(code="oauth-code", state="valid-state")
        finally:
            service._http_json = original_http_json
            if original_service_upsert is not None and original_service_get is not None:
                meta_ads_service_module.integration_secrets_store.upsert_secret = original_service_upsert
                meta_ads_service_module.integration_secrets_store.get_secret = original_service_get

        self.assertEqual(len(calls), 2)
        self.assertEqual(stored["access_token"], "long-lived-token")
        self.assertIn("access_token_expires_at", stored)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["token_source"], "database")
        self.assertEqual(payload["oauth_configured"], True)

    def test_oauth_exchange_invalid_state(self):
        self._configure_base_env()
        service = MetaAdsService()
        with self.assertRaisesRegex(MetaAdsIntegrationError, "Invalid OAuth state"):
            service.exchange_oauth_code(code="oauth-code", state="bad-state")


    def test_api_connect_start_happy_path(self):
        user = AuthUser(email="owner@example.com", role="admin")
        original_enforce = meta_ads_api.enforce_action_scope
        original_build = meta_ads_api.meta_ads_service.build_oauth_authorize_url
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            meta_ads_api.meta_ads_service.build_oauth_authorize_url = lambda: {"authorize_url": "https://facebook.com/dialog/oauth?...", "state": "state-1"}
            payload = meta_ads_api.connect_meta_ads(user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.meta_ads_service.build_oauth_authorize_url = original_build

        self.assertEqual(payload["state"], "state-1")
        self.assertIn("authorize_url", payload)

    def test_api_exchange_missing_code_or_state_returns_400(self):
        user = AuthUser(email="owner@example.com", role="admin")
        original_enforce = meta_ads_api.enforce_action_scope
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            with self.assertRaises(meta_ads_api.HTTPException) as ctx_missing_code:
                meta_ads_api.meta_ads_oauth_exchange(payload={"state": "abc"}, user=user)
            self.assertEqual(ctx_missing_code.exception.status_code, 400)
            self.assertIn("Missing code/state", str(ctx_missing_code.exception.detail))

            with self.assertRaises(meta_ads_api.HTTPException) as ctx_missing_state:
                meta_ads_api.meta_ads_oauth_exchange(payload={"code": "abc"}, user=user)
            self.assertEqual(ctx_missing_state.exception.status_code, 400)
            self.assertIn("Missing code/state", str(ctx_missing_state.exception.detail))
        finally:
            meta_ads_api.enforce_action_scope = original_enforce


    def test_api_exchange_invalid_state_returns_400(self):
        user = AuthUser(email="owner@example.com", role="admin")
        original_enforce = meta_ads_api.enforce_action_scope
        original_exchange = meta_ads_api.meta_ads_service.exchange_oauth_code
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None

            def _raise_invalid_state(*, code: str, state: str):
                raise MetaAdsIntegrationError("Invalid OAuth state for Meta connect callback")

            meta_ads_api.meta_ads_service.exchange_oauth_code = _raise_invalid_state
            with self.assertRaises(meta_ads_api.HTTPException) as ctx:
                meta_ads_api.meta_ads_oauth_exchange(payload={"code": "abc", "state": "bad"}, user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.meta_ads_service.exchange_oauth_code = original_exchange

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid OAuth state", str(ctx.exception.detail))

    def test_status_uses_db_token_when_present(self):
        self._configure_base_env()
        os.environ["META_ACCESS_TOKEN"] = "env-fallback-token"

        now = datetime(2026, 3, 7, tzinfo=timezone.utc)

        def _fake_get_secret(*, provider: str, secret_key: str, scope: str = "agency_default"):
            if provider != "meta_ads":
                return None
            if secret_key == "access_token":
                return IntegrationSecretValue(provider="meta_ads", secret_key="access_token", scope=scope, value="db-token", updated_at=now)
            if secret_key == "access_token_expires_at":
                return IntegrationSecretValue(provider="meta_ads", secret_key="access_token_expires_at", scope=scope, value="2026-04-01T00:00:00+00:00", updated_at=now)
            return None

        try:
            import app.services.meta_ads as meta_ads_service_module

            original_service_get = meta_ads_service_module.integration_secrets_store.get_secret
            meta_ads_service_module.integration_secrets_store.get_secret = _fake_get_secret

            status = MetaAdsService().integration_status()
        finally:
            meta_ads_service_module.integration_secrets_store.get_secret = original_service_get

        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["token_source"], "database")
        self.assertEqual(status["token_updated_at"], now.isoformat())
        self.assertEqual(status["token_expires_at"], "2026-04-01T00:00:00+00:00")

    def test_status_falls_back_to_env_token(self):
        self._configure_base_env()
        os.environ["META_ACCESS_TOKEN"] = "env-fallback-token"

        def _fake_get_secret(*, provider: str, secret_key: str, scope: str = "agency_default"):
            return None

        try:
            import app.services.meta_ads as meta_ads_service_module

            original_service_get = meta_ads_service_module.integration_secrets_store.get_secret
            meta_ads_service_module.integration_secrets_store.get_secret = _fake_get_secret

            status = MetaAdsService().integration_status()
        finally:
            meta_ads_service_module.integration_secrets_store.get_secret = original_service_get

        self.assertEqual(status["status"], "connected")
        self.assertEqual(status["token_source"], "env_fallback")
        self.assertIsNone(status["token_updated_at"])


if __name__ == "__main__":
    unittest.main()
