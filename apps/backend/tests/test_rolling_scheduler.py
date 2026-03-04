import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app.workers import rolling_scheduler


class RollingSchedulerTests(unittest.TestCase):
    def test_resolve_rolling_window_dates_is_exact_7_days(self):
        with patch.object(rolling_scheduler, "datetime") as datetime_mock:
            datetime_mock.now.return_value = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)
            start_date, end_date = rolling_scheduler._resolve_rolling_window_dates(timezone_name="UTC")

        self.assertEqual(end_date, date(2026, 3, 3))
        self.assertEqual(start_date, date(2026, 2, 25))
        self.assertEqual((end_date - start_date).days, 6)

    def test_account_eligibility_requires_mapping_and_history(self):
        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": 10, "sync_start_date": "2024-01-09"})
        self.assertTrue(ok)
        self.assertIsNone(reason)

        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": None, "sync_start_date": "2024-01-09"})
        self.assertFalse(ok)
        self.assertEqual(reason, "unmapped")

        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": 10, "sync_start_date": None})
        self.assertFalse(ok)
        self.assertEqual(reason, "history_not_initialized")

    def test_enqueue_rolling_sync_runs_filters_and_creates_runs(self):
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

        accounts = [
            {
                "id": "1001",
                "display_name": "Mapped stale",
                "attached_client_id": 11,
                "timezone": "UTC",
                "rolling_synced_through": str(yesterday - timedelta(days=2)),
                "sync_start_date": "2024-01-09",
            },
            {
                "id": "1002",
                "display_name": "Mapped up to date",
                "attached_client_id": 12,
                "timezone": "UTC",
                "rolling_synced_through": str(yesterday),
                "sync_start_date": "2024-01-09",
            },
            {
                "id": "1003",
                "display_name": "Unmapped",
                "attached_client_id": None,
                "timezone": "UTC",
                "rolling_synced_through": None,
                "sync_start_date": "2024-01-09",
            },
            {
                "id": "1004",
                "display_name": "No history",
                "attached_client_id": 15,
                "timezone": "UTC",
                "rolling_synced_through": None,
                "sync_start_date": None,
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
        self.assertEqual(summary["skipped_history_not_initialized_count"], 1)
        self.assertEqual(summary["enqueued_account_ids"], ["1001"])
        self.assertEqual(len(state["run_calls"]), 1)
        self.assertGreaterEqual(len(state["chunk_calls"]), 1)
        self.assertEqual(state["run_calls"][0]["job_type"], "rolling_refresh")
        self.assertEqual(state["run_calls"][0]["grain"], "account_daily")
        self.assertEqual(state["run_calls"][0]["metadata"].get("trigger_source"), "cron")


if __name__ == "__main__":
    unittest.main()
