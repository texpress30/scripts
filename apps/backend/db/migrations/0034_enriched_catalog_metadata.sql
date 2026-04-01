-- Enriched catalog metadata: output feeds and template render jobs.
-- Creative templates and treatments are stored in MongoDB;
-- this migration covers the Postgres side for relational tracking.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'output_feed_status') THEN
        CREATE TYPE output_feed_status AS ENUM (
            'draft',
            'rendering',
            'published',
            'error'
        );
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'render_job_status') THEN
        CREATE TYPE render_job_status AS ENUM (
            'pending',
            'in_progress',
            'completed',
            'failed'
        );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS output_feeds (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    subaccount_id INT NOT NULL,
    name TEXT NOT NULL,
    feed_source_id UUID REFERENCES feed_sources(id) ON DELETE SET NULL,
    status output_feed_status NOT NULL DEFAULT 'draft',
    enriched_feed_url TEXT,
    last_render_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_output_feeds_subaccount_id
    ON output_feeds(subaccount_id);

CREATE INDEX IF NOT EXISTS idx_output_feeds_feed_source_id
    ON output_feeds(feed_source_id);

CREATE TABLE IF NOT EXISTS template_render_jobs (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    template_id TEXT NOT NULL,
    output_feed_id UUID NOT NULL REFERENCES output_feeds(id) ON DELETE CASCADE,
    status render_job_status NOT NULL DEFAULT 'pending',
    total_products INT NOT NULL DEFAULT 0,
    rendered_products INT NOT NULL DEFAULT 0,
    errors JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_template_render_jobs_template_id
    ON template_render_jobs(template_id);

CREATE INDEX IF NOT EXISTS idx_template_render_jobs_output_feed_id
    ON template_render_jobs(output_feed_id);
