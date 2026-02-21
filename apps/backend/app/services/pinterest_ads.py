from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.config import load_settings
from app.services.pinterest_store import pinterest_snapshot_store


class PinterestAdsIntegrationError(RuntimeError):
    pass


class PinterestAdsService:
    def integration_status(self) -> dict[str, str]:
        settings = load_settings()
        if not settings.ff_pinterest_integration:
            return {
                "provider": "pinterest_ads",
                "status": "disabled",
                "message": "Pinterest integration is disabled by feature flag.",
            }

        return {
            "provider": "pinterest_ads",
            "status": "connected",
            "message": "Pinterest integration mock adapter is enabled.",
        }

    def _provider_snapshot(self, *, client_id: int, attempt: int, forced_failures: int) -> dict[str, float | int | str]:
        if attempt <= forced_failures:
            raise RuntimeError("Transient Pinterest provider timeout")

        spend = float(45 + client_id * 7)
        impressions = 1800 + client_id * 50
        clicks = 90 + client_id * 3
        conversions = 2 + (client_id % 5)
        revenue = round(spend * 2.1, 2)

        return {
            "client_id": client_id,
            "platform": "pinterest_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "attempts": attempt,
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_pinterest_integration:
            raise PinterestAdsIntegrationError("Pinterest integration is disabled by feature flag.")

        if client_id <= 0:
            raise PinterestAdsIntegrationError("Client id must be a positive integer.")

        retry_attempts = max(1, settings.pinterest_sync_retry_attempts)
        backoff_seconds = max(0, settings.pinterest_sync_backoff_ms) / 1000.0
        forced_failures = max(0, settings.pinterest_sync_force_transient_failures)

        last_error: Exception | None = None
        for attempt in range(1, retry_attempts + 1):
            try:
                snapshot = self._provider_snapshot(
                    client_id=client_id,
                    attempt=attempt,
                    forced_failures=forced_failures,
                )
                pinterest_snapshot_store.upsert_snapshot(payload=snapshot)
                return snapshot
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retry_attempts and backoff_seconds > 0:
                    time.sleep(backoff_seconds * attempt)

        raise PinterestAdsIntegrationError(
            f"Pinterest provider transient failure after {retry_attempts} attempts"
        ) from last_error

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return pinterest_snapshot_store.get_snapshot(client_id=client_id)


pinterest_ads_service = PinterestAdsService()
