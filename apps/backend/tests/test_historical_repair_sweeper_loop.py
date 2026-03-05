import os
import unittest

from app.workers import historical_repair_sweeper_loop


class HistoricalRepairSweeperLoopTests(unittest.TestCase):
    def test_run_single_iteration_includes_historical_and_rolling_summary(self):
        calls = []
        original_load_settings = historical_repair_sweeper_loop.load_settings
        original_hist = historical_repair_sweeper_loop.sync_runs_store.sweep_stale_historical_runs
        original_roll = historical_repair_sweeper_loop.sync_runs_store.sweep_stale_rolling_runs

        class _Settings:
            sync_run_repair_stale_minutes = 33

        historical_repair_sweeper_loop.load_settings = lambda: _Settings()

        def _hist(**kwargs):
            calls.append(("historical", kwargs))
            return {"processed_count": 2, "repaired_count": 1, "error_count": 0}

        def _roll(**kwargs):
            calls.append(("rolling", kwargs))
            return {"processed_count": 3, "repaired_count": 2, "error_count": 1}

        historical_repair_sweeper_loop.sync_runs_store.sweep_stale_historical_runs = _hist
        historical_repair_sweeper_loop.sync_runs_store.sweep_stale_rolling_runs = _roll
        try:
            summary = historical_repair_sweeper_loop.run_single_iteration(limit=11)
        finally:
            historical_repair_sweeper_loop.load_settings = original_load_settings
            historical_repair_sweeper_loop.sync_runs_store.sweep_stale_historical_runs = original_hist
            historical_repair_sweeper_loop.sync_runs_store.sweep_stale_rolling_runs = original_roll

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "historical")
        self.assertEqual(calls[0][1]["stale_after_minutes"], 33)
        self.assertEqual(calls[1][0], "rolling")
        self.assertEqual(calls[1][1]["limit"], 11)
        self.assertEqual(summary["total_processed_count"], 5)
        self.assertEqual(summary["total_repaired_count"], 3)
        self.assertEqual(summary["total_error_count"], 1)

    def test_run_periodic_loop_disabled_exits_immediately(self):
        calls = []
        original_run_single = historical_repair_sweeper_loop.run_single_iteration
        historical_repair_sweeper_loop.run_single_iteration = lambda **kwargs: calls.append(kwargs)
        try:
            summary = historical_repair_sweeper_loop.run_periodic_loop(
                enabled=False,
                interval_seconds=30,
                stale_after_minutes=15,
                limit=5,
                max_iterations=2,
            )
        finally:
            historical_repair_sweeper_loop.run_single_iteration = original_run_single

        self.assertEqual(summary["status"], "disabled")
        self.assertEqual(calls, [])

    def test_run_periodic_loop_uses_interval_and_invokes_iterations(self):
        iter_calls = []
        sleep_calls = []
        original_run_single = historical_repair_sweeper_loop.run_single_iteration
        original_sleep = historical_repair_sweeper_loop.time.sleep

        historical_repair_sweeper_loop.run_single_iteration = lambda **kwargs: iter_calls.append(kwargs) or {"status": "ok"}
        historical_repair_sweeper_loop.time.sleep = lambda seconds: sleep_calls.append(seconds)
        try:
            summary = historical_repair_sweeper_loop.run_periodic_loop(
                enabled=True,
                interval_seconds=11,
                stale_after_minutes=20,
                limit=9,
                max_iterations=2,
            )
        finally:
            historical_repair_sweeper_loop.run_single_iteration = original_run_single
            historical_repair_sweeper_loop.time.sleep = original_sleep

        self.assertEqual(summary["status"], "stopped")
        self.assertEqual(summary["iterations"], 2)
        self.assertEqual(len(iter_calls), 2)
        self.assertEqual(iter_calls[0]["stale_after_minutes"], 20)
        self.assertEqual(iter_calls[0]["limit"], 9)
        self.assertEqual(sleep_calls, [11])

    def test_iteration_error_is_logged_and_loop_continues(self):
        iter_calls = []
        sleep_calls = []
        exception_calls = []
        original_run_single = historical_repair_sweeper_loop.run_single_iteration
        original_sleep = historical_repair_sweeper_loop.time.sleep
        original_logger_exception = historical_repair_sweeper_loop.logger.exception

        def _run_single(**kwargs):
            iter_calls.append(kwargs)
            if len(iter_calls) == 1:
                raise RuntimeError("boom")
            return {"status": "ok"}

        historical_repair_sweeper_loop.run_single_iteration = _run_single
        historical_repair_sweeper_loop.time.sleep = lambda seconds: sleep_calls.append(seconds)
        historical_repair_sweeper_loop.logger.exception = lambda *args, **kwargs: exception_calls.append((args, kwargs))
        try:
            summary = historical_repair_sweeper_loop.run_periodic_loop(
                enabled=True,
                interval_seconds=7,
                stale_after_minutes=None,
                limit=4,
                max_iterations=2,
            )
        finally:
            historical_repair_sweeper_loop.run_single_iteration = original_run_single
            historical_repair_sweeper_loop.time.sleep = original_sleep
            historical_repair_sweeper_loop.logger.exception = original_logger_exception

        self.assertEqual(summary["status"], "stopped")
        self.assertEqual(summary["iterations"], 2)
        self.assertEqual(len(iter_calls), 2)
        self.assertEqual(len(exception_calls), 1)
        self.assertEqual(sleep_calls, [7])

    def test_main_reads_env_contract(self):
        original_env = dict(os.environ)
        original_run_loop = historical_repair_sweeper_loop.run_periodic_loop
        calls = []

        os.environ["HISTORICAL_REPAIR_SWEEPER_ENABLED"] = "false"
        os.environ["HISTORICAL_REPAIR_SWEEPER_INTERVAL_SECONDS"] = "19"
        os.environ["HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES"] = "44"
        os.environ["HISTORICAL_REPAIR_SWEEPER_LIMIT"] = "8"

        historical_repair_sweeper_loop.run_periodic_loop = lambda **kwargs: calls.append(kwargs) or {"status": "disabled"}
        try:
            historical_repair_sweeper_loop.main()
        finally:
            historical_repair_sweeper_loop.run_periodic_loop = original_run_loop
            os.environ.clear()
            os.environ.update(original_env)

        self.assertEqual(calls[0]["enabled"], False)
        self.assertEqual(calls[0]["interval_seconds"], 19)
        self.assertEqual(calls[0]["stale_after_minutes"], 44)
        self.assertEqual(calls[0]["limit"], 8)


if __name__ == "__main__":
    unittest.main()
