import os
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

    def test_account_eligibility_requires_mapping_history_and_active_status(self):
        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": 10, "sync_start_date": "2024-01-09", "status": "active"})
        self.assertTrue(ok)
        self.assertIsNone(reason)

        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": None, "sync_start_date": "2024-01-09", "status": "active"})
        self.assertFalse(ok)
        self.assertEqual(reason, "unmapped")

        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": 10, "sync_start_date": None, "status": "active"})
        self.assertFalse(ok)
        self.assertEqual(reason, "history_not_initialized")

        ok, reason = rolling_scheduler._is_account_eligible_for_daily_rolling({"attached_client_id": 10, "sync_start_date": "2024-01-09", "status": "disabled"})
        self.assertFalse(ok)
        self.assertEqual(reason, "inactive")

    def _base_account(self, *, platform: str = "google_ads") -> dict[str, object]:
        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        return {
            "id": "1001",
            "platform": platform,
            "display_name": "Eligible",
            "attached_client_id": 11,
            "timezone": "UTC",
            "rolling_synced_through": str(yesterday - timedelta(days=2)),
            "sync_start_date": "2024-01-09",
            "status": "active",
        }

    def _run_scheduler(self, *, account: dict[str, object], env_value: str | None, existing_grains: set[str] | None = None):
        state = {"run_calls": [], "chunk_calls": []}
        existing_grains = existing_grains or set()

        def _list_platform_accounts(*, platform: str):
            self.assertEqual(platform, str(account.get("platform") or "google_ads"))
            return [dict(account)]

        def _create_or_dedupe_run(**kwargs):
            state["run_calls"].append(dict(kwargs))
            grain = str(kwargs.get("grain") or "")
            if grain in existing_grains:
                return {"created": False, "run": {"job_id": f"existing-{grain}", "grain": grain}}
            return {"created": True, "run": {"job_id": kwargs["job_id"], "grain": grain}}

        def _create_chunk(**kwargs):
            state["chunk_calls"].append(dict(kwargs))
            return kwargs

        env_patch = {"ROLLING_ENTITY_GRAINS_ENABLED": env_value} if env_value is not None else {}
        with patch.dict(os.environ, env_patch, clear=False), patch.object(
            rolling_scheduler.client_registry_service,
            "list_platform_accounts",
            side_effect=_list_platform_accounts,
        ), patch.object(
            rolling_scheduler.sync_runs_store,
            "create_rolling_sync_run_if_not_active",
            side_effect=_create_or_dedupe_run,
        ), patch.object(
            rolling_scheduler.sync_run_chunks_store,
            "create_sync_run_chunk",
            side_effect=_create_chunk,
        ):
            summary = rolling_scheduler.enqueue_rolling_sync_runs(platform=str(account.get("platform") or "google_ads"), limit=500, chunk_days=7, force=False)

        return summary, state

    def test_flag_off_enqueues_only_account_daily(self):
        summary, state = self._run_scheduler(account=self._base_account(platform="google_ads"), env_value="0")

        self.assertEqual(len(state["run_calls"]), 1)
        self.assertEqual(state["run_calls"][0]["grain"], "account_daily")
        self.assertEqual(summary["enqueued_count"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["account_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["campaign_daily"], 0)

    def test_flag_on_google_enqueues_account_and_entity_grains_with_same_window(self):
        summary, state = self._run_scheduler(account=self._base_account(platform="google_ads"), env_value="1")

        grains = [call["grain"] for call in state["run_calls"]]
        self.assertEqual(grains, ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily", "keyword_daily"])

        windows = {(str(call["date_start"]), str(call["date_end"])) for call in state["run_calls"]}
        self.assertEqual(len(windows), 1)

        self.assertEqual(summary["enqueued_count"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["account_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["campaign_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_group_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["keyword_daily"], 1)

    def test_flag_on_meta_platform_enqueues_meta_entity_grains_without_keyword(self):
        summary, state = self._run_scheduler(account=self._base_account(platform="meta_ads"), env_value="1")

        grains = [call["grain"] for call in state["run_calls"]]
        self.assertEqual(grains, ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily"])
        self.assertEqual(summary["enqueued_count_by_grain"]["account_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["campaign_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_group_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["keyword_daily"], 0)

    def test_flag_on_dedupe_skips_existing_campaign_daily(self):
        summary, state = self._run_scheduler(
            account=self._base_account(platform="google_ads"),
            env_value="1",
            existing_grains={"campaign_daily", "keyword_daily"},
        )

        grains_called = [call["grain"] for call in state["run_calls"]]
        self.assertEqual(grains_called, ["account_daily", "campaign_daily", "ad_group_daily", "ad_daily", "keyword_daily"])

        self.assertEqual(summary["enqueued_count_by_grain"]["account_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["campaign_daily"], 0)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_group_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["ad_daily"], 1)
        self.assertEqual(summary["enqueued_count_by_grain"]["keyword_daily"], 0)
    def test_invalid_platform_raises_value_error(self):
        with self.assertRaisesRegex(ValueError, "supports only platform"):
            rolling_scheduler.enqueue_rolling_sync_runs(platform="tiktok_ads", limit=10, chunk_days=7, force=False)


if __name__ == "__main__":
    unittest.main()
