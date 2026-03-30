-- 0028: Make *_norm columns NOT NULL with DEFAULT, re-backfill any NULLs.
--
-- After this migration every norm column is guaranteed non-NULL so that
-- hot-path joins can use direct  norm = norm  comparisons without
-- COALESCE(norm, regexp_replace(...)) fallback.

-- 1. ad_performance_reports.customer_id_norm
UPDATE ad_performance_reports
   SET customer_id_norm = regexp_replace(COALESCE(customer_id, ''), '[^0-9]', '', 'g')
 WHERE customer_id_norm IS NULL;

ALTER TABLE ad_performance_reports
    ALTER COLUMN customer_id_norm SET DEFAULT '',
    ALTER COLUMN customer_id_norm SET NOT NULL;

-- 2. agency_account_client_mappings.account_id_norm
UPDATE agency_account_client_mappings
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm IS NULL;

ALTER TABLE agency_account_client_mappings
    ALTER COLUMN account_id_norm SET DEFAULT '',
    ALTER COLUMN account_id_norm SET NOT NULL;

-- 3. agency_platform_accounts.account_id_norm
UPDATE agency_platform_accounts
   SET account_id_norm = regexp_replace(COALESCE(account_id, ''), '[^0-9]', '', 'g')
 WHERE account_id_norm IS NULL;

ALTER TABLE agency_platform_accounts
    ALTER COLUMN account_id_norm SET DEFAULT '',
    ALTER COLUMN account_id_norm SET NOT NULL;
