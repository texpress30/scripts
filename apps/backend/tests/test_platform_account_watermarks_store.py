import os
from datetime import date, datetime, timezone
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.platform_account_watermarks_store import (
    get_platform_account_watermark,
    upsert_platform_account_watermark,
)


class PlatformAccountWatermarksStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ.get("DATABASE_URL")
        if psycopg is None or not database_url:
            raise unittest.SkipTest("psycopg/DATABASE_URL not available for migration DB test")

        cls._schema = f"test_mig_{uuid4().hex[:10]}"
        cls._conn = psycopg.connect(database_url)
        cls._conn.autocommit = True

        with cls._conn.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA {cls._schema}")
            cursor.execute(f"SET search_path TO {cls._schema}, public")
            migrations_dir = Path(__file__).resolve().parents[1] / "db" / "migrations"
            for migration_path in sorted(migrations_dir.glob("*.sql")):
                cursor.execute(migration_path.read_text())

    @classmethod
    def tearDownClass(cls):
        conn = getattr(cls, "_conn", None)
        schema = getattr(cls, "_schema", None)
        if conn is not None and schema:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            conn.close()

    def setUp(self):
        with self._conn.cursor() as cursor:
            cursor.execute(f"SET search_path TO {self._schema}, public")

    def test_insert_new_watermark_row(self):
        result = upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="acct-1",
            grain="campaign_daily",
            sync_start_date=date(2024, 1, 1),
            historical_synced_through=date(2024, 2, 1),
            rolling_synced_through=date(2024, 2, 10),
            last_success_at=datetime(2024, 2, 10, tzinfo=timezone.utc),
            last_error="boom",
            last_job_id="job-1",
        )

        self.assertEqual(result["platform"], "google_ads")
        self.assertEqual(result["account_id"], "acct-1")
        self.assertEqual(result["grain"], "campaign_daily")
        self.assertEqual(result["sync_start_date"], date(2024, 1, 1))
        self.assertEqual(result["historical_synced_through"], date(2024, 2, 1))

        fetched = get_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="acct-1",
            grain="campaign_daily",
        )
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["last_job_id"], "job-1")

    def test_non_regression_and_forward_progress_rules(self):
        upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="acct-2",
            grain="ad_group_daily",
            sync_start_date=date(2024, 1, 10),
            historical_synced_through=date(2024, 3, 10),
            rolling_synced_through=date(2024, 3, 20),
            last_success_at=datetime(2024, 3, 20, tzinfo=timezone.utc),
            last_error="old-error",
            last_job_id="job-1",
        )

        # Attempt regressions (later sync_start_date, earlier synced_through/success)
        regressed = upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="acct-2",
            grain="ad_group_daily",
            sync_start_date=date(2024, 1, 15),
            historical_synced_through=date(2024, 3, 1),
            rolling_synced_through=date(2024, 3, 1),
            last_success_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(regressed["sync_start_date"], date(2024, 1, 10))
        self.assertEqual(regressed["historical_synced_through"], date(2024, 3, 10))
        self.assertEqual(regressed["rolling_synced_through"], date(2024, 3, 20))
        self.assertEqual(regressed["last_success_at"], datetime(2024, 3, 20, tzinfo=timezone.utc))
        self.assertEqual(regressed["last_error"], "old-error")
        self.assertEqual(regressed["last_job_id"], "job-1")

        # Advance values and overwrite mutable fields when provided.
        advanced = upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="acct-2",
            grain="ad_group_daily",
            sync_start_date=date(2024, 1, 5),
            historical_synced_through=date(2024, 3, 25),
            rolling_synced_through=date(2024, 3, 26),
            last_success_at=datetime(2024, 3, 26, tzinfo=timezone.utc),
            last_error="new-error",
            last_job_id="job-2",
        )

        self.assertEqual(advanced["sync_start_date"], date(2024, 1, 5))
        self.assertEqual(advanced["historical_synced_through"], date(2024, 3, 25))
        self.assertEqual(advanced["rolling_synced_through"], date(2024, 3, 26))
        self.assertEqual(advanced["last_success_at"], datetime(2024, 3, 26, tzinfo=timezone.utc))
        self.assertEqual(advanced["last_error"], "new-error")
        self.assertEqual(advanced["last_job_id"], "job-2")


if __name__ == "__main__":
    unittest.main()
