from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.config import load_settings
from app.services.snapchat_store import snapchat_snapshot_store


class SnapchatAdsIntegrationError(RuntimeError):
    pass


class SnapchatAdsService:
    def integration_status(self) -> dict[str, str]:
        settings = load_settings()
        if not settings.ff_snapchat_integration:
            return {
                "provider": "snapchat_ads",
                "status": "disabled",
                "message": "Snapchat integration is disabled by feature flag.",
            }

        return {
            "provider": "snapchat_ads",
            "status": "connected",
            "message": "Snapchat integration mock adapter is enabled.",
        }

    def _provider_snapshot(self, *, client_id: int, attempt: int, forced_failures: int) -> dict[str, float | int | str]:
        if attempt <= forced_failures:
            raise RuntimeError("Transient Snapchat provider timeout")

        spend = float(38 + client_id * 6)
        impressions = 1600 + client_id * 45
        clicks = 84 + client_id * 2
        conversions = 1 + (client_id % 4)
        revenue = round(spend * 1.95, 2)

        return {
            "client_id": client_id,
            "platform": "snapchat_ads",
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
        if not settings.ff_snapchat_integration:
            raise SnapchatAdsIntegrationError("Snapchat integration is disabled by feature flag.")

        if client_id <= 0:
            raise SnapchatAdsIntegrationError("Client id must be a positive integer.")

        retry_attempts = max(1, settings.snapchat_sync_retry_attempts)
        backoff_seconds = max(0, settings.snapchat_sync_backoff_ms) / 1000.0
        forced_failures = max(0, settings.snapchat_sync_force_transient_failures)

        last_error: Exception | None = None
        for attempt in range(1, retry_attempts + 1):
            try:
                snapshot = self._provider_snapshot(
                    client_id=client_id,
                    attempt=attempt,
                    forced_failures=forced_failures,
                )
                snapchat_snapshot_store.upsert_snapshot(payload=snapshot)
                return snapshot
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retry_attempts and backoff_seconds > 0:
                    time.sleep(backoff_seconds * attempt)

        raise SnapchatAdsIntegrationError(
            f"Snapchat provider transient failure after {retry_attempts} attempts"
        ) from last_error

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return snapchat_snapshot_store.get_snapshot(client_id=client_id)


snapchat_ads_service = SnapchatAdsService()
