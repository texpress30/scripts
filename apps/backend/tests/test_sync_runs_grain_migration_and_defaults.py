import os
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.sync_runs_store import sync_runs_store


class _ConnectionContext:
    def __init__(self, conn, schema: str):
        self._conn = conn
        self._schema = schema

    def __enter__(self):
        with self._conn.cursor() as cursor:
            cursor.execute(f"SET search_path TO {self._schema}, public")
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        return False


class SyncRunsGrainMigrationAndDefaultsTests(unittest.TestCase):
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

        # Ensure runtime schema hardening in store is applied in isolated schema.
        original_connect = sync_runs_store._connect
        original_schema_initialized = sync_runs_store._schema_initialized
        sync_runs_store._connect = lambda: _ConnectionContext(cls._conn, cls._schema)
        sync_runs_store._schema_initialized = False
        try:
            sync_runs_store._ensure_schema()
        finally:
            sync_runs_store._connect = original_connect
            sync_runs_store._schema_initialized = original_schema_initialized

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
            cursor.execute("DELETE FROM sync_runs")

    def test_sync_runs_grain_column_exists(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'sync_runs'
                  AND column_name = 'grain'
                """,
                (self._schema,),
            )
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "grain")
        self.assertEqual(row[1], "NO")
        self.assertIn("account_daily", str(row[2]))

    def test_sync_runs_grain_defaults_to_account_daily(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sync_runs(job_id, platform, status, date_start, date_end, chunk_days)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                ("job-default-grain", "google_ads", "queued", "2024-01-01", "2024-01-07", 7),
            )
            cursor.execute("SELECT grain FROM sync_runs WHERE job_id = %s", ("job-default-grain",))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "account_daily")

    def test_sync_runs_accepts_explicit_entity_grain(self):
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sync_runs(job_id, platform, status, date_start, date_end, chunk_days, grain)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                ("job-campaign-grain", "google_ads", "queued", "2024-01-01", "2024-01-07", 7, "campaign_daily"),
            )
            cursor.execute("SELECT grain FROM sync_runs WHERE job_id = %s", ("job-campaign-grain",))
            row = cursor.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "campaign_daily")


if __name__ == "__main__":
    unittest.main()
