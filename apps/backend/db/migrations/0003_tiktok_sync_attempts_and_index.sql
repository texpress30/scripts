ALTER TABLE tiktok_sync_snapshots
ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_tiktok_sync_snapshots_synced_at
ON tiktok_sync_snapshots (synced_at DESC);
