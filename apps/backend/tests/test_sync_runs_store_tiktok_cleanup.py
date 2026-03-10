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

        if "SELECT f.job_id, f.account_id FROM sync_runs f" in q:
            self._fetchall = list(self.state.get("superseded_rows", []))
            return

        if q.startswith("DELETE FROM sync_run_chunks"):
            deleted = int(self.state.get("deleted_chunks", 0))
            self.rowcount = deleted
            return

        if q.startswith("DELETE FROM sync_runs"):
            deleted = int(self.state.get("deleted_runs", 0))
            self.rowcount = deleted
            return

        if "SELECT sr.status, sr.job_type" in q and "ORDER BY COALESCE" in q:
            account_id = str(params[0])
            self._fetchone = self.state.get("latest_by_account", {}).get(account_id)
            return

        if "SELECT MAX(sr.finished_at) FROM sync_runs sr" in q and "sr.status = 'done'" in q:
            account_id = str(params[0])
            value = self.state.get("success_at_by_account", {}).get(account_id)
            self._fetchone = (value,)
            return

        if "SELECT MAX(sr.date_end) FROM sync_runs sr" in q and "sr.job_type = 'historical_backfill'" in q:
            account_id = str(params[0])
            value = self.state.get("backfill_by_account", {}).get(account_id)
            self._fetchone = (value,)
            return

        if q.startswith("UPDATE agency_platform_accounts"):
            account_id = str(params[-1])
            updated_accounts = set(self.state.setdefault("updated_accounts", set()))
            if account_id in set(self.state.get("accounts_present", [])):
                updated_accounts.add(account_id)
                self.rowcount = 1
            else:
                self.rowcount = 0
            self.state["updated_accounts"] = updated_accounts
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
        self.commit_calls = 0

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commit_calls += 1

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
        return store, state, conn

    def test_cleanup_deletes_superseded_runs_and_chunks_and_recomputes_metadata(self):
        state = {
            "superseded_rows": [("failed-1", "acc-1")],
            "deleted_chunks": 3,
            "deleted_runs": 1,
            "accounts_present": ["acc-1"],
            "latest_by_account": {"acc-1": ("done", "historical_backfill", "2026-03-01T00:00:00+00:00", "2026-03-01T01:00:00+00:00", None, "2026-02-28")},
            "success_at_by_account": {"acc-1": "2026-03-01T01:00:00+00:00"},
            "backfill_by_account": {"acc-1": "2026-02-28"},
        }
        store, state_ref, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs()

        self.assertEqual(result["superseded_run_count"], 1)
        self.assertEqual(result["deleted_runs"], 1)
        self.assertEqual(result["deleted_chunks"], 3)
        self.assertEqual(result["affected_account_ids"], ["acc-1"])
        self.assertIn("acc-1", state_ref.get("updated_accounts", set()))
        self.assertEqual(result["metadata_updates"][0]["last_run_status"], "done")
        self.assertIsNone(result["metadata_updates"][0]["last_error"])

    def test_cleanup_keeps_runs_when_no_superseded_failure_exists(self):
        state = {
            "superseded_rows": [],
            "deleted_chunks": 0,
            "deleted_runs": 0,
        }
        store, _, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(account_ids=["acc-no-success"])

        self.assertEqual(result["superseded_run_count"], 0)
        self.assertEqual(result["deleted_runs"], 0)
        self.assertEqual(result["deleted_chunks"], 0)
        self.assertEqual(result["affected_account_ids"], [])
        self.assertEqual(result["metadata_updates"], [])

    def test_cleanup_dry_run_recomputes_metadata_without_deletion(self):
        state = {
            "superseded_rows": [("failed-2", "acc-2")],
            "deleted_chunks": 99,
            "deleted_runs": 99,
            "accounts_present": ["acc-2"],
            "latest_by_account": {"acc-2": ("error", "historical_backfill", "2026-01-01T00:00:00+00:00", "2026-01-01T01:00:00+00:00", "boom", "2026-01-01")},
            "success_at_by_account": {"acc-2": None},
            "backfill_by_account": {"acc-2": None},
        }
        store, _, _ = self._build_store(state)

        result = store.cleanup_superseded_tiktok_failed_runs(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["superseded_run_count"], 1)
        self.assertEqual(result["deleted_runs"], 0)
        self.assertEqual(result["deleted_chunks"], 0)
        self.assertEqual(result["metadata_updates"][0]["last_error"], "boom")


if __name__ == "__main__":
    unittest.main()
