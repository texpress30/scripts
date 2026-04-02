-- Master Field Mappings (maparea universală per sursă)
CREATE TABLE IF NOT EXISTS master_field_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_source_id UUID NOT NULL REFERENCES feed_sources(id) ON DELETE CASCADE,
    target_field VARCHAR(100) NOT NULL,  -- câmpul target (id, title, price, make, etc.)
    source_field VARCHAR(100),           -- câmpul din sursa de date
    mapping_type VARCHAR(50) DEFAULT 'direct',  -- direct, static, template
    static_value TEXT,                   -- pentru mapping_type='static'
    template_value TEXT,                 -- pentru mapping_type='template', ex: "{{make}} {{model}} {{year}}"
    is_required BOOLEAN DEFAULT false,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(feed_source_id, target_field)
);

-- Feed Channels (canalele de publicare)
CREATE TABLE IF NOT EXISTS feed_channels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    feed_source_id UUID NOT NULL REFERENCES feed_sources(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    channel_type VARCHAR(50) NOT NULL,  -- google_shopping, facebook_product_ads, etc.
    status VARCHAR(50) DEFAULT 'draft',
    feed_format VARCHAR(20) DEFAULT 'xml',
    public_token VARCHAR(64) UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
    feed_url VARCHAR(500),
    s3_key VARCHAR(500),
    included_products INTEGER DEFAULT 0,
    excluded_products INTEGER DEFAULT 0,
    last_generated_at TIMESTAMPTZ,
    error_message TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Channel Field Overrides (override-uri per canal)
CREATE TABLE IF NOT EXISTS channel_field_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES feed_channels(id) ON DELETE CASCADE,
    target_field VARCHAR(100) NOT NULL,
    source_field VARCHAR(100),
    mapping_type VARCHAR(50) DEFAULT 'direct',
    static_value TEXT,
    template_value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(channel_id, target_field)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_master_fields_source ON master_field_mappings(feed_source_id);
CREATE INDEX IF NOT EXISTS idx_channels_source ON feed_channels(feed_source_id);
CREATE INDEX IF NOT EXISTS idx_channels_token ON feed_channels(public_token);
CREATE INDEX IF NOT EXISTS idx_channel_overrides_channel ON channel_field_overrides(channel_id);
