CREATE TABLE IF NOT EXISTS platform_keywords (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  keyword_id TEXT NOT NULL,
  campaign_id TEXT NULL,
  ad_group_id TEXT NULL,
  keyword_text TEXT NULL,
  match_type TEXT NULL,
  status TEXT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  payload_hash TEXT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (platform, account_id, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_keywords_platform_account
  ON platform_keywords(platform, account_id);

CREATE INDEX IF NOT EXISTS idx_platform_keywords_platform_account_ad_group
  ON platform_keywords(platform, account_id, ad_group_id);

DO $$
BEGIN
  IF to_regclass('public.keyword_performance_reports') IS NULL THEN
    CREATE TABLE keyword_performance_reports (
      platform TEXT NOT NULL,
      account_id TEXT NOT NULL,
      keyword_id TEXT NOT NULL,
      report_date DATE NOT NULL,
      campaign_id TEXT NULL,
      ad_group_id TEXT NULL,
      spend DOUBLE PRECISION NOT NULL DEFAULT 0,
      impressions BIGINT NOT NULL DEFAULT 0,
      clicks BIGINT NOT NULL DEFAULT 0,
      conversions DOUBLE PRECISION NOT NULL DEFAULT 0,
      conversion_value DOUBLE PRECISION NOT NULL DEFAULT 0,
      extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
      ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      source_window_start DATE NULL,
      source_window_end DATE NULL,
      source_job_id TEXT NULL,
      CONSTRAINT uq_keyword_perf_reports_daily_partitioned
        UNIQUE (platform, account_id, keyword_id, report_date)
    ) PARTITION BY RANGE (report_date);
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_keyword_perf_reports_partitioned_platform_account_date
  ON keyword_performance_reports(platform, account_id, report_date);

CREATE INDEX IF NOT EXISTS idx_keyword_perf_reports_partitioned_platform_account_keyword
  ON keyword_performance_reports(platform, account_id, keyword_id);

CREATE TABLE IF NOT EXISTS keyword_performance_reports_default
  PARTITION OF keyword_performance_reports DEFAULT;

DO $$
DECLARE
  start_month DATE := DATE '2024-01-01';
  end_month DATE := DATE '2027-01-01';
  cursor_month DATE;
BEGIN
  cursor_month := start_month;
  WHILE cursor_month < end_month LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS %I PARTITION OF keyword_performance_reports FOR VALUES FROM (%L) TO (%L)',
      format('keyword_performance_reports_%s', to_char(cursor_month, 'YYYY_MM')),
      cursor_month,
      (cursor_month + INTERVAL '1 month')::date
    );
    cursor_month := (cursor_month + INTERVAL '1 month')::date;
  END LOOP;
END
$$;

ALTER TABLE platform_account_watermarks
  DROP CONSTRAINT IF EXISTS ck_platform_account_watermarks_grain;

ALTER TABLE platform_account_watermarks
  ADD CONSTRAINT ck_platform_account_watermarks_grain
  CHECK (grain IN ('account_daily', 'campaign_daily', 'ad_group_daily', 'ad_daily', 'keyword_daily'));

ALTER TABLE sync_runs
  DROP CONSTRAINT IF EXISTS sync_runs_grain_check;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'sync_runs' AND column_name = 'grain') THEN
    ALTER TABLE sync_runs
      ADD CONSTRAINT sync_runs_grain_check
      CHECK (grain IN ('account_daily', 'campaign_daily', 'ad_group_daily', 'ad_daily', 'keyword_daily'));
  END IF;
END
$$;
