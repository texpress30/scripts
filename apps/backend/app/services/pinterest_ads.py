from __future__ import annotations

from app.core.config import load_settings


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
            "status": "preview",
            "message": "Pinterest integration skeleton is enabled (sync is a contract stub).",
        }

    def sync_client(self, client_id: int) -> dict[str, int | str]:
        settings = load_settings()
        if not settings.ff_pinterest_integration:
            raise PinterestAdsIntegrationError("Pinterest integration is disabled by feature flag.")

        if client_id <= 0:
            raise PinterestAdsIntegrationError("Client id must be a positive integer.")

        return {
            "client_id": client_id,
            "platform": "pinterest_ads",
            "status": "stub",
            "message": "Pinterest sync contract accepted. Provider adapter will be added in next slice.",
        }


pinterest_ads_service = PinterestAdsService()
