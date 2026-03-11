import unittest

from app.services.sync_runs_store import SyncRunsStore


class _CleanupCursor:
    def __init__(self, state):
        self.state = state
        self._fetchall = None
        self._fetchone = None
        self.rowcount = 0

    def execute(self, query, params=None):
        q = " ".join(str(query).split())
        self._fetchall = None
        self._fetchone = None
        self.rowcount = 0

        if "FROM sync_runs sr" in q and "WHERE sr.status IN ('error', 'failed')" in q:
            self._fetchall = list(self.state.get("failed_rows", []))
            return

        if "FROM sync_runs sr" in q and "sr.status = 'done'" in q and "sr.job_type = 'historical_backfill'" in q and "SELECT sr.job_id" in q:
            self._fetchall = list(self.state.get("success_rows", []))
            return

        if q.startswith("SELECT job_id, COUNT(*)::int FROM sync_run_chunks"):
            self._fetchall = list(self.state.get("chunk_count_rows", []))
            return

        if q.startswith("DELETE FROM sync_run_chunks"):
            self.rowcount = int(self.state.get("deleted_chunks", 0))
            return

        if q.startswith("DELETE FROM sync_runs"):
            self.rowcount = int(self.state.get("deleted_runs", 0))
            return

        if "SELECT sr.status, sr.job_type" in q and "LIMIT 1" in q:
            account_id = str(params[0])
            self._fetchone = self.state.get("latest_by_account", {}).get(account_id)
            return

        if "SELECT MAX(sr.finished_at)" in q:
            account_id = str(params[0])
            self._fetchone = (self.state.get("success_at_by_account", {}).get(account_id),)
            return

        if "SELECT MAX(sr.date_end)" in q:
            account_id = str(params[0])
            self._fetchone = (self.state.get("backfill_by_account", {}).get(account_id),)
            return

        if q.startswith("UPDATE agency_platform_accounts"):
            account_id = str(params[-1])
            self.state.setdefault("updated_accounts", []).append(account_id)
            self.rowcount = 1
            return

        raise AssertionError(f"Unexpected query: {q}")

    def fetchall(self):
        return self._fetchall or []

    def fetchone(self):
        return self._fetchone

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _CleanupConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SyncRunsStoreTikTokCleanupTests(unittest.TestCase):
    def _build_store(self, state):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        cursor = _CleanupCursor(state)
        conn = _CleanupConn(cursor)
        store._connect = lambda: conn
        return store, state

    def test_same_account_same_grain_later_success_with_different_start_date_is_deleted(self):
        state = {
            "failed_rows": [
                ("f1", "tiktok_ads", "historical_backfill", "error", " 123 ", "account_daily", "2024-09-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
            ],
            "success_rows": [
                ("s1", "123", "account_daily", "2025-03-10", "2026-03-09", "2026-03-09T10:00:00+00:00"),
            ],
            "chunk_count_rows": [("f1", 2)],
            "deleted_chunks": 2,
            "deleted_runs": 1,
            "latest_by_account": {"123": ("done", "historical_backfill", "2026-03-09T10:00:00+00:00", "2026-03-09T11:00:00+00:00", None)},
            "success_at_by_account": {"123": "2026-03-09T11:00:00+00:00"},
            "backfill_by_account": {"123": "2026-03-09"},
        }
        store, state_ref = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(dry_run=False)

        self.assertEqual(result["superseded_run_count"], 1)
        self.assertEqual(result["deleted_runs"], 1)
        self.assertEqual(result["deleted_chunks"], 2)
        self.assertEqual(result["superseded_runs"][0]["matched_by_success_job_id"], "s1")
        self.assertEqual(state_ref.get("updated_accounts"), ["123"])

    def test_same_account_but_grain_mismatch_not_deleted(self):
        state = {
            "failed_rows": [
                ("f2", "tiktok_ads", "historical_backfill", "error", "123", "ad_group_daily", "2026-03-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
            ],
            "success_rows": [
                ("s2", "123", "account_daily", "2026-03-01", "2026-03-09", "2026-03-09T10:00:00+00:00"),
            ],
            "chunk_count_rows": [("f2", 1)],
        }
        store, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(dry_run=True)

        self.assertEqual(result["superseded_run_count"], 0)
        self.assertEqual(result["non_superseded_runs"][0]["reason"], "grain_mismatch")

    def test_without_later_success_not_deleted(self):
        state = {
            "failed_rows": [
                ("f3", "tiktok_ads", "historical_backfill", "error", "123", "account_daily", "2026-03-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
            ],
            "success_rows": [
                ("s3", "123", "account_daily", "2026-03-01", "2026-03-07", "2026-03-07T10:00:00+00:00"),
            ],
            "chunk_count_rows": [("f3", 1)],
        }
        store, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(dry_run=True)

        self.assertEqual(result["superseded_run_count"], 0)
        self.assertEqual(result["non_superseded_runs"][0]["reason"], "window_mismatch_but_legacy_tiktok_cleanup_should_match")

    def test_dry_run_includes_explicit_reasons_and_filtered_out(self):
        state = {
            "failed_rows": [
                ("f4", "tiktok_ads", "historical_backfill", "error", " ", "account_daily", "2026-03-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
                ("f5", "google_ads", "historical_backfill", "error", "123", "account_daily", "2026-03-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
                ("f6", "tiktok_ads", "rolling_refresh", "error", "123", "account_daily", "2026-03-01", "2026-03-08", "2026-03-08T10:00:00+00:00"),
            ],
            "success_rows": [],
            "chunk_count_rows": [],
        }
        store, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(dry_run=True)

        self.assertIn("account_id_mismatch", result["non_superseded_runs"][0]["reason"])
        self.assertIn("wrong_platform", result["non_match_reason_counts"])
        self.assertIn("wrong_job_type", result["non_match_reason_counts"])


if __name__ == "__main__":
    unittest.main()
