import os
import unittest
from datetime import date

from app.services.client_registry import client_registry_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store


class MetaAdsSyncContractTests(unittest.TestCase):
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

        self.original_token_resolver = meta_ads_service._resolve_active_access_token_with_source
        self.original_campaign_fetch = meta_ads_service._fetch_campaign_daily_insights

    def tearDown(self):
        meta_ads_service._resolve_active_access_token_with_source = self.original_token_resolver
        meta_ads_service._fetch_campaign_daily_insights = self.original_campaign_fetch
        os.environ.clear()
        os.environ.update(self.original_env)

    def _create_client_with_accounts(self, account_ids: list[str]) -> int:
        client = client_registry_service.create_client(name="Meta Client", owner_email="owner@example.com")
        client_id = int(client["id"])
        client_registry_service.upsert_platform_accounts(
            platform="meta_ads",
            accounts=[{"id": aid, "name": f"Meta {aid}"} for aid in account_ids],
        )
        for aid in account_ids:
            client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id=aid)
        return client_id

    def test_sync_client_accepts_window_grain_and_selected_account_scope(self):
        client_id = self._create_client_with_accounts(["act_1", "act_2"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)

        captured_account_ids: list[str] = []

        def _fetch_campaign(**kwargs):
            captured_account_ids.append(str(kwargs["account_id"]))
            return [{"campaign_id": "cmp1", "date_start": "2026-03-01", "spend": "1", "impressions": "10", "clicks": "1", "actions": [], "action_values": []}]

        meta_ads_service._fetch_campaign_daily_insights = _fetch_campaign

        payload = meta_ads_service.sync_client(
            client_id=client_id,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 1),
            grain="campaign_daily",
            account_id="act_2",
        )

        self.assertEqual(payload["grain"], "campaign_daily")
        self.assertEqual(payload["accounts_processed"], 1)
        self.assertEqual(captured_account_ids, ["act_2"])

    def test_sync_client_errors_when_selected_account_not_attached(self):
        client_id = self._create_client_with_accounts(["act_1"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)

        with self.assertRaisesRegex(MetaAdsIntegrationError, "not attached"):
            meta_ads_service.sync_client(
                client_id=client_id,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                grain="campaign_daily",
                account_id="act_2",
            )

    def test_sync_client_validates_grain_and_window(self):
        client_id = self._create_client_with_accounts(["act_1"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)

        with self.assertRaisesRegex(MetaAdsIntegrationError, "grain invalid"):
            meta_ads_service.sync_client(client_id=client_id, grain="invalid")

        with self.assertRaisesRegex(MetaAdsIntegrationError, "start_date cannot be after end_date"):
            meta_ads_service.sync_client(
                client_id=client_id,
                start_date=date(2026, 3, 2),
                end_date=date(2026, 3, 1),
                grain="campaign_daily",
            )

    def test_sync_client_errors_for_missing_token_and_no_accounts(self):
        client_id = self._create_client_with_accounts([])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("", "missing", None, "Meta Ads token is missing or placeholder.")

        with self.assertRaisesRegex(MetaAdsIntegrationError, "token is missing"):
            meta_ads_service.sync_client(client_id=client_id, grain="campaign_daily")

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)
        with self.assertRaisesRegex(MetaAdsIntegrationError, "No Meta Ads accounts attached"):
            meta_ads_service.sync_client(client_id=client_id, grain="campaign_daily")

    def test_meta_account_id_helpers_normalize_and_match_numeric_and_prefixed(self):
        self.assertEqual(meta_ads_service.normalize_meta_account_id("123456789"), "act_123456789")
        self.assertEqual(meta_ads_service.normalize_meta_account_id("act_123456789"), "act_123456789")
        self.assertEqual(meta_ads_service.meta_account_numeric_id("act_123456789"), "123456789")
        self.assertEqual(meta_ads_service.meta_graph_account_path("123456789"), "act_123456789")
        self.assertEqual(meta_ads_service.meta_graph_account_path("act_123456789"), "act_123456789")
        self.assertNotIn("act_act_", meta_ads_service.meta_graph_account_path("act_123456789"))
        self.assertTrue(meta_ads_service.meta_account_ids_match("act_123", "123"))
        self.assertTrue(meta_ads_service.meta_account_ids_match("123", "act_123"))

    def test_fetch_insights_never_generates_double_act_prefix(self):
        captured_urls: list[str] = []

        def _fake_http_json(*, method: str, url: str):
            captured_urls.append(url)
            return {"data": []}

        original_http_json = meta_ads_service._http_json
        try:
            meta_ads_service._http_json = _fake_http_json
            meta_ads_service._fetch_campaign_daily_insights(
                account_id="act_1810211459482188",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                access_token="token-ok",
            )
            self.assertEqual(len(captured_urls), 1)
            self.assertIn("/act_1810211459482188/insights", captured_urls[0])
            self.assertNotIn("act_act_", captured_urls[0])
            self.assertIn("/v24.0/", captured_urls[0])
        finally:
            meta_ads_service._http_json = original_http_json

    def test_selected_account_matching_accepts_numeric_against_attached_prefixed(self):
        client_id = self._create_client_with_accounts(["act_123"]) 
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)
        calls: list[str] = []

        def _fetch_campaign(**kwargs):
            calls.append(str(kwargs["account_id"]))
            return []

        meta_ads_service._fetch_campaign_daily_insights = _fetch_campaign
        payload = meta_ads_service.sync_client(
            client_id=client_id,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 1),
            grain="campaign_daily",
            account_id="123",
        )
        self.assertEqual(payload["accounts_processed"], 1)
        self.assertEqual(calls, ["act_123"])

    def test_account_probe_validates_explorer_like_response_shape(self):
        captured_urls: list[str] = []

        def _fake_http_json(*, method: str, url: str):
            captured_urls.append(url)
            return {"account_id": "1666914214322527", "id": "act_1666914214322527"}

        original_http_json = meta_ads_service._http_json
        try:
            meta_ads_service._http_json = _fake_http_json
            probe = meta_ads_service._probe_account_access(
                account_id="act_1666914214322527",
                access_token="token-ok",
                token_source="database",
            )
            self.assertEqual(probe["id"], "act_1666914214322527")
            self.assertEqual(probe["account_id"], "1666914214322527")
            self.assertEqual(probe["account_path"], "act_1666914214322527")
            self.assertEqual(probe["graph_version"], "v24.0")
            self.assertEqual(probe["token_source"], "database")
            self.assertIn("/v24.0/act_1666914214322527?", captured_urls[0])
            self.assertNotIn("act_act_", captured_urls[0])
        finally:
            meta_ads_service._http_json = original_http_json

    def test_sync_client_reuses_same_account_path_for_probe_and_insights(self):
        client_id = self._create_client_with_accounts(["act_1666914214322527"])
        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-ok", "database", None, None)

        captured_urls: list[str] = []

        def _fake_http_json(*, method: str, url: str):
            captured_urls.append(url)
            if "/insights" in url:
                return {"data": []}
            return {"account_id": "1666914214322527", "id": "act_1666914214322527"}

        original_http_json = meta_ads_service._http_json
        try:
            meta_ads_service._http_json = _fake_http_json
            payload = meta_ads_service.sync_client(
                client_id=client_id,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                grain="campaign_daily",
                account_id="1666914214322527",
            )
            self.assertEqual(payload["graph_version"], "v24.0")
            self.assertEqual(payload["token_source"], "database")
            self.assertEqual(len(captured_urls), 1)
            self.assertIn("/act_1666914214322527/insights?", captured_urls[0])
            self.assertNotIn("act_act_", " ".join(captured_urls))
            self.assertEqual(payload["accounts"][0]["account_path"], "act_1666914214322527")
            self.assertNotIn("token-ok", str(payload))
        finally:
            meta_ads_service._http_json = original_http_json


if __name__ == "__main__":
    unittest.main()
