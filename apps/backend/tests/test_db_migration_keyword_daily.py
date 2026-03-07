import os
import unittest
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover - dependency may be unavailable in sandbox
    psycopg = None


class KeywordDailyMigrationTests(unittest.TestCase):
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

    def test_keyword_tables_exist(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  to_regclass(%s),
                  to_regclass(%s)
                """,
                (
                    f"{self._schema}.platform_keywords",
                    f"{self._schema}.keyword_performance_reports",
                ),
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertIsNotNone(row[0])
        self.assertIsNotNone(row[1])

    def test_keyword_fact_parent_is_partitioned_and_has_expected_partitions(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT relkind
                FROM pg_class
                WHERE oid = to_regclass(%s)
                """,
                (f"{self._schema}.keyword_performance_reports",),
            )
            relkind = (cursor.fetchone() or [None])[0]

            cursor.execute(
                """
                SELECT
                  to_regclass(%s),
                  to_regclass(%s)
                """,
                (
                    f"{self._schema}.keyword_performance_reports_default",
                    f"{self._schema}.keyword_performance_reports_2024_01",
                ),
            )
            partitions = cursor.fetchone()

        self.assertEqual(relkind, "p")
        self.assertIsNotNone(partitions)
        self.assertIsNotNone(partitions[0])
        self.assertIsNotNone(partitions[1])

    def test_grain_checks_accept_keyword_daily(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO platform_account_watermarks(platform, account_id, grain)
                VALUES (%s, %s, %s)
                """,
                ("google_ads", "acc-kw-1", "keyword_daily"),
            )

            cursor.execute(
                """
                INSERT INTO sync_runs(
                  job_id,
                  platform,
                  status,
                  client_id,
                  account_id,
                  date_start,
                  date_end,
                  chunk_days,
                  metadata,
                  job_type,
                  grain,
                  chunks_total,
                  chunks_done,
                  rows_written
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                """,
                (
                    f"job-{uuid4().hex[:10]}",
                    "google_ads",
                    "queued",
                    1,
                    "acc-kw-1",
                    "2026-01-01",
                    "2026-01-07",
                    7,
                    "{}",
                    "historical_backfill",
                    "keyword_daily",
                    1,
                    0,
                    0,
                ),
            )


if __name__ == "__main__":
    unittest.main()
