import unittest
from datetime import date

from app.services.sync_runs_store import SyncRunsStore


class _RetryCursor:
    def __init__(self, state):
        self.state = state
        self._fetchone = None
        self._fetchall = None
        self.queries: list[tuple[str, tuple | None]] = []

    def execute(self, query, params=None):
        q = " ".join(str(query).split())
        self.queries.append((q, params))
        self._fetchone = None
        self._fetchall = None

        if "pg_advisory_xact_lock" in q:
            self._fetchone = (1,)
            return

        if "FROM sync_runs WHERE job_id = %s FOR UPDATE" in q:
            job_id = str(params[0])
            self._fetchone = self.state.get("runs", {}).get(job_id)
            return

        if "FROM sync_runs WHERE job_type = 'historical_backfill'" in q and "retry_of_job_id" in q:
            self._fetchone = self.state.get("existing_retry")
            return

        if "SELECT chunk_index, date_start, date_end FROM sync_run_chunks" in q:
            self._fetchall = list(self.state.get("failed_chunks", []))
            return

        if q.startswith("INSERT INTO sync_runs"):
            row = self.state.get("created_retry_row")
            self._fetchone = row
            return

        if q.startswith("INSERT INTO sync_run_chunks"):
            self.state.setdefault("inserted_chunks", []).append(params)
            return

        raise AssertionError(f"Unexpected query: {q}")

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _RetryConn:
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


class SyncRunsStoreRetryFailedTests(unittest.TestCase):
    def _build_run_row(self, *, job_id: str, status: str, job_type: str = "historical_backfill"):
        return (
            job_id,
            "google_ads",
            status,
            11,
            "3986597205",
            date(2026, 1, 1),
            date(2026, 1, 10),
            2,
            None,
            None,
            None,
            None,
            None,
            {},
            "batch-1",
            job_type,
            "account_daily",
            5,
            3,
            20,
        )

    def _build_store(self, state):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        cursor = _RetryCursor(state)
        conn = _RetryConn(cursor)
        store._connect = lambda: conn
        return store, state, cursor, conn

    def test_not_found(self):
        store, _, _, _ = self._build_store({"runs": {}})
        result = store.retry_failed_historical_run(source_job_id="missing", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "not_found")

    def test_not_retryable_non_historical(self):
        state = {"runs": {"src": self._build_run_row(job_id="src", status="done", job_type="manual")}}
        store, _, _, _ = self._build_store(state)
        result = store.retry_failed_historical_run(source_job_id="src", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "not_retryable")

    def test_not_retryable_active(self):
        state = {"runs": {"src": self._build_run_row(job_id="src", status="running")}}
        store, _, _, _ = self._build_store(state)
        result = store.retry_failed_historical_run(source_job_id="src", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "not_retryable")

    def test_no_failed_chunks(self):
        state = {
            "runs": {"src": self._build_run_row(job_id="src", status="done")},
            "failed_chunks": [],
        }
        store, _, _, _ = self._build_store(state)
        result = store.retry_failed_historical_run(source_job_id="src", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "no_failed_chunks")

    def test_already_exists(self):
        state = {
            "runs": {"src": self._build_run_row(job_id="src", status="error")},
            "existing_retry": self._build_run_row(job_id="retry-existing", status="queued"),
        }
        store, _, _, _ = self._build_store(state)
        result = store.retry_failed_historical_run(source_job_id="src", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "already_exists")
        self.assertEqual(result["retry_job_id"], "retry-existing")

    def test_created_with_only_failed_chunk_intervals(self):
        created_retry_row = self._build_run_row(job_id="retry-1", status="queued")
        state = {
            "runs": {"src": self._build_run_row(job_id="src", status="error")},
            "failed_chunks": [
                (3, date(2026, 1, 5), date(2026, 1, 6)),
                (4, date(2026, 1, 7), date(2026, 1, 8)),
            ],
            "created_retry_row": created_retry_row,
        }
        store, state_ref, _, _ = self._build_store(state)
        result = store.retry_failed_historical_run(source_job_id="src", retry_job_id="retry-1")
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["chunks_created"], 2)
        self.assertEqual(result["failed_chunks_count"], 2)
        inserted = state_ref.get("inserted_chunks", [])
        self.assertEqual(len(inserted), 2)
        self.assertEqual(inserted[0][3], date(2026, 1, 5))
        self.assertEqual(inserted[0][4], date(2026, 1, 6))
        self.assertEqual(inserted[1][3], date(2026, 1, 7))
        self.assertEqual(inserted[1][4], date(2026, 1, 8))


if __name__ == "__main__":
    unittest.main()
