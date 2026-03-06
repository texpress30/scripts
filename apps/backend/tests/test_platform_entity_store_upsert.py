import os
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.platform_entity_store import (
    upsert_platform_ad_groups,
    upsert_platform_ads,
    upsert_platform_campaigns,
)


class PlatformEntityStoreUpsertTests(unittest.TestCase):
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

    def test_campaign_upsert_overwrites_fields(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "campaign_id": "camp-1",
            "name": "A",
            "status": "ENABLED",
            "raw_payload": {"name": "A"},
            "payload_hash": "h1",
        }
        written = upsert_platform_campaigns(self._conn, [row])
        self.assertEqual(written, 1)

        row["name"] = "B"
        row["status"] = "PAUSED"
        row["raw_payload"] = {"name": "B"}
        row["payload_hash"] = "h2"
        upsert_platform_campaigns(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT name, status, payload_hash
                FROM platform_campaigns
                WHERE platform=%s AND account_id=%s AND campaign_id=%s
                """,
                ("google_ads", "acct-1", "camp-1"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(found[0], "B")
        self.assertEqual(found[1], "PAUSED")
        self.assertEqual(found[2], "h2")

    def test_ad_group_upsert_overwrites_fields(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "ad_group_id": "ag-1",
            "campaign_id": "camp-1",
            "name": "A",
            "status": "ENABLED",
            "raw_payload": {"name": "A"},
            "payload_hash": "h1",
        }
        written = upsert_platform_ad_groups(self._conn, [row])
        self.assertEqual(written, 1)

        row["campaign_id"] = "camp-2"
        row["name"] = "B"
        row["status"] = "PAUSED"
        row["raw_payload"] = {"name": "B"}
        row["payload_hash"] = "h2"
        upsert_platform_ad_groups(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT campaign_id, name, status, payload_hash
                FROM platform_ad_groups
                WHERE platform=%s AND account_id=%s AND ad_group_id=%s
                """,
                ("google_ads", "acct-1", "ag-1"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(found[0], "camp-2")
        self.assertEqual(found[1], "B")
        self.assertEqual(found[2], "PAUSED")
        self.assertEqual(found[3], "h2")

    def test_ad_upsert_overwrites_fields(self):
        row = {
            "platform": "google_ads",
            "account_id": "acct-1",
            "ad_id": "ad-1",
            "ad_group_id": "ag-1",
            "campaign_id": "camp-1",
            "name": "A",
            "status": "ENABLED",
            "raw_payload": {"name": "A"},
            "payload_hash": "h1",
        }
        written = upsert_platform_ads(self._conn, [row])
        self.assertEqual(written, 1)

        row["ad_group_id"] = "ag-2"
        row["campaign_id"] = "camp-2"
        row["name"] = "B"
        row["status"] = "PAUSED"
        row["raw_payload"] = {"name": "B"}
        row["payload_hash"] = "h2"
        upsert_platform_ads(self._conn, [row])

        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ad_group_id, campaign_id, name, status, payload_hash
                FROM platform_ads
                WHERE platform=%s AND account_id=%s AND ad_id=%s
                """,
                ("google_ads", "acct-1", "ad-1"),
            )
            found = cursor.fetchone()

        self.assertIsNotNone(found)
        self.assertEqual(found[0], "ag-2")
        self.assertEqual(found[1], "camp-2")
        self.assertEqual(found[2], "B")
        self.assertEqual(found[3], "PAUSED")
        self.assertEqual(found[4], "h2")


if __name__ == "__main__":
    unittest.main()
