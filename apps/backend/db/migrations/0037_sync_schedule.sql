-- 0037: Add sync scheduling columns to feed_sources.

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS sync_schedule VARCHAR(20) NOT NULL DEFAULT 'manual';
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS next_scheduled_sync TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_feed_sources_next_sync
    ON feed_sources(next_scheduled_sync)
    WHERE sync_schedule != 'manual' AND next_scheduled_sync IS NOT NULL;
