-- Cleanup: normalize channel slugs + seed Product catalog fields
--
-- 1. Fix any non-normalized channel_slug values in existing data
-- 2. Seed Product catalog fields (22 fields) for google_shopping + facebook_product_ads

-- ============================================================================
-- 1. Fix non-normalized slugs (idempotent — skips if already correct)
-- ============================================================================

UPDATE feed_schema_channel_fields
SET channel_slug = LOWER(REGEXP_REPLACE(TRIM(channel_slug), '[\s.\-]+', '_', 'g'))
WHERE channel_slug != LOWER(REGEXP_REPLACE(TRIM(channel_slug), '[\s.\-]+', '_', 'g'));

UPDATE feed_schema_imports
SET channel_slug = LOWER(REGEXP_REPLACE(TRIM(channel_slug), '[\s.\-]+', '_', 'g'))
WHERE channel_slug != LOWER(REGEXP_REPLACE(TRIM(channel_slug), '[\s.\-]+', '_', 'g'));

-- ============================================================================
-- 2. Seed Product fields (7 common + 15 product-specific = 22 total)
-- ============================================================================

-- Common / system fields
INSERT INTO feed_schema_fields (id, catalog_type, field_key, display_name, description, data_type, allowed_values, example_value, is_system)
VALUES
  (gen_random_uuid(), 'product', 'id',               'ID',               'Unique identifier for the item',       'string',    NULL, 'SKU-12345', true),
  (gen_random_uuid(), 'product', 'title',            'Title',            'Title of the item',                    'string',    NULL, 'Blue Cotton T-Shirt', true),
  (gen_random_uuid(), 'product', 'description',      'Description',      'Description of the item',              'string',    NULL, NULL, true),
  (gen_random_uuid(), 'product', 'link',             'Link',             'URL to the item''s page',              'url',       NULL, 'https://example.com/product/blue-tshirt', true),
  (gen_random_uuid(), 'product', 'image_link',       'Image Link',       'URL of the main image',                'url',       NULL, 'https://example.com/images/blue-tshirt.jpg', true),
  (gen_random_uuid(), 'product', 'price',            'Price',            'Price of the item',                    'price',     NULL, '29.99 RON', true),
  (gen_random_uuid(), 'product', 'availability',     'Availability',     'Stock status',                         'enum',      '["in_stock","out_of_stock","preorder","backorder"]', 'in_stock', false),

  -- Product-specific fields
  (gen_random_uuid(), 'product', 'brand',            'Brand',            'Brand of the product',                 'string',    NULL, 'Nike', false),
  (gen_random_uuid(), 'product', 'gtin',             'GTIN',             'Global Trade Item Number (UPC, EAN, ISBN)', 'string', NULL, '0123456789012', false),
  (gen_random_uuid(), 'product', 'mpn',              'MPN',              'Manufacturer Part Number',             'string',    NULL, NULL, false),
  (gen_random_uuid(), 'product', 'condition',        'Condition',        'Condition of the product',             'enum',      '["new","refurbished","used"]', 'new', false),
  (gen_random_uuid(), 'product', 'sale_price',       'Sale Price',       'Discounted price',                     'price',     NULL, '19.99 RON', false),
  (gen_random_uuid(), 'product', 'google_product_category', 'Google Product Category', 'Google''s product taxonomy category', 'string', NULL, 'Apparel & Accessories > Clothing', false),
  (gen_random_uuid(), 'product', 'product_type',     'Product Type',     'Your product category',                'string',    NULL, 'T-Shirts', false),
  (gen_random_uuid(), 'product', 'color',            'Color',            'Color of the product',                 'string',    NULL, 'Blue', false),
  (gen_random_uuid(), 'product', 'size',             'Size',             'Size of the product',                  'string',    NULL, 'M', false),
  (gen_random_uuid(), 'product', 'gender',           'Gender',           'Target gender',                        'enum',      '["male","female","unisex"]', NULL, false),
  (gen_random_uuid(), 'product', 'age_group',        'Age Group',        'Target age group',                     'enum',      '["newborn","infant","toddler","kids","adult"]', NULL, false),
  (gen_random_uuid(), 'product', 'material',         'Material',         'Material of the product',              'string',    NULL, 'Cotton', false),
  (gen_random_uuid(), 'product', 'pattern',          'Pattern',          'Pattern or print',                     'string',    NULL, NULL, false),
  (gen_random_uuid(), 'product', 'additional_image_link', 'Additional Images', 'Additional product images',      'url',       NULL, NULL, false),
  (gen_random_uuid(), 'product', 'shipping_weight',  'Shipping Weight',  'Weight for shipping calculation',      'string',    NULL, '0.3 kg', false)
ON CONFLICT (catalog_type, field_key) DO NOTHING;

-- ============================================================================
-- 3. Link Product fields to google_shopping + facebook_product_ads
-- ============================================================================

-- google_shopping — all 22 product fields
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'google_shopping',
       f.field_key IN ('id','title','description','link','image_link','price','availability'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'link' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'price' THEN 6 WHEN 'availability' THEN 7
         WHEN 'brand' THEN 8 WHEN 'gtin' THEN 9 WHEN 'mpn' THEN 10 WHEN 'condition' THEN 11
         WHEN 'sale_price' THEN 12 WHEN 'google_product_category' THEN 13 WHEN 'product_type' THEN 14
         WHEN 'color' THEN 15 WHEN 'size' THEN 16 WHEN 'gender' THEN 17 WHEN 'age_group' THEN 18
         WHEN 'material' THEN 19 WHEN 'pattern' THEN 20 WHEN 'additional_image_link' THEN 21
         WHEN 'shipping_weight' THEN 22 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'product'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;

-- facebook_product_ads — all 22 product fields
INSERT INTO feed_schema_channel_fields (id, schema_field_id, channel_slug, is_required, channel_field_name, sort_order)
SELECT gen_random_uuid(), f.id, 'facebook_product_ads',
       f.field_key IN ('id','title','description','link','image_link','price','availability'),
       f.field_key,
       CASE f.field_key
         WHEN 'id' THEN 1 WHEN 'title' THEN 2 WHEN 'description' THEN 3 WHEN 'link' THEN 4
         WHEN 'image_link' THEN 5 WHEN 'price' THEN 6 WHEN 'availability' THEN 7
         WHEN 'brand' THEN 8 WHEN 'gtin' THEN 9 WHEN 'mpn' THEN 10 WHEN 'condition' THEN 11
         WHEN 'sale_price' THEN 12 WHEN 'google_product_category' THEN 13 WHEN 'product_type' THEN 14
         WHEN 'color' THEN 15 WHEN 'size' THEN 16 WHEN 'gender' THEN 17 WHEN 'age_group' THEN 18
         WHEN 'material' THEN 19 WHEN 'pattern' THEN 20 WHEN 'additional_image_link' THEN 21
         WHEN 'shipping_weight' THEN 22 ELSE 99
       END
FROM feed_schema_fields f WHERE f.catalog_type = 'product'
ON CONFLICT (schema_field_id, channel_slug) DO NOTHING;
