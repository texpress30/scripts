DO $$
DECLARE
  start_month DATE := DATE '2024-01-01';
  end_month DATE := DATE '2027-01-01';
  cursor_month DATE;
BEGIN
  IF to_regclass('public.campaign_performance_reports') IS NOT NULL
     AND COALESCE((SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('public.campaign_performance_reports')), '') <> 'p' THEN
    ALTER TABLE campaign_performance_reports RENAME TO campaign_performance_reports_unpartitioned;

    CREATE TABLE campaign_performance_reports (
      LIKE campaign_performance_reports_unpartitioned INCLUDING DEFAULTS
    ) PARTITION BY RANGE (report_date);

    ALTER TABLE campaign_performance_reports
      ALTER COLUMN platform SET NOT NULL,
      ALTER COLUMN account_id SET NOT NULL,
      ALTER COLUMN campaign_id SET NOT NULL,
      ALTER COLUMN report_date SET NOT NULL;

    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname = 'uq_campaign_perf_reports_daily_partitioned'
        AND conrelid = 'campaign_performance_reports'::regclass
    ) THEN
      ALTER TABLE campaign_performance_reports
        ADD CONSTRAINT uq_campaign_perf_reports_daily_partitioned
        UNIQUE (platform, account_id, campaign_id, report_date);
    END IF;

    CREATE INDEX IF NOT EXISTS idx_campaign_perf_reports_partitioned_platform_account_date
      ON campaign_performance_reports(platform, account_id, report_date);

    CREATE INDEX IF NOT EXISTS idx_campaign_perf_reports_partitioned_platform_account_campaign
      ON campaign_performance_reports(platform, account_id, campaign_id);

    CREATE TABLE IF NOT EXISTS campaign_performance_reports_default
      PARTITION OF campaign_performance_reports DEFAULT;

    cursor_month := start_month;
    WHILE cursor_month < end_month LOOP
      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF campaign_performance_reports FOR VALUES FROM (%L) TO (%L)',
        format('campaign_performance_reports_%s', to_char(cursor_month, 'YYYY_MM')),
        cursor_month,
        (cursor_month + INTERVAL '1 month')::date
      );
      cursor_month := (cursor_month + INTERVAL '1 month')::date;
    END LOOP;

    INSERT INTO campaign_performance_reports
    SELECT * FROM campaign_performance_reports_unpartitioned;

    DROP TABLE campaign_performance_reports_unpartitioned;
  END IF;
END
$$;

DO $$
DECLARE
  start_month DATE := DATE '2024-01-01';
  end_month DATE := DATE '2027-01-01';
  cursor_month DATE;
BEGIN
  IF to_regclass('public.ad_group_performance_reports') IS NOT NULL
     AND COALESCE((SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('public.ad_group_performance_reports')), '') <> 'p' THEN
    ALTER TABLE ad_group_performance_reports RENAME TO ad_group_performance_reports_unpartitioned;

    CREATE TABLE ad_group_performance_reports (
      LIKE ad_group_performance_reports_unpartitioned INCLUDING DEFAULTS
    ) PARTITION BY RANGE (report_date);

    ALTER TABLE ad_group_performance_reports
      ALTER COLUMN platform SET NOT NULL,
      ALTER COLUMN account_id SET NOT NULL,
      ALTER COLUMN ad_group_id SET NOT NULL,
      ALTER COLUMN report_date SET NOT NULL;

    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname = 'uq_ad_group_perf_reports_daily_partitioned'
        AND conrelid = 'ad_group_performance_reports'::regclass
    ) THEN
      ALTER TABLE ad_group_performance_reports
        ADD CONSTRAINT uq_ad_group_perf_reports_daily_partitioned
        UNIQUE (platform, account_id, ad_group_id, report_date);
    END IF;

    CREATE INDEX IF NOT EXISTS idx_ad_group_perf_reports_partitioned_platform_account_date
      ON ad_group_performance_reports(platform, account_id, report_date);

    CREATE INDEX IF NOT EXISTS idx_ad_group_perf_reports_partitioned_platform_account_ad_group
      ON ad_group_performance_reports(platform, account_id, ad_group_id);

    CREATE TABLE IF NOT EXISTS ad_group_performance_reports_default
      PARTITION OF ad_group_performance_reports DEFAULT;

    cursor_month := start_month;
    WHILE cursor_month < end_month LOOP
      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF ad_group_performance_reports FOR VALUES FROM (%L) TO (%L)',
        format('ad_group_performance_reports_%s', to_char(cursor_month, 'YYYY_MM')),
        cursor_month,
        (cursor_month + INTERVAL '1 month')::date
      );
      cursor_month := (cursor_month + INTERVAL '1 month')::date;
    END LOOP;

    INSERT INTO ad_group_performance_reports
    SELECT * FROM ad_group_performance_reports_unpartitioned;

    DROP TABLE ad_group_performance_reports_unpartitioned;
  END IF;
END
$$;

DO $$
DECLARE
  start_month DATE := DATE '2024-01-01';
  end_month DATE := DATE '2027-01-01';
  cursor_month DATE;
BEGIN
  IF to_regclass('public.ad_unit_performance_reports') IS NOT NULL
     AND COALESCE((SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('public.ad_unit_performance_reports')), '') <> 'p' THEN
    ALTER TABLE ad_unit_performance_reports RENAME TO ad_unit_performance_reports_unpartitioned;

    CREATE TABLE ad_unit_performance_reports (
      LIKE ad_unit_performance_reports_unpartitioned INCLUDING DEFAULTS
    ) PARTITION BY RANGE (report_date);

    ALTER TABLE ad_unit_performance_reports
      ALTER COLUMN platform SET NOT NULL,
      ALTER COLUMN account_id SET NOT NULL,
      ALTER COLUMN ad_id SET NOT NULL,
      ALTER COLUMN report_date SET NOT NULL;

    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname = 'uq_ad_unit_perf_reports_daily_partitioned'
        AND conrelid = 'ad_unit_performance_reports'::regclass
    ) THEN
      ALTER TABLE ad_unit_performance_reports
        ADD CONSTRAINT uq_ad_unit_perf_reports_daily_partitioned
        UNIQUE (platform, account_id, ad_id, report_date);
    END IF;

    CREATE INDEX IF NOT EXISTS idx_ad_unit_perf_reports_partitioned_platform_account_date
      ON ad_unit_performance_reports(platform, account_id, report_date);

    CREATE INDEX IF NOT EXISTS idx_ad_unit_perf_reports_partitioned_platform_account_ad
      ON ad_unit_performance_reports(platform, account_id, ad_id);

    CREATE TABLE IF NOT EXISTS ad_unit_performance_reports_default
      PARTITION OF ad_unit_performance_reports DEFAULT;

    cursor_month := start_month;
    WHILE cursor_month < end_month LOOP
      EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF ad_unit_performance_reports FOR VALUES FROM (%L) TO (%L)',
        format('ad_unit_performance_reports_%s', to_char(cursor_month, 'YYYY_MM')),
        cursor_month,
        (cursor_month + INTERVAL '1 month')::date
      );
      cursor_month := (cursor_month + INTERVAL '1 month')::date;
    END LOOP;

    INSERT INTO ad_unit_performance_reports
    SELECT * FROM ad_unit_performance_reports_unpartitioned;

    DROP TABLE ad_unit_performance_reports_unpartitioned;
  END IF;
END
$$;
