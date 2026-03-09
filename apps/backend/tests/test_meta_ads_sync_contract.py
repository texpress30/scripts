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


if __name__ == "__main__":
    unittest.main()
