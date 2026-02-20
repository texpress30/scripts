from __future__ import annotations

from app.services.google_ads import google_ads_service
from app.services.meta_ads import meta_ads_service
from app.services.tiktok_ads import tiktok_ads_service


def _to_float(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _to_int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


class UnifiedDashboardService:
    def get_client_dashboard(self, client_id: int) -> dict[str, object]:
        google_metrics = google_ads_service.get_metrics(client_id)
        meta_metrics = meta_ads_service.get_metrics(client_id)
        tiktok_metrics = tiktok_ads_service.get_metrics(client_id)

        total_spend = (
            _to_float(google_metrics.get("spend"))
            + _to_float(meta_metrics.get("spend"))
            + _to_float(tiktok_metrics.get("spend"))
        )
        total_revenue = (
            _to_float(google_metrics.get("revenue"))
            + _to_float(meta_metrics.get("revenue"))
            + _to_float(tiktok_metrics.get("revenue"))
        )
        total_impressions = (
            _to_int(google_metrics.get("impressions"))
            + _to_int(meta_metrics.get("impressions"))
            + _to_int(tiktok_metrics.get("impressions"))
        )
        total_clicks = (
            _to_int(google_metrics.get("clicks"))
            + _to_int(meta_metrics.get("clicks"))
            + _to_int(tiktok_metrics.get("clicks"))
        )
        total_conversions = (
            _to_int(google_metrics.get("conversions"))
            + _to_int(meta_metrics.get("conversions"))
            + _to_int(tiktok_metrics.get("conversions"))
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
            },
            "is_synced": bool(
                google_metrics.get("is_synced")
                or meta_metrics.get("is_synced")
                or tiktok_metrics.get("is_synced")
            ),
        }


unified_dashboard_service = UnifiedDashboardService()
