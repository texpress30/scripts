import os
import unittest

from app.api import tiktok_ads as tiktok_ads_api
from app.services.auth import AuthUser
from app.services.tiktok_ads import TikTokAdsIntegrationError, TikTokAdsService


class TikTokAdsImportAccountsTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["TIKTOK_APP_ID"] = "tt-app-id"
        os.environ["TIKTOK_APP_SECRET"] = "tt-app-secret"
        os.environ["TIKTOK_REDIRECT_URI"] = "https://app.example.com/agency/integrations/tiktok/callback"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_service_list_accessible_advertiser_accounts_paginates_and_normalizes(self):
        service = TikTokAdsService()

        calls: list[tuple[str, str, dict[str, str] | None]] = []
        responses = [
            {
                "code": 0,
                "message": "OK",
                "data": {
                    "list": [
                        {
                            "advertiser_id": "1001",
                            "advertiser_name": "Advertiser One",
                            "status": "STATUS_ENABLE",
                            "currency": "usd",
                            "timezone": "UTC",
                        },
                    ],
                    "page_info": {"page": 1, "total_page": 2},
                },
            },
            {
                "code": 0,
                "message": "OK",
                "data": {
                    "list": [
                        {
                            "advertiser_id": 1002,
                            "name": "Advertiser Two",
                            "advertiser_status": "STATUS_DISABLE",
                            "currency_code": "eur",
                            "account_timezone": "Europe/Bucharest",
                        },
                    ],
                    "page_info": {"page": 2, "total_page": 2},
                },
            },
        ]

        def _fake_http_json(*, method: str, url: str, payload=None, headers: dict[str, str] | None = None):
            calls.append((method, url, headers))
            return responses[len(calls) - 1]

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            rows = service.list_accessible_advertiser_accounts(access_token="tok")
        finally:
            service._http_json = original_http

        self.assertEqual(len(calls), 2)
        self.assertIn("oauth2/advertiser/get/", calls[0][1])
        self.assertEqual(calls[0][2], {"Access-Token": "tok"})
        self.assertEqual(rows[0]["account_id"], "1001")
        self.assertEqual(rows[0]["account_name"], "Advertiser One")
        self.assertEqual(rows[0]["currency_code"], "USD")
        self.assertEqual(rows[1]["account_id"], "1002")
        self.assertEqual(rows[1]["status"], "STATUS_DISABLE")

    def test_service_list_accessible_advertiser_accounts_supports_alternate_rows_container(self):
        service = TikTokAdsService()

        original_http = service._http_json
        try:
            service._http_json = lambda **kwargs: {
                "code": 0,
                "message": "OK",
                "data": {
                    "rows": [
                        {
                            "advertiser_id": "2201",
                            "advertiser_name": "Alt Container Advertiser",
                            "status": "STATUS_ENABLE",
                        }
                    ],
                    "page_info": {"page": 1, "total_page": 1},
                },
            }
            rows = service.list_accessible_advertiser_accounts(access_token="tok")
        finally:
            service._http_json = original_http

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account_id"], "2201")

    def test_import_accounts_zero_advertisers_returns_diagnostics_message(self):
        service = TikTokAdsService()

        original_access = service._access_token_with_source
        original_discover = service._discover_accessible_advertiser_accounts
        original_list = tiktok_ads_api.client_registry_service.list_platform_accounts
        original_upsert = tiktok_ads_api.client_registry_service.upsert_platform_accounts
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._discover_accessible_advertiser_accounts = lambda **kwargs: ([], {
                "last_api_code": 0,
                "last_api_message": "OK",
                "page_count_checked": 1,
                "row_container_used": "data.list",
            })
            tiktok_ads_api.client_registry_service.list_platform_accounts = lambda **kwargs: []
            tiktok_ads_api.client_registry_service.upsert_platform_accounts = lambda **kwargs: None

            payload = service.import_accounts()
        finally:
            service._access_token_with_source = original_access
            service._discover_accessible_advertiser_accounts = original_discover
            tiktok_ads_api.client_registry_service.list_platform_accounts = original_list
            tiktok_ads_api.client_registry_service.upsert_platform_accounts = original_upsert

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["accounts_discovered"], 0)
        self.assertIn("returned zero accounts", str(payload["message"]))
        self.assertEqual(payload["api_code"], 0)
        self.assertEqual(payload["api_message"], "OK")
        self.assertEqual(payload["page_count_checked"], 1)
        self.assertEqual(payload["row_container_used"], "data.list")

    def test_import_accounts_happy_path_and_idempotent_rerun(self):
        service = TikTokAdsService()
        discovered = [
            {
                "account_id": "1001",
                "account_name": "TikTok A",
                "status": "STATUS_ENABLE",
                "currency_code": "USD",
                "account_timezone": "UTC",
            },
            {
                "account_id": "1002",
                "account_name": "TikTok B Updated",
                "status": "STATUS_ENABLE",
                "currency_code": "EUR",
                "account_timezone": "Europe/Bucharest",
            },
            {
                "account_id": "1003",
                "account_name": "TikTok C",
                "status": "STATUS_DISABLE",
                "currency_code": "USD",
                "account_timezone": None,
            },
        ]
        existing_first = [
            {"id": "1002", "name": "TikTok B Old", "status": "STATUS_ENABLE", "currency": "EUR", "timezone": "Europe/Bucharest"},
            {"id": "1003", "name": "TikTok C", "status": "STATUS_DISABLE", "currency": "USD", "timezone": None},
        ]
        existing_second = [
            {"id": "1001", "name": "TikTok A", "status": "STATUS_ENABLE", "currency": "USD", "timezone": "UTC"},
            {"id": "1002", "name": "TikTok B Updated", "status": "STATUS_ENABLE", "currency": "EUR", "timezone": "Europe/Bucharest"},
            {"id": "1003", "name": "TikTok C", "status": "STATUS_DISABLE", "currency": "USD", "timezone": None},
        ]

        original_access = service._access_token_with_source
        original_discover = service._discover_accessible_advertiser_accounts
        original_list = tiktok_ads_api.client_registry_service.list_platform_accounts
        original_upsert = tiktok_ads_api.client_registry_service.upsert_platform_accounts
        original_update = tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata

        list_calls = {"count": 0}
        updates: list[dict[str, object]] = []

        def _list_platform_accounts(*, platform: str):
            list_calls["count"] += 1
            return existing_first if list_calls["count"] == 1 else existing_second

        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._discover_accessible_advertiser_accounts = lambda **kwargs: (discovered, {"page_count_checked": 1, "row_container_used": "data.list", "last_api_code": 0, "last_api_message": "OK"})
            tiktok_ads_api.client_registry_service.list_platform_accounts = _list_platform_accounts
            tiktok_ads_api.client_registry_service.upsert_platform_accounts = lambda **kwargs: None
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: updates.append(kwargs) or kwargs

            first = service.import_accounts()
            second = service.import_accounts()
        finally:
            service._access_token_with_source = original_access
            service._discover_accessible_advertiser_accounts = original_discover
            tiktok_ads_api.client_registry_service.list_platform_accounts = original_list
            tiktok_ads_api.client_registry_service.upsert_platform_accounts = original_upsert
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = original_update

        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["platform"], "tiktok_ads")
        self.assertEqual(first["accounts_discovered"], 3)
        self.assertEqual(first["imported"], 1)
        self.assertEqual(first["updated"], 1)
        self.assertEqual(first["unchanged"], 1)

        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["updated"], 0)
        self.assertEqual(second["unchanged"], 3)
        self.assertEqual(len(updates), 2)
        self.assertEqual({item["account_id"] for item in updates}, {"1001", "1002"})

    def test_import_accounts_requires_token(self):
        service = TikTokAdsService()
        original_access = service._access_token_with_source
        try:
            service._access_token_with_source = lambda: ("", "missing", None)
            with self.assertRaises(TikTokAdsIntegrationError):
                service.import_accounts()
        finally:
            service._access_token_with_source = original_access

    def test_service_maps_tiktok_api_error(self):
        service = TikTokAdsService()
        original_http = service._http_json
        try:
            service._http_json = lambda **kwargs: {"code": 40100, "message": "invalid access token"}
            with self.assertRaises(TikTokAdsIntegrationError) as ctx:
                service.list_accessible_advertiser_accounts(access_token="tok")
        finally:
            service._http_json = original_http

        self.assertIn("TikTok advertiser discovery failed", str(ctx.exception))

    def test_import_accounts_endpoint_contract_summary(self):
        user = AuthUser(email="owner@example.com", role="admin")

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_import = tiktok_ads_api.tiktok_ads_service.import_accounts
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None
            tiktok_ads_api.tiktok_ads_service.import_accounts = lambda: {
                "status": "ok",
                "message": "done",
                "platform": "tiktok_ads",
                "token_source": "database",
                "accounts_discovered": 2,
                "imported": 1,
                "updated": 1,
                "unchanged": 0,
            }
            payload = tiktok_ads_api.import_tiktok_accounts(user=user)
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.tiktok_ads_service.import_accounts = original_import

        self.assertEqual(payload["platform"], "tiktok_ads")
        self.assertEqual(payload["accounts_discovered"], 2)
        self.assertEqual(payload["imported"], 1)

    def test_import_accounts_endpoint_maps_tiktok_error(self):
        user = AuthUser(email="owner@example.com", role="admin")

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_import = tiktok_ads_api.tiktok_ads_service.import_accounts
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None

            def _raise_error():
                raise TikTokAdsIntegrationError("TikTok advertiser discovery failed: code=40100")

            tiktok_ads_api.tiktok_ads_service.import_accounts = _raise_error
            with self.assertRaises(tiktok_ads_api.HTTPException) as ctx:
                tiktok_ads_api.import_tiktok_accounts(user=user)
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.tiktok_ads_service.import_accounts = original_import

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("discovery failed", str(ctx.exception.detail).lower())


if __name__ == "__main__":
    unittest.main()
