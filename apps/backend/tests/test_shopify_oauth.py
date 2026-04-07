import importlib
import os
import unittest
from datetime import datetime, timezone

from app.services.integration_secrets_store import IntegrationSecretValue


def _reload_shopify_modules():
    """Reload config + service so module-level env reads pick up new values."""
    import app.integrations.shopify.config as cfg

    importlib.reload(cfg)
    import app.integrations.shopify.service as svc

    importlib.reload(svc)
    return cfg, svc


class ShopifyConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
        _reload_shopify_modules()

    def test_validate_shop_domain_normalizes_case(self):
        _, svc = _reload_shopify_modules()
        from app.integrations.shopify.config import validate_shop_domain

        self.assertEqual(validate_shop_domain("My-Store.myshopify.com"), "my-store.myshopify.com")

    def test_validate_shop_domain_rejects_non_myshopify(self):
        from app.integrations.shopify.config import validate_shop_domain

        with self.assertRaises(ValueError):
            validate_shop_domain("evil.com")

    def test_validate_shop_domain_rejects_path(self):
        from app.integrations.shopify.config import validate_shop_domain

        with self.assertRaises(ValueError):
            validate_shop_domain("store.myshopify.com/admin")

    def test_oauth_configured_false_when_missing(self):
        os.environ.pop("SHOPIFY_APP_CLIENT_ID", None)
        os.environ.pop("SHOPIFY_APP_CLIENT_SECRET", None)
        cfg, _ = _reload_shopify_modules()
        self.assertFalse(cfg.oauth_configured())

    def test_oauth_configured_true_when_set(self):
        os.environ["SHOPIFY_APP_CLIENT_ID"] = "id"
        os.environ["SHOPIFY_APP_CLIENT_SECRET"] = "secret"
        cfg, _ = _reload_shopify_modules()
        self.assertTrue(cfg.oauth_configured())


class ShopifyOAuthServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["SHOPIFY_APP_CLIENT_ID"] = "voxel-client-id"
        os.environ["SHOPIFY_APP_CLIENT_SECRET"] = "voxel-client-secret"
        os.environ["SHOPIFY_REDIRECT_URI"] = "https://example.com/agency/integrations/shopify/callback"
        os.environ["SHOPIFY_API_VERSION"] = "2026-04"
        os.environ["SHOPIFY_SCOPES"] = "read_products,read_inventory"
        self.cfg, self.svc = _reload_shopify_modules()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)
        _reload_shopify_modules()

    def test_generate_connect_url_builds_full_authorize_url(self):
        payload = self.svc.generate_connect_url(shop="My-Store.myshopify.com")
        url = payload["authorize_url"]
        self.assertIn("https://my-store.myshopify.com/admin/oauth/authorize", url)
        self.assertIn("client_id=voxel-client-id", url)
        self.assertIn("scope=read_products", url)
        self.assertIn("redirect_uri=", url)
        self.assertIn(f"state={payload['state']}", url)

    def test_generate_connect_url_rejects_invalid_shop(self):
        with self.assertRaises(ValueError):
            self.svc.generate_connect_url(shop="evil.com")

    def test_exchange_code_for_token_happy_path(self):
        captured: dict = {}

        def _fake_post(url, body):
            captured["url"] = url
            captured["body"] = body
            return {"access_token": "shpua_TESTTOKEN", "scope": "read_products,read_inventory"}

        original = self.svc._http_post_json
        try:
            self.svc._http_post_json = _fake_post
            result = self.svc.exchange_code_for_token(code="abc123", shop="test-store.myshopify.com")
        finally:
            self.svc._http_post_json = original

        self.assertEqual(result["access_token"], "shpua_TESTTOKEN")
        self.assertEqual(result["shop"], "test-store.myshopify.com")
        self.assertEqual(result["scope"], "read_products,read_inventory")
        self.assertEqual(captured["url"], "https://test-store.myshopify.com/admin/oauth/access_token")
        self.assertEqual(captured["body"]["client_id"], "voxel-client-id")
        self.assertEqual(captured["body"]["code"], "abc123")

    def test_store_and_get_token_uses_secrets_store(self):
        stored: dict[tuple[str, str, str], str] = {}

        def _fake_upsert(*, provider: str, secret_key: str, value: str, scope: str = "agency_default"):
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
                updated_at=datetime(2026, 4, 7, tzinfo=timezone.utc),
            )

        original_upsert = self.svc.integration_secrets_store.upsert_secret
        original_get = self.svc.integration_secrets_store.get_secret
        try:
            self.svc.integration_secrets_store.upsert_secret = _fake_upsert
            self.svc.integration_secrets_store.get_secret = _fake_get

            self.svc.store_shopify_token(
                shop="store.myshopify.com",
                access_token="shpua_PERSIST",
                scope="read_products",
            )
            token = self.svc.get_access_token_for_shop("store.myshopify.com")
        finally:
            self.svc.integration_secrets_store.upsert_secret = original_upsert
            self.svc.integration_secrets_store.get_secret = original_get

        self.assertEqual(token, "shpua_PERSIST")
        self.assertEqual(stored[("shopify", "access_token", "store.myshopify.com")], "shpua_PERSIST")
        self.assertEqual(stored[("shopify", "scope", "store.myshopify.com")], "read_products")

    def test_status_when_configured_with_no_shops(self):
        def _fake_list():
            return []

        original = self.svc._list_connected_shops
        try:
            self.svc._list_connected_shops = _fake_list
            payload = self.svc.get_shopify_status()
        finally:
            self.svc._list_connected_shops = original

        self.assertTrue(payload["oauth_configured"])
        self.assertEqual(payload["connected_shops"], [])
        self.assertEqual(payload["token_count"], 0)

    def test_status_when_not_configured(self):
        os.environ.pop("SHOPIFY_APP_CLIENT_ID", None)
        os.environ.pop("SHOPIFY_APP_CLIENT_SECRET", None)
        _, svc = _reload_shopify_modules()
        payload = svc.get_shopify_status()
        self.assertFalse(payload["oauth_configured"])
        self.assertEqual(payload["token_count"], 0)


if __name__ == "__main__":
    unittest.main()
