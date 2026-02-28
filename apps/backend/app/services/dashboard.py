from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import logging

import requests

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
    def __init__(self) -> None:
        self._fx_cache: dict[tuple[str, str], float] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for dashboard Postgres queries")
        return psycopg.connect(settings.database_url)

    def _normalize_currency_code(self, value: object, *, fallback: str = "RON") -> str:
        code = str(value or "").strip().upper()
        if len(code) == 3 and code.isalpha():
            return code
        return fallback

    def _fallback_fx_rate_to_ron(self, *, currency_code: str) -> float:
        defaults = {
            "USD": 4.318394,
            "EUR": 4.97,
            "GBP": 5.82,
            "CHF": 5.12,
            "CAD": 3.2,
            "AUD": 2.85,
        }
        return float(defaults.get(currency_code, 1.0))

    def _get_fx_rate_to_ron(self, *, currency_code: str, rate_date: date) -> float:
        normalized_currency = self._normalize_currency_code(currency_code, fallback="RON")
        if normalized_currency == "RON":
            return 1.0

        cache_key = (rate_date.isoformat(), normalized_currency)
        cached = self._fx_cache.get(cache_key)
        if cached is not None:
            return cached

        for day_offset in range(0, 7):
            target_date = rate_date - timedelta(days=day_offset)
            url = f"https://api.frankfurter.app/{target_date.isoformat()}"
            try:
                response = requests.get(url, params={"from": normalized_currency, "to": "RON"}, timeout=6)
                response.raise_for_status()
                payload = response.json() if response.content else {}
                rates = payload.get("rates", {}) if isinstance(payload, dict) else {}
                value = rates.get("RON")
                if isinstance(value, (int, float)) and float(value) > 0:
                    rate = float(value)
                    self._fx_cache[cache_key] = rate
                    return rate
            except Exception:  # noqa: BLE001
                continue

        fallback_rate = self._fallback_fx_rate_to_ron(currency_code=normalized_currency)
        logger.warning(
            "agency_dashboard_fx_fallback",
            extra={"currency": normalized_currency, "date": rate_date.isoformat(), "fallback_rate": fallback_rate},
        )
        self._fx_cache[cache_key] = fallback_rate
        return fallback_rate

    def _aggregate_agency_rows(self, rows: list[tuple[object, object, object, object, object, object, object, object]]) -> tuple[dict[str, float | int], dict[int, float], dict[int, float], dict[int, str], int]:
        totals: dict[str, float | int] = {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
        spend_by_client_ron: dict[int, float] = {}
        spend_by_client_native: dict[int, float] = {}
        client_currency_votes: dict[int, dict[str, int]] = {}

        for row in rows:
            report_date = row[0] if isinstance(row[0], date) else date.today()
            resolved_client_id = _to_int(row[1])
            currency = self._normalize_currency_code(row[2], fallback="RON")
            spend = _to_float(row[3])
            impressions = _to_int(row[4])
            clicks = _to_int(row[5])
            conversions = _to_int(row[6])
            revenue = _to_float(row[7])

            rate = self._get_fx_rate_to_ron(currency_code=currency, rate_date=report_date)
            spend_ron = spend * rate
            revenue_ron = revenue * rate

            totals["spend"] = float(totals["spend"]) + spend_ron
            totals["impressions"] = int(totals["impressions"]) + impressions
            totals["clicks"] = int(totals["clicks"]) + clicks
            totals["conversions"] = int(totals["conversions"]) + conversions
            totals["revenue"] = float(totals["revenue"]) + revenue_ron

            if resolved_client_id > 0:
                spend_by_client_ron[resolved_client_id] = spend_by_client_ron.get(resolved_client_id, 0.0) + spend_ron
                spend_by_client_native[resolved_client_id] = spend_by_client_native.get(resolved_client_id, 0.0) + spend
                votes = client_currency_votes.setdefault(resolved_client_id, {})
                votes[currency] = votes.get(currency, 0) + 1

        client_currency: dict[int, str] = {}
        for client_id, votes in client_currency_votes.items():
            client_currency[client_id] = sorted(votes.items(), key=lambda item: item[1], reverse=True)[0][0]

        return totals, spend_by_client_ron, spend_by_client_native, client_currency, len(rows)

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

    def _client_reports_query(self) -> str:
        return """
                        WITH perf AS (
                            SELECT
                                apr.platform,
                                COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                                apr.report_date,
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
                          AND report_date BETWEEN %s AND %s
                        GROUP BY platform
                        """

    def get_client_dashboard(self, client_id: int, *, start_date: date | None = None, end_date: date | None = None) -> dict[str, object]:
        resolved_end = end_date or date.today()
        resolved_start = start_date or (resolved_end - timedelta(days=29))

        if not self._is_test_mode():
            performance_reports_store.initialize_schema()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        self._client_reports_query(),
                        (client_id, resolved_start, resolved_end),
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

        preferred_currency = client_registry_service.get_preferred_currency_for_client(client_id=client_id)

        return {
            "client_id": client_id,
            "currency": preferred_currency,
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

    def _agency_reports_query(self) -> str:
        return """
                    WITH perf AS (
                        SELECT
                            apr.report_date,
                            COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                            COALESCE(NULLIF(TRIM(mapped.account_currency), ''), NULLIF(TRIM(client.currency), ''), 'RON') AS account_currency,
                            apr.spend,
                            apr.impressions,
                            apr.clicks,
                            apr.conversions,
                            apr.conversion_value
                        FROM ad_performance_reports apr
                        LEFT JOIN LATERAL (
                            SELECT m.client_id, m.account_currency
                            FROM agency_account_client_mappings m
                            WHERE m.platform = apr.platform
                              AND (
                                  m.account_id = apr.customer_id
                                  OR (
                                      apr.platform = 'google_ads'
                                      AND regexp_replace(m.account_id, '[^0-9]', '', 'g') = regexp_replace(apr.customer_id, '[^0-9]', '', 'g')
                                  )
                              )
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ) mapped ON TRUE
                        LEFT JOIN agency_clients client ON client.id = COALESCE(apr.client_id, mapped.client_id)
                        WHERE apr.report_date BETWEEN %s AND %s
                    )
                    SELECT
                        report_date,
                        resolved_client_id,
                        account_currency,
                        COALESCE(spend, 0),
                        COALESCE(impressions, 0),
                        COALESCE(clicks, 0),
                        COALESCE(conversions, 0),
                        COALESCE(conversion_value, 0)
                    FROM perf
                    """

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
                top_clients.append({"client_id": cid, "name": str(client.get("name") or f"Client {cid}"), "spend": round(spend, 2), "currency": "RON", "spend_ron": round(spend, 2)})

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
                "currency": "RON",
            }

        performance_reports_store.initialize_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH perf AS (
                        SELECT
                            apr.report_date,
                            COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                            COALESCE(NULLIF(TRIM(mapped.account_currency), ''), 'RON') AS account_currency,
                            apr.spend,
                            apr.impressions,
                            apr.clicks,
                            apr.conversions,
                            apr.conversion_value
                        FROM ad_performance_reports apr
                        LEFT JOIN LATERAL (
                            SELECT m.client_id, m.account_currency
                            FROM agency_account_client_mappings m
                            WHERE m.platform = apr.platform AND m.account_id = apr.customer_id
                            ORDER BY m.updated_at DESC, m.created_at DESC
                            LIMIT 1
                        ) mapped ON TRUE
                        WHERE apr.report_date BETWEEN %s AND %s
                    )
                    SELECT
                        report_date,
                        resolved_client_id,
                        account_currency,
                        COALESCE(spend, 0),
                        COALESCE(impressions, 0),
                        COALESCE(clicks, 0),
                        COALESCE(conversions, 0),
                        COALESCE(conversion_value, 0)
                    FROM perf
                    """,
                    (start_date, end_date),
                )
                rows = cur.fetchall()

        totals, spend_by_client_ron, spend_by_client_native, client_currency, row_count = self._aggregate_agency_rows(rows)

        manual_clients = client_registry_service.list_clients()
        active_clients = len(manual_clients)
        client_names = {int(item["id"]): str(item.get("name") or f"Client {item['id']}") for item in manual_clients}

        top_clients: list[dict[str, object]] = []
        for client_id, spend_ron in sorted(spend_by_client_ron.items(), key=lambda item: item[1], reverse=True):
            if client_id not in client_names:
                continue
            preferred_currency = client_currency.get(client_id, "RON")
            display_spend = spend_by_client_native.get(client_id, 0.0) if preferred_currency != "RON" else spend_ron
            top_clients.append(
                {
                    "client_id": client_id,
                    "name": client_names[client_id],
                    "spend": round(display_spend, 2),
                    "currency": preferred_currency,
                    "spend_ron": round(spend_ron, 2),
                }
            )
            if len(top_clients) >= 5:
                break

        if row_count == 0:
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
                    "rows": row_count,
                    "top_clients": len(top_clients),
                },
            )

        total_spend = float(totals["spend"])
        total_revenue = float(totals["revenue"])
        return {
            "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "active_clients": active_clients,
            "currency": "RON",
            "totals": {
                "spend": round(total_spend, 2),
                "impressions": int(totals["impressions"]),
                "clicks": int(totals["clicks"]),
                "conversions": int(totals["conversions"]),
                "revenue": round(total_revenue, 2),
                "roas": round(total_revenue / total_spend, 2) if total_spend > 0 else 0.0,
            },
            "top_clients": top_clients,
        }


unified_dashboard_service = UnifiedDashboardService()
