from __future__ import annotations

from datetime import date
from threading import Lock
import os

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


class PerformanceReportsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memory_rows: list[dict[str, object]] = []

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test" and os.environ.get("PYTEST_CURRENT_TEST") is not None

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for ad performance persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._is_test_mode():
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
                        synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
            conn.commit()

    def initialize_schema(self) -> None:
        self._ensure_schema()

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
                self._memory_rows.append(payload)
            return

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ad_performance_reports (
                        report_date, platform, customer_id, client_id, spend, impressions, clicks, conversions, conversion_value
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
