CREATE TABLE IF NOT EXISTS platform_campaigns (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  campaign_id TEXT NOT NULL,
  name TEXT NULL,
  status TEXT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NULL,
  payload_hash TEXT NULL,
  PRIMARY KEY (platform, account_id, campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_campaigns_platform_account
  ON platform_campaigns(platform, account_id);

CREATE TABLE IF NOT EXISTS platform_ad_groups (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  ad_group_id TEXT NOT NULL,
  campaign_id TEXT NULL,
  name TEXT NULL,
  status TEXT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NULL,
  payload_hash TEXT NULL,
  PRIMARY KEY (platform, account_id, ad_group_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_ad_groups_platform_account
  ON platform_ad_groups(platform, account_id);

CREATE INDEX IF NOT EXISTS idx_platform_ad_groups_platform_account_campaign
  ON platform_ad_groups(platform, account_id, campaign_id);

CREATE TABLE IF NOT EXISTS platform_ads (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  ad_id TEXT NOT NULL,
  ad_group_id TEXT NULL,
  campaign_id TEXT NULL,
  name TEXT NULL,
  status TEXT NULL,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NULL,
  payload_hash TEXT NULL,
  PRIMARY KEY (platform, account_id, ad_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_ads_platform_account
  ON platform_ads(platform, account_id);

CREATE INDEX IF NOT EXISTS idx_platform_ads_platform_account_ad_group
  ON platform_ads(platform, account_id, ad_group_id);

CREATE TABLE IF NOT EXISTS platform_account_watermarks (
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  grain TEXT NOT NULL,
  sync_start_date DATE NULL,
  historical_synced_through DATE NULL,
  rolling_synced_through DATE NULL,
  last_success_at TIMESTAMPTZ NULL,
  last_error TEXT NULL,
  last_job_id TEXT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_platform_account_watermarks_platform_account_grain
    UNIQUE (platform, account_id, grain),
  CONSTRAINT ck_platform_account_watermarks_grain
    CHECK (grain IN ('account_daily', 'campaign_daily', 'ad_group_daily', 'ad_daily'))
);

CREATE INDEX IF NOT EXISTS idx_platform_account_watermarks_platform_account
  ON platform_account_watermarks(platform, account_id);
