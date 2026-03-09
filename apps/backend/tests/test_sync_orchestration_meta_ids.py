import unittest

from app.api import sync_orchestration
from app.services.auth import AuthUser


class SyncOrchestrationMetaIdTests(unittest.TestCase):
    def setUp(self):
        self.original_list_platform_accounts = sync_orchestration.client_registry_service.list_platform_accounts
        self.original_create_historical = sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active
        self.original_create_chunk = sync_orchestration.sync_run_chunks_store.create_sync_run_chunk
        self.original_enforce = sync_orchestration.enforce_action_scope

        sync_orchestration.enforce_action_scope = lambda **kwargs: None
        self.created_runs = []
        self.created_chunks = []

        sync_orchestration.client_registry_service.list_platform_accounts = lambda *, platform: [
            {"id": "act_123", "attached_client_id": 99}
        ] if platform == "meta_ads" else []

        def _create_historical(**kwargs):
            payload = {
                "job_id": kwargs["job_id"],
                "platform": kwargs["platform"],
                "account_id": kwargs["account_id"],
                "grain": kwargs.get("grain"),
                "status": "queued",
                "date_start": str(kwargs["date_start"]),
                "date_end": str(kwargs["date_end"]),
                "job_type": "historical_backfill",
                "chunks_total": kwargs.get("chunks_total", 0),
            }
            self.created_runs.append(payload)
            return {"created": True, "run": payload}

        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = _create_historical
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = lambda **kwargs: self.created_chunks.append(kwargs) or kwargs

    def tearDown(self):
        sync_orchestration.client_registry_service.list_platform_accounts = self.original_list_platform_accounts
        sync_orchestration.sync_runs_store.create_historical_sync_run_if_not_active = self.original_create_historical
        sync_orchestration.sync_run_chunks_store.create_sync_run_chunk = self.original_create_chunk
        sync_orchestration.enforce_action_scope = self.original_enforce

    def test_meta_batch_maps_numeric_input_to_prefixed_stored_account_and_creates_four_grains(self):
        payload = sync_orchestration.CreateBatchSyncRunsRequest(
            platform="meta_ads",
            account_ids=["123"],
            job_type="historical_backfill",
            start_date="2026-02-01",
            end_date="2026-02-07",
            chunk_days=7,
            grains=["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"],
        )
        user = AuthUser(email="owner@example.com", role="admin")

        response = sync_orchestration.create_batch_sync_runs(payload=payload, user=user)

        self.assertEqual(response["created_count"], 4)
        self.assertEqual(response["invalid_account_ids"], [])
        self.assertEqual({run["account_id"] for run in self.created_runs}, {"act_123"})
        self.assertEqual({run["grain"] for run in self.created_runs}, {"account_daily", "campaign_daily", "ad_group_daily", "ad_daily"})


if __name__ == "__main__":
    unittest.main()
