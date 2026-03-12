ALTER TABLE media_buying_configs
    ADD COLUMN IF NOT EXISTS custom_rate_label_1 TEXT NOT NULL DEFAULT 'Custom Value Rate 1',
    ADD COLUMN IF NOT EXISTS custom_rate_label_2 TEXT NOT NULL DEFAULT 'Custom Value Rate 2',
    ADD COLUMN IF NOT EXISTS custom_cost_label_1 TEXT NOT NULL DEFAULT 'Cost Custom Value 1',
    ADD COLUMN IF NOT EXISTS custom_cost_label_2 TEXT NOT NULL DEFAULT 'Cost Custom Value 2';
