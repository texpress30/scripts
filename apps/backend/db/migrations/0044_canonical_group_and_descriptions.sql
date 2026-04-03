-- Add source_description to channel fields (stores description from platform template)
ALTER TABLE feed_schema_channel_fields
    ADD COLUMN IF NOT EXISTS source_description TEXT;

-- Add canonical grouping columns to schema fields
ALTER TABLE feed_schema_fields
    ADD COLUMN IF NOT EXISTS canonical_group VARCHAR(100);

ALTER TABLE feed_schema_fields
    ADD COLUMN IF NOT EXISTS canonical_status VARCHAR(20) DEFAULT 'unset';
-- canonical_status: 'unset', 'suggested', 'confirmed', 'custom'
