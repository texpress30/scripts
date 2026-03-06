CREATE TABLE IF NOT EXISTS campaign_performance_reports (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  report_date DATE NOT NULL,
  spend NUMERIC(14, 4) NOT NULL DEFAULT 0,
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  conversions NUMERIC(14, 4) NOT NULL DEFAULT 0,
  conversion_value NUMERIC(14, 4) NOT NULL DEFAULT 0,
  extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_window_start DATE NULL,
  source_window_end DATE NULL,
  source_job_id TEXT NULL,
  CONSTRAINT uq_campaign_performance_reports_daily
    UNIQUE (platform, account_id, campaign_id, report_date)
);

CREATE INDEX IF NOT EXISTS idx_campaign_performance_reports_platform_account_date
  ON campaign_performance_reports(platform, account_id, report_date);

CREATE INDEX IF NOT EXISTS idx_campaign_performance_reports_platform_account_campaign
  ON campaign_performance_reports(platform, account_id, campaign_id);

CREATE TABLE IF NOT EXISTS ad_group_performance_reports (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  ad_group_id TEXT NOT NULL,
  campaign_id TEXT NULL,
  report_date DATE NOT NULL,
  spend NUMERIC(14, 4) NOT NULL DEFAULT 0,
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  conversions NUMERIC(14, 4) NOT NULL DEFAULT 0,
  conversion_value NUMERIC(14, 4) NOT NULL DEFAULT 0,
  extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_window_start DATE NULL,
  source_window_end DATE NULL,
  source_job_id TEXT NULL,
  CONSTRAINT uq_ad_group_performance_reports_daily
    UNIQUE (platform, account_id, ad_group_id, report_date)
);

CREATE INDEX IF NOT EXISTS idx_ad_group_performance_reports_platform_account_date
  ON ad_group_performance_reports(platform, account_id, report_date);

CREATE INDEX IF NOT EXISTS idx_ad_group_performance_reports_platform_account_ad_group
  ON ad_group_performance_reports(platform, account_id, ad_group_id);

CREATE TABLE IF NOT EXISTS ad_unit_performance_reports (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  ad_id TEXT NOT NULL,
  campaign_id TEXT NULL,
  ad_group_id TEXT NULL,
  report_date DATE NOT NULL,
  spend NUMERIC(14, 4) NOT NULL DEFAULT 0,
  impressions BIGINT NOT NULL DEFAULT 0,
  clicks BIGINT NOT NULL DEFAULT 0,
  conversions NUMERIC(14, 4) NOT NULL DEFAULT 0,
  conversion_value NUMERIC(14, 4) NOT NULL DEFAULT 0,
  extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_window_start DATE NULL,
  source_window_end DATE NULL,
  source_job_id TEXT NULL,
  CONSTRAINT uq_ad_unit_performance_reports_daily
    UNIQUE (platform, account_id, ad_id, report_date)
);

CREATE INDEX IF NOT EXISTS idx_ad_unit_performance_reports_platform_account_date
  ON ad_unit_performance_reports(platform, account_id, report_date);

CREATE INDEX IF NOT EXISTS idx_ad_unit_performance_reports_platform_account_ad
  ON ad_unit_performance_reports(platform, account_id, ad_id);
