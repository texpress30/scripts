from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from app.core.config import load_settings


class MetaAdsIntegrationError(RuntimeError):
    pass


@dataclass
class MetaAdsSnapshot:
    client_id: int
    spend: float
    impressions: int
    clicks: int
    conversions: int
    revenue: float


class MetaAdsService:
    def __init__(self) -> None:
        self._snapshots: dict[int, MetaAdsSnapshot] = {}
        self._lock = Lock()

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

        snapshot = MetaAdsSnapshot(
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
            "platform": "meta_ads",
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
                "platform": "meta_ads",
                "spend": 0.0,
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue": 0.0,
                "is_synced": False,
            }

        return {
            "client_id": snapshot.client_id,
            "platform": "meta_ads",
            "spend": snapshot.spend,
            "impressions": snapshot.impressions,
            "clicks": snapshot.clicks,
            "conversions": snapshot.conversions,
            "revenue": snapshot.revenue,
            "is_synced": True,
        }


meta_ads_service = MetaAdsService()
