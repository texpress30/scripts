import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.workers import rolling_scheduler


class RollingSchedulerTests(unittest.TestCase):
    def test_enqueue_rolling_sync_runs_filters_and_creates_runs(self):
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        accounts = [
            {
                "id": "1001",
                "name": "Mapped stale",
                "attached_client_id": 11,
                "account_timezone": "UTC",
                "rolling_window_days": 7,
                "rolling_synced_through": str(yesterday - timedelta(days=2)),
                "status": "active",
            },
            {
                "id": "1002",
                "name": "Mapped up to date",
                "attached_client_id": 12,
                "account_timezone": "UTC",
                "rolling_window_days": 7,
                "rolling_synced_through": str(yesterday),
                "status": "active",
            },
            {
                "id": "1003",
                "name": "Unmapped",
                "attached_client_id": None,
                "account_timezone": "UTC",
                "rolling_window_days": 7,
                "rolling_synced_through": None,
                "status": "active",
            },
        ]

        state = {"run_calls": [], "chunk_calls": []}

        def _list_platform_accounts(*, platform: str):
            self.assertEqual(platform, "google_ads")
            return list(accounts)

        def _create_run(**kwargs):
            state["run_calls"].append(dict(kwargs))
            return {"job_id": kwargs["job_id"], "client_id": kwargs["client_id"]}

        def _create_chunk(**kwargs):
            state["chunk_calls"].append(dict(kwargs))
            return kwargs

        with patch.object(rolling_scheduler.client_registry_service, "list_platform_accounts", side_effect=_list_platform_accounts), patch.object(
            rolling_scheduler.sync_runs_store,
            "create_sync_run",
            side_effect=_create_run,
        ), patch.object(
            rolling_scheduler.sync_run_chunks_store,
            "create_sync_run_chunk",
            side_effect=_create_chunk,
        ):
            summary = rolling_scheduler.enqueue_rolling_sync_runs(platform="google_ads", limit=500, chunk_days=7, force=False)

        self.assertEqual(summary["enqueued_count"], 1)
        self.assertEqual(summary["skipped_up_to_date_count"], 1)
        self.assertEqual(summary["skipped_unmapped_count"], 1)
        self.assertEqual(summary["enqueued_account_ids"], ["1001"])
        self.assertEqual(len(state["run_calls"]), 1)
        self.assertGreaterEqual(len(state["chunk_calls"]), 1)
        self.assertEqual(state["run_calls"][0]["job_type"], "rolling_refresh")
        self.assertEqual(state["run_calls"][0]["grain"], "account_daily")


if __name__ == "__main__":
    unittest.main()
