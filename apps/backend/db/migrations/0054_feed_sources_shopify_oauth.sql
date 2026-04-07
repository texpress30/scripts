-- 0054: Extend feed_sources with Shopify OAuth + connection-tracking columns.
-- Backwards-compatible: all new columns are nullable or have defaults so
-- existing rows (CSV/JSON/file/etc.) keep working without backfill.

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS shop_domain VARCHAR(255);
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS catalog_variant VARCHAR(50) NOT NULL DEFAULT 'physical_products';
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS connection_status VARCHAR(30) NOT NULL DEFAULT 'pending';
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS last_connection_check TIMESTAMPTZ;
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS last_error TEXT;
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS has_token BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS token_scopes TEXT;
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS last_import_at TIMESTAMPTZ;

-- Existing rows (created before this migration) should be considered
-- "connected" if they're already active with a credentials secret, otherwise
-- they remain "pending". This avoids breaking the dashboard for legacy rows.
UPDATE feed_sources
SET connection_status = 'connected'
WHERE connection_status = 'pending'
  AND is_active = TRUE
  AND credentials_secret_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_feed_sources_source_type
    ON feed_sources(source_type);

-- A given subaccount cannot have two Shopify sources pointing at the same
-- shop_domain. Partial unique index lets non-Shopify rows (NULL shop_domain)
-- coexist freely.
CREATE UNIQUE INDEX IF NOT EXISTS uq_feed_sources_subaccount_type_shop
    ON feed_sources(subaccount_id, source_type, shop_domain)
    WHERE shop_domain IS NOT NULL;
