from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from app.core.config import load_settings


class GoogleAdsIntegrationError(RuntimeError):
    pass


@dataclass
class GoogleAdsSnapshot:
    client_id: int
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float


class GoogleAdsService:
    def __init__(self) -> None:
        self._snapshots: dict[int, GoogleAdsSnapshot] = {}
        self._lock = Lock()

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

        snapshot = GoogleAdsSnapshot(
            client_id=client_id,
            spend=round(spend, 2),
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            revenue=revenue,
        )

        with self._lock:
            self._snapshots[client_id] = snapshot

        return {
            "client_id": snapshot.client_id,
            "platform": "google_ads",
            "spend": snapshot.spend,
            "impressions": snapshot.impressions,
            "clicks": snapshot.clicks,
            "conversions": snapshot.conversions,
            "revenue": snapshot.revenue,
        }

    def get_metrics(self, client_id: int) -> dict[str, float | int | str | bool]:
        with self._lock:
            snapshot = self._snapshots.get(client_id)

        if snapshot is None:
            return {
                "client_id": client_id,
                "platform": "google_ads",
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "is_synced": False,
            }

        return {
            "client_id": snapshot.client_id,
            "platform": "google_ads",
            "spend": snapshot.spend,
            "impressions": snapshot.impressions,
            "clicks": snapshot.clicks,
            "conversions": snapshot.conversions,
            "revenue": snapshot.revenue,
            "is_synced": True,
        }


google_ads_service = GoogleAdsService()
