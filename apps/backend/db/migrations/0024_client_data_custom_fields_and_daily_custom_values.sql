CREATE TABLE IF NOT EXISTS client_data_custom_fields (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES agency_clients(id) ON DELETE CASCADE,
  field_key TEXT NOT NULL,
  label TEXT NOT NULL,
  value_kind TEXT NOT NULL CHECK (value_kind IN ('count', 'amount')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  archived_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (client_id, field_key)
);

CREATE INDEX IF NOT EXISTS idx_client_data_custom_fields_client_active_sort
ON client_data_custom_fields (client_id, is_active, sort_order);

CREATE INDEX IF NOT EXISTS idx_client_data_custom_fields_client_field_key
ON client_data_custom_fields (client_id, field_key);

CREATE TABLE IF NOT EXISTS client_data_daily_custom_values (
  id BIGSERIAL PRIMARY KEY,
  daily_input_id BIGINT NOT NULL REFERENCES client_data_daily_inputs(id) ON DELETE CASCADE,
  custom_field_id BIGINT NOT NULL REFERENCES client_data_custom_fields(id) ON DELETE CASCADE,
  numeric_value NUMERIC(18,2) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (daily_input_id, custom_field_id)
);

CREATE INDEX IF NOT EXISTS idx_client_data_daily_custom_values_custom_field_id
ON client_data_daily_custom_values (custom_field_id);

CREATE INDEX IF NOT EXISTS idx_client_data_daily_custom_values_daily_input_id
ON client_data_daily_custom_values (daily_input_id);
