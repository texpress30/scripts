from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import load_settings
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

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.")

        spend = float(70 + client_id * 11)
        impressions = 3200 + client_id * 90
        clicks = 140 + client_id * 6
        conversions = 3 + client_id
        revenue = round(spend * 2.4, 2)
        synced_at = datetime.now(timezone.utc).isoformat()

        snapshot = {
            "client_id": client_id,
            "platform": "tiktok_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": synced_at,
            "status": "success",
        }
        tiktok_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return tiktok_snapshot_store.get_snapshot(client_id=client_id)


tiktok_ads_service = TikTokAdsService()
