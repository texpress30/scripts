-- 0060: Background removal pipeline + preview render cache.
--
-- Creates:
--   * image_cutouts            — one row per (client_id, source_hash); holds the
--                                status of a background-removed cutout for a source
--                                product image. Dedup key is the SHA-256 of the raw
--                                image bytes so variants of the same product that
--                                share a photo collapse to a single cutout.
--   * template_render_results  — cache of rendered preview PNGs, keyed by
--                                (template_id, template_version, output_feed_id,
--                                product_id). Cache is invalidated whenever a
--                                template is mutated (version bump) or treatments
--                                change on the parent output feed.
--   * cutout_batch_jobs        — progress tracking for bulk cutout jobs (e.g. when
--                                a new feed source is connected for the first time
--                                and we need to prime thousands of cutouts).
--   * output_feeds.include_out_of_stock — per-feed flag to allow OOS products
--                                through the enriched feed generator (default off).

CREATE TABLE IF NOT EXISTS image_cutouts (
    id BIGSERIAL PRIMARY KEY,
    subaccount_id INT NOT NULL,
    client_id INT NOT NULL,
    -- Real dedup key: SHA-256 of the raw image bytes. Variants of the same
    -- product that share a photo collapse to a single cutout.
    source_hash CHAR(64) NOT NULL,
    -- URL-based cache hint: lets fast paths (shuffle pool, image renderer)
    -- resolve a cutout without re-downloading the source bytes to hash them.
    -- Not unique — the same content may live at multiple URLs.
    source_url_hash CHAR(64),
    source_url TEXT NOT NULL,
    media_id TEXT,
    model VARCHAR(32) NOT NULL DEFAULT 'u2net',
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    has_native_alpha BOOLEAN NOT NULL DEFAULT FALSE,
    cutout_width INT,
    cutout_height INT,
    error TEXT,
    last_referenced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_image_cutouts_client_hash
    ON image_cutouts(client_id, source_hash);

CREATE INDEX IF NOT EXISTS idx_image_cutouts_client_url_hash
    ON image_cutouts(client_id, source_url_hash)
    WHERE source_url_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_image_cutouts_status
    ON image_cutouts(status, updated_at);

CREATE INDEX IF NOT EXISTS idx_image_cutouts_subaccount
    ON image_cutouts(subaccount_id);

CREATE INDEX IF NOT EXISTS idx_image_cutouts_last_referenced
    ON image_cutouts(last_referenced_at);


CREATE TABLE IF NOT EXISTS template_render_results (
    id BIGSERIAL PRIMARY KEY,
    template_id TEXT NOT NULL,
    template_version INT NOT NULL,
    output_feed_id UUID NOT NULL REFERENCES output_feeds(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    image_url TEXT,
    media_id TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'ready',
    error TEXT,
    rendered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_template_render_results_key
    ON template_render_results(template_id, template_version, output_feed_id, product_id);

CREATE INDEX IF NOT EXISTS idx_template_render_results_feed
    ON template_render_results(output_feed_id, template_version);


CREATE TABLE IF NOT EXISTS cutout_batch_jobs (
    id BIGSERIAL PRIMARY KEY,
    subaccount_id INT NOT NULL,
    client_id INT NOT NULL,
    feed_source_id UUID REFERENCES feed_sources(id) ON DELETE SET NULL,
    kind VARCHAR(16) NOT NULL DEFAULT 'bulk',   -- bulk | prime | delta
    total INT NOT NULL DEFAULT 0,
    done INT NOT NULL DEFAULT 0,
    failed INT NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cutout_batch_jobs_feed
    ON cutout_batch_jobs(feed_source_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cutout_batch_jobs_status
    ON cutout_batch_jobs(status, created_at DESC);


ALTER TABLE output_feeds
    ADD COLUMN IF NOT EXISTS include_out_of_stock BOOLEAN NOT NULL DEFAULT FALSE;
