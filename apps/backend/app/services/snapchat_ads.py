from __future__ import annotations

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

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_snapchat_integration:
            raise SnapchatAdsIntegrationError("Snapchat integration is disabled by feature flag.")

        if client_id <= 0:
            raise SnapchatAdsIntegrationError("Client id must be a positive integer.")

        spend = float(38 + client_id * 6)
        impressions = 1600 + client_id * 45
        clicks = 84 + client_id * 2
        conversions = 1 + (client_id % 4)
        revenue = round(spend * 1.95, 2)

        snapshot: dict[str, float | int | str] = {
            "client_id": client_id,
            "platform": "snapchat_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }
        snapchat_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return snapchat_snapshot_store.get_snapshot(client_id=client_id)


snapchat_ads_service = SnapchatAdsService()
