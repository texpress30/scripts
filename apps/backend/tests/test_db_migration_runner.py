import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from app.db import migrate

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None


class MigrationRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ.get("DATABASE_URL")
        if psycopg is None or not database_url:
            raise unittest.SkipTest("psycopg/DATABASE_URL not available for migration runner DB test")
        cls._database_url = database_url

    def test_runner_creates_schema_migrations_and_is_idempotent(self):
        schema_name = f"test_runner_{uuid4().hex[:10]}"
        migration_name = f"9999_runner_test_{uuid4().hex[:8]}.sql"

        with tempfile.TemporaryDirectory(prefix="migrations_") as tmp:
            migrations_dir = Path(tmp)
            migration_sql = (
                f"CREATE SCHEMA IF NOT EXISTS {schema_name};\n"
                f"CREATE TABLE {schema_name}.runner_check (id INT PRIMARY KEY);\n"
                f"INSERT INTO {schema_name}.runner_check(id) VALUES (1);\n"
            )
            (migrations_dir / migration_name).write_text(migration_sql, encoding="utf-8")

            applied_first = migrate.run_migrations(database_url=self._database_url, migrations_dir=migrations_dir)
            self.assertEqual(applied_first, [migration_name])

            with psycopg.connect(self._database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass(%s)", (f"{schema_name}.runner_check",))
                    self.assertEqual(cur.fetchone()[0], f"{schema_name}.runner_check")

                    cur.execute("SELECT COUNT(*) FROM schema_migrations WHERE id = %s", (migration_name,))
                    self.assertEqual(int(cur.fetchone()[0]), 1)

                    cur.execute(f"SELECT COUNT(*) FROM {schema_name}.runner_check")
                    self.assertEqual(int(cur.fetchone()[0]), 1)

            applied_second = migrate.run_migrations(database_url=self._database_url, migrations_dir=migrations_dir)
            self.assertEqual(applied_second, [])

            with psycopg.connect(self._database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM schema_migrations WHERE id = %s", (migration_name,))
                    self.assertEqual(int(cur.fetchone()[0]), 1)
                    cur.execute(f"SELECT COUNT(*) FROM {schema_name}.runner_check")
                    self.assertEqual(int(cur.fetchone()[0]), 1)
                    cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                conn.commit()


if __name__ == "__main__":
    unittest.main()
