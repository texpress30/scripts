CREATE TABLE IF NOT EXISTS sync_runs (
  job_id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  status TEXT NOT NULL,
  client_id BIGINT NULL,
  account_id TEXT NULL,
  date_start DATE NOT NULL,
  date_end DATE NOT NULL,
  chunk_days INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ NULL,
  finished_at TIMESTAMPTZ NULL,
  error TEXT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT sync_runs_date_range_check CHECK (date_end >= date_start),
  CONSTRAINT sync_runs_chunk_days_check CHECK (chunk_days > 0)
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_status
ON sync_runs (status);

CREATE INDEX IF NOT EXISTS idx_sync_runs_platform_created_at
ON sync_runs (platform, created_at DESC);
