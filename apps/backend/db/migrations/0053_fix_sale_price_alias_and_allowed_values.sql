-- Fix: sale_price and price are DIFFERENT Meta Vehicles fields.
-- The seed migration (0043) aliased sale_price → price, but Meta Vehicles
-- has both as separate fields. The alias caused channel_field_name for
-- price to be overwritten to "sale_price" on re-import.

-- 1. Delete the incorrect alias: sale_price → price
DELETE FROM feed_field_aliases
WHERE catalog_type = 'vehicle'
  AND alias_key = 'sale_price'
  AND canonical_key = 'price';

-- 2. Create 'sale_price' as its own canonical field for vehicle catalog
INSERT INTO feed_schema_fields
  (id, catalog_type, field_key, display_name, description, data_type,
   example_value)
VALUES
  (gen_random_uuid(), 'vehicle', 'sale_price', 'Sale Price',
   'Discounted or sale price of the vehicle with currency',
   'price', '10000.00 EUR')
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- 3. Link 'sale_price' to facebook_catalog_vehicles (optional)
INSERT INTO feed_schema_channel_fields
  (id, schema_field_id, channel_slug, is_required, channel_field_name,
   sort_order, subtype_slug)
SELECT gen_random_uuid(), f.id, 'facebook_catalog_vehicles', false, 'sale_price',
       91, 'vehicle_listings'
FROM feed_schema_fields f
WHERE f.catalog_type = 'vehicle' AND f.field_key = 'sale_price'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- 4. Fix price channel_field_name back to 'price' for facebook_catalog_vehicles
UPDATE feed_schema_channel_fields
SET channel_field_name = 'price'
WHERE channel_slug = 'facebook_catalog_vehicles'
  AND schema_field_id = (
    SELECT id FROM feed_schema_fields
    WHERE catalog_type = 'vehicle' AND field_key = 'price'
  );

-- 5. Update vehicle_condition allowed_values to include CPO (both cases)
UPDATE feed_schema_fields
SET allowed_values = '["new","used","cpo","NEW","USED","CPO"]'::jsonb
WHERE catalog_type = 'vehicle' AND field_key = 'vehicle_condition';

-- 6. Update body_style allowed_values to match Meta's full list
UPDATE feed_schema_fields
SET allowed_values = '["CONVERTIBLE","COUPE","CROSSOVER","ESTATE","GRANDTOURER","HATCHBACK","MINIBUS","MINIVAN","MPV","PICKUP","ROADSTER","SALOON","SEDAN","SMALL_CAR","SPORTSCAR","SUPERCAR","SUPERMINI","SUV","TRUCK","VAN","WAGON","OTHER","NONE"]'::jsonb
WHERE catalog_type = 'vehicle' AND field_key = 'body_style';
