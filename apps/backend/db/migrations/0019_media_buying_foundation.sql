CREATE TABLE IF NOT EXISTS media_buying_configs (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES agency_clients(id) ON DELETE CASCADE,
    template_type TEXT NOT NULL DEFAULT 'lead' CHECK (template_type IN ('lead', 'ecommerce', 'programmatic')),
    display_currency TEXT NOT NULL DEFAULT 'RON',
    custom_label_1 TEXT NOT NULL DEFAULT 'Custom Value 1',
    custom_label_2 TEXT NOT NULL DEFAULT 'Custom Value 2',
    custom_label_3 TEXT NOT NULL DEFAULT 'Custom Value 3',
    custom_label_4 TEXT NOT NULL DEFAULT 'Custom Value 4',
    custom_label_5 TEXT NOT NULL DEFAULT 'Custom Value 5',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id)
);

CREATE INDEX IF NOT EXISTS idx_media_buying_configs_client_id
    ON media_buying_configs(client_id);

CREATE TABLE IF NOT EXISTS media_buying_lead_daily_manual_values (
    id BIGSERIAL PRIMARY KEY,
    client_id BIGINT NOT NULL REFERENCES agency_clients(id) ON DELETE CASCADE,
    metric_date DATE NOT NULL,
    leads INTEGER NOT NULL DEFAULT 0 CHECK (leads >= 0),
    phones INTEGER NOT NULL DEFAULT 0 CHECK (phones >= 0),
    custom_value_1_count INTEGER NOT NULL DEFAULT 0 CHECK (custom_value_1_count >= 0),
    custom_value_2_count INTEGER NOT NULL DEFAULT 0 CHECK (custom_value_2_count >= 0),
    custom_value_3_amount_ron NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (custom_value_3_amount_ron >= 0),
    custom_value_4_amount_ron NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (custom_value_4_amount_ron >= 0),
    custom_value_5_amount_ron NUMERIC(18,2) NOT NULL DEFAULT 0,
    sales_count INTEGER NOT NULL DEFAULT 0 CHECK (sales_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (client_id, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_media_buying_lead_daily_manual_values_client_date
    ON media_buying_lead_daily_manual_values(client_id, metric_date);
