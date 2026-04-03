-- Populate canonical_group on all existing feed_schema_fields rows.
-- Every remaining field IS its own canonical (aliases were merged/deleted).

UPDATE feed_schema_fields
SET canonical_group = field_key,
    canonical_status = 'confirmed'
WHERE canonical_group IS NULL;
