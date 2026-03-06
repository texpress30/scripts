from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.db import migrate


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._fetchall_rows = []

    def execute(self, query, params=None):
        q = str(query)
        self.conn.executed.append((q, params))
        if "SELECT id FROM schema_migrations" in q:
            self._fetchall_rows = [(item,) for item in sorted(self.conn.applied_ids)]
        elif "INSERT INTO schema_migrations(id) VALUES (%s)" in q and params is not None:
            self.conn.applied_ids.add(str(params[0]))

    def executemany(self, query, seq_of_params):
        q = str(query)
        params_list = list(seq_of_params)
        self.conn.executed_many.append((q, params_list))
        if "INSERT INTO schema_migrations(id) VALUES (%s)" in q:
            for params in params_list:
                self.conn.applied_ids.add(str(params[0]))

    def fetchall(self):
        return list(self._fetchall_rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, applied_ids: set[str] | None = None):
        self.applied_ids = set(applied_ids or set())
        self.executed: list[tuple[str, tuple | None]] = []
        self.executed_many: list[tuple[str, list[tuple]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commit_calls += 1

    def rollback(self):
        self.rollback_calls += 1


class MigrationBaselineTests(unittest.TestCase):
    def test_baseline_inserts_only_legacy_migrations_when_schema_migrations_empty(self):
        conn = _FakeConn(applied_ids=set())
        migration_ids = ["0001_init.sql", "0014_sync.sql", "0015_entities.sql", "0016_facts.sql"]

        applied_ids = migrate._apply_baseline_if_needed(
            conn,
            migration_ids=migration_ids,
            applied_ids=set(),
            baseline_before="0015_",
        )

        self.assertEqual(applied_ids, {"0001_init.sql", "0014_sync.sql"})
        self.assertEqual(len(conn.executed_many), 1)
        inserted = [item[0] for item in conn.executed_many[0][1]]
        self.assertEqual(inserted, ["0001_init.sql", "0014_sync.sql"])

    def test_baseline_noop_when_schema_migrations_has_existing_entries(self):
        conn = _FakeConn(applied_ids={"0001_init.sql"})
        migration_ids = ["0001_init.sql", "0014_sync.sql", "0015_entities.sql"]

        applied_ids = migrate._apply_baseline_if_needed(
            conn,
            migration_ids=migration_ids,
            applied_ids={"0001_init.sql"},
            baseline_before="0015_",
        )

        self.assertEqual(applied_ids, {"0001_init.sql"})
        self.assertEqual(conn.executed_many, [])

    def test_apply_migrations_keeps_newer_migrations_unapplied_for_normal_flow(self):
        with tempfile.TemporaryDirectory(prefix="baseline_migrations_") as tmp:
            migrations_dir = Path(tmp)
            (migrations_dir / "0001_init.sql").write_text("SELECT 1;", encoding="utf-8")
            (migrations_dir / "0014_sync.sql").write_text("SELECT 2;", encoding="utf-8")
            (migrations_dir / "0015_entities.sql").write_text("SELECT 3;", encoding="utf-8")
            (migrations_dir / "0016_facts.sql").write_text("SELECT 4;", encoding="utf-8")

            conn = _FakeConn(applied_ids=set())
            applied_now = migrate.apply_migrations(
                conn=conn,
                migrations_dir=migrations_dir,
                baseline_before="0015_",
            )

        self.assertEqual(applied_now, ["0015_entities.sql", "0016_facts.sql"])
        self.assertIn("0015_entities.sql", conn.applied_ids)
        self.assertIn("0016_facts.sql", conn.applied_ids)
        self.assertIn("0014_sync.sql", conn.applied_ids)


if __name__ == "__main__":
    unittest.main()
