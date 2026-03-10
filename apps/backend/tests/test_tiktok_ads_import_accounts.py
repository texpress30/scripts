import json
from datetime import date
import os
import unittest
from urllib import parse as urlparse

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

    def test_probe_uses_discovery_helper_and_succeeds_when_advertiser_present(self):
        service = TikTokAdsService()

        calls: list[str] = []
        original_discover = service._discover_accessible_advertiser_accounts
        try:
            def _fake_discover(*, access_token: str | None = None):
                calls.append(str(access_token))
                return ([{"account_id": "101"}, {"account_id": "202"}], {"page_count_checked": 1})

            service._discover_accessible_advertiser_accounts = _fake_discover
            result = service._probe_selected_advertiser_access(account_id="202", access_token="tok", token_source="database")
        finally:
            service._discover_accessible_advertiser_accounts = original_discover

        self.assertEqual(calls, ["tok"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["advertiser_id"], "202")
        self.assertIn("/oauth2/advertiser/get/", str(result["endpoint"]))

    def test_probe_returns_provider_access_denied_when_advertiser_missing_from_discovery(self):
        service = TikTokAdsService()

        original_discover = service._discover_accessible_advertiser_accounts
        try:
            service._discover_accessible_advertiser_accounts = lambda **kwargs: ([{"account_id": "101"}], {"page_count_checked": 1})
            with self.assertRaises(TikTokAdsIntegrationError) as ctx:
                service._probe_selected_advertiser_access(account_id="999", access_token="tt-sensitive-token-123", token_source="database")
        finally:
            service._discover_accessible_advertiser_accounts = original_discover

        self.assertEqual(ctx.exception.error_category, "provider_access_denied")
        self.assertEqual(ctx.exception.advertiser_id, "999")
        self.assertNotIn("tt-sensitive-token-123", str(ctx.exception.to_details()))

    def test_import_discovery_and_probe_share_endpoint_shape(self):
        service = TikTokAdsService()

        calls: list[tuple[str, str]] = []
        responses = [
            {
                "code": 0,
                "message": "OK",
                "data": {
                    "list": [{"advertiser_id": "301", "advertiser_name": "A"}],
                    "page_info": {"page": 1, "total_page": 1},
                },
            },
            {
                "code": 0,
                "message": "OK",
                "data": {
                    "list": [{"advertiser_id": "301", "advertiser_name": "A"}],
                    "page_info": {"page": 1, "total_page": 1},
                },
            },
        ]

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            calls.append((method, url))
            return responses[len(calls) - 1]

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            discovered = service.list_accessible_advertiser_accounts(access_token="tok")
            probe = service._probe_selected_advertiser_access(account_id="301", access_token="tok", token_source="database")
        finally:
            service._http_json = original_http

        self.assertEqual(len(discovered), 1)
        self.assertEqual(probe["status"], "ok")
        self.assertEqual(calls[0][0], "GET")
        self.assertEqual(calls[1][0], "GET")
        self.assertIn("oauth2/advertiser/get/", calls[0][1])
        self.assertIn("oauth2/advertiser/get/", calls[1][1])

    def test_report_integrated_get_uses_get_with_query_params_and_header(self):
        service = TikTokAdsService()

        captured: dict[str, object] = {}

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            captured["method"] = method
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            return {"code": 0, "data": {"list": []}}

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            service._report_integrated_get(
                account_id="401",
                access_token="tt-token",
                report_type="BASIC",
                data_level="AUCTION_ADVERTISER",
                dimensions=["stat_time_day"],
                metrics=["spend", "clicks"],
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 2),
            )
        finally:
            service._http_json = original_http

        self.assertEqual(captured["method"], "GET")
        self.assertIsNone(captured["payload"])
        self.assertEqual(captured["headers"], {"Access-Token": "tt-token"})
        self.assertNotIn("tt-token", str(captured["url"]))
        parsed_url = urlparse.urlsplit(str(captured["url"]))
        params = urlparse.parse_qs(parsed_url.query)
        self.assertEqual(params.get("advertiser_id"), ["401"])
        self.assertEqual(params.get("report_type"), ["BASIC"])
        self.assertEqual(params.get("data_level"), ["AUCTION_ADVERTISER"])
        self.assertEqual(params.get("start_date"), ["2026-03-01"])
        self.assertEqual(params.get("end_date"), ["2026-03-02"])
        self.assertEqual(params.get("page"), ["1"])
        self.assertEqual(params.get("page_size"), ["1000"])
        self.assertEqual(json.loads(str(params.get("dimensions", ["[]"])[0])), ["stat_time_day"])
        self.assertEqual(json.loads(str(params.get("metrics", ["[]"])[0])), ["spend", "clicks"])

    def test_all_reporting_grains_use_common_report_integrated_get_helper(self):
        service = TikTokAdsService()

        calls: list[str] = []

        def _fake_report_integrated_get(**kwargs):
            calls.append(str(kwargs.get("data_level") or ""))
            return {"code": 0, "data": {"list": []}}

        original_report = service._report_integrated_get
        try:
            service._report_integrated_get = _fake_report_integrated_get
            start = date(2026, 3, 1)
            end = date(2026, 3, 2)
            service._fetch_account_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_campaign_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_group_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
        finally:
            service._report_integrated_get = original_report

        self.assertEqual(calls, ["AUCTION_ADVERTISER", "AUCTION_CAMPAIGN", "AUCTION_ADGROUP", "AUCTION_AD"])

    def test_reporting_schema_per_grain_respects_metric_and_dimension_constraints(self):
        service = TikTokAdsService()

        account_schema = service._report_schema_for_grain("account_daily")
        campaign_schema = service._report_schema_for_grain("campaign_daily")
        ad_group_schema = service._report_schema_for_grain("ad_group_daily")
        ad_schema = service._report_schema_for_grain("ad_daily")

        self.assertEqual(account_schema.data_level, "AUCTION_ADVERTISER")
        self.assertEqual(account_schema.dimensions, ("stat_time_day",))
        self.assertNotIn("conversion_value", account_schema.metrics)
        self.assertEqual(campaign_schema.data_level, "AUCTION_CAMPAIGN")
        self.assertEqual(campaign_schema.dimensions, ("stat_time_day", "campaign_id"))
        self.assertNotIn("campaign_name", campaign_schema.dimensions)
        self.assertEqual(ad_group_schema.dimensions, ("stat_time_day", "adgroup_id"))
        self.assertNotIn("campaign_id", ad_group_schema.dimensions)
        self.assertNotIn("campaign_name", ad_group_schema.dimensions)
        self.assertEqual(ad_schema.dimensions, ("stat_time_day", "ad_id"))
        self.assertNotIn("adgroup_id", ad_schema.dimensions)
        self.assertNotIn("campaign_id", ad_schema.dimensions)

    def test_reporting_fetchers_generate_structurally_valid_requests_for_known_tiktok_errors(self):
        service = TikTokAdsService()

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            self.assertEqual(method, "GET")
            self.assertIsNone(payload)
            self.assertEqual(headers, {"Access-Token": "tok"})
            parsed_url = urlparse.urlsplit(str(url))
            params = urlparse.parse_qs(parsed_url.query)
            dimensions = json.loads(str(params.get("dimensions", ["[]"])[0]))
            metrics = json.loads(str(params.get("metrics", ["[]"])[0]))
            data_level = str(params.get("data_level", [""])[0])

            if data_level == "AUCTION_CAMPAIGN" and "campaign_name" in dimensions:
                return {"code": 40020, "message": "campaign_name is not supported"}
            if data_level == "AUCTION_ADGROUP" and "campaign_id" in dimensions:
                return {"code": 40021, "message": "data_level AUCTION_ADGROUP and dimension campaign_id do not match"}
            if data_level == "AUCTION_AD" and "adgroup_id" in dimensions:
                return {"code": 40022, "message": "data_level AUCTION_AD and dimension adgroup_id do not match"}
            if data_level == "AUCTION_ADVERTISER" and "conversion_value" in metrics:
                return {"code": 40010, "message": "Invalid metric fields: ['conversion_value']"}
            if len(dimensions) < 1 or len(dimensions) > 4:
                return {"code": 40011, "message": "dimensions: Length must be between 1 and 4"}
            return {"code": 0, "data": {"list": []}}

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            start = date(2026, 3, 1)
            end = date(2026, 3, 1)
            service._fetch_account_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_campaign_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_group_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
        finally:
            service._http_json = original_http

    def test_reporting_requests_exclude_runtime_invalid_dimensions_per_grain(self):
        service = TikTokAdsService()

        captured: dict[str, list[str]] = {}

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            parsed_url = urlparse.urlsplit(str(url))
            params = urlparse.parse_qs(parsed_url.query)
            data_level = str(params.get("data_level", [""])[0])
            dimensions = json.loads(str(params.get("dimensions", ["[]"])[0]))
            captured[data_level] = dimensions
            return {"code": 0, "data": {"list": []}}

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            start = date(2026, 3, 1)
            end = date(2026, 3, 1)
            service._fetch_campaign_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_group_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            service._fetch_ad_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
        finally:
            service._http_json = original_http

        self.assertEqual(captured.get("AUCTION_CAMPAIGN"), ["stat_time_day", "campaign_id"])
        self.assertNotIn("campaign_name", captured.get("AUCTION_CAMPAIGN", []))
        self.assertEqual(captured.get("AUCTION_ADGROUP"), ["stat_time_day", "adgroup_id"])
        self.assertNotIn("campaign_id", captured.get("AUCTION_ADGROUP", []))
        self.assertNotIn("campaign_name", captured.get("AUCTION_ADGROUP", []))
        self.assertEqual(captured.get("AUCTION_AD"), ["stat_time_day", "ad_id"])
        self.assertNotIn("adgroup_id", captured.get("AUCTION_AD", []))
        self.assertNotIn("campaign_id", captured.get("AUCTION_AD", []))

    def test_account_daily_conversion_value_uses_safe_fallback_without_conversion_value_metric(self):
        service = TikTokAdsService()

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            parsed_url = urlparse.urlsplit(str(url))
            params = urlparse.parse_qs(parsed_url.query)
            metrics = json.loads(str(params.get("metrics", ["[]"])[0]))
            self.assertNotIn("conversion_value", metrics)
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "dimensions": {"stat_time_day": "2026-03-01"},
                            "metrics": {
                                "spend": "12.5",
                                "impressions": "100",
                                "clicks": "6",
                                "conversion": "1",
                                "total_purchase_value": "44.2",
                            },
                        }
                    ]
                },
            }

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            rows = service._fetch_account_daily_metrics(
                account_id="401",
                access_token="tok",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
            )
        finally:
            service._http_json = original_http

        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0].conversion_value, 44.2)

    def test_reporting_request_shape_avoids_405_method_mismatch(self):
        service = TikTokAdsService()

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            if method != "GET":
                raise AssertionError("reporting must use GET to avoid 405")
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "dimensions": {"stat_time_day": "2026-03-01"},
                            "metrics": {"spend": "10", "impressions": "100", "clicks": "5"},
                        }
                    ]
                },
            }

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            rows = service._fetch_account_daily_metrics(
                account_id="401",
                access_token="tok",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
            )
        finally:
            service._http_json = original_http

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].account_id, "401")

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
