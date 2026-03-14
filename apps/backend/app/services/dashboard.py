from __future__ import annotations

from datetime import date, timedelta
import json
from decimal import Decimal
import logging

import requests

from app.core.config import load_settings
from app.services.account_currency_resolver import sql_effective_attached_account_currency_expression
from app.services.client_registry import client_registry_service
from app.services.business_metric_formulas import build_business_derived_metrics
from app.services.client_business_inputs_store import client_business_inputs_store
from app.services.report_metric_formulas import build_derived_metrics
from app.services.google_ads import google_ads_service
from app.services.meta_ads import meta_ads_service
from app.services.performance_reports import performance_reports_store
from app.services.pinterest_ads import pinterest_ads_service
from app.services.snapchat_ads import snapchat_ads_service
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.sync_runs_store import sync_runs_store
from app.services.tiktok_ads import tiktok_ads_service
from app.services.tiktok_account_daily_identity_resolver import resolve_tiktok_account_daily_persistence_identity

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

    def _normalize_currency_code(self, value: object, *, fallback: str = "USD") -> str:
        code = str(value or "").strip().upper()
        if len(code) == 3 and code.isalpha():
            return code
        return fallback

    def _fallback_fx_rate_to_ron(self, *, currency_code: str) -> float:
        defaults = {
            "USD": 4.62,
            "EUR": 4.97,
            "GBP": 5.86,
            "CHF": 5.20,
            "CAD": 3.34,
            "AUD": 2.99,
        }
        return float(defaults.get(currency_code, 1.0))

    def _get_fx_rate_to_ron(self, *, currency_code: str, rate_date: date) -> float:
        normalized_currency = self._normalize_currency_code(currency_code, fallback="USD")
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

    def _normalize_money(self, *, amount: float, from_currency: object, to_currency: object, rate_date: date) -> float:
        source = self._normalize_currency_code(from_currency, fallback="USD")
        target = self._normalize_currency_code(to_currency, fallback="USD")
        if source == target:
            return float(amount)
        amount_ron = float(amount) * self._get_fx_rate_to_ron(currency_code=source, rate_date=rate_date)
        if target == "RON":
            return amount_ron
        target_rate = self._get_fx_rate_to_ron(currency_code=target, rate_date=rate_date)
        if target_rate <= 0:
            return amount_ron
        return amount_ron / target_rate

    def _aggregate_client_rows(
        self,
        *,
        rows: list[tuple[object, object, object, object, object, object, object, object, object]],
        target_currency: str,
    ) -> dict[str, dict[str, object]]:
        platform_totals: dict[str, dict[str, object]] = {}
        for row in rows:
            report_date = row[1] if isinstance(row[1], date) else date.today()
            account_currency = self._normalize_currency_code(row[2], fallback=target_currency)
            platform = str(row[0] or "")
            if platform == "":
                continue

            spend = self._normalize_money(amount=_to_float(row[3]), from_currency=account_currency, to_currency=target_currency, rate_date=report_date)
            conversion_value = self._normalize_money(amount=_to_float(row[7]), from_currency=account_currency, to_currency=target_currency, rate_date=report_date)

            current = platform_totals.setdefault(
                platform,
                {
                    "spend": 0.0,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0.0,
                    "conversion_value": 0.0,
                    "extra_metrics": {},
                },
            )
            current["spend"] = _to_float(current.get("spend")) + spend
            current["impressions"] = _to_int(current.get("impressions")) + _to_int(row[4])
            current["clicks"] = _to_int(current.get("clicks")) + _to_int(row[5])
            current["conversions"] = _to_float(current.get("conversions")) + _to_float(row[6])
            current["conversion_value"] = _to_float(current.get("conversion_value")) + conversion_value
            incoming_extra = self._coerce_extra_metrics(row[8])
            current["extra_metrics"] = self._merge_extra_metrics(
                current.get("extra_metrics") if isinstance(current.get("extra_metrics"), dict) else {},
                incoming_extra,
            )
        return platform_totals

    def _aggregate_agency_rows(self, rows: list[tuple[object, object, object, object, object, object, object, object]]) -> tuple[dict[str, float | int], dict[int, float], dict[int, float], dict[int, str], int]:
        totals: dict[str, float | int] = {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
        spend_by_client_ron: dict[int, float] = {}
        spend_by_client_native: dict[int, float] = {}
        client_currency_votes: dict[int, dict[str, int]] = {}

        for row in rows:
            report_date = row[0] if isinstance(row[0], date) else date.today()
            resolved_client_id = _to_int(row[1])
            currency = self._normalize_currency_code(row[2], fallback="USD")
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
        conversion_value = round(_to_float(metrics.get("conversion_value", metrics.get("revenue"))), 2)
        extra_metrics = metrics.get("extra_metrics") if isinstance(metrics.get("extra_metrics"), dict) else {}
        conversions = _to_float(metrics.get("conversions"))

        normalized: dict[str, object] = {
            "client_id": _to_int(metrics.get("client_id")) or client_id,
            "platform": platform,
            "spend": spend,
            "impressions": _to_int(metrics.get("impressions")),
            "clicks": _to_int(metrics.get("clicks")),
            "conversions": conversions,
            "conversion_value": conversion_value,
            "revenue": conversion_value,
            "roas": round(conversion_value / spend, 2) if spend > 0 else 0.0,
            "extra_metrics": extra_metrics,
            "derived_metrics": build_derived_metrics(
                platform=platform,
                spend=spend,
                impressions=_to_int(metrics.get("impressions")),
                clicks=_to_int(metrics.get("clicks")),
                conversions=conversions,
                conversion_value=conversion_value,
                extra_metrics=extra_metrics,
            ),
            "is_synced": bool(metrics.get("is_synced")),
            "synced_at": str(metrics.get("synced_at") or ""),
            "attempts": _to_int(metrics.get("attempts")),
        }
        return normalized

    def _effective_attached_account_currency_sql(self, *, mapping_currency_expr: str, platform_currency_expr: str, client_currency_expr: str, fallback_literal: str) -> str:
        return sql_effective_attached_account_currency_expression(
            mapping_currency_expr=mapping_currency_expr,
            platform_currency_expr=platform_currency_expr,
            client_currency_expr=client_currency_expr,
            fallback_literal=fallback_literal,
        )

    def _client_reports_query(self) -> str:
        effective_currency_sql = self._effective_attached_account_currency_sql(
            mapping_currency_expr="mapped.account_currency",
            platform_currency_expr="apa.currency_code",
            client_currency_expr="client.currency",
            fallback_literal="USD",
        )
        return f"""
                        SELECT
                            apr.platform,
                            apr.report_date,
                            COALESCE(
                                NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), ''),
                                {effective_currency_sql}
                            ) AS account_currency,
                            COALESCE(apr.spend, 0),
                            COALESCE(apr.impressions, 0),
                            COALESCE(apr.clicks, 0),
                            COALESCE(apr.conversions, 0),
                            COALESCE(apr.conversion_value, 0),
                            COALESCE(apr.extra_metrics, '{{}}'::jsonb) AS extra_metrics
                        FROM ad_performance_reports apr
                        JOIN agency_account_client_mappings mapped
                          ON mapped.platform = apr.platform
                         AND mapped.client_id = %s
                         AND (
                              mapped.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND regexp_replace(mapped.account_id, '[^0-9]', '', 'g') = regexp_replace(apr.customer_id, '[^0-9]', '', 'g')
                              )
                         )
                        LEFT JOIN agency_platform_accounts apa
                          ON apa.platform = apr.platform
                         AND (
                              apa.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND regexp_replace(apa.account_id, '[^0-9]', '', 'g') = regexp_replace(apr.customer_id, '[^0-9]', '', 'g')
                              )
                         )
                        JOIN agency_clients client
                          ON client.id = mapped.client_id
                        WHERE apr.report_date BETWEEN %s AND %s
                          AND apr.platform IN ('google_ads', 'meta_ads', 'tiktok_ads', 'pinterest_ads', 'snapchat_ads')
                          AND COALESCE(
                              NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                              'account_daily'
                          ) = 'account_daily'
                        """


    def _client_dashboard_reconciliation_rows_query(self) -> str:
        effective_currency_sql = self._effective_attached_account_currency_sql(
            mapping_currency_expr="mapped.account_currency",
            platform_currency_expr="apa.currency_code",
            client_currency_expr="client.currency",
            fallback_literal="USD",
        )
        return f"""
                        SELECT
                            apr.platform,
                            apr.customer_id,
                            apr.report_date,
                            COALESCE(apr.spend, 0) AS spend,
                            COALESCE(apr.impressions, 0) AS impressions,
                            COALESCE(apr.clicks, 0) AS clicks,
                            COALESCE(apr.conversions, 0) AS conversions,
                            COALESCE(apr.conversion_value, 0) AS conversion_value,
                            NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), '') AS grain_raw,
                            COALESCE(
                                NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                                'account_daily'
                            ) AS grain_resolved,
                            NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), '') AS report_currency,
                            NULLIF(TRIM(apa.currency_code), '') AS platform_account_currency,
                            NULLIF(TRIM(mapped.account_currency), '') AS mapped_account_currency,
                            COALESCE(
                                NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), ''),
                                {effective_currency_sql}
                            ) AS resolved_currency,
                            CASE
                                WHEN NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), '') IS NOT NULL THEN 'report_extra_metrics'
                                WHEN NULLIF(TRIM(mapped.account_currency), '') IS NOT NULL THEN 'mapping_account_currency'
                                WHEN NULLIF(TRIM(apa.currency_code), '') IS NOT NULL THEN 'platform_account_currency'
                                WHEN NULLIF(TRIM(client.currency), '') IS NOT NULL THEN 'client_currency'
                                ELSE 'fallback_usd'
                            END AS currency_source,
                            mapped.client_id IS NOT NULL AS has_mapping
                        FROM ad_performance_reports apr
                        LEFT JOIN agency_account_client_mappings mapped
                          ON mapped.platform = apr.platform
                         AND mapped.client_id = %s
                         AND (
                              mapped.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND regexp_replace(mapped.account_id, '[^0-9]', '', 'g') = regexp_replace(apr.customer_id, '[^0-9]', '', 'g')
                              )
                         )
                        LEFT JOIN agency_platform_accounts apa
                          ON apa.platform = apr.platform
                         AND (
                              apa.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND regexp_replace(apa.account_id, '[^0-9]', '', 'g') = regexp_replace(apr.customer_id, '[^0-9]', '', 'g')
                              )
                         )
                        LEFT JOIN agency_clients client
                          ON client.id = mapped.client_id
                        WHERE apr.report_date BETWEEN %s AND %s
                          AND apr.platform IN ('google_ads', 'meta_ads', 'tiktok_ads', 'pinterest_ads', 'snapchat_ads')
                        """


    def _client_mappings_query(self) -> str:
        return """
                SELECT
                    platform,
                    account_id,
                    client_id,
                    account_currency,
                    created_at
                FROM agency_account_client_mappings
                WHERE client_id = %s
                ORDER BY platform, account_id
                """

    def _empty_metric_totals(self) -> dict[str, float | int]:
        return {
            "spend": 0.0,
            "impressions": 0,
            "clicks": 0,
            "conversions": 0.0,
            "revenue": 0.0,
        }

    def _add_to_metric_totals(self, totals: dict[str, float | int], *, spend: float, impressions: int, clicks: int, conversions: float, revenue: float) -> None:
        totals["spend"] = _to_float(totals.get("spend")) + spend
        totals["impressions"] = _to_int(totals.get("impressions")) + impressions
        totals["clicks"] = _to_int(totals.get("clicks")) + clicks
        totals["conversions"] = _to_float(totals.get("conversions")) + conversions
        totals["revenue"] = _to_float(totals.get("revenue")) + revenue

    def _platform_sync_audit_rows_query(self) -> str:
        return """
                    SELECT
                        apr.id,
                        apr.customer_id,
                        apr.report_date,
                        COALESCE(apr.spend, 0) AS spend,
                        COALESCE(apr.impressions, 0) AS impressions,
                        COALESCE(apr.clicks, 0) AS clicks,
                        COALESCE(apr.conversions, 0) AS conversions,
                        COALESCE(apr.conversion_value, 0) AS conversion_value,
                        apr.client_id,
                        COALESCE(
                            NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                            'account_daily'
                        ) AS grain,
                        NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), '') AS report_currency,
                        COALESCE(apr.extra_metrics, '{}'::jsonb) AS extra_metrics
                    FROM ad_performance_reports apr
                    WHERE apr.platform = %s
                      AND apr.report_date BETWEEN %s AND %s
                      AND (%s::text IS NULL OR apr.customer_id = %s::text)
                      AND (
                            apr.client_id = %s
                            OR apr.customer_id = ANY(%s::text[])
                      )
                    ORDER BY apr.report_date ASC, apr.customer_id ASC, apr.id ASC
                    """

    def _tiktok_account_daily_repair_rows_query(self) -> str:
        return """
                    SELECT
                        apr.id,
                        apr.customer_id,
                        apr.report_date,
                        COALESCE(apr.spend, 0) AS spend,
                        COALESCE(apr.impressions, 0) AS impressions,
                        COALESCE(apr.clicks, 0) AS clicks,
                        COALESCE(apr.conversions, 0) AS conversions,
                        COALESCE(apr.conversion_value, 0) AS conversion_value,
                        apr.client_id,
                        COALESCE(apr.extra_metrics, '{}'::jsonb) AS extra_metrics
                    FROM ad_performance_reports apr
                    WHERE apr.platform = 'tiktok_ads'
                      AND apr.report_date BETWEEN %s AND %s
                      AND (
                            apr.client_id = %s
                            OR apr.customer_id = ANY(%s::text[])
                      )
                      AND COALESCE(
                            NULLIF(TRIM(COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '')), ''),
                            'account_daily'
                      ) = 'account_daily'
                    ORDER BY apr.report_date ASC, apr.customer_id ASC, apr.id ASC
                    """

    def _tiktok_repair_provider_ids_for_row(self, *, customer_id: str, extra_metrics: dict[str, object]) -> list[str]:
        ids: list[str] = []
        normalized_customer = str(customer_id or '').strip()
        if normalized_customer != '':
            ids.append(normalized_customer)

        tiktok_meta = extra_metrics.get('tiktok_ads') if isinstance(extra_metrics, dict) else None
        if isinstance(tiktok_meta, dict):
            candidates = tiktok_meta.get('provider_identity_candidates')
            if isinstance(candidates, list):
                for raw in candidates:
                    normalized = str(raw or '').strip()
                    if normalized != '':
                        ids.append(normalized)
        deduped: list[str] = []
        seen: set[str] = set()
        for value in ids:
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    def _tiktok_repair_metrics_signature(self, row: dict[str, object]) -> tuple[float, int, int, float, float]:
        return (
            round(_to_float(row.get('spend')), 6),
            _to_int(row.get('impressions')),
            _to_int(row.get('clicks')),
            round(_to_float(row.get('conversions')), 6),
            round(_to_float(row.get('conversion_value')), 6),
        )

    def _resolve_tiktok_repair_attached_account(self, *, row: dict[str, object], attached_account_ids: list[str]) -> str | None:
        customer_id = str(row.get('customer_id') or '').strip()
        if customer_id in attached_account_ids:
            return customer_id
        provider_ids = self._tiktok_repair_provider_ids_for_row(customer_id=customer_id, extra_metrics=row.get('extra_metrics') if isinstance(row.get('extra_metrics'), dict) else {})
        matched = sorted({pid for pid in provider_ids if pid in set(attached_account_ids)})
        if len(matched) == 1:
            return matched[0]
        return None

    def _platform_sync_audit_rows_query(self) -> str:
        return """
                    SELECT
                        apr.id,
                        apr.customer_id,
                        apr.report_date,
                        COALESCE(apr.spend, 0) AS spend,
                        COALESCE(apr.impressions, 0) AS impressions,
                        COALESCE(apr.clicks, 0) AS clicks,
                        COALESCE(apr.conversions, 0) AS conversions,
                        COALESCE(apr.conversion_value, 0) AS conversion_value,
                        apr.client_id,
                        COALESCE(
                            NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                            'account_daily'
                        ) AS grain,
                        NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), '') AS report_currency,
                        COALESCE(apr.extra_metrics, '{}'::jsonb) AS extra_metrics
                    FROM ad_performance_reports apr
                    WHERE apr.platform = %s
                      AND apr.report_date BETWEEN %s AND %s
                      AND (%s::text IS NULL OR apr.customer_id = %s::text)
                      AND (
                            apr.client_id = %s
                            OR apr.customer_id = ANY(%s::text[])
                      )
                    ORDER BY apr.report_date ASC, apr.customer_id ASC, apr.id ASC
                    """

    def _sanitize_error_details(self, value: object) -> object:
        blocked_tokens = ("token", "secret", "password", "authorization", "auth", "cookie", "apikey", "api_key", "access_key")
        if isinstance(value, dict):
            sanitized: dict[str, object] = {}
            for key, item in value.items():
                key_text = str(key)
                if any(flag in key_text.lower() for flag in blocked_tokens):
                    sanitized[key_text] = "[redacted]"
                else:
                    sanitized[key_text] = self._sanitize_error_details(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize_error_details(item) for item in value]
        if isinstance(value, str) and any(flag in value.lower() for flag in ("bearer ", "ghp_", "github_pat_")):
            return "[redacted]"
        return value

    def _platform_supported_history_floor(self, *, platform: str) -> date | None:
        if str(platform) == "tiktok_ads":
            return date(2024, 9, 1)
        return None

    def _build_platform_sync_runs_summary(self, *, client_id: int, platform: str, attached_account_ids: list[str]) -> list[dict[str, object]]:
        runs: list[dict[str, object]] = []
        for account_id in attached_account_ids:
            for run in sync_runs_store.list_sync_runs_for_account(platform=platform, account_id=account_id, limit=20):
                run_client_id = run.get("client_id")
                if run_client_id is not None and int(run_client_id) != int(client_id):
                    continue
                chunk_counts = sync_run_chunks_store.get_sync_run_chunk_status_counts(str(run.get("job_id") or "")) if run.get("job_id") else {}
                metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
                runs.append(
                    {
                        "job_id": run.get("job_id"),
                        "platform": run.get("platform"),
                        "account_id": run.get("account_id"),
                        "client_id": run.get("client_id"),
                        "job_type": run.get("job_type"),
                        "trigger_source": metadata.get("trigger_source"),
                        "status": run.get("status"),
                        "grain": run.get("grain"),
                        "date_start": run.get("date_start"),
                        "date_end": run.get("date_end"),
                        "chunks_total": run.get("chunks_total"),
                        "chunks_done": run.get("chunks_done"),
                        "chunk_status_counts": chunk_counts,
                        "rows_written": run.get("rows_written"),
                        "sync_health_status": metadata.get("sync_health_status") or metadata.get("coverage_status"),
                        "coverage_status": metadata.get("coverage_status") or metadata.get("sync_health_status"),
                        "requested_start_date": metadata.get("requested_start_date") or run.get("date_start"),
                        "requested_end_date": metadata.get("requested_end_date") or run.get("date_end"),
                        "total_chunk_count": metadata.get("total_chunk_count") or run.get("chunks_total"),
                        "successful_chunk_count": metadata.get("successful_chunk_count") or run.get("chunks_done"),
                        "failed_chunk_count": metadata.get("failed_chunk_count") or run.get("chunks_error"),
                        "retry_attempted": metadata.get("retry_attempted"),
                        "retry_recovered_chunk_count": metadata.get("retry_recovered_chunk_count"),
                        "rows_written_count": metadata.get("rows_written_count") or run.get("rows_written"),
                        "first_persisted_date": metadata.get("first_persisted_date"),
                        "last_persisted_date": metadata.get("last_persisted_date"),
                        "last_error": metadata.get("last_error") or run.get("error"),
                        "last_error_summary": metadata.get("last_error_summary") or run.get("error"),
                        "last_error_details": self._sanitize_error_details(metadata.get("last_error_details") or metadata.get("error_details")),
                        "created_at": run.get("created_at"),
                        "updated_at": run.get("updated_at"),
                        "started_at": run.get("started_at"),
                        "finished_at": run.get("finished_at"),
                    }
                )
        runs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return runs[:100]

    def _build_dashboard_platform_sync_summary(self, *, client_id: int) -> dict[str, object]:
        payload: dict[str, object] = {}
        for platform in ("meta_ads", "tiktok_ads"):
            attached_accounts = client_registry_service.list_client_platform_accounts(platform=platform, client_id=client_id)
            attached_account_ids = [str(item.get("id") or "") for item in attached_accounts if str(item.get("id") or "") != ""]
            if len(attached_account_ids) <= 0:
                payload[platform] = {"accounts": []}
                continue

            recent_runs = self._build_platform_sync_runs_summary(client_id=client_id, platform=platform, attached_account_ids=attached_account_ids)
            latest_by_account: dict[str, dict[str, object]] = {}
            for run in recent_runs:
                account_id = str(run.get("account_id") or "")
                if account_id == "" or account_id in latest_by_account:
                    continue
                latest_by_account[account_id] = run

            account_items: list[dict[str, object]] = []
            for attached in attached_accounts:
                account_id = str(attached.get("id") or "")
                latest = latest_by_account.get(account_id, {})
                account_items.append(
                    {
                        "id": account_id,
                        "name": str(attached.get("name") or account_id),
                        "sync_health_status": latest.get("sync_health_status"),
                        "coverage_status": latest.get("coverage_status"),
                        "last_sync_at": latest.get("finished_at") or latest.get("updated_at") or latest.get("created_at"),
                        "requested_start_date": latest.get("requested_start_date"),
                        "requested_end_date": latest.get("requested_end_date"),
                        "total_chunk_count": latest.get("total_chunk_count"),
                        "successful_chunk_count": latest.get("successful_chunk_count"),
                        "failed_chunk_count": latest.get("failed_chunk_count"),
                        "retry_attempted": latest.get("retry_attempted"),
                        "retry_recovered_chunk_count": latest.get("retry_recovered_chunk_count"),
                        "rows_written_count": latest.get("rows_written_count"),
                        "first_persisted_date": latest.get("first_persisted_date"),
                        "last_persisted_date": latest.get("last_persisted_date"),
                        "last_error_summary": latest.get("last_error_summary"),
                        "last_error": latest.get("last_error"),
                    }
                )
            payload[platform] = {"accounts": account_items}
        return payload

    def get_client_platform_sync_audit(
        self,
        *,
        client_id: int,
        platform: str,
        start_date: date,
        end_date: date,
        account_id: str | None = None,
        include_daily_breakdown: bool = False,
    ) -> dict[str, object]:
        normalized_platform = str(platform).strip().lower()
        if normalized_platform not in {"meta_ads", "tiktok_ads"}:
            raise ValueError("platform must be one of: meta_ads, tiktok_ads")

        attached_accounts_all = client_registry_service.list_client_platform_accounts(platform=normalized_platform, client_id=client_id)
        if account_id is not None and str(account_id).strip() != "":
            filter_account_id = str(account_id).strip()
            attached_accounts = [item for item in attached_accounts_all if str(item.get("id") or "") == filter_account_id]
        else:
            filter_account_id = None
            attached_accounts = list(attached_accounts_all)

        attached_account_ids = [str(item.get("id") or "") for item in attached_accounts if str(item.get("id") or "") != ""]
        platform_rows = client_registry_service.list_platform_accounts_for_mapping(platform=normalized_platform)
        platform_meta_by_id = {
            str(item.get("account_id") or ""): item
            for item in platform_rows
            if str(item.get("client_id") or "") == str(client_id)
        }

        performance_reports_store.initialize_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._platform_sync_audit_rows_query(),
                    (
                        normalized_platform,
                        start_date,
                        end_date,
                        filter_account_id,
                        filter_account_id,
                        client_id,
                        attached_account_ids,
                    ),
                )
                report_rows = cur.fetchall() or []

        persisted_rows: list[dict[str, object]] = []
        for row in report_rows:
            persisted_rows.append(
                {
                    "row_id": _to_int(row[0]),
                    "customer_id": str(row[1] or ""),
                    "report_date": row[2].isoformat() if isinstance(row[2], date) else str(row[2] or ""),
                    "spend": _to_float(row[3]),
                    "impressions": _to_int(row[4]),
                    "clicks": _to_int(row[5]),
                    "conversions": _to_float(row[6]),
                    "revenue": _to_float(row[7]),
                    "client_id": _to_int(row[8]) if row[8] is not None else None,
                    "grain": str(row[9] or "account_daily"),
                    "report_currency": self._normalize_currency_code(row[10], fallback="") if row[10] else None,
                    "extra_metrics": row[11] if isinstance(row[11], dict) else {},
                }
            )

        by_grain: dict[str, dict[str, object]] = {}
        per_account_grain: dict[tuple[str, str], dict[str, object]] = {}
        account_daily_by_account_day: dict[tuple[str, str], list[dict[str, object]]] = {}
        lower_grain_by_account_day: dict[tuple[str, str], list[dict[str, object]]] = {}
        rows_present_no_mapping = 0
        duplicate_like_map: dict[tuple[str, str, str, str | None], int] = {}
        currency_mismatches: list[dict[str, object]] = []

        attached_currency_map = {
            str(item.get("id") or ""): str(item.get("effective_account_currency") or item.get("currency") or "").upper()
            for item in attached_accounts
        }

        for item in persisted_rows:
            grain = str(item.get("grain") or "account_daily")
            customer_id_value = str(item.get("customer_id") or "")
            day = str(item.get("report_date") or "")
            report_currency = str(item.get("report_currency") or "").upper() or None

            summary = by_grain.setdefault(
                grain,
                {
                    "grain": grain,
                    "row_count": 0,
                    "spend": 0.0,
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0.0,
                    "revenue": 0.0,
                },
            )
            summary["row_count"] = _to_int(summary.get("row_count")) + 1
            summary["spend"] = _to_float(summary.get("spend")) + _to_float(item.get("spend"))
            summary["impressions"] = _to_int(summary.get("impressions")) + _to_int(item.get("impressions"))
            summary["clicks"] = _to_int(summary.get("clicks")) + _to_int(item.get("clicks"))
            summary["conversions"] = _to_float(summary.get("conversions")) + _to_float(item.get("conversions"))
            summary["revenue"] = _to_float(summary.get("revenue")) + _to_float(item.get("revenue"))

            key = (customer_id_value, grain)
            per_account = per_account_grain.setdefault(
                key,
                {
                    "customer_id": customer_id_value,
                    "grain": grain,
                    "row_count": 0,
                    "first_date": day,
                    "last_date": day,
                    "spend": 0.0,
                    "report_currencies": set(),
                },
            )
            per_account["row_count"] = _to_int(per_account.get("row_count")) + 1
            per_account["first_date"] = min(str(per_account.get("first_date") or day), day)
            per_account["last_date"] = max(str(per_account.get("last_date") or day), day)
            per_account["spend"] = _to_float(per_account.get("spend")) + _to_float(item.get("spend"))
            if report_currency:
                per_account["report_currencies"].add(report_currency)

            dup_key = (customer_id_value, day, grain, report_currency)
            duplicate_like_map[dup_key] = duplicate_like_map.get(dup_key, 0) + 1

            if customer_id_value not in set(attached_account_ids):
                rows_present_no_mapping += 1

            account_currency = attached_currency_map.get(customer_id_value)
            if account_currency and report_currency and account_currency != report_currency:
                currency_mismatches.append(
                    {
                        "customer_id": customer_id_value,
                        "report_date": day,
                        "expected_currency": account_currency,
                        "report_currency": report_currency,
                        "grain": grain,
                    }
                )

            bucket_key = (customer_id_value, day)
            if grain == "account_daily":
                account_daily_by_account_day.setdefault(bucket_key, []).append(item)
            else:
                lower_grain_by_account_day.setdefault(bucket_key, []).append(item)

        duplicate_like_rows = [
            {
                "customer_id": key[0],
                "report_date": key[1],
                "grain": key[2],
                "report_currency": key[3],
                "row_count": count,
            }
            for key, count in duplicate_like_map.items()
            if count > 1
        ]
        multiple_account_daily = [
            {
                "customer_id": key[0],
                "report_date": key[1],
                "row_count": len(rows),
            }
            for key, rows in account_daily_by_account_day.items()
            if len(rows) > 1
        ]
        lower_without_account_daily = [
            {
                "customer_id": key[0],
                "report_date": key[1],
                "lower_grain_rows": len(rows),
            }
            for key, rows in lower_grain_by_account_day.items()
            if key not in account_daily_by_account_day
        ]

        missing_account_daily_days: list[dict[str, object]] = []
        if len(attached_account_ids) > 0:
            days: list[date] = []
            cursor_day = start_date
            while cursor_day <= end_date:
                days.append(cursor_day)
                cursor_day += timedelta(days=1)
            for attached_id in attached_account_ids:
                present_days = {key[1] for key in account_daily_by_account_day.keys() if key[0] == attached_id}
                missing = [day.isoformat() for day in days if day.isoformat() not in present_days]
                if len(missing) > 0:
                    missing_account_daily_days.append({"account_id": attached_id, "missing_days": missing})

        supported_floor = self._platform_supported_history_floor(platform=normalized_platform)
        rows_before_floor = []
        if supported_floor is not None:
            for item in persisted_rows:
                try:
                    row_date = date.fromisoformat(str(item.get("report_date") or ""))
                except Exception:
                    continue
                if row_date < supported_floor:
                    rows_before_floor.append(
                        {
                            "customer_id": item.get("customer_id"),
                            "report_date": item.get("report_date"),
                            "grain": item.get("grain"),
                        }
                    )

        account_daily_totals: list[dict[str, object]] = []
        for (customer_id_value, day), rows in sorted(account_daily_by_account_day.items()):
            account_daily_totals.append(
                {
                    "customer_id": customer_id_value,
                    "report_date": day,
                    "row_count": len(rows),
                    "spend": sum(_to_float(row.get("spend")) for row in rows),
                    "impressions": sum(_to_int(row.get("impressions")) for row in rows),
                    "clicks": sum(_to_int(row.get("clicks")) for row in rows),
                    "conversions": sum(_to_float(row.get("conversions")) for row in rows),
                    "revenue": sum(_to_float(row.get("revenue")) for row in rows),
                }
            )

        lower_grain_totals: dict[str, object] = {
            "by_grain": [value for key, value in sorted(by_grain.items()) if key != "account_daily"],
            "daily_breakdown": [],
        }
        if include_daily_breakdown:
            lower_grain_totals["daily_breakdown"] = [
                {
                    "customer_id": key[0],
                    "report_date": key[1],
                    "row_count": len(rows),
                    "spend": sum(_to_float(row.get("spend")) for row in rows),
                    "grains": sorted({str(row.get("grain") or "") for row in rows}),
                }
                for key, rows in sorted(lower_grain_by_account_day.items())
            ]

        mixed_ids_for_same_day = False
        if normalized_platform == "tiktok_ads":
            if len(attached_account_ids) == 1:
                day_to_ids: dict[str, set[str]] = {}
                for item in persisted_rows:
                    if str(item.get("grain")) != "account_daily":
                        continue
                    day_key = str(item.get("report_date") or "")
                    day_to_ids.setdefault(day_key, set()).add(str(item.get("customer_id") or ""))
                mixed_ids_for_same_day = any(len(ids) > 1 for ids in day_to_ids.values())

        grains_with_rows = [grain for grain, summary in by_grain.items() if _to_int(summary.get("row_count")) > 0]
        possible_overcount = len(grains_with_rows) > 1 and _to_float(by_grain.get("account_daily", {}).get("spend", 0.0)) > 0

        anomaly_flags = {
            "duplicate_like_rows_on_natural_key": len(duplicate_like_rows) > 0,
            "multiple_account_daily_rows_same_account_same_day": len(multiple_account_daily) > 0,
            "lower_grain_rows_present_without_account_daily": len(lower_without_account_daily) > 0,
            "account_daily_missing_for_days_inside_range": len(missing_account_daily_days) > 0,
            "persisted_dates_before_platform_supported_start": len(rows_before_floor) > 0,
            "mixed_customer_ids_for_same_attached_account": mixed_ids_for_same_day,
            "currency_mismatch_with_attached_account_currency": len(currency_mismatches) > 0,
            "rows_present_but_no_attached_mapping": rows_present_no_mapping > 0,
            "possible_overcount_if_summing_multiple_grains": possible_overcount,
        }

        suspected_root_causes: list[str] = []
        if anomaly_flags["duplicate_like_rows_on_natural_key"]:
            suspected_root_causes.append("duplicate-like persisted rows on natural key")
        if anomaly_flags["multiple_account_daily_rows_same_account_same_day"]:
            suspected_root_causes.append("duplicate account_daily rows for same account/day")
        if anomaly_flags["lower_grain_rows_present_without_account_daily"]:
            suspected_root_causes.append("lower-grain persistence without account_daily coverage")
        if anomaly_flags["account_daily_missing_for_days_inside_range"]:
            suspected_root_causes.append("partial date coverage in account_daily")
        if anomaly_flags["rows_present_but_no_attached_mapping"]:
            suspected_root_causes.append("persisted rows exist for non-attached customer ids")
        if anomaly_flags["mixed_customer_ids_for_same_attached_account"]:
            suspected_root_causes.append("same logical attached account/day appears under multiple customer ids")
        if anomaly_flags["currency_mismatch_with_attached_account_currency"]:
            suspected_root_causes.append("persisted row currency mismatches attached-account effective currency")
        if anomaly_flags["persisted_dates_before_platform_supported_start"]:
            suspected_root_causes.append("rows persisted before supported platform historical floor")
        if anomaly_flags["possible_overcount_if_summing_multiple_grains"]:
            suspected_root_causes.append("summing multiple grains would overcount spend")

        recommended_next_fix_scope = [
            "verify write-path dedupe key per provider grain/account/day",
            "verify sync-run chunk failures and retry gaps for missing account_daily dates",
            "verify mapping/customer-id consistency between attached accounts and persisted customer_id",
        ]

        attached_accounts_payload = []
        for item in attached_accounts:
            aid = str(item.get("id") or "")
            meta = platform_meta_by_id.get(aid, {})
            attached_accounts_payload.append(
                {
                    "account_id": aid,
                    "account_name": item.get("name"),
                    "effective_account_currency": item.get("effective_account_currency") or item.get("currency"),
                    "account_currency_source": item.get("account_currency_source"),
                    "last_sync_at": meta.get("last_success_at") or meta.get("last_synced_at"),
                    "last_error": meta.get("last_error"),
                    "last_error_summary": (str(meta.get("last_error") or "")[:200] or None),
                    "last_error_details": self._sanitize_error_details(meta.get("last_error")),
                }
            )

        sync_runs = self._build_platform_sync_runs_summary(
            client_id=client_id,
            platform=normalized_platform,
            attached_account_ids=attached_account_ids,
        )

        latest_run_by_account: dict[str, dict[str, object]] = {}
        for run in sync_runs:
            account_key = str(run.get("account_id") or "")
            if account_key == "":
                continue
            if account_key not in latest_run_by_account:
                latest_run_by_account[account_key] = run

        if normalized_platform == "meta_ads":
            for account_item in attached_accounts_payload:
                account_key = str(account_item.get("account_id") or "")
                latest = latest_run_by_account.get(account_key)
                if not isinstance(latest, dict):
                    continue
                account_item["sync_health_status"] = latest.get("sync_health_status") or latest.get("coverage_status")
                account_item["coverage_status"] = latest.get("coverage_status") or latest.get("sync_health_status")
                account_item["requested_start_date"] = latest.get("requested_start_date")
                account_item["requested_end_date"] = latest.get("requested_end_date")
                account_item["total_chunk_count"] = latest.get("total_chunk_count")
                account_item["successful_chunk_count"] = latest.get("successful_chunk_count")
                account_item["failed_chunk_count"] = latest.get("failed_chunk_count")
                account_item["retry_attempted"] = latest.get("retry_attempted")
                account_item["retry_recovered_chunk_count"] = latest.get("retry_recovered_chunk_count")
                account_item["rows_written_count"] = latest.get("rows_written_count")
                account_item["first_persisted_date"] = latest.get("first_persisted_date")
                account_item["last_persisted_date"] = latest.get("last_persisted_date")
                account_item["last_error"] = latest.get("last_error") or account_item.get("last_error")
                account_item["last_error_summary"] = latest.get("last_error_summary") or account_item.get("last_error_summary")
                account_item["last_error_details"] = latest.get("last_error_details") or account_item.get("last_error_details")

        per_account_grain_summary = []
        for item in per_account_grain.values():
            per_account_grain_summary.append(
                {
                    "customer_id": item.get("customer_id"),
                    "grain": item.get("grain"),
                    "row_count": item.get("row_count"),
                    "first_date": item.get("first_date"),
                    "last_date": item.get("last_date"),
                    "spend": round(_to_float(item.get("spend")), 4),
                    "report_currencies": sorted(item.get("report_currencies") if isinstance(item.get("report_currencies"), set) else []),
                }
            )
        per_account_grain_summary.sort(key=lambda v: (str(v.get("customer_id") or ""), str(v.get("grain") or "")))

        return {
            "client_platform_context": {
                "client_id": client_id,
                "platform": normalized_platform,
                "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                "filters": {"account_id": filter_account_id, "include_daily_breakdown": bool(include_daily_breakdown)},
                "platform_supported_history_floor": supported_floor.isoformat() if supported_floor is not None else None,
            },
            "attached_accounts": attached_accounts_payload,
            "sync_run_summary": {
                "recent_runs": sync_runs,
                "run_count": len(sync_runs),
            },
            "persisted_rows_summary": {
                "total_rows": len(persisted_rows),
                "row_counts_by_grain": [by_grain[key] for key in sorted(by_grain.keys())],
                "per_account_grain_coverage": per_account_grain_summary,
            },
            "account_daily_totals": account_daily_totals,
            "lower_grain_totals": lower_grain_totals,
            "anomaly_flags": anomaly_flags,
            "anomaly_details": {
                "duplicate_like_rows_on_natural_key": duplicate_like_rows,
                "multiple_account_daily_rows_same_account_same_day": multiple_account_daily,
                "lower_grain_rows_present_without_account_daily": lower_without_account_daily,
                "account_daily_missing_for_days_inside_range": missing_account_daily_days,
                "persisted_dates_before_platform_supported_start": rows_before_floor,
                "currency_mismatch_with_attached_account_currency": currency_mismatches,
                "rows_present_but_no_attached_mapping_count": rows_present_no_mapping,
            },
            "suspected_root_causes": suspected_root_causes,
            "recommended_next_fix_scope": recommended_next_fix_scope,
        }


    def repair_client_tiktok_account_daily(
        self,
        *,
        client_id: int,
        start_date: date,
        end_date: date,
        account_id: str | None = None,
        dry_run: bool = True,
    ) -> dict[str, object]:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")

        attached_accounts_all = client_registry_service.list_client_platform_accounts(platform="tiktok_ads", client_id=int(client_id))
        attached_accounts = [item for item in attached_accounts_all if isinstance(item, dict) and str(item.get("id") or "").strip() != ""]
        if account_id is not None and str(account_id).strip() != "":
            attached_filter = str(account_id).strip()
            attached_accounts = [item for item in attached_accounts if str(item.get("id") or "") == attached_filter]
        attached_account_ids = sorted({str(item.get("id") or "") for item in attached_accounts if str(item.get("id") or "") != ""})

        performance_reports_store.initialize_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._tiktok_account_daily_repair_rows_query(),
                    (
                        start_date,
                        end_date,
                        int(client_id),
                        attached_account_ids,
                    ),
                )
                raw_rows = cur.fetchall() or []

            persisted_rows: list[dict[str, object]] = []
            for row in raw_rows:
                persisted_rows.append(
                    {
                        "row_id": _to_int(row[0]),
                        "customer_id": str(row[1] or "").strip(),
                        "report_date": row[2].isoformat() if isinstance(row[2], date) else str(row[2] or ""),
                        "spend": _to_float(row[3]),
                        "impressions": _to_int(row[4]),
                        "clicks": _to_int(row[5]),
                        "conversions": _to_float(row[6]),
                        "conversion_value": _to_float(row[7]),
                        "client_id": _to_int(row[8]) if row[8] is not None else None,
                        "extra_metrics": row[9] if isinstance(row[9], dict) else {},
                    }
                )

            units: dict[tuple[str, str], list[dict[str, object]]] = {}
            unresolved_units: list[dict[str, object]] = []
            for row in persisted_rows:
                mapped_attached_id = self._resolve_tiktok_repair_attached_account(row=row, attached_account_ids=attached_account_ids)
                if mapped_attached_id is None:
                    unresolved_units.append(
                        {
                            "attached_account_id": None,
                            "report_date": str(row.get("report_date") or ""),
                            "row_ids": [row.get("row_id")],
                            "customer_ids": [str(row.get("customer_id") or "")],
                            "reason": "missing_attached_mapping",
                        }
                    )
                    continue
                key = (mapped_attached_id, str(row.get("report_date") or ""))
                units.setdefault(key, []).append(row)

            safe_units: list[dict[str, object]] = []
            skipped_units: list[dict[str, object]] = list(unresolved_units)
            per_account_summary: dict[str, dict[str, object]] = {}

            attached_id_set = set(attached_account_ids)
            for (attached_id, report_day), rows in sorted(units.items()):
                provider_ids: list[str] = []
                for row in rows:
                    row_provider_ids = self._tiktok_repair_provider_ids_for_row(
                        customer_id=str(row.get("customer_id") or ""),
                        extra_metrics=row.get("extra_metrics") if isinstance(row.get("extra_metrics"), dict) else {},
                    )
                    provider_ids.extend([item for item in row_provider_ids if item in attached_id_set])

                identity = resolve_tiktok_account_daily_persistence_identity(
                    attached_account_id=attached_id,
                    provider_ids_in_scope=provider_ids,
                )
                if identity.is_ambiguous or identity.canonical_persistence_customer_id is None:
                    skipped_units.append(
                        {
                            "attached_account_id": attached_id,
                            "report_date": report_day,
                            "row_ids": [row.get("row_id") for row in rows],
                            "customer_ids": sorted({str(row.get("customer_id") or "") for row in rows}),
                            "reason": "ambiguous_identity",
                        }
                    )
                    continue

                canonical_id = str(identity.canonical_persistence_customer_id)
                signatures = {self._tiktok_repair_metrics_signature(row) for row in rows}
                if len(signatures) > 1:
                    skipped_units.append(
                        {
                            "attached_account_id": attached_id,
                            "report_date": report_day,
                            "row_ids": [row.get("row_id") for row in rows],
                            "customer_ids": sorted({str(row.get("customer_id") or "") for row in rows}),
                            "reason": "conflicting_metrics",
                        }
                    )
                    continue

                canonical_rows = [row for row in rows if str(row.get("customer_id") or "") == canonical_id]
                noncanonical_rows = [row for row in rows if str(row.get("customer_id") or "") != canonical_id]
                rewrite_row_id: int | None = None
                delete_row_ids: list[int] = []

                if len(rows) == 1 and len(noncanonical_rows) == 1:
                    rewrite_row_id = int(noncanonical_rows[0].get("row_id") or 0)
                elif len(rows) > 1:
                    if len(canonical_rows) > 0:
                        canonical_rows_sorted = sorted(canonical_rows, key=lambda item: int(item.get("row_id") or 0))
                        survivor_id = int(canonical_rows_sorted[0].get("row_id") or 0)
                        delete_row_ids = [int(item.get("row_id") or 0) for item in rows if int(item.get("row_id") or 0) != survivor_id]
                    else:
                        sorted_rows = sorted(rows, key=lambda item: int(item.get("row_id") or 0))
                        survivor_id = int(sorted_rows[0].get("row_id") or 0)
                        rewrite_row_id = survivor_id
                        delete_row_ids = [int(item.get("row_id") or 0) for item in sorted_rows[1:]]

                if rewrite_row_id is None and len(delete_row_ids) == 0:
                    account_summary = per_account_summary.setdefault(attached_id, {"safe_candidate_units": 0, "applied_units": 0, "skipped_units": 0, "rewritten_rows": 0, "deleted_rows": 0})
                    account_summary["safe_candidate_units"] = _to_int(account_summary.get("safe_candidate_units")) + 1
                    continue

                unit = {
                    "attached_account_id": attached_id,
                    "report_date": report_day,
                    "canonical_customer_id": canonical_id,
                    "rewrite_row_id": rewrite_row_id,
                    "delete_row_ids": [item for item in delete_row_ids if item > 0],
                    "customer_ids": sorted({str(row.get("customer_id") or "") for row in rows}),
                    "row_ids": [int(row.get("row_id") or 0) for row in rows],
                }
                safe_units.append(unit)
                account_summary = per_account_summary.setdefault(attached_id, {"safe_candidate_units": 0, "applied_units": 0, "skipped_units": 0, "rewritten_rows": 0, "deleted_rows": 0})
                account_summary["safe_candidate_units"] = _to_int(account_summary.get("safe_candidate_units")) + 1

            rewritten_rows = 0
            deleted_rows = 0
            applied_units = 0

            if not dry_run:
                with conn.cursor() as cur:
                    for unit in safe_units:
                        try:
                            cur.execute("SAVEPOINT tiktok_repair_unit")
                            rewrite_row_id = unit.get("rewrite_row_id")
                            if isinstance(rewrite_row_id, int) and rewrite_row_id > 0:
                                cur.execute(
                                    """
                                    UPDATE ad_performance_reports
                                    SET customer_id = %s,
                                        synced_at = NOW()
                                    WHERE id = %s
                                      AND platform = 'tiktok_ads'
                                    """,
                                    (str(unit.get("canonical_customer_id") or ""), int(rewrite_row_id)),
                                )
                                rewritten_rows += 1

                            delete_ids = [int(item) for item in (unit.get("delete_row_ids") or []) if int(item) > 0]
                            if len(delete_ids) > 0:
                                cur.execute(
                                    """
                                    DELETE FROM ad_performance_reports
                                    WHERE id = ANY(%s::int[])
                                      AND platform = 'tiktok_ads'
                                    """,
                                    (delete_ids,),
                                )
                                deleted_rows += len(delete_ids)

                            cur.execute("RELEASE SAVEPOINT tiktok_repair_unit")
                            applied_units += 1
                        except Exception:
                            cur.execute("ROLLBACK TO SAVEPOINT tiktok_repair_unit")
                            skipped_units.append(
                                {
                                    "attached_account_id": unit.get("attached_account_id"),
                                    "report_date": unit.get("report_date"),
                                    "row_ids": unit.get("row_ids") or [],
                                    "customer_ids": unit.get("customer_ids") or [],
                                    "reason": "canonical_target_conflict",
                                }
                            )
                    conn.commit()

            for item in skipped_units:
                attached_id = str(item.get("attached_account_id") or "")
                if attached_id == "":
                    continue
                account_summary = per_account_summary.setdefault(attached_id, {"safe_candidate_units": 0, "applied_units": 0, "skipped_units": 0, "rewritten_rows": 0, "deleted_rows": 0})
                account_summary["skipped_units"] = _to_int(account_summary.get("skipped_units")) + 1

            if not dry_run:
                for unit in safe_units[:applied_units]:
                    attached_id = str(unit.get("attached_account_id") or "")
                    if attached_id == "":
                        continue
                    account_summary = per_account_summary.setdefault(attached_id, {"safe_candidate_units": 0, "applied_units": 0, "skipped_units": 0, "rewritten_rows": 0, "deleted_rows": 0})
                    account_summary["applied_units"] = _to_int(account_summary.get("applied_units")) + 1
                    if isinstance(unit.get("rewrite_row_id"), int) and int(unit.get("rewrite_row_id") or 0) > 0:
                        account_summary["rewritten_rows"] = _to_int(account_summary.get("rewritten_rows")) + 1
                    account_summary["deleted_rows"] = _to_int(account_summary.get("deleted_rows")) + len(unit.get("delete_row_ids") or [])

        skipped_reason_examples: dict[str, int] = {}
        for item in skipped_units:
            reason = str(item.get("reason") or "unknown")
            skipped_reason_examples[reason] = _to_int(skipped_reason_examples.get(reason)) + 1

        return {
            "client_id": int(client_id),
            "platform": "tiktok_ads",
            "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "account_id": str(account_id).strip() if account_id is not None and str(account_id).strip() != "" else None,
            "dry_run": bool(dry_run),
            "total_units_scanned": len(units) + len(unresolved_units),
            "safe_repair_candidate_units": len(safe_units),
            "applied_units": int(applied_units),
            "skipped_units": len(skipped_units),
            "rewritten_rows": int(rewritten_rows),
            "deleted_rows": int(deleted_rows),
            "unresolved_units": skipped_units,
            "per_account_summary": [
                {"account_id": account_id_key, **summary}
                for account_id_key, summary in sorted(per_account_summary.items())
            ],
            "example_skipped_reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(skipped_reason_examples.items())
            ],
            "suspected_remaining_issues_needing_provider_resync": [
                "rows skipped due to conflicting_metrics",
                "rows skipped due to ambiguous_identity",
                "rows skipped due to missing_attached_mapping",
            ],
        }


    def audit_and_repair_client_display_currency_drift(
        self,
        *,
        client_id: int | None = None,
        dry_run: bool = True,
    ) -> dict[str, object]:
        candidate_ids: list[int] = []
        if client_id is not None:
            candidate_ids = [int(client_id)]
        else:
            for item in client_registry_service.list_clients():
                try:
                    candidate_ids.append(int(item.get("id") or 0))
                except Exception:  # noqa: BLE001
                    continue
            candidate_ids = sorted({value for value in candidate_ids if value > 0})

        findings: list[dict[str, object]] = []
        clients_with_drift = 0
        clients_repaired = 0
        configs_repaired = 0
        clients_skipped = 0

        for scoped_client_id in candidate_ids:
            decision = self._client_reporting_currency_decision(client_id=scoped_client_id)
            expected_currency = self._normalize_currency_code(
                decision.get("client_display_currency") or decision.get("reporting_currency"),
                fallback="USD",
            )
            display_currency_source = str(
                decision.get("display_currency_source")
                or decision.get("reporting_currency_source")
                or "safe_fallback"
            )
            if display_currency_source == "safe_fallback":
                clients_skipped += 1
                findings.append(
                    {
                        "client_id": scoped_client_id,
                        "status": "skipped",
                        "reason": "ambiguous_expected_currency",
                        "expected_display_currency": expected_currency,
                        "display_currency_source": display_currency_source,
                        "changes": [],
                    }
                )
                continue

            config_rows: list[tuple[object, object]] = []
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, display_currency
                        FROM media_buying_configs
                        WHERE client_id = %s
                        ORDER BY id
                        """,
                        (scoped_client_id,),
                    )
                    config_rows = list(cur.fetchall() or [])

                    change_rows: list[dict[str, object]] = []
                    for row in config_rows:
                        config_id = _to_int(row[0])
                        stored_currency = self._normalize_currency_code(row[1], fallback="USD")
                        if stored_currency == expected_currency:
                            continue

                        change_rows.append(
                            {
                                "field": "media_buying_configs.display_currency",
                                "config_id": config_id,
                                "before": stored_currency,
                                "after": expected_currency,
                                "action": "repair" if not dry_run else "candidate",
                            }
                        )
                        if not dry_run:
                            cur.execute(
                                """
                                UPDATE media_buying_configs
                                SET display_currency = %s,
                                    updated_at = NOW()
                                WHERE id = %s
                                """,
                                (expected_currency, config_id),
                            )

                if not dry_run:
                    conn.commit()

            if len(change_rows) > 0:
                clients_with_drift += 1
                if not dry_run:
                    clients_repaired += 1
                    configs_repaired += len(change_rows)
                findings.append(
                    {
                        "client_id": scoped_client_id,
                        "status": "drift_detected" if dry_run else "repaired",
                        "expected_display_currency": expected_currency,
                        "display_currency_source": display_currency_source,
                        "changes": change_rows,
                    }
                )
            else:
                findings.append(
                    {
                        "client_id": scoped_client_id,
                        "status": "aligned",
                        "expected_display_currency": expected_currency,
                        "display_currency_source": display_currency_source,
                        "changes": [],
                    }
                )

        return {
            "client_id": int(client_id) if client_id is not None else None,
            "dry_run": bool(dry_run),
            "total_clients_scanned": len(candidate_ids),
            "clients_with_drift": clients_with_drift,
            "clients_repaired": clients_repaired,
            "configs_repaired": configs_repaired,
            "clients_skipped": clients_skipped,
            "findings": findings,
            "notes": [
                "attached-account currency metadata is read-only and never mutated by this repair",
            ],
        }


    def get_client_dashboard_reconciliation(
        self,
        *,
        client_id: int,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        performance_reports_store.initialize_schema()
        currency_decision = self._client_reporting_currency_decision(client_id=client_id)
        reporting_currency = str(currency_decision.get("reporting_currency") or "USD")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(self._client_mappings_query(), (client_id,))
                mapping_rows = cur.fetchall()
                cur.execute(self._client_dashboard_reconciliation_rows_query(), (client_id, start_date, end_date))
                report_rows = cur.fetchall()

        mappings = [
            {
                "platform": str(row[0] or ""),
                "account_id": str(row[1] or ""),
                "client_id": _to_int(row[2]),
                "account_currency": self._normalize_currency_code(row[3], fallback="USD"),
                "created_at": str(row[4]) if row[4] is not None else None,
            }
            for row in mapping_rows
        ]

        raw_totals_by_group: dict[tuple[str, str, str | None], dict[str, object]] = {}
        included_totals_by_group: dict[tuple[str, str, str], dict[str, object]] = {}

        raw_before = self._empty_metric_totals()
        included_before = self._empty_metric_totals()
        included_after = self._empty_metric_totals()

        per_platform: dict[str, dict[str, object]] = {}
        per_account: dict[str, dict[str, object]] = {}

        excluded_rows: list[dict[str, object]] = []
        currency_fallback_rows: list[dict[str, object]] = []
        included_count = 0
        excluded_count = 0

        for row in report_rows:
            platform = str(row[0] or "")
            customer_id = str(row[1] or "")
            report_date = row[2] if isinstance(row[2], date) else end_date
            spend = _to_float(row[3])
            impressions = _to_int(row[4])
            clicks = _to_int(row[5])
            conversions = _to_float(row[6])
            revenue = _to_float(row[7])
            grain_resolved = str(row[9] or "account_daily")
            report_currency = self._normalize_currency_code(row[10], fallback="USD") if row[10] else None
            resolved_currency = self._normalize_currency_code(row[13], fallback="USD")
            currency_source = str(row[14] or "fallback_usd")
            has_mapping = bool(row[15])

            raw_key = (platform, customer_id, report_currency)
            raw_entry = raw_totals_by_group.setdefault(
                raw_key,
                {
                    "platform": platform,
                    "account_id": customer_id,
                    "report_currency": report_currency,
                    "totals": self._empty_metric_totals(),
                },
            )
            self._add_to_metric_totals(raw_entry["totals"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
            self._add_to_metric_totals(raw_before, spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)

            is_included = has_mapping and grain_resolved == "account_daily"
            reasons: list[str] = []
            if not has_mapping:
                reasons.append("missing_mapping")
            if grain_resolved != "account_daily":
                reasons.append("grain_not_account_daily")
            if currency_source == "fallback_usd":
                reasons.append("currency_resolution_fallback")

            normalized_spend = self._normalize_money(
                amount=spend,
                from_currency=resolved_currency,
                to_currency=reporting_currency,
                rate_date=report_date,
            )
            normalized_revenue = self._normalize_money(
                amount=revenue,
                from_currency=resolved_currency,
                to_currency=reporting_currency,
                rate_date=report_date,
            )

            platform_bucket = per_platform.setdefault(
                platform,
                {
                    "platform": platform,
                    "included_rows": 0,
                    "excluded_rows": 0,
                    "raw_before_conversion": self._empty_metric_totals(),
                    "included_before_conversion": self._empty_metric_totals(),
                    "included_after_conversion": self._empty_metric_totals(),
                },
            )
            account_key = f"{platform}:{customer_id}"
            account_bucket = per_account.setdefault(
                account_key,
                {
                    "platform": platform,
                    "account_id": customer_id,
                    "included_rows": 0,
                    "excluded_rows": 0,
                    "raw_before_conversion": self._empty_metric_totals(),
                    "included_before_conversion": self._empty_metric_totals(),
                    "included_after_conversion": self._empty_metric_totals(),
                },
            )
            self._add_to_metric_totals(platform_bucket["raw_before_conversion"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
            self._add_to_metric_totals(account_bucket["raw_before_conversion"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)

            if currency_source == "fallback_usd":
                currency_fallback_rows.append(
                    {
                        "platform": platform,
                        "account_id": customer_id,
                        "report_date": report_date.isoformat(),
                        "resolved_currency": resolved_currency,
                    }
                )

            if is_included:
                included_count += 1
                platform_bucket["included_rows"] = _to_int(platform_bucket.get("included_rows")) + 1
                account_bucket["included_rows"] = _to_int(account_bucket.get("included_rows")) + 1
                self._add_to_metric_totals(included_before, spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
                self._add_to_metric_totals(included_after, spend=normalized_spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=normalized_revenue)
                self._add_to_metric_totals(platform_bucket["included_before_conversion"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
                self._add_to_metric_totals(account_bucket["included_before_conversion"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
                self._add_to_metric_totals(platform_bucket["included_after_conversion"], spend=normalized_spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=normalized_revenue)
                self._add_to_metric_totals(account_bucket["included_after_conversion"], spend=normalized_spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=normalized_revenue)

                included_key = (platform, customer_id, resolved_currency)
                included_entry = included_totals_by_group.setdefault(
                    included_key,
                    {
                        "platform": platform,
                        "account_id": customer_id,
                        "resolved_currency": resolved_currency,
                        "totals_before_conversion": self._empty_metric_totals(),
                        "totals_after_conversion": self._empty_metric_totals(),
                    },
                )
                self._add_to_metric_totals(included_entry["totals_before_conversion"], spend=spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=revenue)
                self._add_to_metric_totals(included_entry["totals_after_conversion"], spend=normalized_spend, impressions=impressions, clicks=clicks, conversions=conversions, revenue=normalized_revenue)
            else:
                excluded_count += 1
                platform_bucket["excluded_rows"] = _to_int(platform_bucket.get("excluded_rows")) + 1
                account_bucket["excluded_rows"] = _to_int(account_bucket.get("excluded_rows")) + 1
                excluded_rows.append(
                    {
                        "platform": platform,
                        "account_id": customer_id,
                        "report_date": report_date.isoformat(),
                        "grain": grain_resolved,
                        "resolved_currency": resolved_currency,
                        "currency_source": currency_source,
                        "reasons": reasons,
                        "metrics": {
                            "spend": spend,
                            "impressions": impressions,
                            "clicks": clicks,
                            "conversions": conversions,
                            "revenue": revenue,
                        },
                    }
                )

        return {
            "client_id": client_id,
            "date_range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
            "reporting_currency": reporting_currency,
            "reporting_currency_source": str(currency_decision.get("reporting_currency_source") or "safe_fallback"),
            "mixed_attached_account_currencies": bool(currency_decision.get("mixed_attached_account_currencies")),
            "attached_account_currency_summary": currency_decision.get("attached_account_currency_summary") if isinstance(currency_decision.get("attached_account_currency_summary"), list) else [],
            "attached_account_mappings": mappings,
            "counts": {
                "total_rows_scanned": len(report_rows),
                "included_rows": included_count,
                "excluded_rows": excluded_count,
                "currency_fallback_rows": len(currency_fallback_rows),
            },
            "raw_db_totals_by_platform_account_currency": list(raw_totals_by_group.values()),
            "included_dashboard_totals_by_platform_account_currency": list(included_totals_by_group.values()),
            "excluded_rows": excluded_rows,
            "currency_resolution_fallback_rows": currency_fallback_rows,
            "summed_metrics": {
                "before_conversion": {
                    "raw_db": raw_before,
                    "included_dashboard": included_before,
                },
                "after_conversion": {
                    "included_dashboard": included_after,
                },
            },
            "per_platform_summary": list(per_platform.values()),
            "per_account_summary": list(per_account.values()),
        }


    def _coerce_extra_metrics(self, value: object) -> dict[str, object]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:  # noqa: BLE001
                return {}
        return {}

    def _merge_extra_metrics(self, base: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
        merged = dict(base)
        for key, incoming_value in incoming.items():
            base_value = merged.get(key)
            if isinstance(base_value, dict) and isinstance(incoming_value, dict):
                merged[key] = self._merge_extra_metrics(base_value, incoming_value)
            elif isinstance(base_value, (int, float, Decimal)) and isinstance(incoming_value, (int, float, Decimal)):
                merged[key] = float(base_value) + float(incoming_value)
            elif key not in merged:
                merged[key] = incoming_value
            else:
                merged[key] = incoming_value
        return merged


    def _business_inputs_totals(self, rows: list[dict[str, object]]) -> dict[str, float | int]:
        totals: dict[str, float | int] = {
            "applicants": 0,
            "approved_applicants": 0,
            "actual_revenue": 0.0,
            "target_revenue": 0.0,
            "cogs": 0.0,
            "taxes": 0.0,
            "gross_profit": 0.0,
            "contribution_profit": 0.0,
            "sales_count": 0,
            "new_customers": 0,
        }
        for row in rows:
            applicants = row.get("applicants")
            approved_applicants = row.get("approved_applicants")
            actual_revenue = row.get("actual_revenue")
            target_revenue = row.get("target_revenue")
            cogs = row.get("cogs")
            taxes = row.get("taxes")
            gross_profit = row.get("gross_profit")
            contribution_profit = row.get("contribution_profit")
            sales_count = row.get("sales_count")
            new_customers = row.get("new_customers")

            if isinstance(applicants, (int, float, Decimal)):
                totals["applicants"] = int(totals["applicants"]) + int(applicants)
            if isinstance(approved_applicants, (int, float, Decimal)):
                totals["approved_applicants"] = int(totals["approved_applicants"]) + int(approved_applicants)
            if isinstance(actual_revenue, (int, float, Decimal)):
                totals["actual_revenue"] = float(totals["actual_revenue"]) + float(actual_revenue)
            if isinstance(target_revenue, (int, float, Decimal)):
                totals["target_revenue"] = float(totals["target_revenue"]) + float(target_revenue)
            if isinstance(cogs, (int, float, Decimal)):
                totals["cogs"] = float(totals["cogs"]) + float(cogs)
            if isinstance(taxes, (int, float, Decimal)):
                totals["taxes"] = float(totals["taxes"]) + float(taxes)
            if isinstance(gross_profit, (int, float, Decimal)):
                totals["gross_profit"] = float(totals["gross_profit"]) + float(gross_profit)
            if isinstance(contribution_profit, (int, float, Decimal)):
                totals["contribution_profit"] = float(totals["contribution_profit"]) + float(contribution_profit)
            if isinstance(sales_count, (int, float, Decimal)):
                totals["sales_count"] = int(totals["sales_count"]) + int(sales_count)
            if isinstance(new_customers, (int, float, Decimal)):
                totals["new_customers"] = int(totals["new_customers"]) + int(new_customers)

        return totals

    def _build_business_inputs_payload(self, *, client_id: int, period_grain: str, start_date: date, end_date: date) -> dict[str, object]:
        resolved_grain = "week" if str(period_grain).strip().lower() == "week" else "day"
        try:
            rows = client_business_inputs_store.list_client_business_inputs(
                client_id=client_id,
                period_grain=resolved_grain,
                date_from=start_date,
                date_to=end_date,
            )
        except Exception:  # noqa: BLE001
            rows = []
        return {
            "period_grain": resolved_grain,
            "rows": rows,
            "totals": self._business_inputs_totals(rows),
        }


    def _client_reporting_currency_decision(self, *, client_id: int) -> dict[str, object]:
        decision = client_registry_service.get_client_reporting_currency_decision(client_id=client_id)
        normalized_display_currency = self._normalize_currency_code(
            decision.get("client_display_currency") or decision.get("display_currency") or decision.get("reporting_currency"),
            fallback="USD",
        )
        display_currency_source = str(
            decision.get("display_currency_source")
            or decision.get("reporting_currency_source")
            or "safe_fallback"
        )
        reporting_currency = self._normalize_currency_code(
            decision.get("reporting_currency") or normalized_display_currency,
            fallback="USD",
        )
        return {
            "reporting_currency": reporting_currency,
            "reporting_currency_source": str(decision.get("reporting_currency_source") or display_currency_source),
            "client_display_currency": normalized_display_currency,
            "display_currency_source": display_currency_source,
            "mixed_attached_account_currencies": bool(decision.get("mixed_attached_account_currencies")),
            "attached_account_currency_summary": decision.get("attached_account_currency_summary") if isinstance(decision.get("attached_account_currency_summary"), list) else [],
        }

    def _build_business_derived_metrics_payload(self, *, total_spend: float, business_inputs_totals: dict[str, object]) -> dict[str, float | None]:
        return build_business_derived_metrics(
            total_spend=total_spend,
            actual_revenue=business_inputs_totals.get("actual_revenue"),
            target_revenue=business_inputs_totals.get("target_revenue"),
            applicants=business_inputs_totals.get("applicants"),
            approved_applicants=business_inputs_totals.get("approved_applicants"),
            cogs=business_inputs_totals.get("cogs"),
            taxes=business_inputs_totals.get("taxes"),
            gross_profit=business_inputs_totals.get("gross_profit"),
            contribution_profit=business_inputs_totals.get("contribution_profit"),
            sales_count=business_inputs_totals.get("sales_count"),
            new_customers=business_inputs_totals.get("new_customers"),
        )

    def get_client_dashboard(self, client_id: int, *, start_date: date | None = None, end_date: date | None = None, business_period_grain: str = "day") -> dict[str, object]:
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

            currency_decision = self._client_reporting_currency_decision(client_id=client_id)
            reporting_currency = str(currency_decision.get("reporting_currency") or "USD")
            platform_totals = self._aggregate_client_rows(rows=rows, target_currency=reporting_currency)

            def platform_metrics(name: str) -> dict[str, object]:
                return self._normalize_platform_metrics(name, {"client_id": client_id, **platform_totals.get(name, {})}, client_id)

            google_metrics = platform_metrics("google_ads")
            meta_metrics = platform_metrics("meta_ads")
            tiktok_metrics = platform_metrics("tiktok_ads")
            pinterest_metrics = platform_metrics("pinterest_ads")
            snapchat_metrics = platform_metrics("snapchat_ads")
        else:
            currency_decision = self._client_reporting_currency_decision(client_id=client_id)
            reporting_currency = str(currency_decision.get("reporting_currency") or "USD")
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

        business_inputs_payload = self._build_business_inputs_payload(
            client_id=client_id,
            period_grain=business_period_grain,
            start_date=resolved_start,
            end_date=resolved_end,
        )
        business_derived_metrics = self._build_business_derived_metrics_payload(
            total_spend=total_spend,
            business_inputs_totals=business_inputs_payload.get("totals") if isinstance(business_inputs_payload.get("totals"), dict) else {},
        )

        return {
            "client_id": client_id,
            "currency": reporting_currency,
            "reporting_currency": reporting_currency,
            "reporting_currency_source": str(currency_decision.get("reporting_currency_source") or "safe_fallback"),
            "mixed_attached_account_currencies": bool(currency_decision.get("mixed_attached_account_currencies")),
            "attached_account_currency_summary": currency_decision.get("attached_account_currency_summary") if isinstance(currency_decision.get("attached_account_currency_summary"), list) else [],
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
            "platform_sync_summary": self._build_dashboard_platform_sync_summary(client_id=client_id),
            "is_synced": bool(
                google_metrics.get("is_synced")
                or meta_metrics.get("is_synced")
                or tiktok_metrics.get("is_synced")
                or pinterest_metrics.get("is_synced")
                or snapchat_metrics.get("is_synced")
            ),
            "business_inputs": business_inputs_payload,
            "business_derived_metrics": business_derived_metrics,
        }

    def _agency_reports_query(self) -> str:
        return """
                    WITH perf AS (
                        SELECT
                            apr.report_date,
                            COALESCE(apr.client_id, mapped.client_id) AS resolved_client_id,
                            COALESCE(
                                    NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') ELSE '' END), ''),
                                    NULLIF(TRIM(mapped.account_currency), ''),
                                    NULLIF(TRIM(client.currency), ''),
                                    'RON'
                                ) AS account_currency,
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

    def _format_google_integration_details(self, payload: dict[str, object]) -> str | None:
        parts: list[str] = []
        accounts = payload.get("accounts_found")
        if isinstance(accounts, (int, float)):
            parts.append(f"accounts={int(accounts)}")
        rows = payload.get("rows_in_db_last_30_days")
        if isinstance(rows, (int, float)):
            parts.append(f"rows30={int(rows)}")
        message = str(payload.get("message") or "").strip()
        if message:
            parts.append(message)
        if not parts:
            return None
        return " · ".join(parts)

    def _build_integration_health(self) -> list[dict[str, object | None]]:
        items: list[dict[str, object | None]] = []

        try:
            google_payload = google_ads_service.integration_status()
        except Exception:
            google_payload = {"status": "error", "last_error": "google_ads status unavailable"}

        google_status = str(google_payload.get("status") or "disabled").strip() or "disabled"
        items.append(
            {
                "platform": "google_ads",
                "label": "Google Ads",
                "status": google_status,
                "details": self._format_google_integration_details(google_payload),
                "last_sync_at": google_payload.get("last_sync_at"),
                "last_error": google_payload.get("last_error") if google_status.lower() == "error" else None,
            }
        )

        try:
            meta_payload = meta_ads_service.integration_status()
        except Exception:
            meta_payload = {"status": "error", "message": "meta_ads status unavailable"}

        meta_status = str(meta_payload.get("status") or "disabled").strip() or "disabled"
        meta_message = str(meta_payload.get("message") or "").strip() or None
        items.append(
            {
                "platform": "meta_ads",
                "label": "Meta Ads",
                "status": meta_status,
                "details": meta_message,
                "last_sync_at": meta_payload.get("token_updated_at"),
                "last_error": meta_message if meta_status.lower() == "error" else None,
            }
        )

        try:
            tiktok_payload = tiktok_ads_service.integration_status()
        except Exception:
            tiktok_payload = {"status": "error", "message": "tiktok_ads status unavailable"}

        tiktok_status = str(tiktok_payload.get("status") or "disabled").strip() or "disabled"
        tiktok_message = str(tiktok_payload.get("message") or "").strip() or None
        items.append(
            {
                "platform": "tiktok_ads",
                "label": "TikTok Ads",
                "status": tiktok_status,
                "details": tiktok_message,
                "last_sync_at": tiktok_payload.get("token_updated_at"),
                "last_error": tiktok_message if tiktok_status.lower() == "error" else None,
            }
        )

        for platform, label in (("pinterest_ads", "Pinterest Ads"), ("snapchat_ads", "Snapchat Ads")):
            items.append(
                {
                    "platform": platform,
                    "label": label,
                    "status": "disabled",
                    "details": None,
                    "last_sync_at": None,
                    "last_error": None,
                }
            )

        return items

    def get_agency_dashboard(self, *, start_date: date, end_date: date) -> dict[str, object]:
        if self._is_test_mode():
            clients = client_registry_service.list_clients()
            totals = {"spend": 0.0, "impressions": 0, "clicks": 0, "conversions": 0, "revenue": 0.0}
            top_clients: list[dict[str, object]] = []
            for client in clients:
                cid = int(client["id"])
                metrics = self.get_client_dashboard(cid)
                mt = metrics["totals"]
                source_currency = self._normalize_currency_code(metrics.get("currency"), fallback="USD")
                spend_ron = self._normalize_money(amount=_to_float(mt.get("spend")), from_currency=source_currency, to_currency="RON", rate_date=end_date)
                revenue_ron = self._normalize_money(amount=_to_float(mt.get("revenue")), from_currency=source_currency, to_currency="RON", rate_date=end_date)
                totals["spend"] += spend_ron
                totals["impressions"] += _to_int(mt.get("impressions"))
                totals["clicks"] += _to_int(mt.get("clicks"))
                totals["conversions"] += _to_int(mt.get("conversions"))
                totals["revenue"] += revenue_ron
                top_clients.append({"client_id": cid, "name": str(client.get("name") or f"Client {cid}"), "spend": round(spend_ron, 2), "currency": "RON", "spend_ron": round(spend_ron, 2)})

            top_clients.sort(key=lambda item: float(item["spend_ron"]), reverse=True)
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
                "integration_health": self._build_integration_health(),
            }

        performance_reports_store.initialize_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(self._agency_reports_query(), (start_date, end_date))
                rows = cur.fetchall()

        totals, spend_by_client_ron, _spend_by_client_native, _client_currency, row_count = self._aggregate_agency_rows(rows)

        manual_clients = client_registry_service.list_clients()
        active_clients = len(manual_clients)
        client_names = {int(item["id"]): str(item.get("name") or f"Client {item['id']}") for item in manual_clients}

        top_clients: list[dict[str, object]] = []
        for client_id, spend_ron in sorted(spend_by_client_ron.items(), key=lambda item: item[1], reverse=True):
            if client_id not in client_names:
                continue
            top_clients.append(
                {
                    "client_id": client_id,
                    "name": client_names[client_id],
                    "spend": round(spend_ron, 2),
                    "currency": "RON",
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
            "integration_health": self._build_integration_health(),
        }


unified_dashboard_service = UnifiedDashboardService()
