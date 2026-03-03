ALTER TABLE client_business_inputs
  ADD COLUMN IF NOT EXISTS sales_count INTEGER NULL;

ALTER TABLE client_business_inputs
  ADD COLUMN IF NOT EXISTS new_customers INTEGER NULL;
