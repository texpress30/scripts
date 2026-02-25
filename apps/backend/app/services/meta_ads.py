from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import load_settings
from app.services.meta_store import meta_snapshot_store


class MetaAdsIntegrationError(RuntimeError):
    pass


class MetaAdsService:
    def integration_status(self) -> dict[str, str]:
        settings = load_settings()
        token = settings.meta_access_token.strip()
        if not token or token.startswith("your_"):
            return {
                "provider": "meta_ads",
                "status": "pending",
                "message": "Meta Ads token is configured as placeholder.",
            }
        return {
            "provider": "meta_ads",
            "status": "connected",
            "message": "Meta Ads token is available.",
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        token = settings.meta_access_token.strip()
        if not token or token.startswith("your_"):
            raise MetaAdsIntegrationError("Meta Ads token is missing or placeholder.")

        spend = float(85 + client_id * 13)
        impressions = 4200 + client_id * 95
        clicks = 170 + client_id * 7
        conversions = 4 + client_id
        revenue = round(spend * 2.7, 2)

        snapshot = {
            "client_id": client_id,
            "platform": "meta_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        meta_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return meta_snapshot_store.get_snapshot(client_id=client_id)


meta_ads_service = MetaAdsService()
