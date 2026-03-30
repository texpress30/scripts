-- Phase 3: canonical account id on agency_platform_accounts (dashboard joins use apa.account_id_norm)
ALTER TABLE agency_platform_accounts
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT;

UPDATE agency_platform_accounts
SET account_id_norm = NULLIF(regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g'), '')
WHERE account_id_norm IS NULL;

CREATE INDEX IF NOT EXISTS idx_agency_platform_accounts_platform_account_norm
  ON agency_platform_accounts (platform, account_id_norm);

-- Pre-aggregated daily rows per client/platform/currency (refreshed explicitly; read path optional)
CREATE TABLE IF NOT EXISTS client_platform_daily_rollup (
  client_id INTEGER NOT NULL,
  platform TEXT NOT NULL,
  report_date DATE NOT NULL,
  account_currency TEXT NOT NULL,
  spend NUMERIC(18, 4) NOT NULL DEFAULT 0,
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  conversions NUMERIC(18, 4) NOT NULL DEFAULT 0,
  conversion_value NUMERIC(18, 4) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (client_id, platform, report_date, account_currency)
);

CREATE INDEX IF NOT EXISTS idx_client_platform_daily_rollup_client_date
  ON client_platform_daily_rollup (client_id, report_date DESC);

-- Last successful refresh window (single contiguous range per client for rollup read path)
CREATE TABLE IF NOT EXISTS client_platform_daily_rollup_meta (
  client_id INTEGER PRIMARY KEY,
  range_start DATE NOT NULL,
  range_end DATE NOT NULL,
  refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
