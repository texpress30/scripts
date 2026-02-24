from __future__ import annotations

from app.services.google_ads import google_ads_service
from app.services.meta_ads import meta_ads_service
from app.services.pinterest_ads import pinterest_ads_service
from app.services.snapchat_ads import snapchat_ads_service
from app.services.tiktok_ads import tiktok_ads_service


def _to_float(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _to_int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


class UnifiedDashboardService:
    def _normalize_platform_metrics(self, platform: str, metrics: dict[str, object], client_id: int) -> dict[str, object]:
        spend = round(_to_float(metrics.get("spend")), 2)
        revenue = round(_to_float(metrics.get("revenue")), 2)
        normalized: dict[str, object] = {
            "client_id": _to_int(metrics.get("client_id")) or client_id,
            "platform": platform,
            "spend": spend,
            "impressions": _to_int(metrics.get("impressions")),
            "clicks": _to_int(metrics.get("clicks")),
            "conversions": _to_int(metrics.get("conversions")),
            "revenue": revenue,
            "roas": round(revenue / spend, 2) if spend > 0 else 0.0,
            "is_synced": bool(metrics.get("is_synced")),
            "synced_at": str(metrics.get("synced_at") or ""),
            "attempts": _to_int(metrics.get("attempts")),
        }
        return normalized

    def get_client_dashboard(self, client_id: int) -> dict[str, object]:
        google_metrics = self._normalize_platform_metrics("google_ads", google_ads_service.get_metrics(client_id), client_id)
        meta_metrics = self._normalize_platform_metrics("meta_ads", meta_ads_service.get_metrics(client_id), client_id)
        tiktok_metrics = self._normalize_platform_metrics("tiktok_ads", tiktok_ads_service.get_metrics(client_id), client_id)
        pinterest_metrics = self._normalize_platform_metrics("pinterest_ads", pinterest_ads_service.get_metrics(client_id), client_id)
        snapchat_metrics = self._normalize_platform_metrics("snapchat_ads", snapchat_ads_service.get_metrics(client_id), client_id)

        total_spend = (
            _to_float(google_metrics.get("spend"))
            + _to_float(meta_metrics.get("spend"))
            + _to_float(tiktok_metrics.get("spend"))
            + _to_float(pinterest_metrics.get("spend"))
            + _to_float(snapchat_metrics.get("spend"))
        )
        total_revenue = (
            _to_float(google_metrics.get("revenue"))
            + _to_float(meta_metrics.get("revenue"))
            + _to_float(tiktok_metrics.get("revenue"))
            + _to_float(pinterest_metrics.get("revenue"))
            + _to_float(snapchat_metrics.get("revenue"))
        )
        total_impressions = (
            _to_int(google_metrics.get("impressions"))
            + _to_int(meta_metrics.get("impressions"))
            + _to_int(tiktok_metrics.get("impressions"))
            + _to_int(pinterest_metrics.get("impressions"))
            + _to_int(snapchat_metrics.get("impressions"))
        )
        total_clicks = (
            _to_int(google_metrics.get("clicks"))
            + _to_int(meta_metrics.get("clicks"))
            + _to_int(tiktok_metrics.get("clicks"))
            + _to_int(pinterest_metrics.get("clicks"))
            + _to_int(snapchat_metrics.get("clicks"))
        )
        total_conversions = (
            _to_int(google_metrics.get("conversions"))
            + _to_int(meta_metrics.get("conversions"))
            + _to_int(tiktok_metrics.get("conversions"))
            + _to_int(pinterest_metrics.get("conversions"))
            + _to_int(snapchat_metrics.get("conversions"))
        )

        return {
            "client_id": client_id,
            "totals": {
                "spend": round(total_spend, 2),
                "impressions": total_impressions,
                "clicks": total_clicks,
                "conversions": total_conversions,
                "revenue": round(total_revenue, 2),
                "roas": round(total_revenue / total_spend, 2) if total_spend > 0 else 0.0,
            },
            "platforms": {
                "google_ads": google_metrics,
                "meta_ads": meta_metrics,
                "tiktok_ads": tiktok_metrics,
                "pinterest_ads": pinterest_metrics,
                "snapchat_ads": snapchat_metrics,
            },
            "is_synced": bool(
                google_metrics.get("is_synced")
                or meta_metrics.get("is_synced")
                or tiktok_metrics.get("is_synced")
                or pinterest_metrics.get("is_synced")
                or snapchat_metrics.get("is_synced")
            ),
        }


unified_dashboard_service = UnifiedDashboardService()
