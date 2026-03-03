from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.config import load_settings
from app.services.performance_reports import performance_reports_store
from app.services.tiktok_store import tiktok_snapshot_store


class TikTokAdsIntegrationError(RuntimeError):
    pass


class TikTokAdsService:
    def integration_status(self) -> dict[str, str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            return {
                "provider": "tiktok_ads",
                "status": "disabled",
                "message": "TikTok integration is disabled by feature flag.",
            }

        return {
            "provider": "tiktok_ads",
            "status": "connected",
            "message": "TikTok integration mock adapter is enabled.",
        }

    def _provider_snapshot(self, *, client_id: int, attempt: int, forced_failures: int) -> dict[str, float | int | str]:
        if attempt <= forced_failures:
            raise RuntimeError("Transient TikTok provider timeout")

        spend = float(70 + client_id * 11)
        impressions = 3200 + client_id * 90
        clicks = 140 + client_id * 6
        conversions = 3 + client_id
        revenue = round(spend * 2.4, 2)
        synced_at = datetime.now(timezone.utc).isoformat()

        return {
            "client_id": client_id,
            "platform": "tiktok_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": synced_at,
            "status": "success",
            "attempts": attempt,
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.")

        retry_attempts = max(1, settings.tiktok_sync_retry_attempts)
        backoff_seconds = max(0, settings.tiktok_sync_backoff_ms) / 1000.0
        forced_failures = max(0, settings.tiktok_sync_force_transient_failures)

        last_error: Exception | None = None
        for attempt in range(1, retry_attempts + 1):
            try:
                snapshot = self._provider_snapshot(
                    client_id=client_id,
                    attempt=attempt,
                    forced_failures=forced_failures,
                )
                tiktok_snapshot_store.upsert_snapshot(payload=snapshot)
                performance_reports_store.write_daily_report(
                    report_date=datetime.now(timezone.utc).date(),
                    platform="tiktok_ads",
                    customer_id=f"client-{client_id}",
                    client_id=client_id,
                    spend=float(snapshot["spend"]),
                    impressions=int(snapshot["impressions"]),
                    clicks=int(snapshot["clicks"]),
                    conversions=float(snapshot["conversions"]),
                    conversion_value=float(snapshot["revenue"]),
                    extra_metrics={
                        "tiktok_ads": {
                            "result": float(snapshot["conversions"]),
                            "gmv": float(snapshot["revenue"]),
                            "click_through_rate_clicks": int(snapshot["clicks"]),
                        }
                    },
                )
                return snapshot
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retry_attempts and backoff_seconds > 0:
                    time.sleep(backoff_seconds * attempt)

        raise TikTokAdsIntegrationError(
            f"TikTok provider transient failure after {retry_attempts} attempts"
        ) from last_error

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return tiktok_snapshot_store.get_snapshot(client_id=client_id)


tiktok_ads_service = TikTokAdsService()
