-- Feed Schema Registry: dynamic field definitions per catalog type and channel
-- Replaces the hardcoded catalog_field_schemas.py with database-driven field metadata.

-- 1. feed_schema_fields — superset of all fields per catalog type
CREATE TABLE IF NOT EXISTS feed_schema_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_type catalog_type NOT NULL,                         -- reuses existing ENUM
    field_key VARCHAR(100) NOT NULL,                            -- normalized: make, model, year, vin, etc.
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    data_type VARCHAR(50) NOT NULL DEFAULT 'string',            -- string, number, url, price, boolean, enum, date, html
    allowed_values JSONB,                                       -- for enums, e.g. ["new","used","cpo"]
    format_pattern VARCHAR(500),                                -- regex or format hint
    example_value VARCHAR(500),
    is_system BOOLEAN NOT NULL DEFAULT false,                   -- true for core fields: id, title, description, link, price, image_link
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(catalog_type, field_key)
);

-- 2. feed_schema_channel_fields — per-channel metadata for each schema field
CREATE TABLE IF NOT EXISTS feed_schema_channel_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_field_id UUID NOT NULL REFERENCES feed_schema_fields(id) ON DELETE CASCADE,
    channel_slug VARCHAR(50) NOT NULL,                          -- matches feed_channels.channel_type pattern
    is_required BOOLEAN NOT NULL DEFAULT false,
    channel_field_name VARCHAR(200),                            -- name as the channel calls it (may differ from field_key)
    default_value VARCHAR(500),
    sort_order INTEGER NOT NULL DEFAULT 0,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(schema_field_id, channel_slug)
);

-- 3. feed_schema_imports — audit log of CSV schema imports
CREATE TABLE IF NOT EXISTS feed_schema_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_slug VARCHAR(50) NOT NULL,
    catalog_type catalog_type NOT NULL,
    agency_id BIGINT,                                           -- matches agencies.id (BIGSERIAL)
    filename VARCHAR(500) NOT NULL,
    s3_path VARCHAR(1000),
    fields_added INTEGER NOT NULL DEFAULT 0,
    fields_updated INTEGER NOT NULL DEFAULT 0,
    fields_deprecated INTEGER NOT NULL DEFAULT 0,
    imported_by BIGINT,                                         -- matches users.id (BIGSERIAL)
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_schema_fields_catalog ON feed_schema_fields(catalog_type);
CREATE INDEX IF NOT EXISTS idx_schema_fields_catalog_system ON feed_schema_fields(catalog_type, is_system);
CREATE INDEX IF NOT EXISTS idx_schema_channel_fields_channel ON feed_schema_channel_fields(channel_slug);
CREATE INDEX IF NOT EXISTS idx_schema_channel_fields_field ON feed_schema_channel_fields(schema_field_id);
CREATE INDEX IF NOT EXISTS idx_schema_imports_channel_catalog ON feed_schema_imports(channel_slug, catalog_type);
