-- 0036: Extend output_feeds for feed generation and public URL access.
-- Adds format, public token, refresh scheduling, generation metadata,
-- field mapping reference, and S3 storage key.

ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS feed_format VARCHAR(20) DEFAULT 'xml';
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS public_token VARCHAR(64) UNIQUE;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS refresh_interval_hours INTEGER DEFAULT 24;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS last_generated_at TIMESTAMPTZ;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS products_count INTEGER DEFAULT 0;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT DEFAULT 0;
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS field_mapping_id UUID REFERENCES field_mappings(id);
ALTER TABLE output_feeds ADD COLUMN IF NOT EXISTS s3_key VARCHAR(500);

-- Generate token for existing feeds that lack one.
UPDATE output_feeds SET public_token = encode(gen_random_bytes(32), 'hex')
WHERE public_token IS NULL;

CREATE INDEX IF NOT EXISTS idx_output_feeds_public_token
    ON output_feeds(public_token);

CREATE INDEX IF NOT EXISTS idx_output_feeds_last_generated
    ON output_feeds(last_generated_at);
