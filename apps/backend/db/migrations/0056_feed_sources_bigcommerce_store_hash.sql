-- 0056: Extend feed_sources with a dedicated BigCommerce store_hash column.
--
-- BigCommerce identifies each merchant store with a short alphanumeric "store
-- hash" (e.g. "abc123") returned in the OAuth context as ``stores/{hash}``.
-- The Task 1 (PR #942) shipping cut reused the generic ``shop_domain`` column
-- to keep that hash so we wouldn't need a migration. Now that BigCommerce is
-- about to grow CRUD endpoints + a connector + per-source claim flow, we
-- give it a dedicated, semantically-named column to:
--
--   * Keep ``shop_domain`` strictly for *.myshopify.com domains (the column's
--     original meaning) and avoid muddling search/lookup queries.
--   * Enable a partial unique index keyed on the new column so two
--     subaccounts can never claim the same BigCommerce store independently.
--   * Make the schema self-documenting for future reviewers — searching the
--     table for "where the bc store hash lives" should land on a column with
--     that exact name.
--
-- The column is nullable so non-BigCommerce rows keep working without a
-- backfill. The partial unique index only fires for source_type='bigcommerce'.
--
-- Backfill: any pre-existing BigCommerce rows that the Task 1 callback wrote
-- with ``shop_domain=<store_hash>`` are migrated atomically into the new
-- column. After this migration runs, ``shop_domain`` is cleared on
-- BigCommerce rows so the Shopify uniqueness index doesn't accidentally
-- collide with a hash that happens to look like a Shopify shop slug.

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS bigcommerce_store_hash VARCHAR(64);

UPDATE feed_sources
SET bigcommerce_store_hash = shop_domain,
    shop_domain = NULL
WHERE source_type = 'bigcommerce'
  AND bigcommerce_store_hash IS NULL
  AND shop_domain IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_feed_sources_bigcommerce_store_hash
    ON feed_sources(bigcommerce_store_hash)
    WHERE source_type = 'bigcommerce' AND bigcommerce_store_hash IS NOT NULL;
