from __future__ import annotations

from datetime import date
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
        if self._is_test_mode() or self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS ad_performance_reports (
                            id BIGSERIAL PRIMARY KEY,
                            report_date DATE NOT NULL,
                            platform TEXT NOT NULL,
                            customer_id TEXT NOT NULL,
                            client_id INTEGER NULL,
                            spend NUMERIC(14,2) NOT NULL DEFAULT 0,
                            impressions BIGINT NOT NULL DEFAULT 0,
                            clicks BIGINT NOT NULL DEFAULT 0,
                            conversions NUMERIC(14,4) NOT NULL DEFAULT 0,
                            conversion_value NUMERIC(14,2) NOT NULL DEFAULT 0,
                            synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            UNIQUE (report_date, platform, customer_id)
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_ad_performance_reports_date_platform
                        ON ad_performance_reports (report_date DESC, platform)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_ad_performance_reports_customer
                        ON ad_performance_reports (platform, customer_id, report_date DESC)
                        """
                    )
                    cur.execute("DROP INDEX IF EXISTS idx_ad_performance_reports_unique_daily_customer")
                    cur.execute(
                        """
                        ALTER TABLE ad_performance_reports
                        DROP CONSTRAINT IF EXISTS ad_performance_reports_report_date_platform_customer_id_client_id_key
                        """
                    )
                    cur.execute(self._deduplicate_reports_query())
                    cur.execute(
                        """
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_performance_reports_unique_daily_customer
                        ON ad_performance_reports (report_date, platform, customer_id)
                        """
                    )
                conn.commit()

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
    ) -> None:
        self._ensure_schema()
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
                        report_date, platform, customer_id, client_id, spend, impressions, clicks, conversions, conversion_value
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (report_date, platform, customer_id)
                    DO UPDATE SET
                        spend = EXCLUDED.spend,
                        impressions = EXCLUDED.impressions,
                        clicks = EXCLUDED.clicks,
                        conversions = EXCLUDED.conversions,
                        conversion_value = EXCLUDED.conversion_value,
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
                    ),
                )
            conn.commit()


performance_reports_store = PerformanceReportsStore()
