-- 0047: Extend catalog_type ENUM with 'destination' and 'service'
--
-- IMPORTANT: ALTER TYPE ADD VALUE cannot be used in the same transaction
-- as INSERTs that reference the new values. This migration ONLY adds the
-- enum values. Seed data is in 0048.

ALTER TYPE catalog_type ADD VALUE IF NOT EXISTS 'destination';
ALTER TYPE catalog_type ADD VALUE IF NOT EXISTS 'service';
