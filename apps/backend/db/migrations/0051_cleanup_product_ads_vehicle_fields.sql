-- Remove vehicle field links from facebook_product_ads channel.
-- Vehicle fields are now served by facebook_catalog_vehicle_offer.
-- facebook_product_ads should remain e-commerce (catalog_type = 'product') only.

DELETE FROM feed_schema_channel_fields
WHERE channel_slug = 'facebook_product_ads'
  AND schema_field_id IN (
    SELECT id FROM feed_schema_fields WHERE catalog_type = 'vehicle'
  );
