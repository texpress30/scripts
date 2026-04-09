-- 0058: Rename the ``shift4shop`` enum value on ``feed_source_type`` to
-- ``cart_storefront``.
--
-- PR #950 added a "Shift4Shop / 3dcart" option to the
-- ``FeedSourceType`` enum + DB enum (migration 0057), but the platform
-- DataFeedWatch lists as "Cart Storefront" is actually Cart.com — a
-- different vendor than Shift4Shop. This migration brings the DB enum
-- in lockstep with the corrected Python source of truth so any rows
-- created with ``source_type='shift4shop'`` are seamlessly carried over
-- to ``source_type='cart_storefront'``.
--
-- ``ALTER TYPE … RENAME VALUE`` was added in PostgreSQL 10 and is
-- transactional in PostgreSQL 12+, so it runs cleanly inside the
-- migration runner's per-file transaction (we target PostgreSQL 16 in
-- ``docker-compose.yml``). The rename is purely metadata — existing
-- ``feed_sources`` rows store the enum's internal oid, not the label,
-- so no separate UPDATE is required.
--
-- The DO block keeps the migration idempotent across all three states
-- this hotfix may encounter:
--
--   1. Production / staging where 0057 already added ``shift4shop`` and
--      ``cart_storefront`` does not exist yet → rename the value.
--   2. Environments that re-ran 0057 (or this file) and already have
--      ``cart_storefront`` → no-op.
--   3. Fresh DBs where neither label exists (defensive — should not
--      happen because 0057 always runs first) → add ``cart_storefront``
--      so the application enum stays satisfied.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_enum e
        JOIN pg_type t ON e.enumtypid = t.oid
        WHERE t.typname = 'feed_source_type'
          AND e.enumlabel = 'cart_storefront'
    ) THEN
        IF EXISTS (
            SELECT 1
            FROM pg_enum e
            JOIN pg_type t ON e.enumtypid = t.oid
            WHERE t.typname = 'feed_source_type'
              AND e.enumlabel = 'shift4shop'
        ) THEN
            ALTER TYPE feed_source_type RENAME VALUE 'shift4shop' TO 'cart_storefront';
        ELSE
            ALTER TYPE feed_source_type ADD VALUE 'cart_storefront';
        END IF;
    END IF;
END
$$;
