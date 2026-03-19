from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # pragma: no cover - optional in some test envs
    psycopg = None


_ADVISORY_LOCK_KEY = 842270291337409120


def _candidate_migrations_dirs(*, cli_migrations_dir: Path | None = None) -> list[Path]:
    if cli_migrations_dir is not None:
        return [Path(cli_migrations_dir)]

    file_based = Path(__file__).resolve().parents[2] / "db" / "migrations"
    return [
        Path("db/migrations"),
        Path("apps/backend/db/migrations"),
        file_based,
    ]


def resolve_migrations_dir(*, cli_migrations_dir: Path | None = None) -> Path:
    candidates = _candidate_migrations_dirs(cli_migrations_dir=cli_migrations_dir)
    tried: list[str] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        tried.append(str(resolved))
        if resolved.exists() and resolved.is_dir():
            return resolved

    cwd = Path(os.getcwd()).resolve()
    raise SystemExit(
        "Migrations directory not found. "
        f"cwd={cwd}. "
        "Tried candidates: " + ", ".join(tried)
    )


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




def _compute_baseline_ids(*, migration_ids: list[str], baseline_before: str) -> list[str]:
    return sorted(migration_id for migration_id in migration_ids if migration_id < str(baseline_before))


def _apply_baseline_if_needed(
    conn,
    *,
    migration_ids: list[str],
    applied_ids: set[str],
    baseline_before: str | None,
) -> set[str]:
    if baseline_before is None:
        return set(applied_ids)
    if len(applied_ids) > 0:
        return set(applied_ids)

    baseline_ids = _compute_baseline_ids(migration_ids=migration_ids, baseline_before=baseline_before)
    if len(baseline_ids) <= 0:
        return set(applied_ids)

    try:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO schema_migrations(id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                [(migration_id,) for migration_id in baseline_ids],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return set(applied_ids).union(baseline_ids)

def apply_migrations(*, conn, migrations_dir: Path, baseline_before: str | None = None) -> list[str]:
    migrations_path = Path(migrations_dir)
    if not migrations_path.exists() or not migrations_path.is_dir():
        raise RuntimeError(f"Migrations directory not found: {migrations_path}")

    migration_files = _list_migration_files(migrations_path)
    migration_ids = [migration_file.name for migration_file in migration_files]

    _ensure_schema_migrations_table(conn)
    applied_ids = _fetch_applied_ids(conn)
    applied_ids = _apply_baseline_if_needed(
        conn,
        migration_ids=migration_ids,
        applied_ids=applied_ids,
        baseline_before=baseline_before,
    )
    applied_now: list[str] = []

    for migration_file in migration_files:
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


def run_migrations(*, database_url: str | None = None, migrations_dir: Path | None = None, baseline_before: str | None = None) -> list[str]:
    if psycopg is None:
        raise RuntimeError("psycopg is required to run database migrations")

    db_url = database_url or load_settings().database_url
    if not db_url:
        raise RuntimeError("DATABASE_URL is required to run migrations")

    target_dir = resolve_migrations_dir(cli_migrations_dir=migrations_dir)

    max_retries = 15
    for attempt in range(max_retries):
        try:
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
                try:
                    return apply_migrations(conn=conn, migrations_dir=target_dir, baseline_before=baseline_before)
                finally:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))
            break
        except Exception as e:
            if "timeout" in str(e).lower() or attempt < max_retries - 1:
                import time
                print(f"DB Connection failed: {e}. Retrying {attempt+1}/{max_retries} in 5s...", file=sys.stderr)
                time.sleep(5)
                if attempt == max_retries - 1:
                    raise
            else:
                raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply SQL migrations")
    parser.add_argument("--database-url", default=None, help="Optional DATABASE_URL override")
    parser.add_argument("--migrations-dir", default=None, help="Optional migrations directory override")
    parser.add_argument("--baseline-before", default=None, help="Mark legacy migrations (< this id) as applied when schema_migrations is empty")
    args = parser.parse_args(argv)

    migrations_dir = Path(args.migrations_dir) if args.migrations_dir else None

    try:
        applied = run_migrations(database_url=args.database_url, migrations_dir=migrations_dir, baseline_before=args.baseline_before)
    except SystemExit as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        return 1
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
