from __future__ import annotations

from datetime import date
import json
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_SYNC_RUN_CHUNKS_SELECT_COLUMNS = """
    id,
    job_id,
    chunk_index,
    status,
    date_start,
    date_end,
    created_at,
    updated_at,
    started_at,
    finished_at,
    error,
    metadata,
    attempts,
    rows_written,
    duration_ms
"""


class SyncRunChunksStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for sync_run_chunks persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
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
                        )
                        """
                    )
                    cur.execute("ALTER TABLE sync_run_chunks ADD COLUMN IF NOT EXISTS attempts INTEGER DEFAULT 0")
                    cur.execute("ALTER TABLE sync_run_chunks ADD COLUMN IF NOT EXISTS rows_written BIGINT DEFAULT 0")
                    cur.execute("ALTER TABLE sync_run_chunks ADD COLUMN IF NOT EXISTS duration_ms INTEGER NULL")

                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_run_chunks_status_created_at ON sync_run_chunks(status, created_at)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_run_chunks_job_id_chunk_index ON sync_run_chunks(job_id, chunk_index)")
                conn.commit()

            self._schema_initialized = True

    def _normalize_metadata(self, value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return {str(k): v for k, v in value.items()}
        if isinstance(value, str):
            try:
                payload = json.loads(value)
                if isinstance(payload, dict):
                    return {str(k): v for k, v in payload.items()}
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _row_to_payload(self, row: tuple[object, ...] | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "job_id": str(row[1]),
            "chunk_index": int(row[2]),
            "status": str(row[3]),
            "date_start": str(row[4]),
            "date_end": str(row[5]),
            "created_at": str(row[6]) if row[6] is not None else None,
            "updated_at": str(row[7]) if row[7] is not None else None,
            "started_at": str(row[8]) if row[8] is not None else None,
            "finished_at": str(row[9]) if row[9] is not None else None,
            "error": str(row[10]) if row[10] is not None else None,
            "metadata": self._normalize_metadata(row[11]),
            "attempts": int(row[12]) if row[12] is not None else 0,
            "rows_written": int(row[13]) if row[13] is not None else 0,
            "duration_ms": int(row[14]) if row[14] is not None else None,
        }

    def create_sync_run_chunk(
        self,
        *,
        job_id: str,
        chunk_index: int,
        status: str,
        date_start: date,
        date_end: date,
        metadata: dict[str, object] | None = None,
        attempts: int = 0,
        rows_written: int = 0,
        duration_ms: int | None = None,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sync_run_chunks (
                        job_id,
                        chunk_index,
                        status,
                        date_start,
                        date_end,
                        metadata,
                        attempts,
                        rows_written,
                        duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        str(job_id),
                        int(chunk_index),
                        str(status),
                        date_start,
                        date_end,
                        json.dumps(metadata_payload),
                        int(attempts),
                        int(rows_written),
                        int(duration_ms) if duration_ms is not None else None,
                    ),
                )
            conn.commit()

        chunks = self.list_sync_run_chunks(str(job_id))
        return next((item for item in chunks if int(item.get("chunk_index", -1)) == int(chunk_index)), None)

    def list_sync_run_chunks(self, job_id: str) -> list[dict[str, object]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUN_CHUNKS_SELECT_COLUMNS}
                    FROM sync_run_chunks
                    WHERE job_id = %s
                    ORDER BY chunk_index ASC
                    """,
                    (str(job_id),),
                )
                rows = cur.fetchall() or []
        return [self._row_to_payload(row) for row in rows if row is not None]

    def update_sync_run_chunk_status(
        self,
        *,
        job_id: str,
        chunk_index: int,
        status: str,
        error: str | None = None,
        metadata: dict[str, object] | None = None,
        mark_started: bool = False,
        mark_finished: bool = False,
        rows_written: int | None = None,
        duration_ms: int | None = None,
        increment_attempts: bool = False,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = json.dumps(metadata) if metadata is not None else None

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sync_run_chunks
                    SET
                        status = %s,
                        updated_at = NOW(),
                        started_at = CASE WHEN %s THEN COALESCE(started_at, NOW()) ELSE started_at END,
                        finished_at = CASE WHEN %s THEN NOW() ELSE finished_at END,
                        error = COALESCE(%s, error),
                        metadata = COALESCE(%s::jsonb, metadata),
                        rows_written = COALESCE(%s, rows_written),
                        duration_ms = COALESCE(%s, duration_ms),
                        attempts = CASE WHEN %s THEN attempts + 1 ELSE attempts END
                    WHERE job_id = %s AND chunk_index = %s
                    """,
                    (
                        str(status),
                        bool(mark_started),
                        bool(mark_finished),
                        error,
                        metadata_payload,
                        rows_written,
                        duration_ms,
                        bool(increment_attempts),
                        str(job_id),
                        int(chunk_index),
                    ),
                )
            conn.commit()

        chunks = self.list_sync_run_chunks(str(job_id))
        return next((item for item in chunks if int(item.get("chunk_index", -1)) == int(chunk_index)), None)


    def claim_next_queued_chunk_any(self, *, platform: str | None = None, max_attempts: int = 5) -> dict[str, object] | None:
        self._ensure_schema()
        normalized_platform = str(platform).strip() if platform is not None else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id
                    FROM sync_run_chunks c
                    INNER JOIN sync_runs r ON r.job_id = c.job_id
                    WHERE c.status = 'queued'
                      AND c.attempts < %s
                      AND r.status IN ('queued', 'running')
                      AND (%s IS NULL OR r.platform = %s)
                    ORDER BY r.created_at ASC, c.chunk_index ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    (max(1, int(max_attempts)), normalized_platform, normalized_platform),
                )
                selected = cur.fetchone()
                if selected is None:
                    conn.commit()
                    return None

                cur.execute(
                    f"""
                    UPDATE sync_run_chunks
                    SET
                        status = 'running',
                        attempts = attempts + 1,
                        started_at = COALESCE(started_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING
                        {_SYNC_RUN_CHUNKS_SELECT_COLUMNS}
                    """,
                    (int(selected[0]),),
                )
                claimed = cur.fetchone()
                chunk_payload = self._row_to_payload(claimed)
                if chunk_payload is None:
                    conn.commit()
                    return None

                cur.execute(
                    """
                    SELECT platform, account_id, client_id, job_type, grain, chunk_days, batch_id, status
                    FROM sync_runs
                    WHERE job_id = %s
                    """,
                    (str(chunk_payload.get("job_id")),),
                )
                run_row = cur.fetchone()
            conn.commit()

        if run_row is not None:
            chunk_payload["platform"] = str(run_row[0]) if run_row[0] is not None else None
            chunk_payload["account_id"] = str(run_row[1]) if run_row[1] is not None else None
            chunk_payload["client_id"] = int(run_row[2]) if run_row[2] is not None else None
            chunk_payload["job_type"] = str(run_row[3]) if run_row[3] is not None else None
            chunk_payload["grain"] = str(run_row[4]) if run_row[4] is not None else None
            chunk_payload["chunk_days"] = int(run_row[5]) if run_row[5] is not None else None
            chunk_payload["batch_id"] = str(run_row[6]) if run_row[6] is not None else None
            chunk_payload["run_status"] = str(run_row[7]) if run_row[7] is not None else None
        return chunk_payload

    def get_sync_run_chunk_status_counts(self, job_id: str) -> dict[str, int]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status IN ('queued', 'running'))::int,
                        COUNT(*) FILTER (WHERE status = 'error')::int
                    FROM sync_run_chunks
                    WHERE job_id = %s
                    """,
                    (str(job_id),),
                )
                row = cur.fetchone() or (0, 0)
        return {
            "remaining": int(row[0] or 0),
            "errors": int(row[1] or 0),
        }

    def claim_next_queued_chunk(self, *, job_id: str, max_attempts: int = 5) -> dict[str, object] | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM sync_run_chunks
                    WHERE job_id = %s
                      AND status = 'queued'
                      AND attempts < %s
                    ORDER BY chunk_index ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    (str(job_id), max(1, int(max_attempts))),
                )
                selected = cur.fetchone()
                if selected is None:
                    conn.commit()
                    return None

                cur.execute(
                    f"""
                    UPDATE sync_run_chunks
                    SET
                        status = 'running',
                        attempts = attempts + 1,
                        started_at = COALESCE(started_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING
                        {_SYNC_RUN_CHUNKS_SELECT_COLUMNS}
                    """,
                    (int(selected[0]),),
                )
                claimed = cur.fetchone()
            conn.commit()

        return self._row_to_payload(claimed)


sync_run_chunks_store = SyncRunChunksStore()
