import json
from datetime import date
import os
import unittest
from urllib import parse as urlparse

from app.api import tiktok_ads as tiktok_ads_api
from app.services.auth import AuthUser
from app.services.performance_reports import performance_reports_store
from app.services.tiktok_ads import TikTokAdsIntegrationError, TikTokAdsService, TikTokDailyMetric
from app.services.tiktok_store import tiktok_snapshot_store


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
                service_type="AUCTION",
                query_mode="REGULAR",
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
        self.assertEqual(params.get("service_type"), ["AUCTION"])
        self.assertEqual(params.get("query_mode"), ["REGULAR"])
        self.assertEqual(params.get("data_level"), ["AUCTION_ADVERTISER"])
        self.assertEqual(params.get("start_date"), ["2026-03-01"])
        self.assertEqual(params.get("end_date"), ["2026-03-02"])
        self.assertEqual(params.get("page"), ["1"])
        self.assertEqual(params.get("page_size"), ["1000"])
        self.assertEqual(json.loads(str(params.get("dimensions", ["[]"])[0])), ["stat_time_day"])
        self.assertEqual(json.loads(str(params.get("metrics", ["[]"])[0])), ["spend", "clicks"])


    def test_build_report_integrated_query_params_sets_explicit_parity_defaults(self):
        service = TikTokAdsService()

        params = service._build_report_integrated_query_params(
            account_id="401",
            report_type="BASIC",
            service_type="AUCTION",
            query_mode="REGULAR",
            data_level="AUCTION_ADVERTISER",
            dimensions=["stat_time_day"],
            metrics=["spend"],
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 2),
        )

        self.assertEqual(params["report_type"], "BASIC")
        self.assertEqual(params["service_type"], "AUCTION")
        self.assertEqual(params["query_mode"], "REGULAR")
        self.assertEqual(params["advertiser_id"], "401")

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
        self.assertNotIn("conversion_value", campaign_schema.metrics)
        self.assertEqual(ad_group_schema.dimensions, ("stat_time_day", "adgroup_id"))
        self.assertNotIn("campaign_id", ad_group_schema.dimensions)
        self.assertNotIn("campaign_name", ad_group_schema.dimensions)
        self.assertNotIn("conversion_value", ad_group_schema.metrics)
        self.assertEqual(ad_schema.dimensions, ("stat_time_day", "ad_id"))
        self.assertNotIn("adgroup_id", ad_schema.dimensions)
        self.assertNotIn("campaign_id", ad_schema.dimensions)
        self.assertNotIn("conversion_value", ad_schema.metrics)

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
            if data_level == "AUCTION_AD" and "campaign_id" in dimensions:
                return {"code": 40022, "message": "data_level AUCTION_AD and dimension campaign_id do not match"}
            if "conversion_value" in metrics:
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
        self.assertNotIn("campaign_id", captured.get("AUCTION_AD", []))

    def test_campaign_adgroup_ad_daily_do_not_request_conversion_value_and_keep_fallback(self):
        service = TikTokAdsService()

        seen_metrics: dict[str, list[str]] = {}

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            parsed_url = urlparse.urlsplit(str(url))
            params = urlparse.parse_qs(parsed_url.query)
            data_level = str(params.get("data_level", [""])[0])
            metrics = json.loads(str(params.get("metrics", ["[]"])[0]))
            seen_metrics[data_level] = metrics
            self.assertNotIn("conversion_value", metrics)
            return {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "dimensions": {
                                "stat_time_day": "2026-03-01",
                                "campaign_id": "c1",
                                "adgroup_id": "g1",
                                "ad_id": "a1",
                            },
                            "metrics": {
                                "spend": "11",
                                "impressions": "100",
                                "clicks": "5",
                                "conversion": "2",
                                "total_purchase_value": "77.7",
                            },
                        }
                    ]
                },
            }

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            start = date(2026, 3, 1)
            end = date(2026, 3, 1)
            campaign_rows = service._fetch_campaign_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            ad_group_rows = service._fetch_ad_group_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
            ad_rows = service._fetch_ad_daily_metrics(account_id="401", access_token="tok", start_date=start, end_date=end)
        finally:
            service._http_json = original_http

        self.assertNotIn("conversion_value", seen_metrics.get("AUCTION_CAMPAIGN", []))
        self.assertNotIn("conversion_value", seen_metrics.get("AUCTION_ADGROUP", []))
        self.assertNotIn("conversion_value", seen_metrics.get("AUCTION_AD", []))
        self.assertEqual(campaign_rows[0].conversion_value, 77.7)
        self.assertEqual(ad_group_rows[0].conversion_value, 77.7)
        self.assertEqual(ad_rows[0].conversion_value, 77.7)

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

    def test_account_daily_maps_nested_dimensions_metrics_list_shape(self):
        service = TikTokAdsService()

        def _fake_http_json(*, method: str, url: str, payload=None, headers=None):
            return {
                "code": 0,
                "message": "OK",
                "request_id": "req-1",
                "data": {
                    "list": [
                        {
                            "dimensions": [
                                {"key": "stat_time_day", "value": "2026-03-01T00:00:00Z"},
                                {"key": "campaign_id", "value": "cmp-1"},
                            ],
                            "metrics": [
                                {"key": "spend", "value": "11.2"},
                                {"key": "impressions", "value": "101"},
                                {"key": "clicks", "value": "9"},
                                {"key": "conversion", "value": "2"},
                                {"key": "total_purchase_value", "value": "7.5"},
                            ],
                        }
                    ],
                    "page_info": {"page": 1, "total_page": 1},
                },
            }

        original_http = service._http_json
        try:
            service._http_json = _fake_http_json
            rows = service._fetch_campaign_daily_metrics(
                account_id="401",
                access_token="tok",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
            )
            fetch_stats = service._consume_reporting_fetch_observability(grain="campaign_daily", account_id="401", rows_mapped=len(rows))
        finally:
            service._http_json = original_http

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].report_date.isoformat(), "2026-03-01")
        self.assertEqual(rows[0].campaign_id, "cmp-1")
        self.assertEqual(rows[0].clicks, 9)
        self.assertEqual(fetch_stats.get("rows_mapped"), 1)
        self.assertEqual(fetch_stats.get("skipped_invalid_date"), 0)
        self.assertEqual(fetch_stats.get("date_source_used"), "dimensions.stat_time_day")
        self.assertIn("campaign_id", fetch_stats.get("sample_dimension_keys") or [])
        self.assertIn("spend", fetch_stats.get("sample_metric_keys") or [])

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

    def test_sync_client_records_provider_empty_list_observability(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_http = service._http_json
        original_upsert = service._upsert_campaign_rows
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._upsert_campaign_rows = lambda *args, **kwargs: 0
            service._http_json = lambda **kwargs: {"code": 0, "data": {"list": []}}
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            payload = service.sync_client(
                client_id=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                grain="campaign_daily",
                account_id="401",
            )
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._http_json = original_http
            service._upsert_campaign_rows = original_upsert
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(payload.get("provider_row_count"), 0)
        self.assertEqual(payload.get("rows_downloaded"), 0)
        self.assertEqual(payload.get("rows_mapped"), 0)
        self.assertEqual(payload.get("rows_written"), 0)
        observability = payload.get("zero_row_observability")
        self.assertIsInstance(observability, list)
        self.assertEqual(observability[0].get("zero_row_marker"), "provider_returned_empty_list")
        self.assertEqual(observability[0].get("report_type"), "BASIC")
        self.assertEqual(observability[0].get("service_type"), "AUCTION")
        self.assertEqual(observability[0].get("query_mode"), "REGULAR")
        self.assertNotIn("Access-Token", json.dumps(observability[0]))

    def test_sync_client_records_parsed_but_zero_mapped_observability(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_http = service._http_json
        original_upsert = service._upsert_ad_rows
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._upsert_ad_rows = lambda *args, **kwargs: 0
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None
            service._http_json = lambda **kwargs: {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "dimensions": {"stat_time_day": "2026-03-01"},
                            "metrics": {"spend": "5", "impressions": "50", "clicks": "2", "total_purchase_value": "0"},
                        }
                    ]
                },
            }

            payload = service.sync_client(
                client_id=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                grain="ad_daily",
                account_id="401",
            )
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._http_json = original_http
            service._upsert_ad_rows = original_upsert
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(payload.get("provider_row_count"), 1)
        self.assertEqual(payload.get("rows_downloaded"), 1)
        self.assertEqual(payload.get("rows_mapped"), 0)
        self.assertEqual(payload.get("rows_written"), 0)
        observability = payload.get("zero_row_observability")
        self.assertIsInstance(observability, list)
        self.assertEqual(observability[0].get("zero_row_marker"), "response_parsed_but_zero_rows_mapped")
        self.assertEqual((observability[0].get("missing_required_breakdown") or {}).get("ad_id"), 1)
        self.assertIn("code", observability[0].get("response_top_level_keys") or [])
        self.assertIn("list", observability[0].get("data_container_keys") or [])

    def test_sync_client_account_daily_uses_canonical_identity_for_repeated_provider_id(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        writes: list[dict[str, object]] = []
        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_write = performance_reports_store.write_daily_report
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_account_daily_metrics = lambda **kwargs: [
                TikTokDailyMetric(
                    report_date=date(2026, 3, 1),
                    account_id="401",
                    spend=10.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=20.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401", " 401 "]}},
                ),
                TikTokDailyMetric(
                    report_date=date(2026, 3, 2),
                    account_id="401",
                    spend=12.0,
                    impressions=120,
                    clicks=6,
                    conversions=2.0,
                    conversion_value=25.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                ),
            ]
            performance_reports_store.write_daily_report = lambda **kwargs: writes.append(kwargs)
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            payload = service.sync_client(
                client_id=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 2),
                grain="account_daily",
                account_id="401",
            )
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            performance_reports_store.write_daily_report = original_write
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(payload.get("rows_written"), 2)
        self.assertEqual(payload.get("account_daily_identity_warnings"), [])
        self.assertEqual(len(writes), 2)
        self.assertEqual({item.get("customer_id") for item in writes}, {"401"})

    def test_sync_client_account_daily_raises_explicit_error_on_ambiguous_provider_identities(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        writes: list[dict[str, object]] = []
        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_write = performance_reports_store.write_daily_report
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_account_daily_metrics = lambda **kwargs: [
                TikTokDailyMetric(
                    report_date=date(2026, 3, 1),
                    account_id="401",
                    spend=10.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=20.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401", "999"]}},
                )
            ]
            performance_reports_store.write_daily_report = lambda **kwargs: writes.append(kwargs)
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            with self.assertRaises(TikTokAdsIntegrationError) as ctx:
                service.sync_client(
                    client_id=1,
                    start_date=date(2026, 3, 1),
                    end_date=date(2026, 3, 1),
                    grain="account_daily",
                    account_id="401",
                )
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            performance_reports_store.write_daily_report = original_write
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(writes, [])
        self.assertEqual(ctx.exception.provider_error_code, "acct_daily_ambiguous")
        self.assertEqual(ctx.exception.error_category, "local_attachment_error")
        self.assertEqual(ctx.exception.advertiser_id, "401")
        self.assertIn("\"identity_source\": \"ambiguous\"", str(ctx.exception.provider_error_message or ""))

    def test_sync_client_campaign_daily_unchanged_and_has_no_account_daily_identity_warnings(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_campaign_daily_metrics
        original_upsert = service._upsert_campaign_rows
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_campaign_daily_metrics = lambda **kwargs: []
            service._upsert_campaign_rows = lambda *args, **kwargs: 0
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            payload = service.sync_client(
                client_id=1,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                grain="campaign_daily",
                account_id="401",
            )
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_campaign_daily_metrics = original_fetch
            service._upsert_campaign_rows = original_upsert
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(payload.get("grain"), "campaign_daily")
        self.assertEqual(payload.get("rows_written"), 0)
        self.assertEqual(payload.get("account_daily_identity_warnings"), [])


    def test_sync_client_account_daily_rerun_is_idempotent_for_same_day(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["APP_ENV"] = "test"
        performance_reports_store._memory_rows.clear()

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_account_daily_metrics = lambda **kwargs: [
                TikTokDailyMetric(
                    report_date=date(2026, 3, 3),
                    account_id="401",
                    spend=10.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=12.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                )
            ]
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            first = service.sync_client(client_id=1, start_date=date(2026, 3, 3), end_date=date(2026, 3, 3), grain="account_daily", account_id="401")
            second = service.sync_client(client_id=1, start_date=date(2026, 3, 3), end_date=date(2026, 3, 3), grain="account_daily", account_id="401")
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        self.assertEqual(first.get("rows_written"), 1)
        self.assertEqual(second.get("rows_written"), 1)
        rows = [row for row in performance_reports_store._memory_rows if row.get("platform") == "tiktok_ads" and row.get("customer_id") == "401" and row.get("report_date") == "2026-03-03"]
        self.assertEqual(len(rows), 1)

    def test_sync_client_account_daily_rerun_replaces_metrics_for_same_natural_key(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["APP_ENV"] = "test"
        performance_reports_store._memory_rows.clear()

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            fetch_calls = {"count": 0}

            def _fetch(**kwargs):
                fetch_calls["count"] += 1
                spend = 10.0 if fetch_calls["count"] == 1 else 33.0
                clicks = 5 if fetch_calls["count"] == 1 else 11
                return [
                    TikTokDailyMetric(
                        report_date=date(2026, 3, 4),
                        account_id="401",
                        spend=spend,
                        impressions=100,
                        clicks=clicks,
                        conversions=1.0,
                        conversion_value=12.0,
                        extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                    )
                ]

            service._fetch_account_daily_metrics = _fetch
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            service.sync_client(client_id=1, start_date=date(2026, 3, 4), end_date=date(2026, 3, 4), grain="account_daily", account_id="401")
            service.sync_client(client_id=1, start_date=date(2026, 3, 4), end_date=date(2026, 3, 4), grain="account_daily", account_id="401")
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        rows = [row for row in performance_reports_store._memory_rows if row.get("platform") == "tiktok_ads" and row.get("customer_id") == "401" and row.get("report_date") == "2026-03-04"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("spend"), 33.0)
        self.assertEqual(rows[0].get("clicks"), 11)

    def test_sync_client_account_daily_overlap_windows_are_idempotent_on_overlap_dates(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["APP_ENV"] = "test"
        performance_reports_store._memory_rows.clear()

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}

            def _fetch(**kwargs):
                start = kwargs.get("start_date")
                if start == date(2026, 3, 1):
                    days = [1, 2, 3]
                    overlap_spend = 20.0
                else:
                    days = [2, 3, 4]
                    overlap_spend = 99.0
                rows = []
                for day in days:
                    spend = overlap_spend if day in (2, 3) else float(day)
                    rows.append(
                        TikTokDailyMetric(
                            report_date=date(2026, 3, day),
                            account_id="401",
                            spend=spend,
                            impressions=100,
                            clicks=5,
                            conversions=1.0,
                            conversion_value=12.0,
                            extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                        )
                    )
                return rows

            service._fetch_account_daily_metrics = _fetch
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            service.sync_client(client_id=1, start_date=date(2026, 3, 1), end_date=date(2026, 3, 3), grain="account_daily", account_id="401")
            service.sync_client(client_id=1, start_date=date(2026, 3, 2), end_date=date(2026, 3, 4), grain="account_daily", account_id="401")
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        rows = [row for row in performance_reports_store._memory_rows if row.get("platform") == "tiktok_ads" and row.get("customer_id") == "401"]
        by_day = {row.get("report_date"): row for row in rows}
        self.assertEqual(sorted(by_day.keys()), ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04"])
        self.assertEqual(by_day["2026-03-02"].get("spend"), 99.0)
        self.assertEqual(by_day["2026-03-03"].get("spend"), 99.0)

    def test_sync_client_account_daily_collapses_duplicate_candidates_in_single_batch(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["APP_ENV"] = "test"
        performance_reports_store._memory_rows.clear()

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_account_daily_metrics = lambda **kwargs: [
                TikTokDailyMetric(
                    report_date=date(2026, 3, 5),
                    account_id="401",
                    spend=11.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=12.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                ),
                TikTokDailyMetric(
                    report_date=date(2026, 3, 5),
                    account_id="401",
                    spend=22.0,
                    impressions=200,
                    clicks=7,
                    conversions=2.0,
                    conversion_value=18.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401"]}},
                ),
            ]
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            payload = service.sync_client(client_id=1, start_date=date(2026, 3, 5), end_date=date(2026, 3, 5), grain="account_daily", account_id="401")
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        rows = [row for row in performance_reports_store._memory_rows if row.get("platform") == "tiktok_ads" and row.get("customer_id") == "401" and row.get("report_date") == "2026-03-05"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("spend"), 22.0)
        self.assertEqual(payload.get("rows_written"), 1)
        warnings = payload.get("account_daily_identity_warnings") or []
        self.assertTrue(any(item.get("action") == "collapsed_duplicate_write_candidates" for item in warnings))

    def test_sync_client_account_daily_ambiguous_identity_blocks_persistence_with_explicit_error(self):
        service = TikTokAdsService()
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["APP_ENV"] = "test"
        performance_reports_store._memory_rows.clear()

        original_access = service._access_token_with_source
        original_resolve_ids = service._resolve_target_account_ids
        original_probe = service._probe_selected_advertiser_access
        original_fetch = service._fetch_account_daily_metrics
        original_snapshot_upsert = tiktok_snapshot_store.upsert_snapshot
        try:
            service._access_token_with_source = lambda: ("tok", "database", None)
            service._resolve_target_account_ids = lambda **kwargs: ["401"]
            service._probe_selected_advertiser_access = lambda **kwargs: {"status": "ok"}
            service._fetch_account_daily_metrics = lambda **kwargs: [
                TikTokDailyMetric(
                    report_date=date(2026, 3, 6),
                    account_id="401",
                    spend=10.0,
                    impressions=100,
                    clicks=5,
                    conversions=1.0,
                    conversion_value=20.0,
                    extra_metrics={"tiktok_ads": {"provider_identity_candidates": ["401", "999"]}},
                )
            ]
            tiktok_snapshot_store.upsert_snapshot = lambda **kwargs: None

            with self.assertRaises(TikTokAdsIntegrationError) as ctx:
                service.sync_client(client_id=1, start_date=date(2026, 3, 6), end_date=date(2026, 3, 6), grain="account_daily", account_id="401")
        finally:
            service._access_token_with_source = original_access
            service._resolve_target_account_ids = original_resolve_ids
            service._probe_selected_advertiser_access = original_probe
            service._fetch_account_daily_metrics = original_fetch
            tiktok_snapshot_store.upsert_snapshot = original_snapshot_upsert

        rows = [row for row in performance_reports_store._memory_rows if row.get("platform") == "tiktok_ads" and row.get("report_date") == "2026-03-06"]
        self.assertEqual(rows, [])
        self.assertEqual(ctx.exception.provider_error_code, "acct_daily_ambiguous")
        self.assertEqual(ctx.exception.advertiser_id, "401")


if __name__ == "__main__":
    unittest.main()
