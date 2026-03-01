from __future__ import annotations

from datetime import date
import json
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class SyncRunsStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for sync_runs persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.sync_runs')")
                    row = cur.fetchone() or (None,)
                    if row[0] is None:
                        raise RuntimeError("Database schema for sync_runs is not ready; run DB migrations")

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
            "job_id": str(row[0]),
            "platform": str(row[1]),
            "status": str(row[2]),
            "client_id": int(row[3]) if row[3] is not None else None,
            "account_id": str(row[4]) if row[4] is not None else None,
            "date_start": str(row[5]),
            "date_end": str(row[6]),
            "chunk_days": int(row[7]),
            "created_at": str(row[8]) if row[8] is not None else None,
            "updated_at": str(row[9]) if row[9] is not None else None,
            "started_at": str(row[10]) if row[10] is not None else None,
            "finished_at": str(row[11]) if row[11] is not None else None,
            "error": str(row[12]) if row[12] is not None else None,
            "metadata": self._normalize_metadata(row[13]),
        }

    def create_sync_run(
        self,
        *,
        job_id: str,
        platform: str,
        status: str,
        date_start: date,
        date_end: date,
        chunk_days: int,
        client_id: int | None = None,
        account_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sync_runs (
                        job_id, platform, status, client_id, account_id, date_start, date_end, chunk_days, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(job_id),
                        str(platform),
                        str(status),
                        client_id,
                        str(account_id) if account_id is not None else None,
                        date_start,
                        date_end,
                        int(chunk_days),
                        json.dumps(metadata_payload),
                    ),
                )
            conn.commit()

        return self.get_sync_run(str(job_id))

    def get_sync_run(self, job_id: str) -> dict[str, object] | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        job_id,
                        platform,
                        status,
                        client_id,
                        account_id,
                        date_start,
                        date_end,
                        chunk_days,
                        created_at,
                        updated_at,
                        started_at,
                        finished_at,
                        error,
                        metadata
                    FROM sync_runs
                    WHERE job_id = %s
                    """,
                    (str(job_id),),
                )
                row = cur.fetchone()
        return self._row_to_payload(row)

    def update_sync_run_status(
        self,
        *,
        job_id: str,
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
                    UPDATE sync_runs
                    SET
                        status = %s,
                        updated_at = NOW(),
                        started_at = CASE WHEN %s THEN COALESCE(started_at, NOW()) ELSE started_at END,
                        finished_at = CASE WHEN %s THEN NOW() ELSE finished_at END,
                        error = COALESCE(%s, error),
                        metadata = COALESCE(%s::jsonb, metadata)
                    WHERE job_id = %s
                    """,
                    (
                        str(status),
                        bool(mark_started),
                        bool(mark_finished),
                        error,
                        metadata_payload,
                        str(job_id),
                    ),
                )
            conn.commit()

        return self.get_sync_run(str(job_id))


sync_runs_store = SyncRunsStore()
