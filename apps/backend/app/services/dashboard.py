from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.google_ads import google_ads_service
from app.services.meta_ads import meta_ads_service
from app.services.performance_reports import performance_reports_store
from app.services.pinterest_ads import pinterest_ads_service
from app.services.snapchat_ads import snapchat_ads_service
from app.services.tiktok_ads import tiktok_ads_service

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


def _to_float(value: object) -> float:
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    return 0.0


def _to_int(value: object) -> int:
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    return 0


logger = logging.getLogger(__name__)


class UnifiedDashboardService:
    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for dashboard Postgres queries")
        return psycopg.connect(settings.database_url)

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
        if not self._is_test_mode():
            performance_reports_store.initialize_schema()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        WITH perf AS (
                            SELECT
                                apr.platform,
                                COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                                apr.spend,
                                apr.impressions,
                                apr.clicks,
                                apr.conversions,
                                apr.conversion_value
                            FROM ad_performance_reports apr
                            LEFT JOIN LATERAL (
                                SELECT m.client_id
                                FROM agency_account_client_mappings m
                                WHERE m.platform = apr.platform AND m.account_id = apr.customer_id
                                ORDER BY m.updated_at DESC, m.created_at DESC
                                LIMIT 1
                            ) mapped ON TRUE
                        )
                        SELECT platform,
                               COALESCE(SUM(spend), 0),
                               COALESCE(SUM(impressions), 0),
                               COALESCE(SUM(clicks), 0),
                               COALESCE(SUM(conversions), 0),
                               COALESCE(SUM(conversion_value), 0)
                        FROM perf
                        WHERE resolved_client_id = %s
                        GROUP BY platform
                        """,
                        (client_id,),
                    )
                    rows = cur.fetchall()

            platform_totals = {
                str(row[0]): {
                    "spend": _to_float(row[1]),
                    "impressions": _to_int(row[2]),
                    "clicks": _to_int(row[3]),
                    "conversions": _to_int(row[4]),
                    "revenue": _to_float(row[5]),
                }
                for row in rows
            }

            def platform_metrics(name: str) -> dict[str, object]:
                return self._normalize_platform_metrics(name, {"client_id": client_id, **platform_totals.get(name, {})}, client_id)

            google_metrics = platform_metrics("google_ads")
            meta_metrics = platform_metrics("meta_ads")
            tiktok_metrics = platform_metrics("tiktok_ads")
            pinterest_metrics = platform_metrics("pinterest_ads")
            snapchat_metrics = platform_metrics("snapchat_ads")
        else:
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

    def get_agency_dashboard(self, *, start_date: date, end_date: date) -> dict[str, object]:
        if self._is_test_mode():
            clients = client_registry_service.list_clients()
            totals = {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
            top_clients: list[dict[str, object]] = []
            for client in clients:
                cid = int(client["id"])
                metrics = self.get_client_dashboard(cid)
                mt = metrics["totals"]
                spend = _to_float(mt.get("spend"))
                totals["spend"] += spend
                totals["impressions"] += _to_int(mt.get("impressions"))
                totals["clicks"] += _to_int(mt.get("clicks"))
                totals["conversions"] += _to_int(mt.get("conversions"))
                totals["revenue"] += _to_float(mt.get("revenue"))
                top_clients.append({"client_id": cid, "name": str(client.get("name") or f"Client {cid}"), "spend": round(spend, 2)})

            top_clients.sort(key=lambda item: float(item["spend"]), reverse=True)
            return {
                "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                "active_clients": len(clients),
                "totals": {
                    "spend": round(float(totals["spend"]), 2),
                    "impressions": int(totals["impressions"]),
                    "clicks": int(totals["clicks"]),
                    "conversions": int(totals["conversions"]),
                    "revenue": round(float(totals["revenue"]), 2),
                    "roas": round(float(totals["revenue"]) / float(totals["spend"]), 2) if float(totals["spend"]) > 0 else 0.0,
                },
                "top_clients": top_clients[:5],
            }

        performance_reports_store.initialize_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH perf AS (
                        SELECT
                            apr.platform,
                            apr.customer_id,
                            COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                            apr.spend,
                            apr.impressions,
                            apr.clicks,
                            apr.conversions,
                            apr.conversion_value
                        FROM ad_performance_reports apr
                        LEFT JOIN LATERAL (
                            SELECT m.client_id
                            FROM agency_account_client_mappings m
                            WHERE m.platform = apr.platform AND m.account_id = apr.customer_id
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ) mapped ON TRUE
                        WHERE apr.report_date BETWEEN %s AND %s
                    )
                    SELECT
                        COALESCE(SUM(spend), 0),
                        COALESCE(SUM(impressions), 0),
                        COALESCE(SUM(clicks), 0),
                        COALESCE(SUM(conversions), 0),
                        COALESCE(SUM(conversion_value), 0),
                        COUNT(*)
                    FROM perf
                    """,
                    (start_date, end_date),
                )
                totals_row = cur.fetchone() or (0, 0, 0, 0, 0, 0)

                cur.execute(
                    """
                    WITH perf AS (
                        SELECT
                            COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                            apr.spend
                        FROM ad_performance_reports apr
                        LEFT JOIN LATERAL (
                            SELECT m.client_id
                            FROM agency_account_client_mappings m
                            WHERE m.platform = apr.platform AND m.account_id = apr.customer_id
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ) mapped ON TRUE
                        WHERE apr.report_date BETWEEN %s AND %s
                    )
                    SELECT c.id, c.name, COALESCE(SUM(perf.spend), 0) AS total_spend
                    FROM agency_clients c
                    JOIN perf ON perf.resolved_client_id = c.id
                    WHERE c.source = 'manual'
                    GROUP BY c.id, c.name
                    ORDER BY total_spend DESC, c.id ASC
                    LIMIT 5
                    """,
                    (start_date, end_date),
                )
                top_rows = cur.fetchall()

                cur.execute("SELECT COUNT(*) FROM agency_clients WHERE source = 'manual'")
                active_clients = int((cur.fetchone() or [0])[0])

        if _to_int(totals_row[5]) == 0:
            logger.warning(
                "agency_dashboard_empty_result",
                extra={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            )
        else:
            logger.info(
                "agency_dashboard_query_rows",
                extra={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "rows": _to_int(totals_row[5]),
                    "top_clients": len(top_rows),
                },
            )

        total_spend = _to_float(totals_row[0])
        total_revenue = _to_float(totals_row[4])
        return {
            "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "active_clients": active_clients,
            "totals": {
                "spend": round(total_spend, 2),
                "impressions": _to_int(totals_row[1]),
                "clicks": _to_int(totals_row[2]),
                "conversions": _to_int(totals_row[3]),
                "revenue": round(total_revenue, 2),
                "roas": round(total_revenue / total_spend, 2) if total_spend > 0 else 0.0,
            },
            "top_clients": [
                {"client_id": int(row[0]), "name": str(row[1]), "spend": round(_to_float(row[2]), 2)} for row in top_rows
            ],
        }


unified_dashboard_service = UnifiedDashboardService()
