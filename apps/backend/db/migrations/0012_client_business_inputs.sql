CREATE TABLE IF NOT EXISTS client_business_inputs (
  id BIGSERIAL PRIMARY KEY,
  client_id BIGINT NOT NULL REFERENCES agency_clients(id) ON DELETE CASCADE,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  period_grain TEXT NOT NULL,
  applicants INTEGER NULL,
  approved_applicants INTEGER NULL,
  actual_revenue NUMERIC(18, 6) NULL,
  target_revenue NUMERIC(18, 6) NULL,
  cogs NUMERIC(18, 6) NULL,
  taxes NUMERIC(18, 6) NULL,
  gross_profit NUMERIC(18, 6) NULL,
  contribution_profit NUMERIC(18, 6) NULL,
  notes TEXT NULL,
  source TEXT NOT NULL DEFAULT 'manual',
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT client_business_inputs_period_range_check CHECK (period_end >= period_start),
  CONSTRAINT client_business_inputs_period_grain_check CHECK (period_grain IN ('day', 'week')),
  CONSTRAINT client_business_inputs_day_grain_consistency_check CHECK (
    (period_grain = 'day' AND period_start = period_end)
    OR period_grain = 'week'
  ),
  CONSTRAINT client_business_inputs_unique_period UNIQUE (client_id, period_start, period_end, period_grain)
);

CREATE INDEX IF NOT EXISTS idx_client_business_inputs_client_id
ON client_business_inputs (client_id);

CREATE INDEX IF NOT EXISTS idx_client_business_inputs_grain_period_start
ON client_business_inputs (period_grain, period_start);

CREATE INDEX IF NOT EXISTS idx_client_business_inputs_client_period_start_desc
ON client_business_inputs (client_id, period_start DESC);
