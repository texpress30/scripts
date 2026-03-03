ALTER TABLE sync_runs
  ADD COLUMN IF NOT EXISTS batch_id TEXT NULL,
  ADD COLUMN IF NOT EXISTS job_type TEXT NULL,
  ADD COLUMN IF NOT EXISTS grain TEXT NULL,
  ADD COLUMN IF NOT EXISTS chunks_total INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS chunks_done INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS rows_written BIGINT NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_sync_runs_batch_id
  ON sync_runs(batch_id);

CREATE INDEX IF NOT EXISTS idx_sync_runs_platform_account_created_at
  ON sync_runs(platform, account_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sync_runs_client_created_at
  ON sync_runs(client_id, created_at DESC);

ALTER TABLE sync_run_chunks
  ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS rows_written BIGINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS duration_ms INTEGER NULL;

CREATE INDEX IF NOT EXISTS idx_sync_run_chunks_status_created_at
  ON sync_run_chunks(status, created_at);

ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS rolling_window_days INTEGER NOT NULL DEFAULT 7,
  ADD COLUMN IF NOT EXISTS backfill_completed_through DATE NULL,
  ADD COLUMN IF NOT EXISTS rolling_synced_through DATE NULL,
  ADD COLUMN IF NOT EXISTS last_success_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS last_error TEXT NULL,
  ADD COLUMN IF NOT EXISTS last_run_id TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_agency_platform_accounts_backfill_completed
  ON agency_platform_accounts(backfill_completed_through);

CREATE INDEX IF NOT EXISTS idx_agency_platform_accounts_rolling_synced
  ON agency_platform_accounts(rolling_synced_through);
