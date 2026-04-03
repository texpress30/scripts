-- 0046: Catalog sub-types — platform-specific variants per catalog type
-- e.g. Vehicle has: vehicle_listings, vehicle_offers, vehicle_model

-- 1. Create feed_catalog_subtypes table
CREATE TABLE IF NOT EXISTS feed_catalog_subtypes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog_type catalog_type NOT NULL,
    subtype_slug VARCHAR(100) NOT NULL,
    subtype_name VARCHAR(200) NOT NULL,
    description TEXT,
    icon_hint VARCHAR(50),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(catalog_type, subtype_slug)
);

CREATE INDEX IF NOT EXISTS idx_catalog_subtypes_type ON feed_catalog_subtypes(catalog_type);
CREATE INDEX IF NOT EXISTS idx_catalog_subtypes_type_slug ON feed_catalog_subtypes(catalog_type, subtype_slug);

-- 2. Seed known sub-types
-- Vehicle
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('vehicle', 'vehicle_listings', 'Vehicle Listings', 'Inventar vehicule cu VIN, km, preț', 'car', 1),
    ('vehicle', 'vehicle_offers', 'Vehicle Offers', 'Vehicule cu oferte finanțare (rate, avans, cashback)', 'money', 2),
    ('vehicle', 'vehicle_model', 'Vehicle Models', 'Make/model level, fără VIN individual', 'tag', 3)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Product
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('product', 'product_physical', 'Physical Products', 'Produse fizice e-commerce', 'box', 1),
    ('product', 'product_digital', 'Digital Products', 'Produse digitale, software, apps', 'download', 2)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Hotel
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('hotel', 'hotel_standard', 'Hotel', 'Proprietăți hoteliere standard', 'building', 1)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Flight
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('flight', 'flight_standard', 'Flight', 'Rute de zbor și bilete', 'plane', 1)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Home Listing
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('home_listing', 'home_listing_standard', 'Real Estate', 'Listări imobiliare', 'home', 1)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- Media
INSERT INTO feed_catalog_subtypes (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
VALUES
    ('media', 'media_multishow', 'Multi-Show Experience', 'Cataloage streaming multi-show', 'tv', 1),
    ('media', 'media_card', 'Media Card', 'Cataloage media card format', 'film', 2)
ON CONFLICT (catalog_type, subtype_slug) DO NOTHING;

-- 3. Add subtype_slug column to feed_schema_channel_fields (nullable for backward compat)
ALTER TABLE feed_schema_channel_fields ADD COLUMN IF NOT EXISTS subtype_slug VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_schema_channel_fields_subtype ON feed_schema_channel_fields(subtype_slug);

-- 4. Populate subtype_slug for existing channel fields
UPDATE feed_schema_channel_fields SET subtype_slug = 'vehicle_listings'
WHERE channel_slug = 'google_vehicle_ads_v3' AND subtype_slug IS NULL;

UPDATE feed_schema_channel_fields SET subtype_slug = 'vehicle_listings'
WHERE channel_slug = 'google_vehicle_listings' AND subtype_slug IS NULL;

UPDATE feed_schema_channel_fields SET subtype_slug = 'vehicle_offers'
WHERE channel_slug = 'facebook_product_ads' AND subtype_slug IS NULL;

UPDATE feed_schema_channel_fields SET subtype_slug = 'vehicle_listings'
WHERE channel_slug = 'tiktok_automotive_inventory' AND subtype_slug IS NULL;

-- google_shopping is generic, leave NULL unless explicitly vehicle context
-- (it can be used across product types too)
