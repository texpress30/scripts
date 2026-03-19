from __future__ import annotations

from datetime import date, datetime
import json
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class SyncStateStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for sync_state persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        settings = load_settings()
        if settings.app_env == "production":
            self._schema_initialized = True
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.sync_state')")
                    row = cur.fetchone() or (None,)
                    if row[0] is None:
                        raise RuntimeError("Database schema for sync_state is not ready; run DB migrations")

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
            "platform": str(row[0]),
            "account_id": str(row[1]),
            "grain": str(row[2]),
            "last_status": str(row[3]) if row[3] is not None else None,
            "last_job_id": str(row[4]) if row[4] is not None else None,
            "last_attempted_at": str(row[5]) if row[5] is not None else None,
            "last_successful_at": str(row[6]) if row[6] is not None else None,
            "last_successful_date": str(row[7]) if row[7] is not None else None,
            "error": str(row[8]) if row[8] is not None else None,
            "metadata": self._normalize_metadata(row[9]),
            "created_at": str(row[10]) if row[10] is not None else None,
            "updated_at": str(row[11]) if row[11] is not None else None,
        }

    def get_sync_state(self, platform: str, account_id: str, grain: str) -> dict[str, object] | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        platform,
                        account_id,
                        grain,
                        last_status,
                        last_job_id,
                        last_attempted_at,
                        last_successful_at,
                        last_successful_date,
                        error,
                        metadata,
                        created_at,
                        updated_at
                    FROM sync_state
                    WHERE platform = %s AND account_id = %s AND grain = %s
                    """,
                    (str(platform), str(account_id), str(grain)),
                )
                row = cur.fetchone()
        return self._row_to_payload(row)

    def upsert_sync_state(
        self,
        *,
        platform: str,
        account_id: str,
        grain: str,
        last_status: str | None = None,
        last_job_id: str | None = None,
        last_attempted_at: datetime | None = None,
        last_successful_at: datetime | None = None,
        last_successful_date: date | None = None,
        error: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sync_state (
                        platform,
                        account_id,
                        grain,
                        last_status,
                        last_job_id,
                        last_attempted_at,
                        last_successful_at,
                        last_successful_date,
                        error,
                        metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (platform, account_id, grain)
                    DO UPDATE SET
                        last_status = EXCLUDED.last_status,
                        last_job_id = EXCLUDED.last_job_id,
                        last_attempted_at = EXCLUDED.last_attempted_at,
                        last_successful_at = EXCLUDED.last_successful_at,
                        last_successful_date = EXCLUDED.last_successful_date,
                        error = EXCLUDED.error,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        str(platform),
                        str(account_id),
                        str(grain),
                        last_status,
                        last_job_id,
                        last_attempted_at,
                        last_successful_at,
                        last_successful_date,
                        error,
                        json.dumps(metadata_payload),
                    ),
                )
            conn.commit()

        return self.get_sync_state(str(platform), str(account_id), str(grain))


sync_state_store = SyncStateStore()
