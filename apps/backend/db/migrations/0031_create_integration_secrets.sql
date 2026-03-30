-- Create the integration_secrets table.
-- Previously only created at runtime by _ensure_schema() which skips in production.

CREATE TABLE IF NOT EXISTS integration_secrets (
    provider TEXT NOT NULL,
    secret_key TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'agency_default',
    encrypted_value TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(provider, secret_key, scope)
);

CREATE INDEX IF NOT EXISTS idx_integration_secrets_provider_scope
    ON integration_secrets(provider, scope);
