-- Add account_id_norm to campaign/adgroup performance + entity tables
-- to eliminate regexp_replace from hot dashboard joins.

-- 1. campaign_performance_reports
ALTER TABLE campaign_performance_reports
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT NOT NULL DEFAULT '';

UPDATE campaign_performance_reports
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm = '';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_cpr_platform_account_norm_date
  ON campaign_performance_reports (platform, account_id_norm, report_date);

-- 2. ad_group_performance_reports
ALTER TABLE ad_group_performance_reports
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT NOT NULL DEFAULT '';

UPDATE ad_group_performance_reports
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm = '';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agpr_platform_account_norm_date
  ON ad_group_performance_reports (platform, account_id_norm, report_date);

-- 3. platform_campaigns
ALTER TABLE platform_campaigns
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT NOT NULL DEFAULT '';

UPDATE platform_campaigns
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm = '';

-- 4. platform_ad_groups
ALTER TABLE platform_ad_groups
  ADD COLUMN IF NOT EXISTS account_id_norm TEXT NOT NULL DEFAULT '';

UPDATE platform_ad_groups
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm = '';
