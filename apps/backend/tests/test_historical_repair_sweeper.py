import unittest

from app.workers import historical_repair_sweeper


class HistoricalRepairSweeperTests(unittest.TestCase):
    def test_sweep_stale_historical_runs_includes_historical_and_rolling_totals(self):
        calls = []
        original_load_settings = historical_repair_sweeper.load_settings
        original_hist = historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs
        original_roll = historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs

        class _Settings:
            sync_run_repair_stale_minutes = 21

        historical_repair_sweeper.load_settings = lambda: _Settings()

        def _hist(**kwargs):
            calls.append(("historical", kwargs))
            return {"processed_count": 5, "repaired_count": 3, "error_count": 1}

        def _roll(**kwargs):
            calls.append(("rolling", kwargs))
            return {"processed_count": 4, "repaired_count": 2, "error_count": 0}

        historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs = _hist
        historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs = _roll
        try:
            summary = historical_repair_sweeper.sweep_stale_historical_runs(limit=17)
        finally:
            historical_repair_sweeper.load_settings = original_load_settings
            historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs = original_hist
            historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs = original_roll

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "historical")
        self.assertEqual(calls[0][1]["stale_after_minutes"], 21)
        self.assertEqual(calls[0][1]["limit"], 17)
        self.assertEqual(calls[1][0], "rolling")
        self.assertEqual(calls[1][1]["stale_after_minutes"], 21)
        self.assertEqual(calls[1][1]["limit"], 17)

        self.assertEqual(summary["total_processed_count"], 9)
        self.assertEqual(summary["total_repaired_count"], 5)
        self.assertEqual(summary["total_error_count"], 1)
        self.assertEqual(summary["historical"]["processed_count"], 5)
        self.assertEqual(summary["rolling"]["processed_count"], 4)


if __name__ == "__main__":
    unittest.main()
