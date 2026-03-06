import unittest
from datetime import date

from app.services.sync_runs_store import SyncRunsStore


class _ProgressCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchall(self):
        return list(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ProgressConn:
    def __init__(self, cursor: _ProgressCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SyncRunsStoreProgressBatchTests(unittest.TestCase):
    def _build_store(self, *, rows):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        cursor = _ProgressCursor(rows)
        conn = _ProgressConn(cursor)
        store._connect = lambda: conn
        return store, cursor

    def test_returns_active_run_payload_and_null_for_missing(self):
        rows = [
            ("3986597205", "job-1", "rolling_refresh", "running", date(2026, 1, 1), date(2026, 1, 7), 3, 7, 1),
            ("1000000000", None, None, None, None, None, 0, 0, 0),
        ]
        store, cursor = self._build_store(rows=rows)

        result = store.get_active_runs_progress_batch(
            platform="google_ads",
            account_ids=["3986597205", "1000000000"],
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["account_id"], "3986597205")
        self.assertEqual(result[0]["active_run"]["job_id"], "job-1")
        self.assertEqual(result[0]["active_run"]["chunks_done"], 3)
        self.assertEqual(result[0]["active_run"]["chunks_total"], 7)
        self.assertEqual(result[0]["active_run"]["errors_count"], 1)
        self.assertEqual(result[0]["active_run"]["date_start"], "2026-01-01")
        self.assertEqual(result[0]["active_run"]["date_end"], "2026-01-07")
        self.assertIsNone(result[1]["active_run"])

        self.assertEqual(len(cursor.executed), 1)
        params = cursor.executed[0][1]
        self.assertEqual(params[0], ["3986597205", "1000000000"])
        self.assertEqual(params[1], "google_ads")

    def test_dedupes_and_skips_blank_account_ids_before_query(self):
        store, cursor = self._build_store(rows=[])

        result = store.get_active_runs_progress_batch(
            platform="google_ads",
            account_ids=["", "3986597205", "3986597205", "  ", "111"],
        )

        self.assertEqual(result, [])
        self.assertEqual(len(cursor.executed), 1)
        params = cursor.executed[0][1]
        self.assertEqual(params[0], ["3986597205", "111"])


if __name__ == "__main__":
    unittest.main()
