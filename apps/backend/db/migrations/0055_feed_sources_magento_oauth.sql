-- 0055: Extend feed_sources with Magento 2 OAuth 1.0a connect columns.
--
-- Magento 2 Integrations (System → Extensions → Integrations in the merchant
-- admin) mint four OAuth 1.0a credentials: consumer_key, consumer_secret,
-- access_token, access_token_secret. These are sensitive and are stored
-- encrypted (Fernet) in integration_secrets with
-- provider='magento', scope=<feed_source_id>, one row per secret_key.
--
-- On feed_sources we only persist the non-sensitive routing information:
--   * magento_base_url  — e.g. https://magento.example.com
--   * magento_store_code — Magento supports multi-store; default is 'default'
--
-- Both are nullable so non-Magento rows keep working without a backfill.
-- A partial unique index prevents the same (subaccount, base_url, store_code)
-- from being registered twice. Non-Magento rows (NULL base_url) coexist freely.

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS magento_base_url VARCHAR(500);
ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS magento_store_code VARCHAR(100);

CREATE UNIQUE INDEX IF NOT EXISTS uq_feed_sources_subaccount_magento_store
    ON feed_sources(subaccount_id, magento_base_url, magento_store_code)
    WHERE source_type = 'magento' AND magento_base_url IS NOT NULL;
