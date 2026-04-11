"""Integration tests that require real infrastructure (Redis, Celery, rembg,
Postgres, Mongo, S3-compatible storage).

These tests are skipped by default so `pytest` on a laptop without the full
stack stays fast. Run them explicitly with::

    pytest tests/integration -m integration

or via the helper script::

    scripts/run_integration_tests.sh
"""
