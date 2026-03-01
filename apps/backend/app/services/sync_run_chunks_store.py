from __future__ import annotations

from datetime import date
import json
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


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
                    cur.execute("SELECT to_regclass('public.sync_run_chunks')")
                    row = cur.fetchone() or (None,)
                    if row[0] is None:
                        raise RuntimeError("Database schema for sync_run_chunks is not ready; run DB migrations")

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
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sync_run_chunks (
                        job_id, chunk_index, status, date_start, date_end, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(job_id),
                        int(chunk_index),
                        str(status),
                        date_start,
                        date_end,
                        json.dumps(metadata_payload),
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
                    """
                    SELECT
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
                        metadata
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
                        metadata = COALESCE(%s::jsonb, metadata)
                    WHERE job_id = %s AND chunk_index = %s
                    """,
                    (
                        str(status),
                        bool(mark_started),
                        bool(mark_finished),
                        error,
                        metadata_payload,
                        str(job_id),
                        int(chunk_index),
                    ),
                )
            conn.commit()

        chunks = self.list_sync_run_chunks(str(job_id))
        return next((item for item in chunks if int(item.get("chunk_index", -1)) == int(chunk_index)), None)


sync_run_chunks_store = SyncRunChunksStore()
