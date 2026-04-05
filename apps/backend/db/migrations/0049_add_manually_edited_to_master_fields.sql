-- Add manually_edited flag to master_field_mappings.
-- When TRUE, auto-mapping (fuzzy or AI) will skip this field,
-- preserving the user's explicit choice (including "no mapping").
ALTER TABLE master_field_mappings
    ADD COLUMN IF NOT EXISTS manually_edited BOOLEAN NOT NULL DEFAULT FALSE;
