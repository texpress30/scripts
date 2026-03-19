from __future__ import annotations

from datetime import date
import json
from threading import Lock

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class ClientBusinessInputsStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for client_business_inputs persistence")
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
                    cur.execute("SELECT to_regclass('public.client_business_inputs')")
                    row = cur.fetchone() or (None,)
                    if row[0] is None:
                        raise RuntimeError("Database schema for client_business_inputs is not ready; run DB migrations")

            self._schema_initialized = True

    def initialize_schema(self) -> None:
        self._ensure_schema()

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
            "client_id": int(row[1]),
            "period_start": str(row[2]),
            "period_end": str(row[3]),
            "period_grain": str(row[4]),
            "applicants": int(row[5]) if row[5] is not None else None,
            "approved_applicants": int(row[6]) if row[6] is not None else None,
            "actual_revenue": float(row[7]) if row[7] is not None else None,
            "target_revenue": float(row[8]) if row[8] is not None else None,
            "cogs": float(row[9]) if row[9] is not None else None,
            "taxes": float(row[10]) if row[10] is not None else None,
            "gross_profit": float(row[11]) if row[11] is not None else None,
            "contribution_profit": float(row[12]) if row[12] is not None else None,
            "sales_count": int(row[13]) if row[13] is not None else None,
            "new_customers": int(row[14]) if row[14] is not None else None,
            "notes": str(row[15]) if row[15] is not None else None,
            "source": str(row[16]),
            "metadata": self._normalize_metadata(row[17]),
            "created_at": str(row[18]) if row[18] is not None else None,
            "updated_at": str(row[19]) if row[19] is not None else None,
        }

    def get_client_business_input(self, client_id: int, period_start: date, period_end: date, period_grain: str) -> dict[str, object] | None:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        client_id,
                        period_start,
                        period_end,
                        period_grain,
                        applicants,
                        approved_applicants,
                        actual_revenue,
                        target_revenue,
                        cogs,
                        taxes,
                        gross_profit,
                        contribution_profit,
                        sales_count,
                        new_customers,
                        notes,
                        source,
                        metadata,
                        created_at,
                        updated_at
                    FROM client_business_inputs
                    WHERE client_id = %s
                      AND period_start = %s
                      AND period_end = %s
                      AND period_grain = %s
                    """,
                    (int(client_id), period_start, period_end, str(period_grain)),
                )
                row = cur.fetchone()
        return self._row_to_payload(row)

    def upsert_client_business_input(
        self,
        *,
        client_id: int,
        period_start: date,
        period_end: date,
        period_grain: str,
        applicants: int | None = None,
        approved_applicants: int | None = None,
        actual_revenue: float | None = None,
        target_revenue: float | None = None,
        cogs: float | None = None,
        taxes: float | None = None,
        gross_profit: float | None = None,
        contribution_profit: float | None = None,
        sales_count: int | None = None,
        new_customers: int | None = None,
        notes: str | None = None,
        source: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        self._ensure_schema()
        metadata_payload = metadata or {}
        resolved_source = str(source or "manual")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO client_business_inputs (
                        client_id,
                        period_start,
                        period_end,
                        period_grain,
                        applicants,
                        approved_applicants,
                        actual_revenue,
                        target_revenue,
                        cogs,
                        taxes,
                        gross_profit,
                        contribution_profit,
                        sales_count,
                        new_customers,
                        notes,
                        source,
                        metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT (client_id, period_start, period_end, period_grain)
                    DO UPDATE SET
                        applicants = EXCLUDED.applicants,
                        approved_applicants = EXCLUDED.approved_applicants,
                        actual_revenue = EXCLUDED.actual_revenue,
                        target_revenue = EXCLUDED.target_revenue,
                        cogs = EXCLUDED.cogs,
                        taxes = EXCLUDED.taxes,
                        gross_profit = EXCLUDED.gross_profit,
                        contribution_profit = EXCLUDED.contribution_profit,
                        sales_count = EXCLUDED.sales_count,
                        new_customers = EXCLUDED.new_customers,
                        notes = EXCLUDED.notes,
                        source = EXCLUDED.source,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    (
                        int(client_id),
                        period_start,
                        period_end,
                        str(period_grain),
                        applicants,
                        approved_applicants,
                        actual_revenue,
                        target_revenue,
                        cogs,
                        taxes,
                        gross_profit,
                        contribution_profit,
                        sales_count,
                        new_customers,
                        notes,
                        resolved_source,
                        json.dumps(metadata_payload),
                    ),
                )
            conn.commit()

        return self.get_client_business_input(
            int(client_id),
            period_start,
            period_end,
            str(period_grain),
        )

    def list_client_business_inputs(
        self,
        *,
        client_id: int,
        period_grain: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, object]]:
        self._ensure_schema()

        # Date filtering rule: interval-overlap semantics.
        # A row is returned if it intersects [date_from, date_to]:
        #   row.period_end >= date_from and row.period_start <= date_to.
        where_clauses = ["client_id = %s", "period_grain = %s"]
        params: list[object] = [int(client_id), str(period_grain)]

        if date_from is not None:
            where_clauses.append("period_end >= %s")
            params.append(date_from)
        if date_to is not None:
            where_clauses.append("period_start <= %s")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        client_id,
                        period_start,
                        period_end,
                        period_grain,
                        applicants,
                        approved_applicants,
                        actual_revenue,
                        target_revenue,
                        cogs,
                        taxes,
                        gross_profit,
                        contribution_profit,
                        sales_count,
                        new_customers,
                        notes,
                        source,
                        metadata,
                        created_at,
                        updated_at
                    FROM client_business_inputs
                    WHERE {where_sql}
                    ORDER BY period_start ASC, period_end ASC
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        return [
            item
            for row in rows
            for item in [self._row_to_payload(row)]
            if item is not None
        ]


client_business_inputs_store = ClientBusinessInputsStore()
