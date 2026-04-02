-- 0038: Add last_sync_at and product_count to feed_sources for display.

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS product_count INTEGER NOT NULL DEFAULT 0;
