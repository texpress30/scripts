import os
import unittest
from datetime import date, datetime, timedelta

from app.api import meta_ads as meta_ads_api
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.meta_store import meta_snapshot_store
from app.services.sync_engine import backfill_job_store
from app.services.performance_reports import performance_reports_store


class MetaAdsSyncDailyTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"

        client_registry_service._clients = []
        client_registry_service._next_id = 1
        client_registry_service._memory_platform_accounts = {}
        client_registry_service._memory_last_import_at = {}
        client_registry_service._memory_account_client_mappings = {}
        client_registry_service._memory_account_profiles = {}

        performance_reports_store._memory_rows = []
        meta_snapshot_store._memory_snapshots = {}
        meta_ads_service._memory_campaign_daily_rows = []
        meta_ads_service._memory_ad_group_daily_rows = []
        meta_ads_service._memory_ad_daily_rows = []
        backfill_job_store._jobs = {}

        self.user = AuthUser(email="owner@example.com", role="admin")

        self.original_enforce = meta_ads_api.enforce_action_scope
        self.original_rate_limit = meta_ads_api.rate_limiter_service.check
        meta_ads_api.enforce_action_scope = lambda **kwargs: None
        meta_ads_api.rate_limiter_service.check = lambda *args, **kwargs: None

        self.original_resolve_token = meta_ads_service._resolve_active_access_token_with_source
        self.original_fetch_account = meta_ads_service._fetch_account_daily_insights
        self.original_fetch_campaign = meta_ads_service._fetch_campaign_daily_insights
        self.original_fetch_ad_group = meta_ads_service._fetch_ad_group_daily_insights
        self.original_fetch_ad_daily = meta_ads_service._fetch_ad_daily_insights
        self.original_sync_client = meta_ads_service.sync_client
        self.original_integration_status = meta_ads_service.integration_status

    def tearDown(self):
        meta_ads_api.enforce_action_scope = self.original_enforce
        meta_ads_api.rate_limiter_service.check = self.original_rate_limit
        meta_ads_service._resolve_active_access_token_with_source = self.original_resolve_token
        meta_ads_service._fetch_account_daily_insights = self.original_fetch_account
        meta_ads_service._fetch_campaign_daily_insights = self.original_fetch_campaign
        meta_ads_service._fetch_ad_group_daily_insights = self.original_fetch_ad_group
        meta_ads_service._fetch_ad_daily_insights = self.original_fetch_ad_daily
        meta_ads_service.sync_client = self.original_sync_client
        meta_ads_service.integration_status = self.original_integration_status
        os.environ.clear()
        os.environ.update(self.original_env)

    def _create_client_with_meta_accounts(self, *, client_name: str, account_ids: list[str]) -> int:
        client = client_registry_service.create_client(name=client_name, owner_email="owner@example.com")
        client_id = int(client["id"])
        client_registry_service.upsert_platform_accounts(
            platform="meta_ads",
            accounts=[{"id": aid, "name": f"Meta {aid}"} for aid in account_ids],
        )
        for aid in account_ids:
            client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id=aid)
        return client_id

    def test_account_daily_happy_path_single_account(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client A", account_ids=["act_101"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", "2026-03-07T10:00:00Z", None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {
                "date_start": "2026-03-01",
                "date_stop": "2026-03-01",
                "spend": "10.50",
                "impressions": "100",
                "clicks": "7",
                "actions": [{"action_type": "lead", "value": "2"}],
                "action_values": [{"action_type": "purchase", "value": "25.75"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="account_daily")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["grain"], "account_daily")
        self.assertEqual(payload["accounts_processed"], 1)
        self.assertEqual(payload["rows_written"], 1)
        self.assertEqual(payload["token_source"], "database")

        rows = performance_reports_store._memory_rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "meta_ads")
        self.assertEqual(rows[0]["customer_id"], "act_101")
        self.assertEqual(rows[0]["report_date"], "2026-03-01")
        self.assertEqual(rows[0]["conversions"], 2.0)
        self.assertEqual(rows[0]["conversion_value"], 25.75)


    def test_lead_conversions_ignore_non_lead_action_types(self):
        value = meta_ads_service._derive_lead_conversions(
            actions=[
                {"action_type": "lead", "value": "3"},
                {"action_type": "offsite_conversion.fb_pixel_lead", "value": "2"},
                {"action_type": "purchase", "value": "100"},
                {"action_type": "add_to_cart", "value": "50"},
                {"action_type": "page_view", "value": "999"},
                {"action_type": "landing_page_view", "value": "40"},
                {"action_type": "post_engagement", "value": "25"},
            ]
        )
        self.assertEqual(value, 3.0)

    def test_lead_conversions_single_lead_type_uses_that_value(self):
        value = meta_ads_service._derive_lead_conversions(
            actions=[
                {"action_type": "offsite_conversion.fb_pixel_lead", "value": "23"},
                {"action_type": "purchase", "value": "100"},
            ]
        )
        self.assertEqual(value, 23.0)

    def test_lead_conversions_deduplicate_duplicate_lead_aliases(self):
        value = meta_ads_service._derive_lead_conversions(
            actions=[
                {"action_type": "lead", "value": "23"},
                {"action_type": "onsite_conversion.lead_grouped", "value": "23"},
                {"action_type": "page_view", "value": "200"},
            ]
        )
        self.assertEqual(value, 23.0)

    def test_lead_conversions_observability_contains_selected_canonical_type(self):
        details = meta_ads_service._derive_lead_conversion_details(
            actions=[
                {"action_type": "lead", "value": "4"},
                {"action_type": "onsite_conversion.lead_grouped", "value": "4"},
                {"action_type": "purchase", "value": "90"},
            ]
        )
        self.assertEqual(details["lead_action_types_found"], ["lead", "onsite_conversion.lead_grouped"])
        self.assertEqual(details["lead_action_type_selected"], "lead")
        self.assertEqual(details["lead_action_values_found"], {"lead": 4.0, "onsite_conversion.lead_grouped": 4.0})

    def test_campaign_daily_uses_lead_only_conversions(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Lead", account_ids=["act_777"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {
                "campaign_id": "cmp-lead",
                "campaign_name": "Lead Campaign",
                "date_start": "2026-03-01",
                "spend": "20",
                "impressions": "200",
                "clicks": "20",
                "actions": [
                    {"action_type": "lead", "value": "4"},
                    {"action_type": "offsite_conversion.fb_pixel_lead", "value": "1"},
                    {"action_type": "purchase", "value": "99"},
                ],
                "action_values": [{"action_type": "purchase", "value": "120.5"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")

        self.assertEqual(payload["rows_written"], 1)
        self.assertEqual(payload["conversions"], 4.0)
        row = meta_ads_service._memory_campaign_daily_rows[0]
        self.assertEqual(float(row.get("conversions") or 0), 4.0)
        extra = (row.get("extra_metrics") or {}).get("meta_ads") or {}
        self.assertEqual(extra.get("lead_action_type_selected"), "lead")

    def test_all_meta_grains_use_lead_only_conversions(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Grains", account_ids=["act_888"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        mixed_actions = [
            {"action_type": "lead", "value": "2"},
            {"action_type": "onsite_conversion.lead_grouped", "value": "1"},
            {"action_type": "purchase", "value": "50"},
            {"action_type": "add_to_cart", "value": "30"},
        ]

        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {"date_start": "2026-03-01", "date_stop": "2026-03-01", "spend": "10", "impressions": "100", "clicks": "10", "actions": mixed_actions, "action_values": []}
        ]
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-1", "campaign_name": "Cmp", "date_start": "2026-03-01", "spend": "10", "impressions": "100", "clicks": "10", "actions": mixed_actions, "action_values": []}
        ]
        meta_ads_service._fetch_ad_group_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-1", "campaign_name": "Cmp", "adset_id": "as-1", "adset_name": "Adset", "date_start": "2026-03-01", "spend": "10", "impressions": "100", "clicks": "10", "actions": mixed_actions, "action_values": []}
        ]
        meta_ads_service._fetch_ad_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-1", "campaign_name": "Cmp", "adset_id": "as-1", "adset_name": "Adset", "ad_id": "ad-1", "ad_name": "Ad", "date_start": "2026-03-01", "spend": "10", "impressions": "100", "clicks": "10", "actions": mixed_actions, "action_values": []}
        ]

        for grain in ("account_daily", "campaign_daily", "ad_group_daily", "ad_daily"):
            payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain=grain)
            self.assertEqual(payload["conversions"], 2.0)

    def test_account_daily_and_snapshot_use_canonical_deduplicated_leads(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Dedup", account_ids=["act_7777"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {
                "date_start": "2026-03-01",
                "date_stop": "2026-03-01",
                "spend": "12",
                "impressions": "120",
                "clicks": "12",
                "actions": [
                    {"action_type": "lead", "value": "23"},
                    {"action_type": "onsite_conversion.lead_grouped", "value": "23"},
                ],
                "action_values": [{"action_type": "purchase", "value": "0"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="account_daily")
        self.assertEqual(payload["conversions"], 23.0)

        rows = performance_reports_store._memory_rows
        self.assertEqual(rows[-1]["conversions"], 23.0)
        extra = (rows[-1].get("extra_metrics") or {}).get("meta_ads") or {}
        self.assertEqual(extra.get("lead_action_type_selected"), "lead")

        snapshot = meta_ads_service.get_metrics(client_id=client_id)
        self.assertEqual(snapshot["conversions"], 23)

    def test_account_daily_insights_request_uses_time_increment_1(self):
        captured: dict[str, str] = {}
        original_build_url = meta_ads_service._build_graph_account_url
        original_http_json = meta_ads_service._http_json
        try:
            meta_ads_service._build_graph_account_url = lambda **kwargs: "https://graph.example/insights"

            def _http_json(*, method: str, url: str):
                captured["method"] = method
                captured["url"] = url
                return {"data": []}

            meta_ads_service._http_json = _http_json
            meta_ads_service._fetch_account_daily_insights(
                account_id="act_1",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 3),
                access_token="token",
            )
        finally:
            meta_ads_service._build_graph_account_url = original_build_url
            meta_ads_service._http_json = original_http_json

        self.assertEqual(captured.get("method"), "GET")
        self.assertIn("time_increment=1", str(captured.get("url") or ""))

    def test_only_account_daily_updates_meta_snapshot_source_of_truth(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Snapshot", account_ids=["act_919"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {
                "date_start": "2026-03-01",
                "date_stop": "2026-03-01",
                "spend": "10",
                "impressions": "100",
                "clicks": "10",
                "actions": [{"action_type": "lead", "value": "2"}],
                "action_values": [{"action_type": "purchase", "value": "20"}],
            }
        ]
        meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="account_daily")
        before = meta_ads_service.get_metrics(client_id=client_id)

        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {
                "campaign_id": "cmp-snapshot",
                "campaign_name": "Snapshot",
                "date_start": "2026-03-01",
                "spend": "999",
                "impressions": "9999",
                "clicks": "999",
                "actions": [{"action_type": "lead", "value": "999"}],
                "action_values": [{"action_type": "purchase", "value": "999"}],
            }
        ]
        meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")
        after = meta_ads_service.get_metrics(client_id=client_id)

        self.assertEqual(before.get("spend"), after.get("spend"))
        self.assertEqual(before.get("impressions"), after.get("impressions"))
        self.assertEqual(before.get("clicks"), after.get("clicks"))
        self.assertEqual(before.get("conversions"), after.get("conversions"))

    def test_campaign_daily_happy_path_single_account(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client B", account_ids=["act_202"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {
                "campaign_id": "cmp-1",
                "campaign_name": "Campaign Alpha",
                "date_start": "2026-03-01",
                "spend": "20.00",
                "impressions": "200",
                "clicks": "12",
                "actions": [{"action_type": "lead", "value": "3"}],
                "action_values": [{"action_type": "purchase", "value": "90.00"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")

        self.assertEqual(payload["grain"], "campaign_daily")
        self.assertEqual(payload["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_campaign_daily_rows), 1)
        row = meta_ads_service._memory_campaign_daily_rows[0]
        self.assertEqual(str(row.get("campaign_id")), "cmp-1")
        self.assertEqual(str(row.get("account_id")), "act_202")
        extra = row.get("extra_metrics")
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["meta_ads"]["campaign_name"], "Campaign Alpha")

    def test_campaign_daily_happy_path_multiple_accounts(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client C", account_ids=["act_301", "act_302"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _campaign_rows(**kwargs):
            if kwargs["account_id"] == "act_301":
                return [{"campaign_id": "cmp-a", "campaign_name": "A", "date_start": "2026-03-01", "spend": "5", "impressions": "50", "clicks": "5", "actions": [], "action_values": []}]
            return [{"campaign_id": "cmp-b", "campaign_name": "B", "date_start": "2026-03-01", "spend": "8", "impressions": "80", "clicks": "8", "actions": [], "action_values": []}]

        meta_ads_service._fetch_campaign_daily_insights = _campaign_rows

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")
        self.assertEqual(payload["accounts_processed"], 2)
        self.assertEqual(payload["rows_written"], 2)
        self.assertEqual(len(meta_ads_service._memory_campaign_daily_rows), 2)

    def test_campaign_daily_idempotent_rerun_same_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client D", account_ids=["act_404"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-4", "campaign_name": "Four", "date_start": "2026-03-01", "spend": "9", "impressions": "90", "clicks": "9", "actions": [], "action_values": []}
        ]

        first = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")
        second = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")

        self.assertEqual(first["rows_written"], 1)
        self.assertEqual(second["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_campaign_daily_rows), 1)

    def test_sync_fails_when_client_has_no_attached_accounts(self):
        client = client_registry_service.create_client(name="Client E", owner_email="owner@example.com")
        client_id = int(client["id"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        with self.assertRaisesRegex(MetaAdsIntegrationError, "No Meta Ads accounts attached"):
            meta_ads_service.sync_client(client_id=client_id, grain="campaign_daily")

    def test_campaign_daily_uses_env_fallback_token_source(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client F", account_ids=["act_505"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("env-token", "env_fallback", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-5", "campaign_name": "Five", "date_start": "2026-03-01", "spend": "3", "impressions": "30", "clicks": "3", "actions": [], "action_values": []}
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")
        self.assertEqual(payload["token_source"], "env_fallback")

    def test_campaign_daily_maps_meta_api_error(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client G", account_ids=["act_606"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _boom(**kwargs):
            raise MetaAdsIntegrationError("Meta API request failed: status=401")

        meta_ads_service._fetch_campaign_daily_insights = _boom

        with self.assertRaisesRegex(MetaAdsIntegrationError, "Meta API request failed"):
            meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily")

    def test_ad_group_daily_happy_path_single_account(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client J", account_ids=["act_909"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_ad_group_daily_insights = lambda **kwargs: [
            {
                "adset_id": "adset-1",
                "adset_name": "Adset One",
                "campaign_id": "cmp-9",
                "campaign_name": "Campaign Nine",
                "date_start": "2026-03-01",
                "spend": "11.25",
                "impressions": "111",
                "clicks": "9",
                "actions": [{"action_type": "lead", "value": "4"}],
                "action_values": [{"action_type": "purchase", "value": "123.45"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")
        self.assertEqual(payload["grain"], "ad_group_daily")
        self.assertEqual(payload["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_ad_group_daily_rows), 1)
        row = meta_ads_service._memory_ad_group_daily_rows[0]
        self.assertEqual(str(row.get("ad_group_id")), "adset-1")
        self.assertEqual(str(row.get("campaign_id")), "cmp-9")
        extra = row.get("extra_metrics")
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["meta_ads"]["adset_name"], "Adset One")
        self.assertEqual(extra["meta_ads"]["campaign_name"], "Campaign Nine")

    def test_ad_group_daily_happy_path_multiple_accounts(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client K", account_ids=["act_1001", "act_1002"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _ad_group_rows(**kwargs):
            if kwargs["account_id"] == "act_1001":
                return [{"adset_id": "adset-a", "campaign_id": "cmp-a", "date_start": "2026-03-01", "spend": "5", "impressions": "50", "clicks": "5", "actions": [], "action_values": []}]
            return [{"adset_id": "adset-b", "campaign_id": "cmp-b", "date_start": "2026-03-01", "spend": "8", "impressions": "80", "clicks": "8", "actions": [], "action_values": []}]

        meta_ads_service._fetch_ad_group_daily_insights = _ad_group_rows
        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")
        self.assertEqual(payload["accounts_processed"], 2)
        self.assertEqual(payload["rows_written"], 2)
        self.assertEqual(len(meta_ads_service._memory_ad_group_daily_rows), 2)

    def test_ad_group_daily_idempotent_rerun_same_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client L", account_ids=["act_1101"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_ad_group_daily_insights = lambda **kwargs: [
            {"adset_id": "adset-11", "campaign_id": "cmp-11", "date_start": "2026-03-01", "spend": "9", "impressions": "90", "clicks": "9", "actions": [], "action_values": []}
        ]

        first = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")
        second = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")
        self.assertEqual(first["rows_written"], 1)
        self.assertEqual(second["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_ad_group_daily_rows), 1)

    def test_ad_group_daily_uses_env_fallback_token_source(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client M", account_ids=["act_1201"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("env-token", "env_fallback", None, None)
        meta_ads_service._fetch_ad_group_daily_insights = lambda **kwargs: [
            {"adset_id": "adset-12", "campaign_id": "cmp-12", "date_start": "2026-03-01", "spend": "3", "impressions": "30", "clicks": "3", "actions": [], "action_values": []}
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")
        self.assertEqual(payload["token_source"], "env_fallback")

    def test_ad_group_daily_maps_meta_api_error(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client N", account_ids=["act_1301"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _boom(**kwargs):
            raise MetaAdsIntegrationError("Meta API request failed: status=401")

        meta_ads_service._fetch_ad_group_daily_insights = _boom

        with self.assertRaisesRegex(MetaAdsIntegrationError, "Meta API request failed"):
            meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily")

    def test_ad_daily_happy_path_single_account(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client P", account_ids=["act_1501"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_ad_daily_insights = lambda **kwargs: [
            {
                "ad_id": "ad-1",
                "ad_name": "Ad One",
                "adset_id": "adset-1",
                "adset_name": "Adset One",
                "campaign_id": "cmp-15",
                "campaign_name": "Campaign Fifteen",
                "date_start": "2026-03-01",
                "spend": "13.50",
                "impressions": "150",
                "clicks": "10",
                "actions": [{"action_type": "lead", "value": "2"}],
                "action_values": [{"action_type": "purchase", "value": "77.70"}],
            }
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")
        self.assertEqual(payload["grain"], "ad_daily")
        self.assertEqual(payload["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_ad_daily_rows), 1)
        row = meta_ads_service._memory_ad_daily_rows[0]
        self.assertEqual(str(row.get("ad_id")), "ad-1")
        self.assertEqual(str(row.get("ad_group_id")), "adset-1")
        self.assertEqual(str(row.get("campaign_id")), "cmp-15")
        extra = row.get("extra_metrics")
        self.assertIsInstance(extra, dict)
        self.assertEqual(extra["meta_ads"]["ad_name"], "Ad One")
        self.assertEqual(extra["meta_ads"]["adset_name"], "Adset One")

    def test_ad_daily_happy_path_multiple_accounts(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Q", account_ids=["act_1601", "act_1602"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _ad_rows(**kwargs):
            if kwargs["account_id"] == "act_1601":
                return [{"ad_id": "ad-a", "adset_id": "adset-a", "campaign_id": "cmp-a", "date_start": "2026-03-01", "spend": "4", "impressions": "40", "clicks": "4", "actions": [], "action_values": []}]
            return [{"ad_id": "ad-b", "adset_id": "adset-b", "campaign_id": "cmp-b", "date_start": "2026-03-01", "spend": "6", "impressions": "60", "clicks": "6", "actions": [], "action_values": []}]

        meta_ads_service._fetch_ad_daily_insights = _ad_rows

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")
        self.assertEqual(payload["accounts_processed"], 2)
        self.assertEqual(payload["rows_written"], 2)
        self.assertEqual(len(meta_ads_service._memory_ad_daily_rows), 2)

    def test_ad_daily_idempotent_rerun_same_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client R", account_ids=["act_1701"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_ad_daily_insights = lambda **kwargs: [
            {"ad_id": "ad-17", "adset_id": "adset-17", "campaign_id": "cmp-17", "date_start": "2026-03-01", "spend": "9", "impressions": "90", "clicks": "9", "actions": [], "action_values": []}
        ]

        first = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")
        second = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")
        self.assertEqual(first["rows_written"], 1)
        self.assertEqual(second["rows_written"], 1)
        self.assertEqual(len(meta_ads_service._memory_ad_daily_rows), 1)

    def test_ad_daily_uses_env_fallback_token_source(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client S", account_ids=["act_1801"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("env-token", "env_fallback", None, None)
        meta_ads_service._fetch_ad_daily_insights = lambda **kwargs: [
            {"ad_id": "ad-18", "adset_id": "adset-18", "campaign_id": "cmp-18", "date_start": "2026-03-01", "spend": "2", "impressions": "20", "clicks": "2", "actions": [], "action_values": []}
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")
        self.assertEqual(payload["token_source"], "env_fallback")

    def test_ad_daily_maps_meta_api_error(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client T", account_ids=["act_1901"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _boom(**kwargs):
            raise MetaAdsIntegrationError("Meta API request failed: status=401")

        meta_ads_service._fetch_ad_daily_insights = _boom

        with self.assertRaisesRegex(MetaAdsIntegrationError, "Meta API request failed"):
            meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_daily")

    def test_api_sync_ad_group_daily_backward_compat_kept(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client U", account_ids=["act_2001"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_ad_group_daily_insights = lambda **kwargs: [
            {"adset_id": "adset-20", "campaign_id": "cmp-20", "date_start": "2026-03-01", "spend": "1", "impressions": "10", "clicks": "1", "actions": [], "action_values": []}
        ]

        response = meta_ads_api.sync_meta_ads(
            client_id=client_id,
            payload=meta_ads_api.MetaSyncRequest(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="ad_group_daily"),
            user=self.user,
        )
        self.assertEqual(response["grain"], "ad_group_daily")

    def test_api_sync_backward_compat_grain_missing_defaults_to_account_daily(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client H", account_ids=["act_707"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {"date_start": "2026-03-01", "spend": "1", "impressions": "10", "clicks": "1", "actions": [], "action_values": []}
        ]

        response = meta_ads_api.sync_meta_ads(client_id=client_id, payload=None, user=self.user)
        self.assertEqual(response["grain"], "account_daily")

    def test_api_sync_campaign_daily_backward_compat_kept(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client O", account_ids=["act_1401"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: [
            {"campaign_id": "cmp-14", "campaign_name": "Fourteen", "date_start": "2026-03-01", "spend": "1", "impressions": "10", "clicks": "1", "actions": [], "action_values": []}
        ]

        response = meta_ads_api.sync_meta_ads(
            client_id=client_id,
            payload=meta_ads_api.MetaSyncRequest(start_date=date(2026, 3, 1), end_date=date(2026, 3, 1), grain="campaign_daily"),
            user=self.user,
        )
        self.assertEqual(response["grain"], "campaign_daily")

    def test_backfill_trigger_happy_path_default_range(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client V", account_ids=["act_2101"])
        meta_ads_service.integration_status = lambda: {"token_source": "database", "status": "connected"}

        calls: list[dict[str, object]] = []

        def _sync_client(**kwargs):
            calls.append(dict(kwargs))
            return {
                "status": "ok",
                "grain": kwargs.get("grain"),
                "accounts_processed": 1,
                "rows_written": 1,
                "token_source": "database",
            }

        meta_ads_service.sync_client = _sync_client

        job_id = backfill_job_store.create(payload={"platform": "meta_ads", "client_id": client_id})
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        meta_ads_api._run_meta_historical_backfill_job(
            job_id,
            client_id=client_id,
            start_date=date(2024, 1, 9),
            end_date=yesterday,
            grains=["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"],
            chunk_days=30,
        )

        payload = backfill_job_store.get(job_id) or {}
        self.assertEqual(payload.get("status"), "done")
        result = payload.get("result") or {}
        self.assertEqual(result.get("mode"), "historical_backfill")
        self.assertEqual(result.get("start_date"), "2024-01-09")
        self.assertEqual(result.get("end_date"), yesterday.isoformat())
        self.assertEqual(result.get("grains"), ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"])
        self.assertGreaterEqual(int(result.get("chunks_total") or 0), 1)
        self.assertGreaterEqual(len(calls), 4)

    def test_backfill_trigger_with_custom_interval_and_grains(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client W", account_ids=["act_2201"])
        meta_ads_service.integration_status = lambda: {"token_source": "database", "status": "connected"}

        calls: list[dict[str, object]] = []

        def _sync_client(**kwargs):
            calls.append(dict(kwargs))
            return {
                "status": "ok",
                "grain": kwargs.get("grain"),
                "accounts_processed": 1,
                "rows_written": 2,
                "token_source": "database",
            }

        meta_ads_service.sync_client = _sync_client

        job_id = backfill_job_store.create(payload={"platform": "meta_ads", "client_id": client_id})
        meta_ads_api._run_meta_historical_backfill_job(
            job_id,
            client_id=client_id,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 3),
            grains=["campaign_daily", "ad_daily"],
            chunk_days=30,
        )

        payload = backfill_job_store.get(job_id) or {}
        result = payload.get("result") or {}
        self.assertEqual(payload.get("status"), "done")
        self.assertEqual(result.get("start_date"), "2026-02-01")
        self.assertEqual(result.get("end_date"), "2026-02-03")
        self.assertEqual(result.get("grains"), ["campaign_daily", "ad_daily"])
        self.assertEqual(result.get("chunks_total"), 1)
        self.assertEqual(result.get("chunks_processed"), 2)
        self.assertEqual(len(calls), 2)

    def test_backfill_endpoint_enqueues_with_defaults(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client AB", account_ids=["act_2601"])
        meta_ads_service.integration_status = lambda: {"token_source": "database", "status": "connected"}

        background_tasks = meta_ads_api.BackgroundTasks()
        response = meta_ads_api.backfill_meta_ads(client_id=client_id, background_tasks=background_tasks, payload=None, user=self.user)

        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["mode"], "enqueued")
        self.assertEqual(response["start_date"], "2024-01-09")
        self.assertEqual(response["grains"], ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"])
        self.assertGreaterEqual(int(response["chunks_enqueued"]), 1)
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_backfill_endpoint_custom_interval_and_grains(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client AC", account_ids=["act_2701"])
        meta_ads_service.integration_status = lambda: {"token_source": "database", "status": "connected"}

        background_tasks = meta_ads_api.BackgroundTasks()
        response = meta_ads_api.backfill_meta_ads(
            client_id=client_id,
            background_tasks=background_tasks,
            payload=meta_ads_api.MetaBackfillRequest(start_date=date(2026, 2, 1), end_date=date(2026, 2, 3), grains=["campaign_daily", "ad_daily"]),
            user=self.user,
        )

        self.assertEqual(response["start_date"], "2026-02-01")
        self.assertEqual(response["end_date"], "2026-02-03")
        self.assertEqual(response["grains"], ["campaign_daily", "ad_daily"])
        self.assertEqual(response["chunks_enqueued"], 1)
        self.assertEqual(response["jobs_enqueued"], 2)
        self.assertEqual(len(background_tasks.tasks), 1)

    def test_backfill_rejects_invalid_grains(self):
        with self.assertRaises(meta_ads_api.HTTPException) as ctx:
            meta_ads_api._normalize_meta_backfill_grains(["invalid_grain"])
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported Meta backfill grain", str(ctx.exception.detail))

    def test_backfill_fails_when_client_has_no_attached_accounts(self):
        client = client_registry_service.create_client(name="Client X", owner_email="owner@example.com")
        client_id = int(client["id"])
        meta_ads_service.integration_status = lambda: {"token_source": "database", "status": "connected"}

        with self.assertRaises(meta_ads_api.HTTPException) as ctx:
            meta_ads_api.backfill_meta_ads(client_id=client_id, background_tasks=meta_ads_api.BackgroundTasks(), payload=None, user=self.user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("No Meta Ads accounts attached", str(ctx.exception.detail))

    def test_backfill_validates_missing_token(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Y", account_ids=["act_2301"])
        meta_ads_service.integration_status = lambda: {"token_source": "missing", "status": "pending"}

        with self.assertRaises(meta_ads_api.HTTPException) as ctx:
            meta_ads_api.backfill_meta_ads(client_id=client_id, background_tasks=meta_ads_api.BackgroundTasks(), payload=None, user=self.user)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("token is missing", str(ctx.exception.detail).lower())

    def test_backfill_env_fallback_token_and_idempotent_rerun(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client Z", account_ids=["act_2401"])
        meta_ads_service.integration_status = lambda: {"token_source": "env_fallback", "status": "connected"}

        calls: list[tuple[str, str, str]] = []

        def _sync_client(**kwargs):
            calls.append((str(kwargs.get("grain")), kwargs["start_date"].isoformat(), kwargs["end_date"].isoformat()))
            return {
                "status": "ok",
                "grain": kwargs.get("grain"),
                "accounts_processed": 1,
                "rows_written": 1,
                "token_source": "env_fallback",
            }

        meta_ads_service.sync_client = _sync_client

        job_one = backfill_job_store.create(payload={"platform": "meta_ads", "client_id": client_id})
        job_two = backfill_job_store.create(payload={"platform": "meta_ads", "client_id": client_id})
        grains = ["ad_daily"]
        start = date(2026, 3, 1)
        end = date(2026, 3, 1)

        meta_ads_api._run_meta_historical_backfill_job(job_one, client_id=client_id, start_date=start, end_date=end, grains=grains, chunk_days=30)
        meta_ads_api._run_meta_historical_backfill_job(job_two, client_id=client_id, start_date=start, end_date=end, grains=grains, chunk_days=30)

        first = backfill_job_store.get(job_one) or {}
        second = backfill_job_store.get(job_two) or {}
        self.assertEqual(first.get("status"), "done")
        self.assertEqual(second.get("status"), "done")
        self.assertEqual((first.get("result") or {}).get("token_source"), "env_fallback")
        self.assertEqual((second.get("result") or {}).get("token_source"), "env_fallback")
        self.assertEqual(len(calls), 2)

    def test_backfill_maps_meta_api_error_clearly(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client AA", account_ids=["act_2501"])

        def _boom(**kwargs):
            raise MetaAdsIntegrationError("Meta API request failed: status=401")

        meta_ads_service.sync_client = _boom
        job_id = backfill_job_store.create(payload={"platform": "meta_ads", "client_id": client_id})
        meta_ads_api._run_meta_historical_backfill_job(
            job_id,
            client_id=client_id,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 1),
            grains=["account_daily"],
            chunk_days=30,
        )

        payload = backfill_job_store.get(job_id) or {}
        self.assertEqual(payload.get("status"), "error")
        self.assertIn("Meta API request failed", str(payload.get("error") or ""))

    def test_api_sync_validates_date_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client I", account_ids=["act_808"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_campaign_daily_insights = lambda **kwargs: []

        with self.assertRaises(meta_ads_api.HTTPException) as ctx:
            meta_ads_api.sync_meta_ads(
                client_id=client_id,
                payload=meta_ads_api.MetaSyncRequest(start_date=date(2026, 3, 5), end_date=date(2026, 3, 1), grain="campaign_daily"),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("start_date", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
