from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.db import migrate


class MigrationResolverTests(unittest.TestCase):
    def test_resolver_prefers_db_migrations_when_cwd_is_apps_backend(self):
        with tempfile.TemporaryDirectory(prefix="resolver_") as tmp:
            root = Path(tmp)
            backend_root = root / "apps" / "backend"
            (backend_root / "db" / "migrations").mkdir(parents=True)
            (backend_root / "app" / "db").mkdir(parents=True)
            fake_migrate_file = backend_root / "app" / "db" / "migrate.py"
            fake_migrate_file.write_text("# fake", encoding="utf-8")

            original_cwd = Path.cwd()
            original_file = migrate.__file__
            try:
                migrate.__file__ = str(fake_migrate_file)
                import os

                os.chdir(backend_root)
                resolved = migrate.resolve_migrations_dir()
            finally:
                migrate.__file__ = original_file
                os.chdir(original_cwd)

            self.assertEqual(resolved, (backend_root / "db" / "migrations").resolve())

    def test_resolver_error_includes_cwd_and_tried_candidates(self):
        with tempfile.TemporaryDirectory(prefix="resolver_missing_") as tmp:
            root = Path(tmp)
            backend_root = root / "apps" / "backend"
            (backend_root / "app" / "db").mkdir(parents=True)
            fake_migrate_file = backend_root / "app" / "db" / "migrate.py"
            fake_migrate_file.write_text("# fake", encoding="utf-8")

            original_cwd = Path.cwd()
            original_file = migrate.__file__
            try:
                migrate.__file__ = str(fake_migrate_file)
                import os

                os.chdir(backend_root)
                with self.assertRaises(SystemExit) as ctx:
                    migrate.resolve_migrations_dir()
            finally:
                migrate.__file__ = original_file
                os.chdir(original_cwd)

            msg = str(ctx.exception)
            self.assertIn("cwd=", msg)
            self.assertIn("Tried candidates:", msg)


if __name__ == "__main__":
    unittest.main()
