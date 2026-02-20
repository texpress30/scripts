from __future__ import annotations

from app.core.config import load_settings


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
            "status": "preview",
            "message": "TikTok integration skeleton is enabled (sync is a stub).",
        }

    def sync_client(self, client_id: int) -> dict[str, int | str]:
        settings = load_settings()
        if not settings.ff_tiktok_integration:
            raise TikTokAdsIntegrationError("TikTok integration is disabled by feature flag.")

        if client_id <= 0:
            raise TikTokAdsIntegrationError("Client id must be a positive integer.")

        return {
            "client_id": client_id,
            "platform": "tiktok_ads",
            "status": "stub",
            "message": "TikTok sync contract accepted. Provider adapter will be added in slice 8.2.2.",
        }


tiktok_ads_service = TikTokAdsService()
