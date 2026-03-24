CREATE TABLE IF NOT EXISTS client_data_daily_inputs (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES agency_clients(id) ON DELETE CASCADE,
  metric_date DATE NOT NULL,
  source TEXT NOT NULL,
  leads INTEGER NOT NULL DEFAULT 0 CHECK (leads >= 0),
  phones INTEGER NOT NULL DEFAULT 0 CHECK (phones >= 0),
  custom_value_1_count INTEGER NOT NULL DEFAULT 0 CHECK (custom_value_1_count >= 0),
  custom_value_2_count INTEGER NOT NULL DEFAULT 0 CHECK (custom_value_2_count >= 0),
  custom_value_3_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (custom_value_3_amount >= 0),
  custom_value_5_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  notes TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (client_id, metric_date, source)
);

CREATE INDEX IF NOT EXISTS idx_client_data_daily_inputs_client_metric_date
ON client_data_daily_inputs (client_id, metric_date);

CREATE INDEX IF NOT EXISTS idx_client_data_daily_inputs_client_source_metric_date
ON client_data_daily_inputs (client_id, source, metric_date);

CREATE TABLE IF NOT EXISTS client_data_sale_entries (
  id BIGSERIAL PRIMARY KEY,
  daily_input_id BIGINT NOT NULL REFERENCES client_data_daily_inputs(id) ON DELETE CASCADE,
  brand TEXT NULL,
  model TEXT NULL,
  sale_price_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (sale_price_amount >= 0),
  actual_price_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (actual_price_amount >= 0),
  notes TEXT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_client_data_sale_entries_daily_input_sort_id
ON client_data_sale_entries (daily_input_id, sort_order, id);
