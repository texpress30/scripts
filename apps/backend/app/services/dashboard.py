from __future__ import annotations

from datetime import date, timedelta
import json
from decimal import Decimal
import logging

import requests

from app.core.config import load_settings
from app.services.client_registry import client_registry_service
from app.services.business_metric_formulas import build_business_derived_metrics
from app.services.client_business_inputs_store import client_business_inputs_store
from app.services.report_metric_formulas import build_derived_metrics
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

    def _normalize_money(self, *, amount: float, from_currency: object, to_currency: object, rate_date: date) -> float:
        source = self._normalize_currency_code(from_currency, fallback="RON")
        target = self._normalize_currency_code(to_currency, fallback="RON")
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

    def _client_reports_query(self) -> str:
        return """
                        SELECT
                            apr.platform,
                            apr.report_date,
                            COALESCE(
                                NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), ''),
                                NULLIF(TRIM(apa.currency_code), ''),
                                NULLIF(TRIM(mapped.account_currency), ''),
                                'RON'
                            ) AS account_currency,
                            COALESCE(apr.spend, 0),
                            COALESCE(apr.impressions, 0),
                            COALESCE(apr.clicks, 0),
                            COALESCE(apr.conversions, 0),
                            COALESCE(apr.conversion_value, 0),
                            COALESCE(apr.extra_metrics, '{}'::jsonb) AS extra_metrics
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
                        WHERE apr.report_date BETWEEN %s AND %s
                          AND apr.platform IN ('google_ads', 'meta_ads', 'tiktok_ads', 'pinterest_ads', 'snapchat_ads')
                          AND COALESCE(
                              NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                              'account_daily'
                          ) = 'account_daily'
                        """

    def _client_dashboard_reconciliation_rows_query(self) -> str:
        return """
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
                                NULLIF(TRIM(apa.currency_code), ''),
                                NULLIF(TRIM(mapped.account_currency), ''),
                                'RON'
                            ) AS resolved_currency,
                            CASE
                                WHEN NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), '') IS NOT NULL THEN 'report_extra_metrics'
                                WHEN NULLIF(TRIM(apa.currency_code), '') IS NOT NULL THEN 'agency_platform_account'
                                WHEN NULLIF(TRIM(mapped.account_currency), '') IS NOT NULL THEN 'mapping_account_currency'
                                ELSE 'fallback_ron'
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

    def get_client_dashboard_reconciliation(
        self,
        *,
        client_id: int,
        start_date: date,
        end_date: date,
    ) -> dict[str, object]:
        performance_reports_store.initialize_schema()
        preferred_currency = client_registry_service.get_preferred_currency_for_client(client_id=client_id)

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
                "account_currency": self._normalize_currency_code(row[3], fallback="RON"),
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
            report_currency = self._normalize_currency_code(row[10], fallback="RON") if row[10] else None
            resolved_currency = self._normalize_currency_code(row[13], fallback="RON")
            currency_source = str(row[14] or "fallback_ron")
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
            if currency_source == "fallback_ron":
                reasons.append("currency_resolution_fallback")

            normalized_spend = self._normalize_money(
                amount=spend,
                from_currency=resolved_currency,
                to_currency=preferred_currency,
                rate_date=report_date,
            )
            normalized_revenue = self._normalize_money(
                amount=revenue,
                from_currency=resolved_currency,
                to_currency=preferred_currency,
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

            if currency_source == "fallback_ron":
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
            "reporting_currency": preferred_currency,
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

            preferred_currency = client_registry_service.get_preferred_currency_for_client(client_id=client_id)
            platform_totals = self._aggregate_client_rows(rows=rows, target_currency=preferred_currency)

            def platform_metrics(name: str) -> dict[str, object]:
                return self._normalize_platform_metrics(name, {"client_id": client_id, **platform_totals.get(name, {})}, client_id)

            google_metrics = platform_metrics("google_ads")
            meta_metrics = platform_metrics("meta_ads")
            tiktok_metrics = platform_metrics("tiktok_ads")
            pinterest_metrics = platform_metrics("pinterest_ads")
            snapchat_metrics = platform_metrics("snapchat_ads")
        else:
            preferred_currency = client_registry_service.get_preferred_currency_for_client(client_id=client_id)
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
                source_currency = self._normalize_currency_code(metrics.get("currency"), fallback="RON")
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
