CREATE TABLE IF NOT EXISTS sync_run_chunks (
  id BIGSERIAL PRIMARY KEY,
  job_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  status TEXT NOT NULL,
  date_start DATE NOT NULL,
  date_end DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ NULL,
  finished_at TIMESTAMPTZ NULL,
  error TEXT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT sync_run_chunks_job_id_fk
    FOREIGN KEY (job_id) REFERENCES sync_runs(job_id) ON DELETE CASCADE,
  CONSTRAINT sync_run_chunks_date_range_check CHECK (date_end >= date_start),
  CONSTRAINT sync_run_chunks_chunk_index_check CHECK (chunk_index >= 0),
  CONSTRAINT sync_run_chunks_job_id_chunk_index_unique UNIQUE (job_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_sync_run_chunks_job_id_chunk_index
ON sync_run_chunks (job_id, chunk_index);

CREATE INDEX IF NOT EXISTS idx_sync_run_chunks_job_id_status
ON sync_run_chunks (job_id, status);
