#!/usr/bin/env bash
# Boot the dev stack via docker-compose, wait for Postgres + Redis to be
# ready, then run the rembg / Celery integration tests.
#
# Usage (from repo root):
#   ./scripts/run_integration_tests.sh
#
# Prerequisites:
#   - docker + docker-compose on PATH
#   - .env with STORAGE_S3_BUCKET / STORAGE_S3_REGION pointing at a MinIO
#     (or real S3) bucket the worker can write to
#   - a Python venv with the backend requirements installed for the host
#     side of the tests (rembg is loaded only inside the worker container)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Booting docker-compose stack"
docker compose up -d postgres redis backend worker-bgremoval worker-render

echo "==> Waiting for Postgres"
for _ in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Waiting for Redis"
for _ in $(seq 1 30); do
  if docker compose exec -T redis redis-cli ping | grep -q PONG; then
    break
  fi
  sleep 1
done

echo "==> Running migrations"
docker compose exec -T backend python -m app.db.migrate

echo "==> Running integration tests"
cd apps/backend
RUN_INTEGRATION=1 \
  DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/mcc}" \
  CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/1}" \
  CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/2}" \
  pytest tests/integration -v "$@"
