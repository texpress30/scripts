-- Feed field aliases: canonical mapping for cross-platform field unification.
-- When Meta calls it "vehicle_offer_id" and TikTok calls it "vehicle_id",
-- both resolve to the same canonical field_key in the superset.

CREATE TABLE IF NOT EXISTS feed_field_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_type catalog_type NOT NULL,
    canonical_key VARCHAR(100) NOT NULL,
    alias_key VARCHAR(100) NOT NULL,
    platform_hint VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(catalog_type, alias_key)
);

CREATE INDEX IF NOT EXISTS idx_field_aliases_catalog_alias
    ON feed_field_aliases(catalog_type, alias_key);

-- ============================================================================
-- Seed known Vehicle aliases (Meta vs TikTok vs Google field naming)
-- ============================================================================

INSERT INTO feed_field_aliases (catalog_type, canonical_key, alias_key, platform_hint) VALUES
  -- Meta uses vehicle_offer_id, canonical is id
  ('vehicle', 'id',          'vehicle_offer_id',  'meta'),
  ('vehicle', 'id',          'vehicle_id',        'tiktok'),
  -- Meta uses offer_description, canonical is description
  ('vehicle', 'description', 'offer_description', 'meta'),
  -- Meta image bracket notation flattened
  ('vehicle', 'image_link',  'image_0_url',       'meta'),
  -- Meta/TikTok URL variants
  ('vehicle', 'link',        'url',               'generic'),
  ('vehicle', 'link',        'vehicle_url',       'tiktok'),
  -- Price variants
  ('vehicle', 'price',       'sale_price',        'generic'),
  ('vehicle', 'price',       'asking_price',      'tiktok'),
  -- Condition variants
  ('vehicle', 'vehicle_condition', 'state_of_vehicle', 'tiktok'),
  ('vehicle', 'vehicle_condition', 'condition',        'generic'),
  -- Mileage variants
  ('vehicle', 'mileage',     'mileage_value',     'tiktok'),
  ('vehicle', 'mileage',     'odometer_value',    'generic')
ON CONFLICT (catalog_type, alias_key) DO NOTHING;

-- ============================================================================
-- Cleanup: merge duplicate fields that now have aliases
-- For each alias where BOTH canonical and alias exist as separate fields,
-- move channel links from alias_field to canonical_field, then delete alias.
-- ============================================================================

DO $$
DECLARE
    r RECORD;
    canonical_field_id UUID;
    alias_field_id UUID;
BEGIN
    FOR r IN
        SELECT a.catalog_type, a.canonical_key, a.alias_key
        FROM feed_field_aliases a
    LOOP
        -- Find both field IDs
        SELECT id INTO canonical_field_id
        FROM feed_schema_fields
        WHERE catalog_type = r.catalog_type AND field_key = r.canonical_key;

        SELECT id INTO alias_field_id
        FROM feed_schema_fields
        WHERE catalog_type = r.catalog_type AND field_key = r.alias_key;

        -- Only merge if BOTH exist as separate fields
        IF canonical_field_id IS NOT NULL AND alias_field_id IS NOT NULL THEN
            -- Move channel_field links: update schema_field_id, keep channel_field_name
            UPDATE feed_schema_channel_fields
            SET schema_field_id = canonical_field_id,
                channel_field_name = COALESCE(channel_field_name, r.alias_key)
            WHERE schema_field_id = alias_field_id
              AND NOT EXISTS (
                  -- Skip if canonical already has a link for this channel
                  SELECT 1 FROM feed_schema_channel_fields cf2
                  WHERE cf2.schema_field_id = canonical_field_id
                    AND cf2.channel_slug = feed_schema_channel_fields.channel_slug
              );

            -- Delete orphaned channel_field links (where canonical already had one)
            DELETE FROM feed_schema_channel_fields
            WHERE schema_field_id = alias_field_id;

            -- Delete the duplicate field
            DELETE FROM feed_schema_fields
            WHERE id = alias_field_id;

            RAISE NOTICE 'Merged alias %.% → %.%',
                r.catalog_type, r.alias_key, r.catalog_type, r.canonical_key;
        END IF;
    END LOOP;
END $$;
