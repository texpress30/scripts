import os
import unittest
from pathlib import Path
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.entity_performance_reports import upsert_keyword_performance_reports
from app.services.platform_entity_store import upsert_platform_keywords


class KeywordStoreUpsertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ.get("DATABASE_URL")
        if psycopg is None or not database_url:
            raise unittest.SkipTest("psycopg/DATABASE_URL not available for keyword store DB tests")

        cls._schema = f"test_kw_store_{uuid4().hex[:10]}"
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

    def test_upsert_platform_keywords_overwrites_keyword_text(self):
        row = {
            "platform": "google_ads",
            "account_id": "3986597205",
            "keyword_id": "ag-1~crit-1",
            "campaign_id": "camp-1",
            "ad_group_id": "ag-1",
            "keyword_text": "initial text",
            "match_type": "EXACT",
            "status": "ENABLED",
            "raw_payload": {"criterion_id": "crit-1"},
            "payload_hash": "h1",
        }
        upsert_platform_keywords(self._conn, [row])

        row_update = dict(row)
        row_update["keyword_text"] = "updated text"
        row_update["payload_hash"] = "h2"
        upsert_platform_keywords(self._conn, [row_update])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT keyword_text, payload_hash
                FROM platform_keywords
                WHERE platform = %s AND account_id = %s AND keyword_id = %s
                """,
                ("google_ads", "3986597205", "ag-1~crit-1"),
            )
            row_db = cursor.fetchone()

        self.assertIsNotNone(row_db)
        self.assertEqual(row_db[0], "updated text")
        self.assertEqual(row_db[1], "h2")

    def test_upsert_keyword_performance_reports_overwrites_spend(self):
        base = {
            "platform": "google_ads",
            "account_id": "3986597205",
            "keyword_id": "ag-1~crit-2",
            "report_date": "2026-02-10",
            "campaign_id": "camp-1",
            "ad_group_id": "ag-1",
            "spend": 10.5,
            "impressions": 100,
            "clicks": 5,
            "conversions": 1.0,
            "conversion_value": 25.0,
            "extra_metrics": {"google_ads": {"cost_micros": 10500000}},
            "source_window_start": "2026-02-01",
            "source_window_end": "2026-02-11",
            "source_job_id": "job-1",
        }
        upsert_keyword_performance_reports(self._conn, [base])

        update = dict(base)
        update["spend"] = 42.75
        update["source_job_id"] = "job-2"
        upsert_keyword_performance_reports(self._conn, [update])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT spend, source_job_id
                FROM keyword_performance_reports
                WHERE platform = %s AND account_id = %s AND keyword_id = %s AND report_date = %s
                """,
                ("google_ads", "3986597205", "ag-1~crit-2", "2026-02-10"),
            )
            row_db = cursor.fetchone()

        self.assertIsNotNone(row_db)
        self.assertAlmostEqual(float(row_db[0]), 42.75, places=6)
        self.assertEqual(row_db[1], "job-2")


if __name__ == "__main__":
    unittest.main()
