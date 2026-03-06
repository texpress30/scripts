import os
from datetime import date
from pathlib import Path
import unittest
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from app.services.client_registry import ClientRegistryService
from app.services.platform_account_watermarks_store import upsert_platform_account_watermark


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


class PlatformAccountEntityWatermarksContractTests(unittest.TestCase):
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
            cursor.execute("DELETE FROM platform_account_watermarks")
            cursor.execute("DELETE FROM agency_account_client_mappings")
            cursor.execute("DELETE FROM agency_platform_accounts")

            cursor.execute(
                """
                INSERT INTO agency_platform_accounts(platform, account_id, account_name, imported_at)
                VALUES
                  ('google_ads', 'A', 'Account A', NOW()),
                  ('google_ads', 'B', 'Account B', NOW())
                """
            )

        upsert_platform_account_watermark(
            self._conn,
            platform="google_ads",
            account_id="A",
            grain="campaign_daily",
            sync_start_date=date(2024, 1, 9),
            historical_synced_through=date(2024, 1, 15),
        )

    def test_list_platform_accounts_includes_entity_watermarks_by_grain(self):
        service = ClientRegistryService()
        service._is_test_mode = lambda: False
        service._connect_or_raise = lambda: _ConnectionContext(self._conn, self._schema)

        rows = service.list_platform_accounts(platform="google_ads")
        self.assertEqual(len(rows), 2)

        by_id = {str(row.get("account_id")): row for row in rows}
        self.assertIn("A", by_id)
        self.assertIn("B", by_id)

        account_a = by_id["A"]
        account_b = by_id["B"]

        self.assertIn("sync_start_date", account_a)  # existing field preserved
        self.assertIn("entity_watermarks", account_a)

        self.assertIsNotNone(account_a["entity_watermarks"]["campaign_daily"])
        self.assertEqual(str(account_a["entity_watermarks"]["campaign_daily"]["sync_start_date"]), "2024-01-09")
        self.assertEqual(
            str(account_a["entity_watermarks"]["campaign_daily"]["historical_synced_through"]),
            "2024-01-15",
        )
        self.assertIsNone(account_a["entity_watermarks"]["ad_group_daily"])
        self.assertIsNone(account_a["entity_watermarks"]["ad_daily"])

        self.assertIsNone(account_b["entity_watermarks"]["campaign_daily"])
        self.assertIsNone(account_b["entity_watermarks"]["ad_group_daily"])
        self.assertIsNone(account_b["entity_watermarks"]["ad_daily"])


if __name__ == "__main__":
    unittest.main()
