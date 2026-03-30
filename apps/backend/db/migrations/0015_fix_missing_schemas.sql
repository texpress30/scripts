-- Fix missing schemas that prevent the application from starting.
--
-- 1. users table: migration 0001 creates it without password_hash and with
--    full_name instead of first_name/last_name/phone/extension/platform_language.
-- 2. ad_performance_reports table: referenced by migrations 0006 & 0011 and by
--    the performance_reports service but never created.

-- ============================================================
-- 1. Patch users table to match what the application expects
-- ============================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Backfill existing rows that have NULL password_hash with a placeholder
-- so the NOT NULL expectation in app code doesn't blow up on SELECT.
UPDATE users SET password_hash = 'needs_reset' WHERE password_hash IS NULL;

ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS extension TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_language TEXT NOT NULL DEFAULT 'ro';

-- ============================================================
-- 2. Create ad_performance_reports table (was never created)
-- ============================================================
CREATE TABLE IF NOT EXISTS ad_performance_reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    platform TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    customer_id_norm TEXT NOT NULL DEFAULT '',
    client_id BIGINT NULL,
    spend NUMERIC(14, 2) NOT NULL DEFAULT 0,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    conversions NUMERIC(14, 4) NOT NULL DEFAULT 0,
    conversion_value NUMERIC(14, 4) NOT NULL DEFAULT 0,
    extra_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Canonical unique key (matches migration 0006 and the ON CONFLICT clause in code)
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_performance_reports_unique_daily_customer
    ON ad_performance_reports (report_date, platform, customer_id);
