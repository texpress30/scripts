import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services.sync_runs_store import SyncRunsStore
from app.workers import historical_repair_sweeper


class _SweeperCursor:
    def __init__(self, *, now, rows_by_job_type):
        self.now = now
        self.rows_by_job_type = dict(rows_by_job_type)
        self._last_one = None
        self._last_all = None

    def execute(self, query, params=None):
        q = " ".join(str(query).split())
        self._last_one = None
        self._last_all = None

        if q.startswith("SELECT NOW()"):
            self._last_one = (self.now,)
            return

        if "FROM sync_runs" in q and "WHERE job_type = %s" in q and "status IN ('queued', 'running')" in q:
            job_type = str((params or [""])[0])
            self._last_all = list(self.rows_by_job_type.get(job_type, []))
            return

        raise AssertionError(f"Unexpected query: {q}")

    def fetchone(self):
        return self._last_one

    def fetchall(self):
        return self._last_all or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _SweeperConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SyncRunsStoreSweeperTests(unittest.TestCase):
    def _build_store(self, *, now, rows_by_job_type):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        cursor = _SweeperCursor(now=now, rows_by_job_type=rows_by_job_type)
        store._connect = lambda: _SweeperConn(cursor)
        return store

    def test_sweeper_repairs_only_stale_historical_active_runs(self):
        now = datetime.now(timezone.utc)
        store = self._build_store(
            now=now,
            rows_by_job_type={
                "historical_backfill": [
                    ("hist-stale", now - timedelta(minutes=90)),
                    ("hist-fresh", now - timedelta(minutes=5)),
                ]
            },
        )

        calls = []

        def _repair(**kwargs):
            calls.append(kwargs)
            return {"outcome": "repaired", "job_id": kwargs["job_id"]}

        store._repair_active_sync_run = _repair

        summary = store.sweep_stale_historical_runs(stale_after_minutes=30, limit=100)

        self.assertEqual(summary["job_type"], "historical_backfill")
        self.assertEqual([c["job_id"] for c in calls], ["hist-stale"])
        self.assertEqual(summary["processed_count"], 1)
        self.assertEqual(summary["repaired_count"], 1)
        self.assertEqual(summary["noop_active_fresh_count"], 1)
        self.assertEqual(summary["noop_active_fresh_job_ids"], ["hist-fresh"])

    def test_sweeper_detects_and_repairs_stale_rolling_runs(self):
        now = datetime.now(timezone.utc)
        store = self._build_store(
            now=now,
            rows_by_job_type={
                "rolling_refresh": [
                    ("roll-stale", now - timedelta(minutes=80)),
                    ("roll-fresh", now - timedelta(minutes=3)),
                ],
                "historical_backfill": [("hist-ignore", now - timedelta(minutes=120))],
            },
        )

        calls = []

        def _repair(**kwargs):
            calls.append(kwargs)
            return {"outcome": "repaired", "job_id": kwargs["job_id"]}

        store._repair_active_sync_run = _repair

        summary = store.sweep_stale_rolling_runs(stale_after_minutes=30, limit=100)

        self.assertEqual(summary["job_type"], "rolling_refresh")
        self.assertEqual([c["job_id"] for c in calls], ["roll-stale"])
        self.assertEqual(summary["noop_active_fresh_job_ids"], ["roll-fresh"])

    def test_sweeper_aggregates_outcomes_and_repeat_call_is_safe_for_rolling(self):
        now = datetime.now(timezone.utc)
        store = self._build_store(
            now=now,
            rows_by_job_type={
                "rolling_refresh": [
                    ("job-repaired", now - timedelta(minutes=70)),
                    ("job-not-active", now - timedelta(minutes=70)),
                    ("job-not-found", now - timedelta(minutes=70)),
                    ("job-fresh", now - timedelta(minutes=2)),
                ]
            },
        )

        outcomes = {
            "job-repaired": {"outcome": "repaired"},
            "job-not-active": {"outcome": "noop_not_active"},
            "job-not-found": {"outcome": "not_found"},
        }

        def _repair(**kwargs):
            return {"job_id": kwargs["job_id"], **outcomes[kwargs["job_id"]]}

        store._repair_active_sync_run = _repair

        summary_1 = store.sweep_stale_rolling_runs(stale_after_minutes=30, limit=100)
        summary_2 = store.sweep_stale_rolling_runs(stale_after_minutes=30, limit=100)

        self.assertEqual(summary_1["repaired_count"], 1)
        self.assertEqual(summary_1["noop_not_active_count"], 1)
        self.assertEqual(summary_1["not_found_count"], 1)
        self.assertEqual(summary_1["noop_active_fresh_count"], 1)
        self.assertEqual(summary_1["error_count"], 0)
        self.assertEqual(summary_2["repaired_count"], 1)
        self.assertEqual(summary_2["noop_not_active_count"], 1)


class HistoricalRepairSweeperWorkerTests(unittest.TestCase):
    def test_worker_uses_store_sweeper_with_default_config_and_limit(self):
        calls = []
        original_load_settings = historical_repair_sweeper.load_settings
        original_sweeper = historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs
        original_rolling_sweeper = historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs

        class _Settings:
            sync_run_repair_stale_minutes = 45

        historical_repair_sweeper.load_settings = lambda: _Settings()

        def _sweeper(**kwargs):
            calls.append(kwargs)
            return {"status": "ok", "processed_count": 0}

        historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs = _sweeper
        historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs = lambda **kwargs: {"status": "ok", "processed_count": 0}
        try:
            summary = historical_repair_sweeper.sweep_stale_historical_runs(limit=12)
        finally:
            historical_repair_sweeper.load_settings = original_load_settings
            historical_repair_sweeper.sync_runs_store.sweep_stale_historical_runs = original_sweeper
            historical_repair_sweeper.sync_runs_store.sweep_stale_rolling_runs = original_rolling_sweeper

        self.assertIn("historical", summary)
        self.assertIn("rolling", summary)
        self.assertEqual(calls[0]["stale_after_minutes"], 45)
        self.assertEqual(calls[0]["limit"], 12)
        self.assertEqual(calls[0]["repair_source"], "sweeper")

    def test_main_handles_db_connection_timeout_with_controlled_summary(self):
        original_sweep = historical_repair_sweeper.sweep_stale_historical_runs
        original_is_db_error = historical_repair_sweeper.is_db_connection_error
        original_warning = historical_repair_sweeper.logger.warning

        warning_calls = []
        print_calls = []
        try:
            historical_repair_sweeper.sweep_stale_historical_runs = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("connection timeout expired"))
            historical_repair_sweeper.is_db_connection_error = lambda exc: True
            historical_repair_sweeper.logger.warning = lambda *args, **kwargs: warning_calls.append((args, kwargs))
            with patch("builtins.print", side_effect=lambda payload: print_calls.append(payload)):
                historical_repair_sweeper.main()
        finally:
            historical_repair_sweeper.sweep_stale_historical_runs = original_sweep
            historical_repair_sweeper.is_db_connection_error = original_is_db_error
            historical_repair_sweeper.logger.warning = original_warning

        self.assertEqual(len(warning_calls), 1)
        self.assertEqual(print_calls[0]["status"], "db_unavailable")
        self.assertEqual(print_calls[0]["error"], "database_connection_unavailable")
        self.assertEqual(print_calls[0]["total_processed_count"], 0)

    def test_main_re_raises_non_db_errors(self):
        original_sweep = historical_repair_sweeper.sweep_stale_historical_runs
        original_is_db_error = historical_repair_sweeper.is_db_connection_error
        try:
            historical_repair_sweeper.sweep_stale_historical_runs = lambda **kwargs: (_ for _ in ()).throw(ValueError("bad payload"))
            historical_repair_sweeper.is_db_connection_error = lambda exc: False
            with self.assertRaises(ValueError):
                historical_repair_sweeper.main()
        finally:
            historical_repair_sweeper.sweep_stale_historical_runs = original_sweep
            historical_repair_sweeper.is_db_connection_error = original_is_db_error


if __name__ == "__main__":
    unittest.main()
