-- Feed sources and feed imports schema for e-commerce platform connections
-- and file-based product imports (CSV, JSON, XML, Google Sheets).

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feed_source_type') THEN
        CREATE TYPE feed_source_type AS ENUM (
            'shopify',
            'woocommerce',
            'magento',
            'bigcommerce',
            'csv',
            'json',
            'xml',
            'google_sheets'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feed_import_status') THEN
        CREATE TYPE feed_import_status AS ENUM (
            'pending',
            'in_progress',
            'completed',
            'failed'
        );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS feed_sources (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    subaccount_id INT NOT NULL,
    source_type feed_source_type NOT NULL,
    name TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    credentials_secret_id TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_feed_sources_subaccount_id
    ON feed_sources(subaccount_id);

CREATE TABLE IF NOT EXISTS feed_imports (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    feed_source_id UUID NOT NULL REFERENCES feed_sources(id) ON DELETE CASCADE,
    status feed_import_status NOT NULL DEFAULT 'pending',
    total_products INT NOT NULL DEFAULT 0,
    imported_products INT NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_feed_imports_feed_source_id
    ON feed_imports(feed_source_id);
