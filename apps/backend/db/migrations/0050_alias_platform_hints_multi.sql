-- Migration: platform_hint → platform_hints (JSONB array)
-- Allows a single alias to track multiple platforms (e.g. vehicle_id used by both tiktok AND meta).

-- 1. Add new JSONB column with default empty array
ALTER TABLE feed_field_aliases
    ADD COLUMN IF NOT EXISTS platform_hints JSONB DEFAULT '[]'::jsonb;

-- 2. Populate from existing platform_hint
UPDATE feed_field_aliases
SET platform_hints = jsonb_build_array(platform_hint)
WHERE platform_hint IS NOT NULL
  AND platform_hint != ''
  AND (platform_hints IS NULL OR platform_hints = '[]'::jsonb);

-- 3. GIN index for efficient containment queries
CREATE INDEX IF NOT EXISTS idx_alias_platform_hints
    ON feed_field_aliases USING GIN(platform_hints);

-- 4. Fix known aliases that are shared across platforms but only stored one.
--    vehicle_id, state_of_vehicle, mileage_value are used by both tiktok AND meta.
UPDATE feed_field_aliases
SET platform_hints = '["tiktok", "meta"]'::jsonb
WHERE catalog_type = 'vehicle'
  AND alias_key IN ('vehicle_id', 'state_of_vehicle', 'mileage_value')
  AND NOT platform_hints @> '"meta"'::jsonb;

-- NOTE: platform_hint (legacy VARCHAR) is kept for backward compatibility.
