CREATE TABLE IF NOT EXISTS sync_state (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  grain TEXT NOT NULL,
  last_status TEXT NULL,
  last_job_id TEXT NULL,
  last_attempted_at TIMESTAMPTZ NULL,
  last_successful_at TIMESTAMPTZ NULL,
  last_successful_date DATE NULL,
  error TEXT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT sync_state_pkey PRIMARY KEY (platform, account_id, grain),
  CONSTRAINT sync_state_platform_non_empty_check CHECK (length(platform) > 0),
  CONSTRAINT sync_state_account_id_non_empty_check CHECK (length(account_id) > 0),
  CONSTRAINT sync_state_grain_non_empty_check CHECK (length(grain) > 0)
);

CREATE INDEX IF NOT EXISTS idx_sync_state_last_status
ON sync_state (last_status);

CREATE INDEX IF NOT EXISTS idx_sync_state_platform_updated_at
ON sync_state (platform, updated_at DESC);
