-- 0047: Add destination + service catalog types, new product subtypes, and seed fields
--
-- 1. Extend catalog_type ENUM with 'destination' and 'service'
-- 2. Seed feed_catalog_subtypes for destination, service, and product (local/other)
-- 3. Seed feed_schema_fields for destination (16 fields) and service (13 fields)
-- 4. Link destination/service fields to placeholder channels via feed_schema_channel_fields

-- ============================================================================
-- 1. Extend catalog_type ENUM
-- ============================================================================

ALTER TYPE catalog_type ADD VALUE IF NOT EXISTS 'destination';
ALTER TYPE catalog_type ADD VALUE IF NOT EXISTS 'service';

-- ============================================================================
-- 2. Seed feed_catalog_subtypes
-- ============================================================================

-- Destination
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('destination', 'destination_standard', 'Destination', 'Destinații turistice / locații', 'map-pin', 1)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Service
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('service', 'professional_services', 'Professional Services', 'Servicii profesionale (consultanță, reparații, etc.)', 'briefcase', 1)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Product — new subtypes
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('product', 'product_local', 'Local Products', 'Produse locale / inventar de proximitate', 'store', 3),
    ('product', 'product_other', 'Other Products', 'Alte tipuri de produse', 'package', 4)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- ============================================================================
-- 3. Seed Destination fields (16 fields: 5 required + 11 optional)
-- ============================================================================

INSERT INTO feed_schema_fields (id, catalog_type, field_key, display_name, description, data_type, allowed_values, format_pattern, example_value, is_system)
VALUES
  -- Required / system fields
  (gen_random_uuid(), 'destination', 'id',            'ID',            'Unique identifier for the destination',   'string',  NULL, NULL, 'DEST-001', true),
  (gen_random_uuid(), 'destination', 'name',          'Name',          'Destination name',                        'string',  NULL, NULL, 'Brașov Old Town', true),
  (gen_random_uuid(), 'destination', 'url',           'URL',           'URL to the destination page',             'url',     NULL, NULL, 'https://example.com/destinations/brasov', true),
  (gen_random_uuid(), 'destination', 'image_link',    'Image Link',    'URL of the main image',                   'url',     NULL, NULL, 'https://example.com/images/brasov.jpg', true),
  (gen_random_uuid(), 'destination', 'description',   'Description',   'Description of the destination',          'string',  NULL, NULL, 'Historic city center with medieval architecture', true),

  -- Optional fields
  (gen_random_uuid(), 'destination', 'address',       'Address',       'Street address',                          'string',  NULL, NULL, 'Piața Sfatului 1', false),
  (gen_random_uuid(), 'destination', 'city',          'City',          'City name',                               'string',  NULL, NULL, 'Brașov', false),
  (gen_random_uuid(), 'destination', 'country',       'Country',       'Country code or name',                    'string',  NULL, '^[A-Z]{2}$', 'RO', false),
  (gen_random_uuid(), 'destination', 'latitude',      'Latitude',      'GPS latitude',                            'number',  NULL, NULL, '45.6427', false),
  (gen_random_uuid(), 'destination', 'longitude',     'Longitude',     'GPS longitude',                           'number',  NULL, NULL, '25.5887', false),
  (gen_random_uuid(), 'destination', 'price_range',   'Price Range',   'Price indication or range',               'string',  NULL, NULL, '$$', false),
  (gen_random_uuid(), 'destination', 'category',      'Category',      'Destination category',                    'string',  NULL, NULL, 'Historic Site', false),
  (gen_random_uuid(), 'destination', 'phone',         'Phone',         'Contact phone number',                    'string',  NULL, NULL, '+40 268 472 000', false),
  (gen_random_uuid(), 'destination', 'rating',        'Rating',        'Average rating (1-5)',                    'number',  NULL, NULL, '4.7', false),
  (gen_random_uuid(), 'destination', 'hours',         'Hours',         'Operating hours',                         'string',  NULL, NULL, 'Mon-Sun 09:00-18:00', false),
  (gen_random_uuid(), 'destination', 'neighborhood',  'Neighborhood',  'Area or neighborhood',                    'string',  NULL, NULL, 'Centru Vechi', false)
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- ============================================================================
-- 4. Seed Service fields (13 fields: 4 required + 9 optional)
-- ============================================================================

INSERT INTO feed_schema_fields (id, catalog_type, field_key, display_name, description, data_type, allowed_values, format_pattern, example_value, is_system)
VALUES
  -- Required / system fields
  (gen_random_uuid(), 'service', 'id',              'ID',              'Unique identifier for the service',       'string',  NULL, NULL, 'SVC-001', true),
  (gen_random_uuid(), 'service', 'title',           'Title',           'Service title',                           'string',  NULL, NULL, 'Plumbing Repair', true),
  (gen_random_uuid(), 'service', 'url',             'URL',             'URL to the service page',                 'url',     NULL, NULL, 'https://example.com/services/plumbing', true),
  (gen_random_uuid(), 'service', 'image_link',      'Image Link',      'URL of the main image',                   'url',     NULL, NULL, 'https://example.com/images/plumbing.jpg', true),

  -- Optional fields
  (gen_random_uuid(), 'service', 'description',     'Description',     'Description of the service',              'string',  NULL, NULL, 'Emergency and scheduled plumbing services', false),
  (gen_random_uuid(), 'service', 'category',        'Category',        'Service category',                        'string',  NULL, NULL, 'Home Services', false),
  (gen_random_uuid(), 'service', 'price',           'Price',           'Service price or starting price',         'price',   NULL, NULL, '150.00 RON', false),
  (gen_random_uuid(), 'service', 'address',         'Address',         'Business address',                        'string',  NULL, NULL, 'Str. Lipscani 10', false),
  (gen_random_uuid(), 'service', 'city',            'City',            'City name',                               'string',  NULL, NULL, 'București', false),
  (gen_random_uuid(), 'service', 'phone',           'Phone',           'Contact phone number',                    'string',  NULL, NULL, '+40 21 300 0000', false),
  (gen_random_uuid(), 'service', 'rating',          'Rating',          'Average rating (1-5)',                    'number',  NULL, NULL, '4.5', false),
  (gen_random_uuid(), 'service', 'availability',    'Availability',    'Service availability status',             'enum',    '["available","unavailable","by_appointment"]', NULL, 'available', false),
  (gen_random_uuid(), 'service', 'area_served',     'Area Served',     'Geographic area served',                  'string',  NULL, NULL, 'București, Ilfov', false)
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- ============================================================================
-- 5. Link Destination fields to facebook_destination_ads channel
-- ============================================================================

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'facebook_destination_ads',
       f.field_key IN ('id','name','url','image_link','description'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'name' THEN 2 WHEN 'description' THEN 3 WHEN 'url' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'address' THEN 6 WHEN 'city' THEN 7 WHEN 'country' THEN 8
         WHEN 'latitude' THEN 9 WHEN 'longitude' THEN 10 WHEN 'price_range' THEN 11
         WHEN 'category' THEN 12 WHEN 'phone' THEN 13 WHEN 'rating' THEN 14
         WHEN 'hours' THEN 15 WHEN 'neighborhood' THEN 16 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'destination'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- tiktok_destination — same fields
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'tiktok_destination',
       f.field_key IN ('id','name','url','image_link','description'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'name' THEN 2 WHEN 'description' THEN 3 WHEN 'url' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'address' THEN 6 WHEN 'city' THEN 7 WHEN 'country' THEN 8
         WHEN 'latitude' THEN 9 WHEN 'longitude' THEN 10 WHEN 'price_range' THEN 11
         WHEN 'category' THEN 12 WHEN 'phone' THEN 13 WHEN 'rating' THEN 14
         WHEN 'hours' THEN 15 WHEN 'neighborhood' THEN 16 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'destination'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- ============================================================================
-- 6. Link Service fields to facebook_professional_services channel
-- ============================================================================

INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'facebook_professional_services',
       f.field_key IN ('id','title','url','image_link'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'url' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'category' THEN 6 WHEN 'price' THEN 7
         WHEN 'address' THEN 8 WHEN 'city' THEN 9 WHEN 'phone' THEN 10
         WHEN 'rating' THEN 11 WHEN 'availability' THEN 12 WHEN 'area_served' THEN 13 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'service'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;
