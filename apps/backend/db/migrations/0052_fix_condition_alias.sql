-- Fix: condition and state_of_vehicle are DIFFERENT Meta Vehicles fields.
-- AI alias suggestions incorrectly mapped both to vehicle_condition.
--   state_of_vehicle (required, NEW/USED/CPO) = vehicle purchase state
--   condition (optional, EXCELLENT/GOOD/FAIR/POOR) = physical condition

-- 1. Delete the incorrect alias: condition → vehicle_condition
DELETE FROM feed_field_aliases
WHERE catalog_type = 'vehicle'
  AND alias_key = 'condition'
  AND canonical_key = 'vehicle_condition';

-- 2. Create 'condition' as its own canonical field
INSERT INTO feed_schema_fields
  (id, catalog_type, field_key, display_name, description, data_type,
   allowed_values, example_value)
VALUES
  (gen_random_uuid(), 'vehicle', 'condition', 'Condition',
   'Physical condition of the vehicle (excellent, good, fair, poor)',
   'enum', '["EXCELLENT","GOOD","FAIR","POOR","NONE"]'::jsonb, 'GOOD')
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- 3. Link 'condition' to facebook_catalog_vehicles (optional field)
INSERT INTO feed_schema_channel_fields
  (id, schema_field_id, channel_slug, is_required, channel_field_name,
   sort_order, subtype_slug)
SELECT
  gen_random_uuid(), f.id, 'facebook_catalog_vehicles', false, 'condition',
  90, 'vehicle_listings'
FROM feed_schema_fields f
WHERE f.catalog_type = 'vehicle' AND f.field_key = 'condition'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- 4. Fix vehicle_condition's channel_field_name back to state_of_vehicle
--    for facebook_catalog_vehicles (was overwritten to "condition" by the alias)
UPDATE feed_schema_channel_fields
SET channel_field_name = 'state_of_vehicle'
WHERE channel_slug = 'facebook_catalog_vehicles'
  AND schema_field_id = (
    SELECT id FROM feed_schema_fields
    WHERE catalog_type = 'vehicle' AND field_key = 'vehicle_condition'
  );
