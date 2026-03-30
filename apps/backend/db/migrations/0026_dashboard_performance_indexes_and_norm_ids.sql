ALTER TABLE ad_performance_reports
  ADD COLUMN IF NOT EXISTS customer_id_norm TEXT;

UPDATE ad_performance_reports
SET customer_id_norm = NULLIF(regexp_replace(COALESCE(customer_id, ''), '[^0-9]', '', 'g'), '')
WHERE customer_id_norm IS NULL;

ALTER TABLE agency_account_client_mappings
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT;

UPDATE agency_account_client_mappings
SET account_id_norm = NULLIF(regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g'), '')
WHERE account_id_norm IS NULL;

CREATE INDEX IF NOT EXISTS idx_ad_perf_platform_customer_date_desc
  ON ad_performance_reports (platform, customer_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_ad_perf_platform_customer_norm_date_desc
  ON ad_performance_reports (platform, customer_id_norm, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_ad_perf_client_platform_date_desc
  ON ad_performance_reports (client_id, platform, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_agency_account_mappings_platform_account_norm
  ON agency_account_client_mappings (platform, account_id_norm);

CREATE TABLE IF NOT EXISTS sync_health_summary (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  client_id INTEGER,
  status TEXT NOT NULL,
  last_sync_at TIMESTAMPTZ,
  last_error TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (platform, account_id)
);

CREATE INDEX IF NOT EXISTS idx_sync_health_summary_client_platform
  ON sync_health_summary (client_id, platform, updated_at DESC);
