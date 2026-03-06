from __future__ import annotations

from datetime import date
import json
import logging
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_SYNC_RUNS_SELECT_COLUMNS = """
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
    metadata,
    batch_id,
    job_type,
    grain,
    chunks_total,
    chunks_done,
    rows_written
"""

_ACTIVE_CHUNK_STATUSES = ("queued", "running", "pending")
_SUCCESS_CHUNK_STATUSES = ("done", "success", "completed")
_ERROR_CHUNK_STATUSES = ("error", "failed")
_TERMINAL_RUN_STATUSES = ("done", "error")

logger = logging.getLogger(__name__)


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
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS sync_runs (
                            job_id TEXT PRIMARY KEY,
                            platform TEXT NOT NULL,
                            status TEXT NOT NULL,
                            client_id BIGINT NULL,
                            account_id TEXT NULL,
                            date_start DATE NOT NULL,
                            date_end DATE NOT NULL,
                            chunk_days INTEGER NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            started_at TIMESTAMPTZ NULL,
                            finished_at TIMESTAMPTZ NULL,
                            error TEXT NULL,
                            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                            CONSTRAINT sync_runs_date_range_check CHECK (date_end >= date_start),
                            CONSTRAINT sync_runs_chunk_days_check CHECK (chunk_days > 0)
                        )
                        """
                    )
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS batch_id TEXT NULL")
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS job_type TEXT NULL")
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS grain TEXT NULL")
                    cur.execute("UPDATE sync_runs SET grain = 'account_daily' WHERE grain IS NULL")
                    cur.execute("ALTER TABLE sync_runs ALTER COLUMN grain SET DEFAULT 'account_daily'")
                    cur.execute("ALTER TABLE sync_runs ALTER COLUMN grain SET NOT NULL")
                    cur.execute(
                        """
                        DO $$
                        BEGIN
                          IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'sync_runs_grain_check'
                              AND conrelid = 'sync_runs'::regclass
                          ) THEN
                            ALTER TABLE sync_runs
                              ADD CONSTRAINT sync_runs_grain_check
                              CHECK (grain IN ('account_daily', 'campaign_daily', 'ad_group_daily', 'ad_daily'));
                          END IF;
                        END
                        $$;
                        """
                    )
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS chunks_total INTEGER DEFAULT 0")
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS chunks_done INTEGER DEFAULT 0")
                    cur.execute("ALTER TABLE sync_runs ADD COLUMN IF NOT EXISTS rows_written BIGINT DEFAULT 0")

                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_batch_id ON sync_runs(batch_id)")
                    cur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_sync_runs_platform_account_created_at ON sync_runs(platform, account_id, created_at DESC)"
                    )
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_client_created_at ON sync_runs(client_id, created_at DESC)")
                    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_runs_platform_account_grain ON sync_runs(platform, account_id, grain)")
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
            "batch_id": str(row[14]) if row[14] is not None else None,
            "job_type": str(row[15]) if row[15] is not None else None,
            "grain": str(row[16]) if row[16] is not None else "account_daily",
            "chunks_total": int(row[17]) if row[17] is not None else 0,
            "chunks_done": int(row[18]) if row[18] is not None else 0,
            "rows_written": int(row[19]) if row[19] is not None else 0,
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
        batch_id: str | None = None,
        job_type: str | None = None,
        grain: str | None = None,
        chunks_total: int = 0,
        chunks_done: int = 0,
        rows_written: int = 0,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO sync_runs (
                        job_id,
                        platform,
                        status,
                        client_id,
                        account_id,
                        date_start,
                        date_end,
                        chunk_days,
                        metadata,
                        batch_id,
                        job_type,
                        grain,
                        chunks_total,
                        chunks_done,
                        rows_written
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
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
                        str(batch_id) if batch_id is not None else None,
                        str(job_type) if job_type is not None else None,
                        str(grain) if grain is not None else "account_daily",
                        int(chunks_total),
                        int(chunks_done),
                        int(rows_written),
                    ),
                )
            conn.commit()

        return self.get_sync_run(str(job_id))

    def create_historical_sync_run_if_not_active(
        self,
        *,
        job_id: str,
        platform: str,
        date_start: date,
        date_end: date,
        chunk_days: int,
        client_id: int | None = None,
        account_id: str | None = None,
        metadata: dict[str, object] | None = None,
        batch_id: str | None = None,
        grain: str | None = None,
        chunks_total: int = 0,
        chunks_done: int = 0,
        rows_written: int = 0,
    ) -> dict[str, object]:
        self._ensure_schema()
        metadata_payload = metadata or {}
        normalized_platform = str(platform)
        normalized_account_id = str(account_id) if account_id is not None else ""

        with self._connect() as conn:
            with conn.cursor() as cur:
                lock_key = (
                    f"sync_runs:historical_backfill:{normalized_platform}:{normalized_account_id}:"
                    f"{date_start.isoformat()}:{date_end.isoformat()}"
                )
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))

                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE platform = %s
                        AND account_id = %s
                        AND job_type = 'historical_backfill'
                        AND date_start = %s
                        AND date_end = %s
                        AND status IN ('queued', 'running')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (
                        normalized_platform,
                        normalized_account_id,
                        date_start,
                        date_end,
                    ),
                )
                existing_row = cur.fetchone()
                if existing_row is not None:
                    conn.commit()
                    return {"created": False, "run": self._row_to_payload(existing_row)}

                cur.execute(
                    f"""
                    INSERT INTO sync_runs (
                        job_id,
                        platform,
                        status,
                        client_id,
                        account_id,
                        date_start,
                        date_end,
                        chunk_days,
                        metadata,
                        batch_id,
                        job_type,
                        grain,
                        chunks_total,
                        chunks_done,
                        rows_written
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    """,
                    (
                        str(job_id),
                        normalized_platform,
                        "queued",
                        client_id,
                        normalized_account_id,
                        date_start,
                        date_end,
                        int(chunk_days),
                        json.dumps(metadata_payload),
                        str(batch_id) if batch_id is not None else None,
                        "historical_backfill",
                        str(grain) if grain is not None else "account_daily",
                        int(chunks_total),
                        int(chunks_done),
                        int(rows_written),
                    ),
                )
                created_row = cur.fetchone()
            conn.commit()

        return {"created": True, "run": self._row_to_payload(created_row)}

    def _repair_active_sync_run(
        self,
        *,
        job_id: str,
        stale_after_minutes: int,
        repair_source: str,
        allowed_job_types: set[str] | None = None,
    ) -> dict[str, object]:
        self._ensure_schema()
        normalized_job_id = str(job_id)
        stale_minutes = max(1, int(stale_after_minutes))

        with self._connect() as conn:
            with conn.cursor() as cur:
                lock_key = f"sync_runs:repair:{normalized_job_id}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))

                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE job_id = %s
                    FOR UPDATE
                    """,
                    (normalized_job_id,),
                )
                run_row = cur.fetchone()
                run_payload = self._row_to_payload(run_row)
                if run_payload is None:
                    conn.commit()
                    return {"outcome": "not_found", "job_id": normalized_job_id}

                run_job_type = str(run_payload.get("job_type") or "").strip().lower()
                if allowed_job_types and run_job_type not in allowed_job_types:
                    conn.commit()
                    return {
                        "outcome": "not_supported_job_type",
                        "job_id": normalized_job_id,
                        "job_type": run_payload.get("job_type"),
                        "run": run_payload,
                    }

                run_status = str(run_payload.get("status") or "").strip().lower()
                if run_status not in {"queued", "running"}:
                    conn.commit()
                    return {
                        "outcome": "noop_not_active",
                        "job_id": normalized_job_id,
                        "job_type": run_payload.get("job_type"),
                        "run": run_payload,
                    }

                cur.execute(
                    """
                    SELECT
                        id,
                        status,
                        COALESCE(updated_at, started_at, created_at) AS freshness_ts
                    FROM sync_run_chunks
                    WHERE job_id = %s
                    FOR UPDATE
                    """,
                    (normalized_job_id,),
                )
                chunk_rows = cur.fetchall() or []
                active_chunk_ids: list[int] = []
                stale_active_chunk_ids: list[int] = []

                cur.execute("SELECT NOW()")
                now_row = cur.fetchone()
                now_ts = now_row[0] if now_row is not None else None

                for row in chunk_rows:
                    chunk_id = int(row[0])
                    chunk_status = str(row[1] or "").strip().lower()
                    freshness_ts = row[2]
                    if chunk_status in _ACTIVE_CHUNK_STATUSES:
                        active_chunk_ids.append(chunk_id)
                        if now_ts is not None and freshness_ts is not None and (now_ts - freshness_ts).total_seconds() >= stale_minutes * 60:
                            stale_active_chunk_ids.append(chunk_id)

                if len(active_chunk_ids) > 0 and len(stale_active_chunk_ids) != len(active_chunk_ids):
                    conn.commit()
                    return {
                        "outcome": "noop_active_fresh",
                        "job_id": normalized_job_id,
                        "job_type": run_payload.get("job_type"),
                        "active_chunks": len(active_chunk_ids),
                        "stale_chunks": len(stale_active_chunk_ids),
                        "run": run_payload,
                    }

                stale_chunks_closed = 0
                repair_reason = "all_chunks_terminal_reconcile"

                if len(stale_active_chunk_ids) > 0:
                    repair_reason = "stale_chunk_timeout"
                    stale_chunks_closed = len(stale_active_chunk_ids)
                    cur.execute(
                        """
                        UPDATE sync_run_chunks
                        SET
                            status = 'error',
                            error = %s,
                            finished_at = COALESCE(finished_at, NOW()),
                            updated_at = NOW(),
                            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                        WHERE id = ANY(%s)
                        """,
                        (
                            "stale_timeout",
                            json.dumps(
                                {
                                    "repair_reason": "stale_timeout",
                                    "repair_source": str(repair_source),
                                    "repaired_at": "now",
                                }
                            ),
                            stale_active_chunk_ids,
                        ),
                    )

                cur.execute(
                    """
                    SELECT
                        COUNT(*)::int,
                        COUNT(*) FILTER (WHERE status IN ('done', 'success', 'completed'))::int,
                        COUNT(*) FILTER (WHERE status IN ('error', 'failed'))::int,
                        COUNT(*) FILTER (WHERE status IN ('queued', 'running', 'pending'))::int,
                        COALESCE(SUM(rows_written), 0)::bigint
                    FROM sync_run_chunks
                    WHERE job_id = %s
                    """,
                    (normalized_job_id,),
                )
                summary_row = cur.fetchone() or (0, 0, 0, 0, 0)

                total_chunks = int(summary_row[0] or 0)
                done_chunks = int(summary_row[1] or 0)
                error_chunks = int(summary_row[2] or 0)
                active_chunks_remaining = int(summary_row[3] or 0)
                rows_written = int(summary_row[4] or 0)

                if active_chunks_remaining > 0:
                    conn.commit()
                    return {
                        "outcome": "noop_active_fresh",
                        "job_id": normalized_job_id,
                        "job_type": run_payload.get("job_type"),
                        "active_chunks": active_chunks_remaining,
                        "stale_chunks": stale_chunks_closed,
                        "run": run_payload,
                    }

                final_status = "error" if error_chunks > 0 or stale_chunks_closed > 0 else "done"
                final_error = None if final_status == "done" else f"repair:{repair_reason}"
                metadata_patch = json.dumps(
                    {
                        "repair": {
                            "reason": repair_reason,
                            "source": str(repair_source),
                            "stale_after_minutes": stale_minutes,
                            "stale_chunks_closed": stale_chunks_closed,
                            "final_status": final_status,
                        }
                    }
                )

                cur.execute(
                    """
                    UPDATE sync_runs
                    SET
                        status = %s,
                        error = %s,
                        chunks_total = GREATEST(chunks_total, %s),
                        chunks_done = %s,
                        rows_written = %s,
                        finished_at = COALESCE(finished_at, NOW()),
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE job_id = %s
                    RETURNING
                        """ + _SYNC_RUNS_SELECT_COLUMNS,
                    (
                        final_status,
                        final_error,
                        total_chunks,
                        done_chunks,
                        rows_written,
                        metadata_patch,
                        normalized_job_id,
                    ),
                )
                repaired_row = cur.fetchone()
            conn.commit()

        return {
            "outcome": "repaired",
            "reason": repair_reason,
            "job_id": normalized_job_id,
            "job_type": run_payload.get("job_type"),
            "stale_chunks_closed": stale_chunks_closed,
            "final_status": final_status,
            "run": self._row_to_payload(repaired_row),
        }

    def repair_historical_sync_run(
        self,
        *,
        job_id: str,
        stale_after_minutes: int,
        repair_source: str = "api",
    ) -> dict[str, object]:
        return self._repair_active_sync_run(
            job_id=job_id,
            stale_after_minutes=stale_after_minutes,
            repair_source=repair_source,
            allowed_job_types={"historical_backfill"},
        )

    def repair_rolling_sync_run(
        self,
        *,
        job_id: str,
        stale_after_minutes: int,
        repair_source: str = "sweeper",
    ) -> dict[str, object]:
        return self._repair_active_sync_run(
            job_id=job_id,
            stale_after_minutes=stale_after_minutes,
            repair_source=repair_source,
            allowed_job_types={"rolling_refresh"},
        )

    def _sweep_stale_runs_for_job_type(
        self,
        *,
        job_type: str,
        stale_after_minutes: int,
        limit: int,
        repair_source: str,
    ) -> dict[str, object]:
        self._ensure_schema()
        normalized_job_type = str(job_type).strip().lower()
        stale_minutes = max(1, int(stale_after_minutes))
        limit_value = max(1, int(limit))

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT NOW()")
                now_row = cur.fetchone()
                now_ts = now_row[0] if now_row is not None else None

                cur.execute(
                    """
                    SELECT
                        job_id,
                        COALESCE(updated_at, started_at, created_at) AS freshness_ts
                    FROM sync_runs
                    WHERE job_type = %s
                      AND status IN ('queued', 'running')
                    ORDER BY COALESCE(updated_at, started_at, created_at) ASC
                    LIMIT %s
                    """,
                    (normalized_job_type, limit_value),
                )
                active_rows = cur.fetchall() or []

        stale_candidate_job_ids: list[str] = []
        fresh_active_job_ids: list[str] = []
        if now_ts is None:
            stale_candidate_job_ids = [str(row[0]) for row in active_rows if row and row[0] is not None]
        else:
            for row in active_rows:
                if row is None or row[0] is None:
                    continue
                job_id = str(row[0])
                freshness_ts = row[1]
                if freshness_ts is None:
                    stale_candidate_job_ids.append(job_id)
                    continue
                age_seconds = (now_ts - freshness_ts).total_seconds()
                if age_seconds >= stale_minutes * 60:
                    stale_candidate_job_ids.append(job_id)
                else:
                    fresh_active_job_ids.append(job_id)

        logger.info(
            "sync_runs.sweeper job_type=%s candidates=%s stale_candidates=%s fresh_active=%s stale_after_minutes=%s limit=%s",
            normalized_job_type,
            len(active_rows),
            len(stale_candidate_job_ids),
            len(fresh_active_job_ids),
            stale_minutes,
            limit_value,
        )

        repaired_job_ids: list[str] = []
        noop_not_active_job_ids: list[str] = []
        not_found_job_ids: list[str] = []
        noop_active_fresh_from_repair: list[str] = []
        errored_job_ids: list[str] = []

        for job_id in stale_candidate_job_ids:
            try:
                repair_result = self._repair_active_sync_run(
                    job_id=job_id,
                    stale_after_minutes=stale_minutes,
                    repair_source=str(repair_source),
                    allowed_job_types={normalized_job_type},
                )
                outcome = str(repair_result.get("outcome") or "")
                if outcome == "repaired":
                    repaired_job_ids.append(job_id)
                    logger.info("sync_runs.sweeper repaired job_type=%s job_id=%s", normalized_job_type, job_id)
                elif outcome == "noop_not_active":
                    noop_not_active_job_ids.append(job_id)
                elif outcome == "not_found":
                    not_found_job_ids.append(job_id)
                elif outcome == "noop_active_fresh":
                    noop_active_fresh_from_repair.append(job_id)
                    logger.info("sync_runs.sweeper skipped_fresh_after_repair job_type=%s job_id=%s", normalized_job_type, job_id)
                else:
                    logger.warning(
                        "sync_runs.sweeper unexpected_outcome=%s job_type=%s job_id=%s",
                        outcome,
                        normalized_job_type,
                        job_id,
                    )
            except Exception:
                logger.exception("sync_runs.sweeper repair_failed job_type=%s job_id=%s", normalized_job_type, job_id)
                errored_job_ids.append(job_id)

        noop_active_fresh_job_ids = fresh_active_job_ids + noop_active_fresh_from_repair

        return {
            "status": "ok",
            "job_type": normalized_job_type,
            "stale_after_minutes": stale_minutes,
            "limit": limit_value,
            "candidate_count": len(active_rows),
            "processed_count": len(stale_candidate_job_ids),
            "repaired_count": len(repaired_job_ids),
            "noop_not_active_count": len(noop_not_active_job_ids),
            "noop_active_fresh_count": len(noop_active_fresh_job_ids),
            "not_found_count": len(not_found_job_ids),
            "error_count": len(errored_job_ids),
            "stale_candidate_job_ids": stale_candidate_job_ids,
            "repaired_job_ids": repaired_job_ids,
            "noop_not_active_job_ids": noop_not_active_job_ids,
            "noop_active_fresh_job_ids": noop_active_fresh_job_ids,
            "not_found_job_ids": not_found_job_ids,
            "error_job_ids": errored_job_ids,
        }

    def sweep_stale_historical_runs(
        self,
        *,
        stale_after_minutes: int,
        limit: int = 100,
        repair_source: str = "sweeper",
    ) -> dict[str, object]:
        return self._sweep_stale_runs_for_job_type(
            job_type="historical_backfill",
            stale_after_minutes=stale_after_minutes,
            limit=limit,
            repair_source=repair_source,
        )

    def sweep_stale_rolling_runs(
        self,
        *,
        stale_after_minutes: int,
        limit: int = 100,
        repair_source: str = "sweeper",
    ) -> dict[str, object]:
        return self._sweep_stale_runs_for_job_type(
            job_type="rolling_refresh",
            stale_after_minutes=stale_after_minutes,
            limit=limit,
            repair_source=repair_source,
        )

    def retry_failed_historical_run(
        self,
        *,
        source_job_id: str,
        retry_job_id: str,
        trigger_source: str = "manual",
    ) -> dict[str, object]:
        self._ensure_schema()
        normalized_source_job_id = str(source_job_id)
        normalized_retry_job_id = str(retry_job_id)

        with self._connect() as conn:
            with conn.cursor() as cur:
                lock_key = f"sync_runs:retry_failed:{normalized_source_job_id}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))

                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE job_id = %s
                    FOR UPDATE
                    """,
                    (normalized_source_job_id,),
                )
                source_row = cur.fetchone()
                source_payload = self._row_to_payload(source_row)
                if source_payload is None:
                    conn.commit()
                    return {"outcome": "not_found", "source_job_id": normalized_source_job_id}

                source_job_type = str(source_payload.get("job_type") or "").strip().lower()
                source_status = str(source_payload.get("status") or "").strip().lower()
                if source_job_type != "historical_backfill" or source_status not in _TERMINAL_RUN_STATUSES:
                    conn.commit()
                    return {
                        "outcome": "not_retryable",
                        "source_job_id": normalized_source_job_id,
                        "platform": source_payload.get("platform"),
                        "account_id": source_payload.get("account_id"),
                        "status": source_payload.get("status"),
                    }

                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE job_type = 'historical_backfill'
                      AND status IN ('queued', 'running')
                      AND COALESCE(metadata->>'retry_of_job_id', '') = %s
                      AND COALESCE(metadata->>'retry_reason', '') = 'failed_chunks'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (normalized_source_job_id,),
                )
                existing_retry_row = cur.fetchone()
                if existing_retry_row is not None:
                    existing_retry_payload = self._row_to_payload(existing_retry_row)
                    conn.commit()
                    return {
                        "outcome": "already_exists",
                        "source_job_id": normalized_source_job_id,
                        "retry_job_id": existing_retry_payload.get("job_id") if existing_retry_payload is not None else None,
                        "platform": source_payload.get("platform"),
                        "account_id": source_payload.get("account_id"),
                        "status": existing_retry_payload.get("status") if existing_retry_payload is not None else "queued",
                        "chunks_created": int(existing_retry_payload.get("chunks_total") or 0) if existing_retry_payload is not None else 0,
                        "failed_chunks_count": int(existing_retry_payload.get("chunks_total") or 0) if existing_retry_payload is not None else 0,
                    }

                cur.execute(
                    """
                    SELECT chunk_index, date_start, date_end
                    FROM sync_run_chunks
                    WHERE job_id = %s
                      AND status IN ('error', 'failed')
                    ORDER BY chunk_index ASC
                    FOR UPDATE
                    """,
                    (normalized_source_job_id,),
                )
                failed_rows = cur.fetchall() or []
                failed_chunks_total = len(failed_rows)
                if failed_chunks_total <= 0:
                    conn.commit()
                    return {
                        "outcome": "no_failed_chunks",
                        "source_job_id": normalized_source_job_id,
                        "platform": source_payload.get("platform"),
                        "account_id": source_payload.get("account_id"),
                        "status": source_payload.get("status"),
                    }

                recovery = self._evaluate_retry_recovery_status(
                    cur,
                    source_job_id=normalized_source_job_id,
                    platform=str(source_payload.get("platform") or ""),
                    account_id=str(source_payload.get("account_id") or ""),
                    failed_rows=failed_rows,
                )
                failed_rows_remaining = recovery["failed_rows_remaining"]
                failed_chunks_count = int(recovery["failed_chunks_remaining"])
                recovery_status = str(recovery["retry_recovery_status"])

                if failed_chunks_count <= 0:
                    logger.info(
                        "sync_runs.retry_failed source_job_id=%s recovery_status=%s outcome=no_failed_chunks",
                        normalized_source_job_id,
                        recovery_status,
                    )
                    conn.commit()
                    return {
                        "outcome": "no_failed_chunks",
                        "source_job_id": normalized_source_job_id,
                        "platform": source_payload.get("platform"),
                        "account_id": source_payload.get("account_id"),
                        "status": source_payload.get("status"),
                        "retry_recovery_status": recovery_status,
                        "failed_chunks_total": failed_chunks_total,
                        "failed_chunks_remaining": 0,
                    }

                failed_start_dates = [row[1] for row in failed_rows_remaining if row[1] is not None]
                failed_end_dates = [row[2] for row in failed_rows_remaining if row[2] is not None]
                retry_start_date = min(failed_start_dates) if failed_start_dates else source_payload.get("date_start")
                retry_end_date = max(failed_end_dates) if failed_end_dates else source_payload.get("date_end")
                source_metadata = source_payload.get("metadata") if isinstance(source_payload.get("metadata"), dict) else {}
                retry_metadata = {
                    **source_metadata,
                    "source": "manual",
                    "trigger_source": str(trigger_source),
                    "job_type": "historical_backfill",
                    "retry_of_job_id": normalized_source_job_id,
                    "retry_reason": "failed_chunks",
                }

                cur.execute(
                    """
                    INSERT INTO sync_runs (
                        job_id,
                        platform,
                        status,
                        client_id,
                        account_id,
                        date_start,
                        date_end,
                        chunk_days,
                        metadata,
                        batch_id,
                        job_type,
                        grain,
                        chunks_total,
                        chunks_done,
                        rows_written
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                    RETURNING
                        """ + _SYNC_RUNS_SELECT_COLUMNS,
                    (
                        normalized_retry_job_id,
                        source_payload.get("platform"),
                        "queued",
                        source_payload.get("client_id"),
                        source_payload.get("account_id"),
                        retry_start_date,
                        retry_end_date,
                        int(source_payload.get("chunk_days") or 1),
                        json.dumps(retry_metadata),
                        None,
                        "historical_backfill",
                        source_payload.get("grain") or "account_daily",
                        failed_chunks_count,
                        0,
                        0,
                    ),
                )
                retry_row = cur.fetchone()

                for retry_chunk_index, failed_row in enumerate(failed_rows_remaining):
                    source_chunk_index = int(failed_row[0])
                    chunk_start = failed_row[1]
                    chunk_end = failed_row[2]
                    chunk_metadata = {
                        "source": "manual",
                        "trigger_source": str(trigger_source),
                        "retry_of_job_id": normalized_source_job_id,
                        "retry_of_chunk_index": source_chunk_index,
                        "retry_reason": "failed_chunks",
                    }
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
                            normalized_retry_job_id,
                            retry_chunk_index,
                            "queued",
                            chunk_start,
                            chunk_end,
                            json.dumps(chunk_metadata),
                            0,
                            0,
                            None,
                        ),
                    )
            conn.commit()

        retry_payload = self._row_to_payload(retry_row)
        return {
            "outcome": "created",
            "source_job_id": normalized_source_job_id,
            "retry_job_id": normalized_retry_job_id,
            "platform": source_payload.get("platform"),
            "account_id": source_payload.get("account_id"),
            "status": retry_payload.get("status") if retry_payload is not None else "queued",
            "chunks_created": failed_chunks_count,
            "failed_chunks_count": failed_chunks_count,
            "failed_chunks_total": failed_chunks_total,
            "failed_chunks_remaining": failed_chunks_count,
            "retry_recovery_status": recovery_status,
            "run": retry_payload,
        }

    def _evaluate_retry_recovery_status(
        self,
        cur,
        *,
        source_job_id: str,
        platform: str,
        account_id: str,
        failed_rows: list[tuple[object, ...]],
    ) -> dict[str, object]:
        failed_chunks_total = len(failed_rows)
        if failed_chunks_total <= 0:
            return {
                "retry_recovery_status": "unrecovered",
                "failed_chunks_total": 0,
                "failed_chunks_remaining": 0,
                "failed_rows_remaining": [],
            }

        cur.execute(
            """
            SELECT DISTINCT c.date_start, c.date_end
            FROM sync_runs r
            JOIN sync_run_chunks c
              ON c.job_id = r.job_id
            WHERE r.platform = %s
              AND r.account_id = %s
              AND r.job_type = 'historical_backfill'
              AND r.status = 'done'
              AND COALESCE(r.metadata->>'retry_of_job_id', '') = %s
              AND COALESCE(r.metadata->>'retry_reason', '') = 'failed_chunks'
              AND c.status IN ('done', 'success', 'completed')
              AND COALESCE(c.metadata->>'retry_of_job_id', '') = %s
              AND COALESCE(c.metadata->>'retry_reason', '') = 'failed_chunks'
            """,
            (platform, account_id, source_job_id, source_job_id),
        )
        recovered_interval_rows = cur.fetchall() or []
        recovered_intervals = {(row[0], row[1]) for row in recovered_interval_rows}

        failed_rows_remaining: list[tuple[object, ...]] = []
        for failed_row in failed_rows:
            interval = (failed_row[1], failed_row[2])
            if interval not in recovered_intervals:
                failed_rows_remaining.append(failed_row)

        failed_chunks_remaining = len(failed_rows_remaining)
        if failed_chunks_remaining <= 0:
            status = "fully_recovered_by_retry"
        elif failed_chunks_remaining < failed_chunks_total:
            status = "partially_recovered"
        else:
            status = "unrecovered"

        return {
            "retry_recovery_status": status,
            "failed_chunks_total": failed_chunks_total,
            "failed_chunks_remaining": failed_chunks_remaining,
            "failed_rows_remaining": failed_rows_remaining,
        }

    def get_sync_run(self, job_id: str) -> dict[str, object] | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
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

    def update_sync_run_progress(
        self,
        *,
        job_id: str,
        chunks_done_delta: int = 0,
        rows_written_delta: int = 0,
        chunks_total: int | None = None,
    ) -> dict[str, object] | None:
        self._ensure_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                if chunks_total is None:
                    cur.execute(
                        """
                        UPDATE sync_runs
                        SET
                            chunks_done = chunks_done + %s,
                            rows_written = rows_written + %s,
                            updated_at = NOW()
                        WHERE job_id = %s
                        """,
                        (
                            int(chunks_done_delta),
                            int(rows_written_delta),
                            str(job_id),
                        ),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE sync_runs
                        SET
                            chunks_done = chunks_done + %s,
                            rows_written = rows_written + %s,
                            chunks_total = GREATEST(chunks_total, %s),
                            updated_at = NOW()
                        WHERE job_id = %s
                        """,
                        (
                            int(chunks_done_delta),
                            int(rows_written_delta),
                            int(chunks_total),
                            str(job_id),
                        ),
                    )
            conn.commit()

        return self.get_sync_run(str(job_id))

    def list_sync_runs_by_batch(self, batch_id: str) -> list[dict[str, object]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE batch_id = %s
                    ORDER BY created_at DESC
                    """,
                    (str(batch_id),),
                )
                rows = cur.fetchall() or []
        return [self._row_to_payload(row) for row in rows if row is not None]

    def list_sync_runs_for_account(self, *, platform: str, account_id: str, limit: int = 50) -> list[dict[str, object]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        {_SYNC_RUNS_SELECT_COLUMNS}
                    FROM sync_runs
                    WHERE platform = %s AND account_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (str(platform), str(account_id), max(1, int(limit))),
                )
                rows = cur.fetchall() or []
        return [self._row_to_payload(row) for row in rows if row is not None]


    def get_active_runs_progress_batch(self, *, platform: str, account_ids: list[str]) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_platform = str(platform)
        normalized_account_ids: list[str] = []
        for raw in account_ids:
            candidate = str(raw).strip()
            if candidate == "":
                continue
            if candidate not in normalized_account_ids:
                normalized_account_ids.append(candidate)

        if len(normalized_account_ids) <= 0:
            return []

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH requested AS (
                        SELECT account_id::text, ord::int
                        FROM unnest(%s::text[]) WITH ORDINALITY AS ids(account_id, ord)
                    ),
                    active_runs AS (
                        SELECT DISTINCT ON (r.account_id)
                            r.account_id,
                            r.job_id,
                            r.job_type,
                            r.status,
                            r.date_start,
                            r.date_end
                        FROM sync_runs r
                        JOIN requested req ON req.account_id = r.account_id
                        WHERE r.platform = %s
                          AND r.status IN ('queued', 'running', 'pending')
                        ORDER BY r.account_id, r.created_at DESC
                    ),
                    chunk_summary AS (
                        SELECT
                            c.job_id,
                            COUNT(*)::int AS chunks_total,
                            COUNT(*) FILTER (WHERE c.status IN ('done', 'success', 'completed'))::int AS chunks_done,
                            COUNT(*) FILTER (WHERE c.status IN ('error', 'failed'))::int AS error_chunks
                        FROM sync_run_chunks c
                        JOIN active_runs ar ON ar.job_id = c.job_id
                        GROUP BY c.job_id
                    )
                    SELECT
                        req.account_id,
                        ar.job_id,
                        ar.job_type,
                        ar.status,
                        ar.date_start,
                        ar.date_end,
                        COALESCE(cs.chunks_done, 0)::int,
                        COALESCE(cs.chunks_total, 0)::int,
                        COALESCE(cs.error_chunks, 0)::int
                    FROM requested req
                    LEFT JOIN active_runs ar ON ar.account_id = req.account_id
                    LEFT JOIN chunk_summary cs ON cs.job_id = ar.job_id
                    ORDER BY req.ord ASC
                    """,
                    (normalized_account_ids, normalized_platform),
                )
                rows = cur.fetchall() or []

        payload: list[dict[str, object]] = []
        for row in rows:
            account_id = str(row[0]) if row[0] is not None else ""
            if row[1] is None:
                payload.append({"account_id": account_id, "active_run": None})
                continue
            payload.append(
                {
                    "account_id": account_id,
                    "active_run": {
                        "job_id": str(row[1]),
                        "job_type": str(row[2]) if row[2] is not None else None,
                        "status": str(row[3]) if row[3] is not None else None,
                        "date_start": str(row[4]) if row[4] is not None else None,
                        "date_end": str(row[5]) if row[5] is not None else None,
                        "chunks_done": int(row[6]) if row[6] is not None else 0,
                        "chunks_total": int(row[7]) if row[7] is not None else 0,
                        "errors_count": int(row[8]) if row[8] is not None else 0,
                    },
                }
            )
        return payload

    def get_batch_progress(self, batch_id: str) -> dict[str, object]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)::int,
                        COUNT(*) FILTER (WHERE status = 'queued')::int,
                        COUNT(*) FILTER (WHERE status = 'running')::int,
                        COUNT(*) FILTER (WHERE status = 'done')::int,
                        COUNT(*) FILTER (WHERE status = 'error')::int,
                        COALESCE(SUM(chunks_total), 0)::bigint,
                        COALESCE(SUM(chunks_done), 0)::bigint,
                        COALESCE(SUM(rows_written), 0)::bigint
                    FROM sync_runs
                    WHERE batch_id = %s
                    """,
                    (str(batch_id),),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0)

        return {
            "batch_id": str(batch_id),
            "total_runs": int(row[0] or 0),
            "status_counts": {
                "queued": int(row[1] or 0),
                "running": int(row[2] or 0),
                "done": int(row[3] or 0),
                "error": int(row[4] or 0),
            },
            "chunks_total_sum": int(row[5] or 0),
            "chunks_done_sum": int(row[6] or 0),
            "rows_written_sum": int(row[7] or 0),
        }


sync_runs_store = SyncRunsStore()
