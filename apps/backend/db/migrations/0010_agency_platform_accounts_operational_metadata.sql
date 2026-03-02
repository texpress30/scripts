ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS status TEXT NULL;

ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS currency_code CHAR(3) NULL;

ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS account_timezone TEXT NULL;

ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS sync_start_date DATE NULL;

ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_agency_platform_accounts_platform_status
ON agency_platform_accounts (platform, status);

CREATE INDEX IF NOT EXISTS idx_agency_platform_accounts_last_synced_at
ON agency_platform_accounts (last_synced_at);
