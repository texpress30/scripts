import os
import unittest
from datetime import date

from app.api import meta_ads as meta_ads_api
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.meta_store import meta_snapshot_store
from app.services.performance_reports import performance_reports_store


class MetaAdsSyncAccountDailyTests(unittest.TestCase):
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

        self.user = AuthUser(email="owner@example.com", role="admin")

        self.original_enforce = meta_ads_api.enforce_action_scope
        self.original_rate_limit = meta_ads_api.rate_limiter_service.check
        meta_ads_api.enforce_action_scope = lambda **kwargs: None
        meta_ads_api.rate_limiter_service.check = lambda *args, **kwargs: None

        self.original_resolve_token = meta_ads_service._resolve_active_access_token_with_source
        self.original_fetch = meta_ads_service._fetch_account_daily_insights

    def tearDown(self):
        meta_ads_api.enforce_action_scope = self.original_enforce
        meta_ads_api.rate_limiter_service.check = self.original_rate_limit
        meta_ads_service._resolve_active_access_token_with_source = self.original_resolve_token
        meta_ads_service._fetch_account_daily_insights = self.original_fetch
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

    def test_sync_happy_path_single_account(self):
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

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))

        self.assertEqual(payload["status"], "ok")
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

    def test_sync_happy_path_multiple_accounts(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client B", account_ids=["act_101", "act_202"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _fetch(**kwargs):
            account_id = kwargs["account_id"]
            if account_id == "act_101":
                return [{"date_start": "2026-03-01", "spend": "5", "impressions": "50", "clicks": "5", "actions": [], "action_values": []}]
            return [{"date_start": "2026-03-01", "spend": "8", "impressions": "80", "clicks": "8", "actions": [], "action_values": []}]

        meta_ads_service._fetch_account_daily_insights = _fetch

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))

        self.assertEqual(payload["accounts_processed"], 2)
        self.assertEqual(payload["rows_written"], 2)
        self.assertEqual(len(performance_reports_store._memory_rows), 2)

    def test_sync_is_idempotent_for_same_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client C", account_ids=["act_303"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {
                "date_start": "2026-03-01",
                "spend": "9",
                "impressions": "90",
                "clicks": "9",
                "actions": [{"action_type": "purchase", "value": "1"}],
                "action_values": [{"action_type": "purchase", "value": "11"}],
            }
        ]

        first = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        second = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))

        self.assertEqual(first["rows_written"], 1)
        self.assertEqual(second["rows_written"], 1)
        self.assertEqual(len(performance_reports_store._memory_rows), 1)

    def test_sync_fails_when_client_has_no_attached_accounts(self):
        client = client_registry_service.create_client(name="Client D", owner_email="owner@example.com")
        client_id = int(client["id"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        with self.assertRaisesRegex(MetaAdsIntegrationError, "No Meta Ads accounts attached"):
            meta_ads_service.sync_client(client_id=client_id)

    def test_sync_uses_env_fallback_token_source(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client E", account_ids=["act_505"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("env-token", "env_fallback", None, None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: [
            {"date_start": "2026-03-01", "spend": "3", "impressions": "30", "clicks": "3", "actions": [], "action_values": []}
        ]

        payload = meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))
        self.assertEqual(payload["token_source"], "env_fallback")

    def test_sync_maps_meta_api_error(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client F", account_ids=["act_606"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)

        def _boom(**kwargs):
            raise MetaAdsIntegrationError("Meta API request failed: status=401")

        meta_ads_service._fetch_account_daily_insights = _boom

        with self.assertRaisesRegex(MetaAdsIntegrationError, "Meta API request failed"):
            meta_ads_service.sync_client(client_id=client_id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 1))

    def test_api_sync_validates_date_interval(self):
        client_id = self._create_client_with_meta_accounts(client_name="Client G", account_ids=["act_707"])

        meta_ads_service._resolve_active_access_token_with_source = lambda: ("token-1", "database", None, None)
        meta_ads_service._fetch_account_daily_insights = lambda **kwargs: []

        with self.assertRaises(meta_ads_api.HTTPException) as ctx:
            meta_ads_api.sync_meta_ads(
                client_id=client_id,
                payload=meta_ads_api.MetaSyncRequest(start_date=date(2026, 3, 5), end_date=date(2026, 3, 1)),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("start_date", str(ctx.exception.detail))


if __name__ == "__main__":
    unittest.main()
