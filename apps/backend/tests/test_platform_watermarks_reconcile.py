import os
from datetime import date
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.platform_account_watermarks_store import get_platform_account_watermark, upsert_platform_account_watermark
from app.services.platform_watermarks_reconcile import (
    derive_fact_coverage_by_account,
    reconcile_platform_account_watermarks_from_facts,
)


class PlatformWatermarksReconcileTests(unittest.TestCase):
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
            cursor.execute("TRUNCATE campaign_performance_reports, platform_account_watermarks")

    def _insert_campaign_fact(self, *, account_id: str, campaign_id: str, report_date: str) -> None:
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO campaign_performance_reports(
                  platform, account_id, campaign_id, report_date,
                  spend, impressions, clicks, conversions, conversion_value, extra_metrics
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                ("google_ads", account_id, campaign_id, report_date, 0, 0, 0, 0, 0, "{}"),
            )

    def test_derive_fact_coverage_by_account_includes_accounts_without_data(self):
        self._insert_campaign_fact(account_id="A", campaign_id="c1", report_date="2024-01-09")
        self._insert_campaign_fact(account_id="A", campaign_id="c2", report_date="2024-01-15")

        coverage = derive_fact_coverage_by_account(
            self._conn,
            platform="google_ads",
            account_ids=["A", "B"],
            grain="campaign_daily",
        )

        self.assertEqual(len(coverage), 2)
        a = coverage[0]
        b = coverage[1]
        self.assertEqual(a["account_id"], "A")
        self.assertEqual(str(a["min_date"]), "2024-01-09")
        self.assertEqual(str(a["max_date"]), "2024-01-15")
        self.assertGreater(a["row_count"], 0)

        self.assertEqual(b["account_id"], "B")
        self.assertIsNone(b["min_date"])
        self.assertIsNone(b["max_date"])
        self.assertEqual(b["row_count"], 0)

    def test_reconcile_writes_watermarks_only_for_accounts_with_data(self):
        self._insert_campaign_fact(account_id="A", campaign_id="c1", report_date="2024-01-09")
        self._insert_campaign_fact(account_id="A", campaign_id="c2", report_date="2024-01-15")

        summary = reconcile_platform_account_watermarks_from_facts(
            self._conn,
            platform="google_ads",
            account_ids=["A", "B"],
            grains=["campaign_daily"],
        )

        self.assertEqual(summary["updated_count_by_grain"]["campaign_daily"], 1)
        self.assertEqual(summary["skipped_no_data_by_grain"]["campaign_daily"], 1)

        a = get_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="A",
            grain="campaign_daily",
        )
        self.assertIsNotNone(a)
        self.assertEqual(str(a["sync_start_date"]), "2024-01-09")
        self.assertEqual(str(a["historical_synced_through"]), "2024-01-15")

        b = get_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="B",
            grain="campaign_daily",
        )
        self.assertIsNone(b)

    def test_reconcile_respects_non_regression(self):
        self._insert_campaign_fact(account_id="A", campaign_id="c1", report_date="2024-01-09")
        self._insert_campaign_fact(account_id="A", campaign_id="c2", report_date="2024-01-15")

        upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="A",
            grain="campaign_daily",
            sync_start_date=date(2024, 1, 1),
            historical_synced_through=date(2024, 2, 1),
        )

        reconcile_platform_account_watermarks_from_facts(
            self._conn,
            platform="google_ads",
            account_ids=["A"],
            grains=["campaign_daily"],
        )

        a = get_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="A",
            grain="campaign_daily",
        )
        self.assertIsNotNone(a)
        self.assertEqual(str(a["sync_start_date"]), "2024-01-01")
        self.assertEqual(str(a["historical_synced_through"]), "2024-02-01")


if __name__ == "__main__":
    unittest.main()
