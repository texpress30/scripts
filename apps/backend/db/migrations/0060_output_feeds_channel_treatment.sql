-- Add channel_id and treatment_mode to output_feeds so the creation modal can
-- associate an output feed with a specific feed-management channel and choose
-- between single-treatment or multi-treatment creative mode.

ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS channel_id VARCHAR;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS treatment_mode VARCHAR NOT NULL DEFAULT 'single';
