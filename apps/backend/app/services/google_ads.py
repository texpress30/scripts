from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import load_settings
from app.services.google_store import google_snapshot_store


class GoogleAdsIntegrationError(RuntimeError):
    pass


class GoogleAdsService:
    def integration_status(self) -> dict[str, str]:
        settings = load_settings()
        token = settings.google_ads_token.strip()
        if not token or token.startswith("your_"):
            return {
                "provider": "google_ads",
                "status": "pending",
                "message": "Google Ads token is configured as placeholder.",
            }
        return {
            "provider": "google_ads",
            "status": "connected",
            "message": "Google Ads token is available.",
        }

    def sync_client(self, client_id: int) -> dict[str, float | int | str]:
        settings = load_settings()
        token = settings.google_ads_token.strip()
        if not token or token.startswith("your_"):
            raise GoogleAdsIntegrationError("Google Ads token is missing or placeholder.")

        spend = float(100 + client_id * 17)
        impressions = 5000 + client_id * 110
        clicks = 200 + client_id * 9
        conversions = 5 + client_id
        revenue = round(spend * 3.2, 2)

        snapshot = {
            "client_id": client_id,
            "platform": "google_ads",
            "spend": round(spend, 2),
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "revenue": revenue,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        google_snapshot_store.upsert_snapshot(payload=snapshot)
        return snapshot

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        return google_snapshot_store.get_snapshot(client_id=client_id)


google_ads_service = GoogleAdsService()
