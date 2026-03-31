-- Migration: Deduplicate client_data_daily_inputs rows
--
-- Previous CSV imports created duplicate rows for the same (client_id, metric_date)
-- with different source values (e.g. 'unknown' and 'meta_ads').
-- This migration keeps the best row per (client_id, metric_date) — preferring
-- non-unknown source — and re-links sale entries to the kept row.

BEGIN;

-- Step 1: For each (client_id, metric_date) with duplicates, identify the row to keep
-- (prefer non-unknown source, then highest id as tiebreaker)
CREATE TEMP TABLE _rows_to_keep AS
SELECT DISTINCT ON (client_id, metric_date)
    id AS keep_id,
    client_id,
    metric_date
FROM client_data_daily_inputs
ORDER BY client_id, metric_date,
    CASE WHEN source IS NOT NULL AND source != 'unknown' THEN 0 ELSE 1 END,
    id DESC;

-- Step 2: Identify duplicate rows to delete
CREATE TEMP TABLE _rows_to_delete AS
SELECT di.id AS delete_id, rk.keep_id
FROM client_data_daily_inputs di
JOIN _rows_to_keep rk
    ON rk.client_id = di.client_id AND rk.metric_date = di.metric_date
WHERE di.id != rk.keep_id;

-- Step 3: Re-link sale entries from duplicate rows to the kept row
UPDATE client_data_sale_entries se
SET daily_input_id = d.keep_id
FROM _rows_to_delete d
WHERE se.daily_input_id = d.delete_id;

-- Step 4: Delete duplicate daily input rows
DELETE FROM client_data_daily_inputs
WHERE id IN (SELECT delete_id FROM _rows_to_delete);

-- Step 5: Clean up temp tables
DROP TABLE _rows_to_delete;
DROP TABLE _rows_to_keep;

COMMIT;
