import os
import unittest

from app.api import meta_ads as meta_ads_api
from app.services.auth import AuthUser
from app.services.meta_ads import MetaAdsIntegrationError, MetaAdsService


class MetaAdsImportAccountsTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_service_list_accessible_accounts_paginates_and_normalizes(self):
        service = MetaAdsService()
        service._active_access_token = lambda: "token-1"  # type: ignore[method-assign]

        responses = [
            {
                "data": [
                    {"id": "act_123", "account_id": "123", "name": "Account A", "account_status": 1, "currency": "usd", "timezone_name": "Europe/Bucharest"},
                    {"id": "456", "name": "Account B", "account_status": 2, "currency": "eur"},
                ],
                "paging": {"cursors": {"after": "cursor-2"}},
            },
            {
                "data": [
                    {"id": "act_789", "name": "Account C", "account_status": 1, "currency": "usd", "timezone_name": "UTC"},
                ],
                "paging": {"cursors": {}},
            },
        ]

        call_count = {"value": 0}

        def _fake_http_json(*, method: str, url: str, headers: dict[str, str] | None = None):
            self.assertEqual(method, "GET")
            self.assertIn("/me/adaccounts", url)
            self.assertEqual(headers, {"Authorization": "Bearer token-1"})
            idx = call_count["value"]
            call_count["value"] += 1
            return responses[idx]

        service._http_json = _fake_http_json  # type: ignore[method-assign]

        items = service.list_accessible_ad_accounts()

        self.assertEqual(call_count["value"], 2)
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["id"], "act_123")
        self.assertEqual(items[1]["id"], "act_456")
        self.assertEqual(items[2]["id"], "act_789")
        self.assertEqual(items[0]["currency_code"], "USD")

    def test_service_list_accessible_accounts_falls_back_to_env_token(self):
        os.environ["META_ACCESS_TOKEN"] = "env-token"

        service = MetaAdsService()

        def _no_db_secret(*, provider: str, secret_key: str, scope: str = "agency_default"):
            return None

        import app.services.meta_ads as meta_ads_service_module

        original_get_secret = meta_ads_service_module.integration_secrets_store.get_secret
        original_http = service._http_json
        try:
            meta_ads_service_module.integration_secrets_store.get_secret = _no_db_secret
            service._http_json = lambda **kwargs: {"data": [], "paging": {"cursors": {}}}  # type: ignore[method-assign]
            items = service.list_accessible_ad_accounts()
        finally:
            meta_ads_service_module.integration_secrets_store.get_secret = original_get_secret
            service._http_json = original_http

        self.assertEqual(items, [])

    def test_import_accounts_endpoint_happy_path_and_idempotent_rerun(self):
        user = AuthUser(email="owner@example.com", role="admin")

        discovered = [
            {"id": "act_101", "name": "Meta A", "account_status": "1", "currency_code": "USD", "account_timezone": "UTC"},
            {"id": "act_202", "name": "Meta B Updated", "account_status": "2", "currency_code": "EUR", "account_timezone": "Europe/Bucharest"},
            {"id": "act_303", "name": "Meta C", "account_status": "1", "currency_code": "USD", "account_timezone": None},
        ]

        existing_initial = [
            {"account_id": "act_202", "name": "Meta B Old", "status": "1", "currency": "EUR", "timezone": "Europe/Bucharest"},
            {"account_id": "act_303", "name": "Meta C", "status": "1", "currency": "USD", "timezone": None},
        ]
        existing_second = [
            {"account_id": "act_101", "name": "Meta A", "status": "1", "currency": "USD", "timezone": "UTC"},
            {"account_id": "act_202", "name": "Meta B Updated", "status": "2", "currency": "EUR", "timezone": "Europe/Bucharest"},
            {"account_id": "act_303", "name": "Meta C", "status": "1", "currency": "USD", "timezone": None},
        ]

        list_calls = {"count": 0}
        updates: list[dict[str, object]] = []

        def _list_platform_accounts(*, platform: str):
            list_calls["count"] += 1
            return existing_initial if list_calls["count"] == 1 else existing_second

        original_enforce = meta_ads_api.enforce_action_scope
        original_discover = meta_ads_api.meta_ads_service.list_accessible_ad_accounts
        original_status = meta_ads_api.meta_ads_service.integration_status
        original_list = meta_ads_api.client_registry_service.list_platform_accounts
        original_upsert = meta_ads_api.client_registry_service.upsert_platform_accounts
        original_update = meta_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = lambda: discovered
            meta_ads_api.meta_ads_service.integration_status = lambda: {"token_source": "database"}
            meta_ads_api.client_registry_service.list_platform_accounts = _list_platform_accounts
            meta_ads_api.client_registry_service.upsert_platform_accounts = lambda **kwargs: None
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: updates.append(kwargs) or kwargs

            first = meta_ads_api.import_meta_accounts(user=user)
            second = meta_ads_api.import_meta_accounts(user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = original_discover
            meta_ads_api.meta_ads_service.integration_status = original_status
            meta_ads_api.client_registry_service.list_platform_accounts = original_list
            meta_ads_api.client_registry_service.upsert_platform_accounts = original_upsert
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = original_update

        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["platform"], "meta_ads")
        self.assertEqual(first["accounts_discovered"], 3)
        self.assertEqual(first["imported"], 1)
        self.assertEqual(first["updated"], 1)
        self.assertEqual(first["unchanged"], 1)

        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 3)

        self.assertEqual(len(updates), 2)
        self.assertEqual({item["account_id"] for item in updates}, {"act_101", "act_202"})

    def test_import_accounts_endpoint_returns_clear_error_when_no_token(self):
        user = AuthUser(email="owner@example.com", role="admin")

        original_enforce = meta_ads_api.enforce_action_scope
        original_discover = meta_ads_api.meta_ads_service.list_accessible_ad_accounts
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None

            def _raise_no_token():
                raise MetaAdsIntegrationError("Meta Ads token is missing or placeholder.")

            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = _raise_no_token

            with self.assertRaises(meta_ads_api.HTTPException) as ctx:
                meta_ads_api.import_meta_accounts(user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = original_discover

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("token is missing", str(ctx.exception.detail).lower())

    def test_import_accounts_endpoint_maps_meta_api_error(self):
        user = AuthUser(email="owner@example.com", role="admin")

        original_enforce = meta_ads_api.enforce_action_scope
        original_discover = meta_ads_api.meta_ads_service.list_accessible_ad_accounts
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None

            def _raise_api_error():
                raise MetaAdsIntegrationError("Meta API request failed: status=401")

            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = _raise_api_error

            with self.assertRaises(meta_ads_api.HTTPException) as ctx:
                meta_ads_api.import_meta_accounts(user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.meta_ads_service.list_accessible_ad_accounts = original_discover

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Meta API request failed", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
