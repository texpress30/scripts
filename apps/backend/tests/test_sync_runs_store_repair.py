import unittest
from datetime import date, datetime, timedelta, timezone

from app.services.sync_runs_store import SyncRunsStore


class _RepairFakeCursor:
    def __init__(self, state):
        self.state = state
        self._last_one = None
        self._last_all = None
        self.executed = []

    def execute(self, query, params=None):
        q = " ".join(str(query).split())
        self.executed.append((q, params))
        self._last_one = None
        self._last_all = None

        if "pg_advisory_xact_lock" in q:
            self._last_one = (1,)
            return

        if "SELECT" in q and "FROM sync_runs" in q and "WHERE job_id = %s" in q and "FOR UPDATE" in q:
            job_id = str(params[0])
            run = self.state.get("run") if self.state.get("job_id") == job_id else None
            self._last_one = run
            return

        if "SELECT" in q and "id" in q and "freshness_ts" in q and "FROM sync_run_chunks" in q:
            chunks = self.state.get("chunks", [])
            self._last_all = [(c["id"], c["status"], c.get("freshness_ts"), c.get("attempts", 0)) for c in chunks]
            return

        if q.startswith("SELECT NOW()"):
            self._last_one = (self.state["now"],)
            return

        if q.startswith("UPDATE sync_run_chunks") and "WHERE id = ANY(%s)" in q:
            if "status = 'queued'" in q:
                ids = set(params[1] or [])
                for chunk in self.state.get("chunks", []):
                    if chunk["id"] in ids:
                        chunk["status"] = "queued"
                        chunk["error"] = None
            else:
                ids = set(params[2] or [])
                for chunk in self.state.get("chunks", []):
                    if chunk["id"] in ids:
                        chunk["status"] = "error"
                        chunk["error"] = "stale_timeout"
            return

        if "SELECT COUNT(*)::int" in q and "FROM sync_run_chunks" in q:
            chunks = self.state.get("chunks", [])
            total = len(chunks)
            done = len([c for c in chunks if c["status"] in {"done", "success", "completed"}])
            err = len([c for c in chunks if c["status"] in {"error", "failed"}])
            active = len([c for c in chunks if c["status"] in {"queued", "running", "pending"}])
            rows = sum(int(c.get("rows_written") or 0) for c in chunks)
            self._last_one = (total, done, err, active, rows)
            return

        if q.startswith("UPDATE sync_runs") and "RETURNING" in q:
            final_status = params[0]
            final_error = params[1]
            chunks_total = params[2]
            chunks_done = params[3]
            rows_written = params[4]
            run = list(self.state["run"])
            run[2] = final_status
            run[12] = final_error
            run[17] = chunks_total
            run[18] = chunks_done
            run[19] = rows_written
            self.state["run"] = tuple(run)
            self._last_one = self.state["run"]
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


class _RepairFakeConn:
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


class SyncRunsStoreRepairTests(unittest.TestCase):
    def _base_run_row(self, status="running"):
        return (
            "job-1",
            "google_ads",
            status,
            11,
            "3986597205",
            date(2026, 1, 1),
            date(2026, 1, 7),
            7,
            None,
            None,
            None,
            None,
            None,
            {},
            "batch-1",
            "historical_backfill",
            "account_daily",
            3,
            0,
            0,
        )

    def _build_store(self, state):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        cursor = _RepairFakeCursor(state)
        conn = _RepairFakeConn(cursor)
        store._connect = lambda: conn
        return store, cursor, conn

    def test_not_found_returns_not_found(self):
        state = {"job_id": "job-1", "run": None, "chunks": [], "now": datetime.now(timezone.utc)}
        store, _, conn = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="missing", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "not_found")
        self.assertEqual(conn.commit_calls, 1)

    def test_noop_not_active_for_terminal_run(self):
        state = {"job_id": "job-1", "run": self._base_run_row(status="done"), "chunks": [], "now": datetime.now(timezone.utc)}
        store, _, _ = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="job-1", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "noop_not_active")

    def test_reconcile_all_terminal_chunks_to_done(self):
        state = {
            "job_id": "job-1",
            "run": self._base_run_row(status="running"),
            "now": datetime.now(timezone.utc),
            "chunks": [
                {"id": 1, "status": "done", "freshness_ts": datetime.now(timezone.utc), "rows_written": 2},
                {"id": 2, "status": "done", "freshness_ts": datetime.now(timezone.utc), "rows_written": 3},
            ],
        }
        store, _, _ = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="job-1", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "repaired")
        self.assertEqual(result["final_status"], "done")
        self.assertEqual(result["reason"], "all_chunks_terminal_reconcile")

    def test_stale_active_chunks_are_requeued_when_under_max_attempts(self):
        now = datetime.now(timezone.utc)
        state = {
            "job_id": "job-1",
            "run": self._base_run_row(status="running"),
            "now": now,
            "chunks": [
                {"id": 1, "status": "running", "freshness_ts": now - timedelta(minutes=61), "rows_written": 2, "attempts": 1},
                {"id": 2, "status": "queued", "freshness_ts": now - timedelta(minutes=62), "rows_written": 0, "attempts": 0},
            ],
        }
        store, _, _ = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="job-1", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "requeued")
        self.assertEqual(result["reason"], "stale_chunk_requeued")
        self.assertEqual(result.get("stale_chunks_requeued"), 2)
        self.assertEqual(result.get("stale_chunks_closed"), 0)

    def test_stale_active_chunks_are_closed_when_max_attempts_exhausted(self):
        now = datetime.now(timezone.utc)
        state = {
            "job_id": "job-1",
            "run": self._base_run_row(status="running"),
            "now": now,
            "chunks": [
                {"id": 1, "status": "running", "freshness_ts": now - timedelta(minutes=61), "rows_written": 2, "attempts": 5},
                {"id": 2, "status": "queued", "freshness_ts": now - timedelta(minutes=62), "rows_written": 0, "attempts": 5},
            ],
        }
        store, _, _ = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="job-1", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "repaired")
        self.assertEqual(result["reason"], "stale_chunk_timeout")
        self.assertEqual(result["final_status"], "error")
        self.assertEqual(result["stale_chunks_closed"], 2)

    def test_active_fresh_chunks_return_noop_active_fresh(self):
        now = datetime.now(timezone.utc)
        state = {
            "job_id": "job-1",
            "run": self._base_run_row(status="running"),
            "now": now,
            "chunks": [
                {"id": 1, "status": "running", "freshness_ts": now - timedelta(minutes=5), "rows_written": 2},
            ],
        }
        store, _, _ = self._build_store(state)
        result = store.repair_historical_sync_run(job_id="job-1", stale_after_minutes=30)
        self.assertEqual(result["outcome"], "noop_active_fresh")
        self.assertEqual(result["active_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
