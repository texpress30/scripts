DO $$
BEGIN
  IF to_regclass('public.ad_performance_reports') IS NULL THEN
    RETURN;
  END IF;

  ALTER TABLE ad_performance_reports
    ADD COLUMN IF NOT EXISTS extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb;
END
$$;
