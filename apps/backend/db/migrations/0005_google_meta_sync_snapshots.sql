CREATE TABLE IF NOT EXISTS google_sync_snapshots (
  client_id INTEGER PRIMARY KEY,
  spend NUMERIC(14,2) NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  conversions INTEGER NOT NULL DEFAULT 0,
  revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_google_sync_snapshots_synced_at
ON google_sync_snapshots (synced_at DESC);

CREATE TABLE IF NOT EXISTS meta_sync_snapshots (
  client_id INTEGER PRIMARY KEY,
  spend NUMERIC(14,2) NOT NULL DEFAULT 0,
  impressions INTEGER NOT NULL DEFAULT 0,
  clicks INTEGER NOT NULL DEFAULT 0,
  conversions INTEGER NOT NULL DEFAULT 0,
  revenue NUMERIC(14,2) NOT NULL DEFAULT 0,
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meta_sync_snapshots_synced_at
ON meta_sync_snapshots (synced_at DESC);
