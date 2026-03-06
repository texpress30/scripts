import os
import unittest
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover - dependency may be unavailable in sandbox
    psycopg = None


class DailyEntityFactsMigrationTests(unittest.TestCase):
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

    def test_fact_tables_exist_after_migrations(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  to_regclass(%s),
                  to_regclass(%s),
                  to_regclass(%s)
                """,
                (
                    f"{self._schema}.campaign_performance_reports",
                    f"{self._schema}.ad_group_performance_reports",
                    f"{self._schema}.ad_unit_performance_reports",
                ),
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        for value in row:
            self.assertIsNotNone(value)

    def test_fact_tables_enforce_daily_unique_keys(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO campaign_performance_reports(
                  platform, account_id, campaign_id, report_date
                ) VALUES (%s, %s, %s, %s)
                """,
                ("google_ads", "acct-1", "camp-1", "2026-01-10"),
            )
            with self.assertRaises(Exception):
                cursor.execute(
                    """
                    INSERT INTO campaign_performance_reports(
                      platform, account_id, campaign_id, report_date
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    ("google_ads", "acct-1", "camp-1", "2026-01-10"),
                )

            cursor.execute(
                """
                INSERT INTO ad_group_performance_reports(
                  platform, account_id, ad_group_id, report_date
                ) VALUES (%s, %s, %s, %s)
                """,
                ("google_ads", "acct-1", "ag-1", "2026-01-10"),
            )
            with self.assertRaises(Exception):
                cursor.execute(
                    """
                    INSERT INTO ad_group_performance_reports(
                      platform, account_id, ad_group_id, report_date
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    ("google_ads", "acct-1", "ag-1", "2026-01-10"),
                )

            cursor.execute(
                """
                INSERT INTO ad_unit_performance_reports(
                  platform, account_id, ad_id, report_date
                ) VALUES (%s, %s, %s, %s)
                """,
                ("google_ads", "acct-1", "ad-1", "2026-01-10"),
            )
            with self.assertRaises(Exception):
                cursor.execute(
                    """
                    INSERT INTO ad_unit_performance_reports(
                      platform, account_id, ad_id, report_date
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    ("google_ads", "acct-1", "ad-1", "2026-01-10"),
                )


if __name__ == "__main__":
    unittest.main()
