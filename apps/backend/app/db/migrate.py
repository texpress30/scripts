from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # pragma: no cover - optional in some test envs
    psycopg = None


_ADVISORY_LOCK_KEY = 842270291337409120


def _default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "db" / "migrations"


def _ensure_schema_migrations_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def _list_migration_files(migrations_dir: Path) -> list[Path]:
    return sorted(path for path in migrations_dir.glob("*.sql") if path.is_file())


def _fetch_applied_ids(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM schema_migrations")
        rows = cur.fetchall() or []
    return {str(row[0]) for row in rows if row and row[0] is not None}


def apply_migrations(*, conn, migrations_dir: Path) -> list[str]:
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists() or not migrations_path.is_dir():
        raise RuntimeError(f"Migrations directory not found: {migrations_path}")

    _ensure_schema_migrations_table(conn)
    applied_ids = _fetch_applied_ids(conn)
    applied_now: list[str] = []

    for migration_file in _list_migration_files(migrations_path):
        migration_id = migration_file.name
        if migration_id in applied_ids:
            continue

        sql = migration_file.read_text(encoding="utf-8")
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("INSERT INTO schema_migrations(id) VALUES (%s)", (migration_id,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        applied_now.append(migration_id)
        applied_ids.add(migration_id)

    return applied_now


def run_migrations(*, database_url: str | None = None, migrations_dir: Path | None = None) -> list[str]:
    if psycopg is None:
        raise RuntimeError("psycopg is required to run database migrations")

    db_url = database_url or load_settings().database_url
    if not db_url:
        raise RuntimeError("DATABASE_URL is required to run migrations")

    target_dir = migrations_dir or _default_migrations_dir()

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
        try:
            return apply_migrations(conn=conn, migrations_dir=target_dir)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply SQL migrations")
    parser.add_argument("--database-url", default=None, help="Optional DATABASE_URL override")
    parser.add_argument("--migrations-dir", default=None, help="Optional migrations directory override")
    args = parser.parse_args(argv)

    migrations_dir = Path(args.migrations_dir) if args.migrations_dir else None

    try:
        applied = run_migrations(database_url=args.database_url, migrations_dir=migrations_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1

    if applied:
        print(f"Applied {len(applied)} migration(s):")
        for migration_id in applied:
            print(f" - {migration_id}")
    else:
        print("No pending migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
