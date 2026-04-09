-- 0057: Add 6 new e-commerce platform values to the feed_source_type enum.
--
-- The application-side ``FeedSourceType`` Python enum was extended in
-- the same PR with six new platform stubs (PrestaShop, OpenCart,
-- Shopware, Lightspeed, Volusion, Shift4Shop). However ``feed_sources.
-- source_type`` is a real PostgreSQL ENUM declared in
-- ``0033_feed_sources_schema.sql`` with only the original 8 values, so
-- any INSERT of one of the new types fails immediately with:
--
--     invalid input value for enum feed_source_type: "prestashop"
--
-- This migration brings the database enum back in lockstep with the
-- Python source of truth. ``ALTER TYPE … ADD VALUE`` is supported
-- inside a transaction block since PostgreSQL 12 — the only restriction
-- is that the new label can't be referenced in the same transaction
-- (we're only adding the labels here, no INSERT, so we're fine).
--
-- ``IF NOT EXISTS`` is used so the migration is idempotent and can run
-- on environments where a previous out-of-band ALTER TYPE has already
-- backfilled some of the values.

ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'prestashop';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'opencart';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'shopware';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'lightspeed';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'volusion';
ALTER TYPE feed_source_type ADD VALUE IF NOT EXISTS 'shift4shop';
