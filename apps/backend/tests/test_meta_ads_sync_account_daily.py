import os
import unittest
from datetime import date

from app.api import meta_ads as meta_ads_api
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.meta_store import meta_snapshot_store
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

        self.user = AuthUser(email="owner@example.com", role="admin")

        self.original_enforce = meta_ads_api.enforce_action_scope
        self.original_rate_limit = meta_ads_api.rate_limiter_service.check
        meta_ads_api.enforce_action_scope = lambda **kwargs: None
        meta_ads_api.rate_limiter_service.check = lambda *args, **kwargs: None

        self.original_resolve_token = meta_ads_service._resolve_active_access_token_with_source
        self.original_fetch_account = meta_ads_service._fetch_account_daily_insights
        self.original_fetch_campaign = meta_ads_service._fetch_campaign_daily_insights
        self.original_fetch_ad_group = meta_ads_service._fetch_ad_group_daily_insights

    def tearDown(self):
        meta_ads_api.enforce_action_scope = self.original_enforce
        meta_ads_api.rate_limiter_service.check = self.original_rate_limit
        meta_ads_service._resolve_active_access_token_with_source = self.original_resolve_token
        meta_ads_service._fetch_account_daily_insights = self.original_fetch_account
        meta_ads_service._fetch_campaign_daily_insights = self.original_fetch_campaign
        meta_ads_service._fetch_ad_group_daily_insights = self.original_fetch_ad_group
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
                "actions": [{"action_type": "purchase", "value": "2"}],
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
                "actions": [{"action_type": "purchase", "value": "3"}],
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
                "actions": [{"action_type": "purchase", "value": "4"}],
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
