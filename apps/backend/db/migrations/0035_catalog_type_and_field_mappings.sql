-- 0035: Add catalog_type to feed_sources and create field_mappings tables
-- Supports mapping source fields to catalog-specific target schemas per channel.

-- Catalog type enum
DO $$ BEGIN
    CREATE TYPE catalog_type AS ENUM (
        'product',
        'vehicle',
        'vehicle_offer',
        'home_listing',
        'hotel',
        'hotel_room',
        'flight',
        'trip',
        'media'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE feed_sources ADD COLUMN IF NOT EXISTS catalog_type catalog_type NOT NULL DEFAULT 'product';

-- Transformation type enum
DO $$ BEGIN
    CREATE TYPE transformation_type AS ENUM (
        'direct',
        'template',
        'static',
        'conditional',
        'concatenate',
        'uppercase',
        'lowercase',
        'prefix',
        'suffix',
        'replace',
        'truncate'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Field Mappings table
CREATE TABLE IF NOT EXISTS field_mappings (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    feed_source_id UUID NOT NULL REFERENCES feed_sources(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    target_channel VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id),
    UNIQUE(feed_source_id, name)
);

-- Field Mapping Rules table
CREATE TABLE IF NOT EXISTS field_mapping_rules (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    field_mapping_id UUID NOT NULL REFERENCES field_mappings(id) ON DELETE CASCADE,
    target_field VARCHAR(100) NOT NULL,
    source_field VARCHAR(100),
    transformation_type transformation_type NOT NULL DEFAULT 'direct',
    transformation_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_field_mappings_feed_source ON field_mappings(feed_source_id);
CREATE INDEX IF NOT EXISTS idx_field_mapping_rules_mapping ON field_mapping_rules(field_mapping_id);
CREATE INDEX IF NOT EXISTS idx_field_mapping_rules_sort ON field_mapping_rules(field_mapping_id, sort_order);
