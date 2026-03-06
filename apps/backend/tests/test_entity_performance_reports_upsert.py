import os
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.entity_performance_reports import (
    upsert_ad_group_performance_reports,
    upsert_ad_unit_performance_reports,
    upsert_campaign_performance_reports,
)


class EntityPerformanceReportsUpsertTests(unittest.TestCase):
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

    def test_campaign_upsert_overwrites_metrics_for_same_daily_key(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "campaign_id": "camp-1",
            "report_date": "2026-01-10",
            "spend": 1,
            "impressions": 100,
            "clicks": 5,
            "conversions": 1,
            "conversion_value": 10,
            "extra_metrics": {"v": 1},
            "source_window_start": "2026-01-01",
            "source_window_end": "2026-01-10",
            "source_job_id": "job-1",
        }
        written = upsert_campaign_performance_reports(self._conn, [row])
        self.assertEqual(written, 1)

        row["spend"] = 2
        row["clicks"] = 9
        row["extra_metrics"] = {"v": 2}
        upsert_campaign_performance_reports(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT spend, clicks, extra_metrics
                FROM campaign_performance_reports
                WHERE platform=%s AND account_id=%s AND campaign_id=%s AND report_date=%s
                """,
                ("google_ads", "acct-1", "camp-1", "2026-01-10"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(float(found[0]), 2.0)
        self.assertEqual(int(found[1]), 9)
        self.assertEqual(found[2].get("v"), 2)

    def test_ad_group_upsert_overwrites_metrics_for_same_daily_key(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "ad_group_id": "ag-1",
            "campaign_id": "camp-1",
            "report_date": "2026-01-10",
            "spend": 1,
            "impressions": 100,
            "clicks": 5,
            "conversions": 1,
            "conversion_value": 10,
            "extra_metrics": {"v": 1},
            "source_window_start": "2026-01-01",
            "source_window_end": "2026-01-10",
            "source_job_id": "job-1",
        }
        written = upsert_ad_group_performance_reports(self._conn, [row])
        self.assertEqual(written, 1)

        row["spend"] = 2
        row["clicks"] = 11
        row["extra_metrics"] = {"v": 3}
        upsert_ad_group_performance_reports(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT spend, clicks, extra_metrics
                FROM ad_group_performance_reports
                WHERE platform=%s AND account_id=%s AND ad_group_id=%s AND report_date=%s
                """,
                ("google_ads", "acct-1", "ag-1", "2026-01-10"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(float(found[0]), 2.0)
        self.assertEqual(int(found[1]), 11)
        self.assertEqual(found[2].get("v"), 3)

    def test_ad_unit_upsert_overwrites_metrics_for_same_daily_key(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "ad_id": "ad-1",
            "campaign_id": "camp-1",
            "ad_group_id": "ag-1",
            "report_date": "2026-01-10",
            "spend": 1,
            "impressions": 100,
            "clicks": 5,
            "conversions": 1,
            "conversion_value": 10,
            "extra_metrics": {"v": 1},
            "source_window_start": "2026-01-01",
            "source_window_end": "2026-01-10",
            "source_job_id": "job-1",
        }
        written = upsert_ad_unit_performance_reports(self._conn, [row])
        self.assertEqual(written, 1)

        row["spend"] = 2
        row["clicks"] = 13
        row["extra_metrics"] = {"v": 4}
        upsert_ad_unit_performance_reports(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT spend, clicks, extra_metrics
                FROM ad_unit_performance_reports
                WHERE platform=%s AND account_id=%s AND ad_id=%s AND report_date=%s
                """,
                ("google_ads", "acct-1", "ad-1", "2026-01-10"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(float(found[0]), 2.0)
        self.assertEqual(int(found[1]), 13)
        self.assertEqual(found[2].get("v"), 4)


if __name__ == "__main__":
    unittest.main()
