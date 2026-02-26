# Slice 8.2.4 — Postgres persistence alignment for TikTok

## Scope
- TikTok sync persistence moved from SQLite runtime storage to the primary Postgres database (`DATABASE_URL`).
- Added Postgres migration for hardening fields (`attempts`) and sync-time index.
- Removed SQLite-specific config and test wiring (`TIKTOK_SYNC_DB_PATH`).
- Added `psycopg[binary]` dependency for Postgres connectivity.

## Notes
- In `APP_ENV=test`, repository uses an in-memory fallback to keep unit/E2E tests deterministic without requiring a live Postgres instance in CI sandbox.
- Production/runtime path now writes and reads TikTok snapshots from Postgres.
