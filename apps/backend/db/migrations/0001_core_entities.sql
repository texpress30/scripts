-- Core MCC schema (PostgreSQL)
-- Scope: agencies/subaccounts identity + ad operations + AI recommendation lifecycle.

CREATE TYPE ad_platform AS ENUM ('google', 'meta', 'tiktok');
CREATE TYPE recommendation_status AS ENUM ('open', 'accepted', 'rejected', 'dismissed');
CREATE TYPE recommendation_action_status AS ENUM ('queued', 'running', 'done', 'failed');

CREATE TABLE agencies (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE subaccounts (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agency_id, code)
);

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE memberships (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT REFERENCES subaccounts(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (agency_id, subaccount_id, user_id)
);

-- Operational tables always carry agency_id and subaccount_id.
CREATE TABLE ad_platform_connections (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    platform ad_platform NOT NULL,
    external_id TEXT NOT NULL,
    account_name TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sync_at TIMESTAMPTZ,
    UNIQUE (platform, external_id)
);

CREATE TABLE campaigns (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    platform ad_platform NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    objective TEXT,
    starts_on DATE,
    ends_on DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE TABLE ad_sets (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    campaign_id BIGINT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    platform ad_platform NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    budget_daily NUMERIC(14, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE TABLE creatives (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    platform ad_platform NOT NULL,
    external_id TEXT NOT NULL,
    headline TEXT,
    body TEXT,
    cta TEXT,
    landing_page_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE TABLE ads (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    campaign_id BIGINT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ad_set_id BIGINT NOT NULL REFERENCES ad_sets(id) ON DELETE CASCADE,
    creative_id BIGINT REFERENCES creatives(id) ON DELETE SET NULL,
    platform ad_platform NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (platform, external_id)
);

CREATE TABLE creative_variants (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    creative_id BIGINT NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
    variant_key TEXT NOT NULL,
    variant_payload JSONB NOT NULL,
    is_winner BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (creative_id, variant_key)
);

CREATE TABLE insights_daily (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE SET NULL,
    ad_set_id BIGINT REFERENCES ad_sets(id) ON DELETE SET NULL,
    ad_id BIGINT REFERENCES ads(id) ON DELETE SET NULL,
    metric_date DATE NOT NULL,
    impressions BIGINT NOT NULL DEFAULT 0,
    clicks BIGINT NOT NULL DEFAULT 0,
    spend NUMERIC(14, 2) NOT NULL DEFAULT 0,
    conversions NUMERIC(14, 4) NOT NULL DEFAULT 0,
    ctr NUMERIC(9, 6),
    cpc NUMERIC(14, 4),
    cpa NUMERIC(14, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (subaccount_id, metric_date, campaign_id, ad_set_id, ad_id)
);

CREATE TABLE ai_recommendations (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    campaign_id BIGINT REFERENCES campaigns(id) ON DELETE SET NULL,
    ad_set_id BIGINT REFERENCES ad_sets(id) ON DELETE SET NULL,
    ad_id BIGINT REFERENCES ads(id) ON DELETE SET NULL,
    recommendation_type TEXT NOT NULL,
    rationale TEXT NOT NULL,
    payload JSONB NOT NULL,
    status recommendation_status NOT NULL DEFAULT 'open',
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE recommendation_actions (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    recommendation_id BIGINT NOT NULL REFERENCES ai_recommendations(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    status recommendation_action_status NOT NULL DEFAULT 'queued',
    action_payload JSONB NOT NULL,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- External ID mapping layer for reconciliation across Google/Meta/TikTok.
CREATE TABLE external_id_mappings (
    id BIGSERIAL PRIMARY KEY,
    agency_id BIGINT NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    subaccount_id BIGINT NOT NULL REFERENCES subaccounts(id) ON DELETE CASCADE,
    platform ad_platform NOT NULL,
    entity_type TEXT NOT NULL,
    internal_id BIGINT NOT NULL,
    external_id TEXT NOT NULL,
    external_parent_id TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,
    UNIQUE (platform, entity_type, external_id),
    UNIQUE (platform, entity_type, internal_id)
);

-- Composite indexes for frequent queries.
CREATE INDEX idx_insights_daily_subaccount_date
    ON insights_daily (subaccount_id, metric_date DESC);

CREATE INDEX idx_ai_recommendations_subaccount_generated_at
    ON ai_recommendations (subaccount_id, generated_at DESC);

CREATE INDEX idx_campaigns_platform_external_id
    ON campaigns (platform, external_id);

CREATE INDEX idx_ad_sets_platform_external_id
    ON ad_sets (platform, external_id);

CREATE INDEX idx_ads_platform_external_id
    ON ads (platform, external_id);

CREATE INDEX idx_creatives_platform_external_id
    ON creatives (platform, external_id);

CREATE INDEX idx_ad_platform_connections_platform_external_id
    ON ad_platform_connections (platform, external_id);

CREATE INDEX idx_external_id_mappings_platform_external_id
    ON external_id_mappings (platform, external_id);
