ALTER TABLE client_data_daily_inputs
  ADD COLUMN IF NOT EXISTS custom_value_4_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (custom_value_4_amount >= 0),
  ADD COLUMN IF NOT EXISTS sales_count INTEGER NOT NULL DEFAULT 0 CHECK (sales_count >= 0);

UPDATE client_data_daily_inputs
SET custom_value_4_amount = COALESCE(custom_value_4_amount, 0),
    sales_count = COALESCE(sales_count, 0)
WHERE custom_value_4_amount IS NULL OR sales_count IS NULL;
