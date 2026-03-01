DO $$
BEGIN
  IF to_regclass('public.ad_performance_reports') IS NULL THEN
    RETURN;
  END IF;

  -- Remove legacy 4-column uniqueness artifacts if they exist.
  DROP INDEX IF EXISTS idx_ad_performance_reports_unique_daily_customer;

  ALTER TABLE ad_performance_reports
    DROP CONSTRAINT IF EXISTS ad_performance_reports_report_date_platform_customer_id_client_id_key;

  -- Deduplicate historical rows on canonical daily key.
  WITH ranked AS (
    SELECT
      id,
      ROW_NUMBER() OVER (
        PARTITION BY report_date, platform, customer_id
        ORDER BY synced_at DESC, id DESC
      ) AS rn
    FROM ad_performance_reports
  )
  DELETE FROM ad_performance_reports apr
  USING ranked
  WHERE apr.id = ranked.id
    AND ranked.rn > 1;

  -- Enforce canonical uniqueness key.
  CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_performance_reports_unique_daily_customer
    ON ad_performance_reports (report_date, platform, customer_id);
END
$$;
