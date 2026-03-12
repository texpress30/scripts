ALTER TABLE media_buying_configs
    ADD COLUMN IF NOT EXISTS visible_columns TEXT[];
