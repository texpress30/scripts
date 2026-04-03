-- Seed data: migrate hardcoded Vehicle catalog fields from catalog_field_schemas.py
-- into the feed_schema_fields and feed_schema_channel_fields tables.
--
-- Source: apps/backend/app/services/feed_management/catalog_field_schemas.py
-- Total: 23 fields (14 required + 9 optional) for catalog_type = 'vehicle'
-- Channels: google_vehicle_ads_v3, google_vehicle_listings, facebook_product_ads, google_shopping

-- ============================================================================
-- 1. feed_schema_fields — 23 Vehicle fields
-- ============================================================================

-- Common / system fields (required)
INSERT INTO feed_schema_fields (id, catalog_type, field_key, display_name, description, data_type, allowed_values, format_pattern, example_value, is_system)
VALUES
  (gen_random_uuid(), 'vehicle', 'id',               'ID',               'Unique identifier for the item',       'string',    NULL, NULL, '60837', true),
  (gen_random_uuid(), 'vehicle', 'title',            'Title',            'Title of the item',                    'string',    NULL, NULL, 'VW TOURAN 2012 AUTOMAT-RATE FIXE', true),
  (gen_random_uuid(), 'vehicle', 'description',      'Description',      'Description of the item',              'string',    NULL, NULL, NULL, true),
  (gen_random_uuid(), 'vehicle', 'link',             'Link',             'URL to the item''s page',              'url',       NULL, NULL, 'https://example.com/produs/vw-touran', true),
  (gen_random_uuid(), 'vehicle', 'image_link',       'Image Link',       'URL of the main image',                'url',       NULL, NULL, 'https://example.com/images/vw-touran.jpg', true),
  (gen_random_uuid(), 'vehicle', 'price',            'Price',            'Price of the item',                    'price',     NULL, NULL, '7500.0 RON', true),
  (gen_random_uuid(), 'vehicle', 'availability',     'Availability',     'Stock status',                         'enum',      '["in_stock","out_of_stock","preorder","backorder"]', NULL, 'in_stock', false),

  -- Vehicle-specific required fields
  (gen_random_uuid(), 'vehicle', 'vin',              'VIN',              'Vehicle Identification Number',         'string',    NULL, '^\w{17}$', 'WVWZZZ1KZ3W123456', false),
  (gen_random_uuid(), 'vehicle', 'make',             'Make',             'Vehicle manufacturer (e.g., Toyota, Ford)', 'string', NULL, NULL, 'Volkswagen', false),
  (gen_random_uuid(), 'vehicle', 'model',            'Model',            'Vehicle model (e.g., Camry, F-150)',   'string',    NULL, NULL, 'Touran', false),
  (gen_random_uuid(), 'vehicle', 'year',             'Year',             'Manufacturing year',                   'number',    NULL, '^\d{4}$', '2012', false),
  (gen_random_uuid(), 'vehicle', 'mileage',          'Mileage',          'Odometer reading',                     'string',    NULL, NULL, '125000 km', false),
  (gen_random_uuid(), 'vehicle', 'vehicle_condition','Condition',        'New or used',                          'enum',      '["new","used"]', NULL, 'used', false),
  (gen_random_uuid(), 'vehicle', 'store_code',       'Store Code',       'Dealership location code',             'string',    NULL, NULL, 'DEALER_001', false),

  -- Vehicle-specific optional fields
  (gen_random_uuid(), 'vehicle', 'trim',             'Trim',             'Trim level (e.g., SE, Limited)',       'string',    NULL, NULL, 'Comfortline', false),
  (gen_random_uuid(), 'vehicle', 'fuel_type',        'Fuel Type',        'Type of fuel',                         'enum',      '["gasoline","diesel","electric","hybrid","plugin_hybrid","lpg"]', NULL, 'diesel', false),
  (gen_random_uuid(), 'vehicle', 'transmission',     'Transmission',     'Transmission type',                    'enum',      '["automatic","manual"]', NULL, 'automatic', false),
  (gen_random_uuid(), 'vehicle', 'body_style',       'Body Style',       'Vehicle body type',                    'enum',      '["sedan","suv","truck","coupe","convertible","van","wagon","hatchback"]', NULL, 'van', false),
  (gen_random_uuid(), 'vehicle', 'exterior_color',   'Exterior Color',   'Exterior color',                       'string',    NULL, NULL, 'Silver', false),
  (gen_random_uuid(), 'vehicle', 'interior_color',   'Interior Color',   'Interior color',                       'string',    NULL, NULL, 'Black', false),
  (gen_random_uuid(), 'vehicle', 'drivetrain',       'Drivetrain',       'Drive system (e.g., AWD, FWD)',        'enum',      '["fwd","rwd","awd","4wd"]', NULL, 'fwd', false),
  (gen_random_uuid(), 'vehicle', 'engine',           'Engine',           'Engine specification',                 'string',    NULL, NULL, '2.0 TDI', false),
  (gen_random_uuid(), 'vehicle', 'dealership_name',  'Dealership Name',  'Name of the dealership',               'string',    NULL, NULL, 'ROC Automobile', false)
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- ============================================================================
-- 2. feed_schema_channel_fields — link fields to channels
--    Channels: google_vehicle_ads_v3, google_vehicle_listings,
--              facebook_product_ads, google_shopping
--    Required/optional status matches catalog_field_schemas.py exactly.
-- ============================================================================

-- Helper: define required field_keys and the channel list, then insert via cross join pattern.
-- Required fields (14): id, title, description, link, image_link, price, availability,
--                        vin, make, model, year, mileage, vehicle_condition, store_code
-- Optional fields (9):  trim, fuel_type, transmission, body_style, exterior_color,
--                        interior_color, drivetrain, engine, dealership_name

-- google_vehicle_ads_v3 — all 23 fields
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 1
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'id'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 2
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'title'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 3
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'description'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 4
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'link'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 5
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'image_link'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 6
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'price'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 7
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'availability'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 8
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'vin'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 9
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'make'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 10
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'model'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 11
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'year'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 12
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'mileage'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 13
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'vehicle_condition'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', true, f.field_key, 14
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'store_code'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 15
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'trim'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 16
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'fuel_type'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 17
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'transmission'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 18
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'body_style'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 19
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'exterior_color'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 20
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'interior_color'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 21
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'drivetrain'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 22
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'engine'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_ads_v3', false, f.field_key, 23
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle' AND f.field_key = 'dealership_name'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- google_vehicle_listings — same 23 fields, same required/optional
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_vehicle_listings',
       f.field_key IN ('id','title','description','link','image_link','price','availability','vin','make','model','year','mileage','vehicle_condition','store_code'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'link' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'price' THEN 6 WHEN 'availability' THEN 7 WHEN 'vin' THEN 8
         WHEN 'make' THEN 9 WHEN 'model' THEN 10 WHEN 'year' THEN 11 WHEN 'mileage' THEN 12
         WHEN 'vehicle_condition' THEN 13 WHEN 'store_code' THEN 14 WHEN 'trim' THEN 15
         WHEN 'fuel_type' THEN 16 WHEN 'transmission' THEN 17 WHEN 'body_style' THEN 18
         WHEN 'exterior_color' THEN 19 WHEN 'interior_color' THEN 20 WHEN 'drivetrain' THEN 21
         WHEN 'engine' THEN 22 WHEN 'dealership_name' THEN 23 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- facebook_product_ads — same 23 fields, same required/optional
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'facebook_product_ads',
       f.field_key IN ('id','title','description','link','image_link','price','availability','vin','make','model','year','mileage','vehicle_condition','store_code'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'link' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'price' THEN 6 WHEN 'availability' THEN 7 WHEN 'vin' THEN 8
         WHEN 'make' THEN 9 WHEN 'model' THEN 10 WHEN 'year' THEN 11 WHEN 'mileage' THEN 12
         WHEN 'vehicle_condition' THEN 13 WHEN 'store_code' THEN 14 WHEN 'trim' THEN 15
         WHEN 'fuel_type' THEN 16 WHEN 'transmission' THEN 17 WHEN 'body_style' THEN 18
         WHEN 'exterior_color' THEN 19 WHEN 'interior_color' THEN 20 WHEN 'drivetrain' THEN 21
         WHEN 'engine' THEN 22 WHEN 'dealership_name' THEN 23 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- google_shopping — same 23 fields, same required/optional
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_shopping',
       f.field_key IN ('id','title','description','link','image_link','price','availability','vin','make','model','year','mileage','vehicle_condition','store_code'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'link' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'price' THEN 6 WHEN 'availability' THEN 7 WHEN 'vin' THEN 8
         WHEN 'make' THEN 9 WHEN 'model' THEN 10 WHEN 'year' THEN 11 WHEN 'mileage' THEN 12
         WHEN 'vehicle_condition' THEN 13 WHEN 'store_code' THEN 14 WHEN 'trim' THEN 15
         WHEN 'fuel_type' THEN 16 WHEN 'transmission' THEN 17 WHEN 'body_style' THEN 18
         WHEN 'exterior_color' THEN 19 WHEN 'interior_color' THEN 20 WHEN 'drivetrain' THEN 21
         WHEN 'engine' THEN 22 WHEN 'dealership_name' THEN 23 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'vehicle'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;
