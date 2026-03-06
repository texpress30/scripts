import unittest
from datetime import date

from app.services.sync_runs_store import SyncRunsStore


class _FakeCursor:
    def __init__(self, fetches):
        self._fetches = list(fetches)
        self.executed: list[tuple[str, tuple | None]] = []

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchone(self):
        if self._fetches:
            return self._fetches.pop(0)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, cursor: _FakeCursor):
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


class SyncRunsStoreDedupeTests(unittest.TestCase):
    def _build_store(self, *, fetches):
        store = SyncRunsStore()
        store._ensure_schema = lambda: None
        fake_cursor = _FakeCursor(fetches)
        fake_conn = _FakeConn(fake_cursor)
        store._connect = lambda: fake_conn
        return store, fake_cursor, fake_conn

    def test_returns_existing_active_historical_run_without_insert(self):
        existing_row = (
            "job-existing",
            "google_ads",
            "running",
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
            2,
            1,
            5,
        )
        store, cursor, conn = self._build_store(fetches=[existing_row])

        result = store.create_historical_sync_run_if_not_active(
            job_id="job-new",
            platform="google_ads",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            chunk_days=7,
            client_id=11,
            account_id="3986597205",
            metadata={"source": "manual"},
            batch_id="batch-2",
            grain="account_daily",
            chunks_total=2,
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["run"]["job_id"], "job-existing")
        self.assertEqual(conn.commit_calls, 1)
        self.assertTrue(any("pg_advisory_xact_lock" in query for query, _ in cursor.executed))
        self.assertFalse(any("INSERT INTO sync_runs" in query for query, _ in cursor.executed))
        lock_params = next(params for query, params in cursor.executed if "pg_advisory_xact_lock" in query)
        self.assertIn("account_daily", str(lock_params[0]))

    def test_creates_new_historical_run_when_no_active_duplicate(self):
        created_row = (
            "job-new",
            "google_ads",
            "queued",
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
            "batch-2",
            "historical_backfill",
            "account_daily",
            2,
            0,
            0,
        )
        store, cursor, conn = self._build_store(fetches=[None, created_row])

        result = store.create_historical_sync_run_if_not_active(
            job_id="job-new",
            platform="google_ads",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            chunk_days=7,
            client_id=11,
            account_id="3986597205",
            metadata={"source": "manual"},
            batch_id="batch-2",
            grain="account_daily",
            chunks_total=2,
        )

        self.assertTrue(result["created"])
        self.assertEqual(result["run"]["job_id"], "job-new")
        self.assertEqual(result["run"]["job_type"], "historical_backfill")
        self.assertEqual(conn.commit_calls, 1)
        self.assertTrue(any("INSERT INTO sync_runs" in query for query, _ in cursor.executed))
        self.assertFalse(any("{_SYNC_RUNS_SELECT_COLUMNS}" in query for query, _ in cursor.executed))

    def test_dedupe_lookup_includes_grain_filter(self):
        created_row = (
            "job-new-campaign",
            "google_ads",
            "queued",
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
            "batch-2",
            "historical_backfill",
            "campaign_daily",
            2,
            0,
            0,
        )
        store, cursor, _ = self._build_store(fetches=[None, created_row])

        result = store.create_historical_sync_run_if_not_active(
            job_id="job-new-campaign",
            platform="google_ads",
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 7),
            chunk_days=7,
            client_id=11,
            account_id="3986597205",
            metadata={"source": "manual"},
            batch_id="batch-2",
            grain="campaign_daily",
            chunks_total=2,
        )

        self.assertTrue(result["created"])
        select_params = next(params for query, params in cursor.executed if "FROM sync_runs" in query)
        self.assertEqual(select_params[2], "campaign_daily")


if __name__ == "__main__":
    unittest.main()
