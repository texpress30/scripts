from __future__ import annotations

from datetime import date
import json
from threading import Lock
import os

from app.core.config import load_settings
from app.services.sync_engine import DailyMetricRow

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class PerformanceReportsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memory_rows: list[dict[str, object]] = []
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test" and os.environ.get("PYTEST_CURRENT_TEST") is not None

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for ad performance persistence")
        return psycopg.connect(settings.database_url)

    def _deduplicate_reports_query(self) -> str:
        return """
                    WITH ranked AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (
                                PARTITION BY report_date, platform, customer_id
                                ORDER BY synced_at DESC, id DESC
                            ) AS rn
                        FROM ad_performance_reports
                    )
                    DELETE FROM ad_performance_reports apr
                    USING ranked
                    WHERE apr.id = ranked.id
                      AND ranked.rn > 1
                    """

    def _ensure_schema(self) -> None:
        settings = load_settings()
        if settings.app_env == "production":
            if hasattr(self, "_schema_initialized"):
                self._schema_initialized = True
            return
        if self._is_test_mode() or self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.ad_performance_reports')")
                    row = cur.fetchone() or (None,)
                    if row[0] is None:
                        raise RuntimeError("Database schema for ad_performance_reports is not ready; run DB migrations")

            self._schema_initialized = True

    def initialize_schema(self) -> None:
        self._ensure_schema()

    def upsert_rows(self, rows: list[DailyMetricRow]) -> int:
        if len(rows) == 0:
            return 0
        for row in rows:
            self.write_daily_report(
                report_date=row.report_date,
                platform=row.platform,
                customer_id=row.account_id,
                client_id=row.client_id,
                spend=float(row.spend),
                impressions=int(row.impressions),
                clicks=int(row.clicks),
                conversions=float(row.conversions),
                conversion_value=float(row.revenue),
                extra_metrics=dict(row.extra_metrics),
            )
        return len(rows)

    def write_daily_report(
        self,
        *,
        report_date: date,
        platform: str,
        customer_id: str,
        client_id: int | None,
        spend: float,
        impressions: int,
        clicks: int,
        conversions: float,
        conversion_value: float,
        extra_metrics: dict[str, object] | None = None,
    ) -> None:
        self._ensure_schema()
        normalized_extra_metrics = dict(extra_metrics or {})
        payload = {
            "report_date": report_date.isoformat(),
            "platform": platform,
            "customer_id": customer_id,
            "client_id": client_id,
            "spend": float(spend),
            "impressions": int(impressions),
            "clicks": int(clicks),
            "conversions": float(conversions),
            "conversion_value": float(conversion_value),
            "extra_metrics": normalized_extra_metrics,
        }

        if self._is_test_mode():
            with self._lock:
                existing_index = next(
                    (
                        index
                        for index, row in enumerate(self._memory_rows)
                        if str(row.get("report_date")) == payload["report_date"]
                        and str(row.get("platform")) == payload["platform"]
                        and str(row.get("customer_id")) == payload["customer_id"]
                    ),
                    None,
                )
                if existing_index is None:
                    self._memory_rows.append(payload)
                else:
                    self._memory_rows[existing_index] = payload
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ad_performance_reports (
                        report_date, platform, customer_id, client_id, spend, impressions, clicks, conversions, conversion_value, extra_metrics
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (report_date, platform, customer_id)
                    DO UPDATE SET
                        spend = EXCLUDED.spend,
                        impressions = EXCLUDED.impressions,
                        clicks = EXCLUDED.clicks,
                        conversions = EXCLUDED.conversions,
                        conversion_value = EXCLUDED.conversion_value,
                        extra_metrics = EXCLUDED.extra_metrics,
                        client_id = EXCLUDED.client_id,
                        synced_at = NOW()
                    """,
                    (
                        report_date,
                        platform,
                        customer_id,
                        client_id,
                        float(spend),
                        int(impressions),
                        int(clicks),
                        float(conversions),
                        float(conversion_value),
                        json.dumps(normalized_extra_metrics),
                    ),
                )
            conn.commit()


performance_reports_store = PerformanceReportsStore()
