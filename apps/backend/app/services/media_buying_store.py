from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import logging
from threading import Lock
import time

from app.core.config import load_settings
from app.services.dashboard import unified_dashboard_service
from app.services.client_registry import client_registry_service

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


_TEMPLATE_TYPES = {"lead", "ecommerce", "programmatic"}
_DEFAULT_LABELS = {
    "custom_label_1": "Custom Value 1",
    "custom_label_2": "Custom Value 2",
    "custom_label_3": "Custom Value 3",
    "custom_label_4": "Custom Value 4",
    "custom_label_5": "Custom Value 5",
    "custom_rate_label_1": "Custom Value Rate 1",
    "custom_rate_label_2": "Custom Value Rate 2",
    "custom_cost_label_1": "Cost Custom Value 1",
    "custom_cost_label_2": "Cost Custom Value 2",
}

_DEFAULT_VISIBLE_COLUMNS = [
    "date",
    "cost_google",
    "cost_meta",
    "cost_tiktok",
    "cost_total",
    "percent_change",
    "leads",
    "phones",
    "total_leads",
    "custom_value_1_count",
    "custom_value_2_count",
    "custom_value_3_amount_ron",
    "custom_value_4_amount_ron",
    "custom_value_5_amount_ron",
    "sales_count",
    "custom_value_rate_1",
    "custom_value_rate_2",
    "cost_per_lead",
    "cost_custom_value_1",
    "cost_custom_value_2",
    "cost_per_sale",
]


logger = logging.getLogger(__name__)


class MediaBuyingStore:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for media buying persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._schema_initialized:
            return

        with self._schema_lock:
            if self._schema_initialized:
                return

            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT to_regclass('public.media_buying_configs')")
                    config_row = cur.fetchone() or (None,)
                    cur.execute("SELECT to_regclass('public.media_buying_lead_daily_manual_values')")
                    manual_row = cur.fetchone() or (None,)
                    if config_row[0] is None or manual_row[0] is None:
                        raise RuntimeError("Database schema for media buying is not ready; run DB migrations")

            self._schema_initialized = True

    def _normalize_template_type(self, value: str | None) -> str:
        normalized = str(value or "lead").strip().lower()
        if normalized not in _TEMPLATE_TYPES:
            raise ValueError("template_type must be one of: lead, ecommerce, programmatic")
        return normalized

    def _normalize_currency(self, value: str | None) -> str:
        normalized = str(value or "USD").strip().upper()
        if len(normalized) != 3:
            raise ValueError("display_currency must be a 3-letter ISO currency code")
        return normalized

    def _normalize_label(self, value: str | None, *, fallback: str) -> str:
        normalized = str(value or fallback).strip()
        if not normalized:
            return fallback
        return normalized[:120]

    def _normalize_visible_columns(self, value: object, *, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return list(fallback)
        allowed = set(_DEFAULT_VISIBLE_COLUMNS)
        normalized: list[str] = []
        for item in value:
            key = str(item or "").strip()
            if key in allowed and key not in normalized:
                normalized.append(key)
        return normalized or list(fallback)

    def _parse_non_negative_int(self, value: object, *, field_name: str) -> int:
        if value is None:
            return 0
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer >= 0")
        if not isinstance(value, int):
            raise ValueError(f"{field_name} must be an integer >= 0")
        if value < 0:
            raise ValueError(f"{field_name} must be an integer >= 0")
        return int(value)

    def _parse_amount(self, value: object, *, field_name: str, allow_negative: bool = False) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            parsed = Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"{field_name} must be a valid number") from exc
        if not allow_negative and parsed < 0:
            raise ValueError(f"{field_name} must be >= 0")
        return parsed.quantize(Decimal("0.01"))

    def _config_from_row(self, row: tuple[object, ...] | None) -> dict[str, object] | None:
        if row is None:
            return None
        return {
            "client_id": int(row[0]),
            "template_type": str(row[1]),
            "display_currency": str(row[2]),
            "custom_label_1": str(row[3]),
            "custom_label_2": str(row[4]),
            "custom_label_3": str(row[5]),
            "custom_label_4": str(row[6]),
            "custom_label_5": str(row[7]),
            "custom_rate_label_1": str(row[8]),
            "custom_rate_label_2": str(row[9]),
            "custom_cost_label_1": str(row[10]),
            "custom_cost_label_2": str(row[11]),
            "visible_columns": self._normalize_visible_columns(row[12], fallback=_DEFAULT_VISIBLE_COLUMNS),
            "enabled": bool(row[13]),
            "created_at": str(row[14]) if row[14] is not None else None,
            "updated_at": str(row[15]) if row[15] is not None else None,
        }

    def _daily_from_row(self, row: tuple[object, ...]) -> dict[str, object]:
        return {
            "client_id": int(row[0]),
            "date": str(row[1]),
            "leads": int(row[2]),
            "phones": int(row[3]),
            "custom_value_1_count": int(row[4]),
            "custom_value_2_count": int(row[5]),
            "custom_value_3_amount_ron": float(row[6]),
            "custom_value_4_amount_ron": float(row[7]),
            "custom_value_5_amount_ron": float(row[8]),
            "sales_count": int(row[9]),
            "created_at": str(row[10]) if row[10] is not None else None,
            "updated_at": str(row[11]) if row[11] is not None else None,
            # TODO(media-buying): `%^` column formula intentionally not implemented in foundation task.
        }

    def _safe_div(self, numerator: float, denominator: float) -> float | None:
        if denominator == 0:
            return None
        return numerator / denominator

    def _month_key(self, value: date) -> str:
        return f"{value.year:04d}-{value.month:02d}"

    def _normalize_money_to_display_currency(self, *, amount: float, from_currency: str, display_currency: str, rate_date: date) -> float:
        return float(
            unified_dashboard_service._normalize_money(
                amount=float(amount),
                from_currency=from_currency,
                to_currency=display_currency,
                rate_date=rate_date,
            )
        )

    def _list_automated_daily_costs(
        self,
        *,
        client_id: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH scoped_mapped AS (
                        SELECT
                            mapped.platform,
                            mapped.account_id,
                            NULLIF(regexp_replace(mapped.account_id, '[^0-9]', '', 'g'), '') AS account_id_digits,
                            mapped.account_currency
                        FROM agency_account_client_mappings mapped
                        WHERE mapped.client_id = %s
                          AND mapped.platform IN ('google_ads', 'meta_ads', 'tiktok_ads')
                    ),
                    scoped_accounts AS (
                        SELECT
                            apa.platform,
                            apa.account_id,
                            NULLIF(regexp_replace(apa.account_id, '[^0-9]', '', 'g'), '') AS account_id_digits,
                            apa.currency_code
                        FROM agency_platform_accounts apa
                        WHERE apa.platform IN ('google_ads', 'meta_ads', 'tiktok_ads')
                    ),
                    perf AS (
                        SELECT
                            apr.platform,
                            apr.report_date,
                            COALESCE(
                                NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'account_currency', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'account_currency', '') ELSE '' END), ''),
                                NULLIF(TRIM(apa.currency_code), ''),
                                NULLIF(TRIM(mapped.account_currency), ''),
                                'USD'
                            ) AS account_currency,
                            COALESCE(apr.spend, 0) AS spend
                        FROM ad_performance_reports apr
                        JOIN scoped_mapped mapped
                          ON mapped.platform = apr.platform
                         AND (
                              mapped.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND mapped.account_id_digits IS NOT NULL
                                  AND mapped.account_id_digits = NULLIF(regexp_replace(apr.customer_id, '[^0-9]', '', 'g'), '')
                              )
                         )
                        LEFT JOIN scoped_accounts apa
                          ON apa.platform = apr.platform
                         AND (
                              apa.account_id = apr.customer_id
                              OR (
                                  apr.platform = 'google_ads'
                                  AND apa.account_id_digits IS NOT NULL
                                  AND apa.account_id_digits = NULLIF(regexp_replace(apr.customer_id, '[^0-9]', '', 'g'), '')
                              )
                         )
                        WHERE COALESCE(
                            NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                            'account_daily'
                        ) = 'account_daily'
                          AND (%s::date IS NULL OR apr.report_date >= %s::date)
                          AND (%s::date IS NULL OR apr.report_date <= %s::date)
                    )
                    SELECT report_date, platform, account_currency, SUM(spend)
                    FROM perf
                    GROUP BY report_date, platform, account_currency
                    ORDER BY report_date ASC
                    """,
                    (int(client_id), date_from, date_from, date_to, date_to),
                )
                rows = cur.fetchall() or []

        payload: list[dict[str, object]] = []
        for row in rows:
            report_date = row[0] if isinstance(row[0], date) else date.today()
            payload.append(
                {
                    "date": report_date,
                    "platform": str(row[1]),
                    "account_currency": str(row[2] or "USD").upper(),
                    "spend": float(row[3] or 0.0),
                }
            )
        return payload

    def _manual_row_has_data(self, row: dict[str, object]) -> bool:
        fields = [
            "leads",
            "phones",
            "custom_value_1_count",
            "custom_value_2_count",
            "custom_value_3_amount_ron",
            "custom_value_4_amount_ron",
            "custom_value_5_amount_ron",
            "sales_count",
        ]
        for field in fields:
            value = row.get(field)
            if isinstance(value, (int, float, Decimal)) and float(value) != 0.0:
                return True
        return False

    def _build_percent_change(self, *, current_total: float | None, previous_total: float | None) -> float | None:
        if current_total is None or previous_total is None:
            return None
        if float(previous_total) == 0.0:
            return None
        return (float(current_total) - float(previous_total)) / float(previous_total)

    def _build_daily_row(
        self,
        *,
        row_date: date,
        display_currency: str,
        daily_costs: dict[str, float],
        manual_row: dict[str, object] | None,
    ) -> dict[str, object]:
        leads = int(manual_row.get("leads", 0)) if isinstance(manual_row, dict) else 0
        phones = int(manual_row.get("phones", 0)) if isinstance(manual_row, dict) else 0
        cv1 = int(manual_row.get("custom_value_1_count", 0)) if isinstance(manual_row, dict) else 0
        cv2 = int(manual_row.get("custom_value_2_count", 0)) if isinstance(manual_row, dict) else 0
        cv3_ron = float(manual_row.get("custom_value_3_amount_ron", 0.0)) if isinstance(manual_row, dict) else 0.0
        cv5_ron = float(manual_row.get("custom_value_5_amount_ron", 0.0)) if isinstance(manual_row, dict) else 0.0
        cv4_ron = max(round(cv3_ron, 2) - round(cv5_ron, 2), 0.0)
        sales_count = int(manual_row.get("sales_count", 0)) if isinstance(manual_row, dict) else 0

        cost_google = round(float(daily_costs.get("google_ads", 0.0)), 2)
        cost_meta = round(float(daily_costs.get("meta_ads", 0.0)), 2)
        cost_tiktok = round(float(daily_costs.get("tiktok_ads", 0.0)), 2)
        cost_total = round(cost_google + cost_meta + cost_tiktok, 2)
        total_leads = leads + phones

        return {
            "date": row_date.isoformat(),
            "cost_google": cost_google,
            "cost_meta": cost_meta,
            "cost_tiktok": cost_tiktok,
            "cost_total": cost_total,
            "percent_change": None,
            "leads": leads,
            "phones": phones,
            "total_leads": total_leads,
            "custom_value_1_count": cv1,
            "custom_value_2_count": cv2,
            "custom_value_3_amount_ron": round(cv3_ron, 2),
            "custom_value_4_amount_ron": round(cv4_ron, 2),
            "custom_value_5_amount_ron": round(cv5_ron, 2),
            "sales_count": sales_count,
            "custom_value_rate_1": self._safe_div(float(sales_count), float(cv1)),
            "custom_value_rate_2": self._safe_div(float(sales_count), float(cv2)),
            "cost_per_lead": self._safe_div(cost_total, float(total_leads)),
            "cost_custom_value_1": self._safe_div(cost_total, float(cv1)),
            "cost_custom_value_2": self._safe_div(cost_total, float(cv2)),
            "cost_per_sale": self._safe_div(cost_total, float(sales_count)),
            "display_currency": display_currency,
        }

    def _rollup_month(self, *, month: str, day_rows: list[dict[str, object]]) -> dict[str, object]:
        sums = {
            "cost_google": sum(float(row.get("cost_google", 0.0)) for row in day_rows),
            "cost_meta": sum(float(row.get("cost_meta", 0.0)) for row in day_rows),
            "cost_tiktok": sum(float(row.get("cost_tiktok", 0.0)) for row in day_rows),
            "leads": sum(int(row.get("leads", 0)) for row in day_rows),
            "phones": sum(int(row.get("phones", 0)) for row in day_rows),
            "custom_value_1_count": sum(int(row.get("custom_value_1_count", 0)) for row in day_rows),
            "custom_value_2_count": sum(int(row.get("custom_value_2_count", 0)) for row in day_rows),
            "custom_value_3_amount_ron": sum(float(row.get("custom_value_3_amount_ron", 0.0)) for row in day_rows),
            "custom_value_4_amount_ron": sum(float(row.get("custom_value_4_amount_ron", 0.0)) for row in day_rows),
            "custom_value_5_amount_ron": sum(float(row.get("custom_value_5_amount_ron", 0.0)) for row in day_rows),
            "sales_count": sum(int(row.get("sales_count", 0)) for row in day_rows),
        }
        cost_total = round(sums["cost_google"] + sums["cost_meta"] + sums["cost_tiktok"], 2)
        total_leads = int(sums["leads"]) + int(sums["phones"])
        return {
            "month": month,
            "date_from": day_rows[0]["date"],
            "date_to": day_rows[-1]["date"],
            "totals": {
                "cost_google": round(sums["cost_google"], 2),
                "cost_meta": round(sums["cost_meta"], 2),
                "cost_tiktok": round(sums["cost_tiktok"], 2),
                "cost_total": cost_total,
                "percent_change": None,
                "leads": int(sums["leads"]),
                "phones": int(sums["phones"]),
                "total_leads": total_leads,
                "custom_value_1_count": int(sums["custom_value_1_count"]),
                "custom_value_2_count": int(sums["custom_value_2_count"]),
                "custom_value_3_amount_ron": round(sums["custom_value_3_amount_ron"], 2),
                "custom_value_4_amount_ron": max(round(sums["custom_value_3_amount_ron"], 2) - round(sums["custom_value_5_amount_ron"], 2), 0.0),
                "custom_value_5_amount_ron": round(sums["custom_value_5_amount_ron"], 2),
                "sales_count": int(sums["sales_count"]),
                "custom_value_rate_1": self._safe_div(float(sums["sales_count"]), float(sums["custom_value_1_count"])),
                "custom_value_rate_2": self._safe_div(float(sums["sales_count"]), float(sums["custom_value_2_count"])),
                "cost_per_lead": self._safe_div(cost_total, float(total_leads)),
                "cost_custom_value_1": self._safe_div(cost_total, float(sums["custom_value_1_count"])),
                "cost_custom_value_2": self._safe_div(cost_total, float(sums["custom_value_2_count"])),
                "cost_per_sale": self._safe_div(cost_total, float(sums["sales_count"])),
            },
            "days": day_rows,
        }

    def _resolve_client_template_type(self, *, client_id: int) -> str:
        details = client_registry_service.get_client_details(client_id=int(client_id))
        if not isinstance(details, dict):
            return "lead"
        client_payload = details.get("client")
        if not isinstance(client_payload, dict):
            return "lead"
        raw = str(client_payload.get("client_type") or "lead").strip().lower()
        if raw == "e-commerce":
            return "ecommerce"
        if raw in {"lead", "ecommerce", "programmatic"}:
            return raw
        return "lead"

    def _resolve_client_display_currency_decision(self, *, client_id: int) -> tuple[str, str]:
        decision = client_registry_service.get_client_reporting_currency_decision(client_id=int(client_id))
        display_currency = self._normalize_currency(
            str(
                decision.get("client_display_currency")
                or decision.get("reporting_currency")
                or "USD"
            )
        )
        source = str(
            decision.get("display_currency_source")
            or decision.get("reporting_currency_source")
            or "agency_client_currency"
        )
        return display_currency, source

    def get_lead_table(
        self,
        *,
        client_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
        include_days: bool = True,
    ) -> dict[str, object]:
        self._ensure_schema()
        if (date_from is None) != (date_to is None):
            raise ValueError("date_from and date_to must be provided together")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be less than or equal to date_to")

        config = self.get_config(client_id=int(client_id))
        effective_template_type = self._resolve_client_template_type(client_id=int(client_id))
        if effective_template_type != "lead":
            raise NotImplementedError("Media Buying table is implemented only for template_type=lead in this task")

        has_explicit_range = date_from is not None and date_to is not None
        display_currency = self._normalize_currency(str(config.get("display_currency") or "USD"))
        display_currency_source = str(config.get("display_currency_source") or "agency_client_currency")
        earliest_data_date: date | None = None
        latest_data_date: date | None = None

        total_start = time.perf_counter()

        bounds_start = time.perf_counter()
        query_date_from = date_from if has_explicit_range else None
        query_date_to = date_to if has_explicit_range else None
        bounds_ms = (time.perf_counter() - bounds_start) * 1000.0

        automated_start = time.perf_counter()
        automated_rows = self._list_automated_daily_costs(
            client_id=int(client_id),
            date_from=query_date_from,
            date_to=query_date_to,
        )
        automated_ms = (time.perf_counter() - automated_start) * 1000.0

        manual_start = time.perf_counter()
        manual_rows = self.list_lead_daily_manual_values(
            client_id=int(client_id),
            date_from=query_date_from,
            date_to=query_date_to,
        )
        manual_ms = (time.perf_counter() - manual_start) * 1000.0

        if not has_explicit_range:
            automated_dates = [
                item.get("date")
                for item in automated_rows
                if isinstance(item.get("date"), date) and float(item.get("spend") or 0.0) != 0.0
            ]
            manual_dates = [
                date.fromisoformat(str(item.get("date")))
                for item in manual_rows
                if self._manual_row_has_data(item)
                and isinstance(item.get("date"), str)
            ]
            all_dates = automated_dates + manual_dates
            earliest_data_date = min(all_dates) if all_dates else None
            latest_data_date = max(all_dates) if all_dates else None
            date_from = earliest_data_date
            date_to = latest_data_date

        if date_from is None or date_to is None:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            logger.info(
                "media_buying_lead_table_timing",
                extra={
                    "client_id": int(client_id),
                    "has_explicit_range": has_explicit_range,
                    "include_days": bool(include_days),
                    "bounds_ms": round(bounds_ms, 2),
                    "automated_query_ms": round(automated_ms, 2),
                    "manual_query_ms": round(manual_ms, 2),
                    "total_ms": round(total_ms, 2),
                    "automated_rows": len(automated_rows),
                    "manual_rows": len(manual_rows),
                    "days": 0,
                    "months": 0,
                },
            )
            return {
                "meta": {
                    "client_id": int(client_id),
                    "template_type": effective_template_type,
                    "display_currency": display_currency,
                    "display_currency_source": display_currency_source,
                    "custom_label_1": str(config.get("custom_label_1") or _DEFAULT_LABELS["custom_label_1"]),
                    "custom_label_2": str(config.get("custom_label_2") or _DEFAULT_LABELS["custom_label_2"]),
                    "custom_label_3": str(config.get("custom_label_3") or _DEFAULT_LABELS["custom_label_3"]),
                    "custom_label_4": str(config.get("custom_label_4") or _DEFAULT_LABELS["custom_label_4"]),
                    "custom_label_5": str(config.get("custom_label_5") or _DEFAULT_LABELS["custom_label_5"]),
                    "custom_rate_label_1": str(config.get("custom_rate_label_1") or _DEFAULT_LABELS["custom_rate_label_1"]),
                    "custom_rate_label_2": str(config.get("custom_rate_label_2") or _DEFAULT_LABELS["custom_rate_label_2"]),
                    "custom_cost_label_1": str(config.get("custom_cost_label_1") or _DEFAULT_LABELS["custom_cost_label_1"]),
                    "custom_cost_label_2": str(config.get("custom_cost_label_2") or _DEFAULT_LABELS["custom_cost_label_2"]),
                    "visible_columns": self._normalize_visible_columns(config.get("visible_columns"), fallback=_DEFAULT_VISIBLE_COLUMNS),
                    "date_from": None,
                    "date_to": None,
                    "effective_date_from": None,
                    "effective_date_to": None,
                    "earliest_data_date": None,
                    "latest_data_date": None,
                    "available_months": [],
                },
                "days": [],
                "months": [],
            }

        if not has_explicit_range:
            automated_rows = [
                item
                for item in automated_rows
                if isinstance(item.get("date"), date) and date_from <= item.get("date") <= date_to
            ]
            manual_rows = [
                item
                for item in manual_rows
                if isinstance(item.get("date"), str)
                and date_from <= date.fromisoformat(str(item.get("date"))) <= date_to
            ]

        manual_by_date = {str(item.get("date")): item for item in manual_rows}
        costs_by_date: dict[str, dict[str, float]] = {}
        for item in automated_rows:
            report_date = item.get("date")
            if not isinstance(report_date, date):
                continue
            day_key = report_date.isoformat()
            platform = str(item.get("platform") or "")
            if platform not in {"google_ads", "meta_ads", "tiktok_ads"}:
                continue
            spend = self._normalize_money_to_display_currency(
                amount=float(item.get("spend") or 0.0),
                from_currency=str(item.get("account_currency") or "USD"),
                display_currency=display_currency,
                rate_date=report_date,
            )
            bucket = costs_by_date.setdefault(day_key, {"google_ads": 0.0, "meta_ads": 0.0, "tiktok_ads": 0.0})
            bucket[platform] = float(bucket.get(platform, 0.0)) + float(spend)

        active_dates: set[date] = set()
        for day_key, platforms in costs_by_date.items():
            if abs(float(platforms.get("google_ads", 0.0))) > 0.0 or abs(float(platforms.get("meta_ads", 0.0))) > 0.0 or abs(float(platforms.get("tiktok_ads", 0.0))) > 0.0:
                active_dates.add(date.fromisoformat(day_key))
        for item in manual_rows:
            raw_day = item.get("date")
            if isinstance(raw_day, str) and self._manual_row_has_data(item):
                active_dates.add(date.fromisoformat(raw_day))

        day_rows = [
            self._build_daily_row(
                row_date=row_date,
                display_currency=display_currency,
                daily_costs=costs_by_date.get(row_date.isoformat(), {}),
                manual_row=manual_by_date.get(row_date.isoformat()),
            )
            for row_date in sorted(active_dates)
            if date_from <= row_date <= date_to
        ]

        if day_rows:
            if earliest_data_date is None:
                earliest_data_date = date.fromisoformat(str(day_rows[0]["date"]))
            if latest_data_date is None:
                latest_data_date = date.fromisoformat(str(day_rows[-1]["date"]))

        monthly_grouped: dict[str, list[dict[str, object]]] = {}
        for row in day_rows:
            row_date = date.fromisoformat(str(row["date"]))
            key = self._month_key(row_date)
            monthly_grouped.setdefault(key, []).append(row)

        previous_day_total: float | None = None
        if include_days:
            for row in day_rows:
                current_total = float(row.get("cost_total", 0.0))
                row["percent_change"] = self._build_percent_change(current_total=current_total, previous_total=previous_day_total)
                previous_day_total = current_total

        months = [self._rollup_month(month=month, day_rows=rows) for month, rows in sorted(monthly_grouped.items(), key=lambda item: item[0])]

        previous_month_total: float | None = None
        for month in months:
            totals = month.get("totals")
            if not isinstance(totals, dict):
                continue
            current_month_total = float(totals.get("cost_total", 0.0))
            totals["percent_change"] = self._build_percent_change(current_total=current_month_total, previous_total=previous_month_total)
            previous_month_total = current_month_total
            if include_days:
                continue
            month_days = month.pop("days", [])
            month["day_count"] = len(month_days) if isinstance(month_days, list) else 0
            month["has_days"] = month.get("day_count", 0) > 0

        total_ms = (time.perf_counter() - total_start) * 1000.0
        logger.info(
            "media_buying_lead_table_timing",
            extra={
                "client_id": int(client_id),
                "has_explicit_range": has_explicit_range,
                "include_days": bool(include_days),
                "bounds_ms": round(bounds_ms, 2),
                "automated_query_ms": round(automated_ms, 2),
                "manual_query_ms": round(manual_ms, 2),
                "total_ms": round(total_ms, 2),
                "automated_rows": len(automated_rows),
                "manual_rows": len(manual_rows),
                "days": len(day_rows) if include_days else 0,
                "months": len(months),
            },
        )

        return {
            "meta": {
                "client_id": int(client_id),
                "template_type": effective_template_type,
                "display_currency": display_currency,
                "display_currency_source": display_currency_source,
                "custom_label_1": str(config.get("custom_label_1") or _DEFAULT_LABELS["custom_label_1"]),
                "custom_label_2": str(config.get("custom_label_2") or _DEFAULT_LABELS["custom_label_2"]),
                "custom_label_3": str(config.get("custom_label_3") or _DEFAULT_LABELS["custom_label_3"]),
                "custom_label_4": str(config.get("custom_label_4") or _DEFAULT_LABELS["custom_label_4"]),
                "custom_label_5": str(config.get("custom_label_5") or _DEFAULT_LABELS["custom_label_5"]),
                "custom_rate_label_1": str(config.get("custom_rate_label_1") or _DEFAULT_LABELS["custom_rate_label_1"]),
                "custom_rate_label_2": str(config.get("custom_rate_label_2") or _DEFAULT_LABELS["custom_rate_label_2"]),
                "custom_cost_label_1": str(config.get("custom_cost_label_1") or _DEFAULT_LABELS["custom_cost_label_1"]),
                "custom_cost_label_2": str(config.get("custom_cost_label_2") or _DEFAULT_LABELS["custom_cost_label_2"]),
                "visible_columns": self._normalize_visible_columns(config.get("visible_columns"), fallback=_DEFAULT_VISIBLE_COLUMNS),
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "effective_date_from": day_rows[0]["date"] if day_rows else None,
                "effective_date_to": day_rows[-1]["date"] if day_rows else None,
                "earliest_data_date": earliest_data_date.isoformat() if earliest_data_date else None,
                "latest_data_date": latest_data_date.isoformat() if latest_data_date else None,
                "available_months": [item["month"] for item in months],
            },
            "days": day_rows if include_days else [],
            "months": months,
        }

    def get_lead_month_days(
        self,
        *,
        client_id: int,
        month_start: date,
    ) -> dict[str, object]:
        month_start_value = date(month_start.year, month_start.month, 1)
        if month_start != month_start_value:
            raise ValueError("month_start must be the first day of month")

        month_end = date(month_start.year + (1 if month_start.month == 12 else 0), 1 if month_start.month == 12 else month_start.month + 1, 1) - timedelta(days=1)

        start = time.perf_counter()
        payload = self.get_lead_table(
            client_id=int(client_id),
            date_from=month_start,
            date_to=month_end,
            include_days=True,
        )
        days = payload.get("days") if isinstance(payload, dict) else []
        month_rows = payload.get("months") if isinstance(payload, dict) else []

        if not isinstance(month_rows, list) or len(month_rows) <= 0:
            raise ValueError("month_start is outside available media buying range")

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info(
            "media_buying_lead_month_days_timing",
            extra={
                "client_id": int(client_id),
                "month_start": month_start.isoformat(),
                "total_ms": round(elapsed_ms, 2),
                "days": len(days) if isinstance(days, list) else 0,
            },
        )
        return {
            "meta": payload.get("meta", {}),
            "month_start": month_start.isoformat(),
            "days": days if isinstance(days, list) else [],
        }

    def _lead_table_day_has_data(self, row: dict[str, object]) -> bool:
        fields = [
            "cost_google",
            "cost_meta",
            "cost_tiktok",
            "leads",
            "phones",
            "custom_value_1_count",
            "custom_value_2_count",
            "custom_value_3_amount_ron",
            "custom_value_4_amount_ron",
            "custom_value_5_amount_ron",
            "sales_count",
        ]
        for field in fields:
            value = row.get(field)
            if isinstance(value, (int, float)) and float(value) != 0.0:
                return True
        return False

    def _get_lead_table_data_bounds(self, *, client_id: int) -> tuple[date | None, date | None]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH scoped AS (
                        SELECT
                            apr.report_date,
                            COALESCE(apr.spend, 0) AS spend
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
                        WHERE apr.platform IN ('google_ads', 'meta_ads', 'tiktok_ads')
                          AND COALESCE(
                              NULLIF(TRIM(CASE WHEN apr.platform = 'meta_ads' THEN COALESCE(apr.extra_metrics -> 'meta_ads' ->> 'grain', '') WHEN apr.platform = 'tiktok_ads' THEN COALESCE(apr.extra_metrics -> 'tiktok_ads' ->> 'grain', '') WHEN apr.platform = 'google_ads' THEN COALESCE(apr.extra_metrics -> 'google_ads' ->> 'grain', '') ELSE '' END), ''),
                              'account_daily'
                          ) = 'account_daily'
                    )
                    SELECT MIN(report_date), MAX(report_date)
                    FROM scoped
                    WHERE COALESCE(spend, 0) <> 0
                    """,
                    (int(client_id),),
                )
                automated_row = cur.fetchone()

                cur.execute(
                    """
                    SELECT MIN(metric_date), MAX(metric_date)
                    FROM media_buying_lead_daily_manual_values
                    WHERE client_id = %s
                      AND (
                        COALESCE(leads, 0) <> 0
                        OR COALESCE(phones, 0) <> 0
                        OR COALESCE(custom_value_1_count, 0) <> 0
                        OR COALESCE(custom_value_2_count, 0) <> 0
                        OR COALESCE(custom_value_3_amount_ron, 0) <> 0
                        OR COALESCE(custom_value_4_amount_ron, 0) <> 0
                        OR COALESCE(custom_value_5_amount_ron, 0) <> 0
                        OR COALESCE(sales_count, 0) <> 0
                      )
                    """,
                    (int(client_id),),
                )
                manual_row = cur.fetchone()

        candidates_min: list[date] = []
        candidates_max: list[date] = []
        for row in (automated_row, manual_row):
            if not isinstance(row, tuple):
                continue
            min_value = row[0] if len(row) > 0 and isinstance(row[0], date) else None
            max_value = row[1] if len(row) > 1 and isinstance(row[1], date) else None
            if min_value is not None:
                candidates_min.append(min_value)
            if max_value is not None:
                candidates_max.append(max_value)

        earliest = min(candidates_min) if candidates_min else None
        latest = max(candidates_max) if candidates_max else None
        return earliest, latest


    def get_config(self, *, client_id: int) -> dict[str, object]:
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        client_id,
                        template_type,
                        display_currency,
                        custom_label_1,
                        custom_label_2,
                        custom_label_3,
                        custom_label_4,
                        custom_label_5,
                        custom_rate_label_1,
                        custom_rate_label_2,
                        custom_cost_label_1,
                        custom_cost_label_2,
                        visible_columns,
                        enabled,
                        created_at,
                        updated_at
                    FROM media_buying_configs
                    WHERE client_id = %s
                    """,
                    (int(client_id),),
                )
                row = cur.fetchone()

        resolved_display_currency, display_currency_source = self._resolve_client_display_currency_decision(client_id=int(client_id))

        payload = self._config_from_row(row)
        if payload is not None:
            payload["display_currency"] = resolved_display_currency
            payload["display_currency_source"] = display_currency_source
            return payload

        effective_template_type = self._resolve_client_template_type(client_id=int(client_id))
        return {
            "client_id": int(client_id),
            "template_type": effective_template_type,
            "display_currency": resolved_display_currency,
            "display_currency_source": display_currency_source,
            "custom_label_1": _DEFAULT_LABELS["custom_label_1"],
            "custom_label_2": _DEFAULT_LABELS["custom_label_2"],
            "custom_label_3": _DEFAULT_LABELS["custom_label_3"],
            "custom_label_4": _DEFAULT_LABELS["custom_label_4"],
            "custom_label_5": _DEFAULT_LABELS["custom_label_5"],
            "custom_rate_label_1": _DEFAULT_LABELS["custom_rate_label_1"],
            "custom_rate_label_2": _DEFAULT_LABELS["custom_rate_label_2"],
            "custom_cost_label_1": _DEFAULT_LABELS["custom_cost_label_1"],
            "custom_cost_label_2": _DEFAULT_LABELS["custom_cost_label_2"],
            "visible_columns": list(_DEFAULT_VISIBLE_COLUMNS),
            "enabled": True,
            "created_at": None,
            "updated_at": None,
        }

    def upsert_config(
        self,
        *,
        client_id: int,
        template_type: str | None = None,
        display_currency: str | None = None,
        custom_label_1: str | None = None,
        custom_label_2: str | None = None,
        custom_label_3: str | None = None,
        custom_label_4: str | None = None,
        custom_label_5: str | None = None,
        custom_rate_label_1: str | None = None,
        custom_rate_label_2: str | None = None,
        custom_cost_label_1: str | None = None,
        custom_cost_label_2: str | None = None,
        visible_columns: list[str] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, object]:
        self._ensure_schema()
        current = self.get_config(client_id=int(client_id))

        effective_template_type = self._resolve_client_template_type(client_id=int(client_id))
        next_template_type = self._normalize_template_type(effective_template_type)
        resolved_display_currency, _ = self._resolve_client_display_currency_decision(client_id=int(client_id))
        next_currency = self._normalize_currency(resolved_display_currency)

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO media_buying_configs (
                        client_id,
                        template_type,
                        display_currency,
                        custom_label_1,
                        custom_label_2,
                        custom_label_3,
                        custom_label_4,
                        custom_label_5,
                        custom_rate_label_1,
                        custom_rate_label_2,
                        custom_cost_label_1,
                        custom_cost_label_2,
                        visible_columns,
                        enabled
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id)
                    DO UPDATE SET
                        template_type = EXCLUDED.template_type,
                        display_currency = EXCLUDED.display_currency,
                        custom_label_1 = EXCLUDED.custom_label_1,
                        custom_label_2 = EXCLUDED.custom_label_2,
                        custom_label_3 = EXCLUDED.custom_label_3,
                        custom_label_4 = EXCLUDED.custom_label_4,
                        custom_label_5 = EXCLUDED.custom_label_5,
                        custom_rate_label_1 = EXCLUDED.custom_rate_label_1,
                        custom_rate_label_2 = EXCLUDED.custom_rate_label_2,
                        custom_cost_label_1 = EXCLUDED.custom_cost_label_1,
                        custom_cost_label_2 = EXCLUDED.custom_cost_label_2,
                        visible_columns = EXCLUDED.visible_columns,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    (
                        int(client_id),
                        next_template_type,
                        next_currency,
                        self._normalize_label(custom_label_1, fallback=str(current["custom_label_1"])),
                        self._normalize_label(custom_label_2, fallback=str(current["custom_label_2"])),
                        self._normalize_label(custom_label_3, fallback=str(current["custom_label_3"])),
                        self._normalize_label(custom_label_4, fallback=str(current["custom_label_4"])),
                        self._normalize_label(custom_label_5, fallback=str(current["custom_label_5"])),
                        self._normalize_label(custom_rate_label_1, fallback=str(current.get("custom_rate_label_1") or _DEFAULT_LABELS["custom_rate_label_1"])),
                        self._normalize_label(custom_rate_label_2, fallback=str(current.get("custom_rate_label_2") or _DEFAULT_LABELS["custom_rate_label_2"])),
                        self._normalize_label(custom_cost_label_1, fallback=str(current.get("custom_cost_label_1") or _DEFAULT_LABELS["custom_cost_label_1"])),
                        self._normalize_label(custom_cost_label_2, fallback=str(current.get("custom_cost_label_2") or _DEFAULT_LABELS["custom_cost_label_2"])),
                        self._normalize_visible_columns(visible_columns, fallback=self._normalize_visible_columns(current.get("visible_columns"), fallback=_DEFAULT_VISIBLE_COLUMNS)),
                        bool(current["enabled"]) if enabled is None else bool(enabled),
                    ),
                )
            conn.commit()

        return self.get_config(client_id=int(client_id))

    def list_lead_daily_manual_values(
        self,
        *,
        client_id: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        if (date_from is None) != (date_to is None):
            raise ValueError("date_from and date_to must be provided together")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from must be less than or equal to date_to")

        with self._connect() as conn:
            with conn.cursor() as cur:
                if date_from is None or date_to is None:
                    cur.execute(
                        """
                        SELECT
                            client_id,
                            metric_date,
                            leads,
                            phones,
                            custom_value_1_count,
                            custom_value_2_count,
                            custom_value_3_amount_ron,
                            custom_value_4_amount_ron,
                            custom_value_5_amount_ron,
                            sales_count,
                            created_at,
                            updated_at
                        FROM media_buying_lead_daily_manual_values
                        WHERE client_id = %s
                        ORDER BY metric_date ASC
                        """,
                        (int(client_id),),
                    )
                else:
                    cur.execute(
                        """
                        SELECT
                            client_id,
                            metric_date,
                            leads,
                            phones,
                            custom_value_1_count,
                            custom_value_2_count,
                            custom_value_3_amount_ron,
                            custom_value_4_amount_ron,
                            custom_value_5_amount_ron,
                            sales_count,
                            created_at,
                            updated_at
                        FROM media_buying_lead_daily_manual_values
                        WHERE client_id = %s
                          AND metric_date >= %s
                          AND metric_date <= %s
                        ORDER BY metric_date ASC
                        """,
                        (int(client_id), date_from, date_to),
                    )
                rows = cur.fetchall() or []

        return [self._daily_from_row(row) for row in rows]

    def upsert_lead_daily_manual_value(
        self,
        *,
        client_id: int,
        metric_date: date,
        leads: object,
        phones: object,
        custom_value_1_count: object,
        custom_value_2_count: object,
        custom_value_3_amount_ron: object,
        custom_value_4_amount_ron: object,
        custom_value_5_amount_ron: object,
        sales_count: object,
    ) -> dict[str, object]:
        self._ensure_schema()

        parsed_leads = self._parse_non_negative_int(leads, field_name="leads")
        parsed_phones = self._parse_non_negative_int(phones, field_name="phones")
        parsed_cv1 = self._parse_non_negative_int(custom_value_1_count, field_name="custom_value_1_count")
        parsed_cv2 = self._parse_non_negative_int(custom_value_2_count, field_name="custom_value_2_count")
        parsed_cv3 = self._parse_amount(custom_value_3_amount_ron, field_name="custom_value_3_amount_ron")
        parsed_cv4 = self._parse_amount(custom_value_4_amount_ron, field_name="custom_value_4_amount_ron")
        parsed_cv5 = self._parse_amount(custom_value_5_amount_ron, field_name="custom_value_5_amount_ron", allow_negative=True)
        parsed_sales = self._parse_non_negative_int(sales_count, field_name="sales_count")

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO media_buying_lead_daily_manual_values (
                        client_id,
                        metric_date,
                        leads,
                        phones,
                        custom_value_1_count,
                        custom_value_2_count,
                        custom_value_3_amount_ron,
                        custom_value_4_amount_ron,
                        custom_value_5_amount_ron,
                        sales_count
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id, metric_date)
                    DO UPDATE SET
                        leads = EXCLUDED.leads,
                        phones = EXCLUDED.phones,
                        custom_value_1_count = EXCLUDED.custom_value_1_count,
                        custom_value_2_count = EXCLUDED.custom_value_2_count,
                        custom_value_3_amount_ron = EXCLUDED.custom_value_3_amount_ron,
                        custom_value_4_amount_ron = EXCLUDED.custom_value_4_amount_ron,
                        custom_value_5_amount_ron = EXCLUDED.custom_value_5_amount_ron,
                        sales_count = EXCLUDED.sales_count,
                        updated_at = NOW()
                    """,
                    (
                        int(client_id),
                        metric_date,
                        parsed_leads,
                        parsed_phones,
                        parsed_cv1,
                        parsed_cv2,
                        parsed_cv3,
                        parsed_cv4,
                        parsed_cv5,
                        parsed_sales,
                    ),
                )
                cur.execute(
                    """
                    SELECT
                        client_id,
                        metric_date,
                        leads,
                        phones,
                        custom_value_1_count,
                        custom_value_2_count,
                        custom_value_3_amount_ron,
                        custom_value_4_amount_ron,
                        custom_value_5_amount_ron,
                        sales_count,
                        created_at,
                        updated_at
                    FROM media_buying_lead_daily_manual_values
                    WHERE client_id = %s AND metric_date = %s
                    """,
                    (int(client_id), metric_date),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise RuntimeError("Failed to persist media buying lead daily manual value")
        return self._daily_from_row(row)


media_buying_store = MediaBuyingStore()
