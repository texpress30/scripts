from __future__ import annotations

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

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_pinterest_integration:
            raise PinterestAdsIntegrationError("Pinterest integration is disabled by feature flag.")

        if client_id <= 0:
            raise PinterestAdsIntegrationError("Client id must be a positive integer.")

        spend = float(45 + client_id * 7)
        impressions = 1800 + client_id * 50
        clicks = 90 + client_id * 3
        conversions = 2 + (client_id % 5)
        revenue = round(spend * 2.1, 2)

        snapshot: dict[str, float | int | str] = {
            "client_id": client_id,
            "platform": "pinterest_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        pinterest_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return pinterest_snapshot_store.get_snapshot(client_id=client_id)


pinterest_ads_service = PinterestAdsService()
