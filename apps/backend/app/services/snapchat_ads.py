from __future__ import annotations

from app.core.config import load_settings


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
            "status": "preview",
            "message": "Snapchat integration skeleton is enabled (sync is a contract stub).",
        }

    def sync_client(self, client_id: int) -> dict[str, int | str]:
        settings = load_settings()
        if not settings.ff_snapchat_integration:
            raise SnapchatAdsIntegrationError("Snapchat integration is disabled by feature flag.")

        if client_id <= 0:
            raise SnapchatAdsIntegrationError("Client id must be a positive integer.")

        return {
            "client_id": client_id,
            "platform": "snapchat_ads",
            "status": "stub",
            "message": "Snapchat sync contract accepted. Provider adapter will be added in next slice.",
        }


snapchat_ads_service = SnapchatAdsService()
