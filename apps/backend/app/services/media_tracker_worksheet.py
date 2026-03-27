from __future__ import annotations

from datetime import date, timedelta
from threading import Lock
from typing import Literal

from app.core.config import load_settings
from app.services.media_buying_store import media_buying_store

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

WorksheetGranularity = Literal["month", "quarter", "year"]

_MANUAL_FIELDS: tuple[dict[str, str], ...] = (
    {"field_key": "weekly_cogs_taxes", "label": "Total COGS + Taxe", "section_key": "summary"},
    {"field_key": "google_leads_manual", "label": "Lead-uri Google (Manual)", "section_key": "google_spend"},
    {"field_key": "google_sales_manual", "label": "Vânzări Google (Manual)", "section_key": "google_spend"},
    {"field_key": "google_revenue_manual", "label": "Venit Google (Manual)", "section_key": "google_spend"},
    {"field_key": "meta_leads_manual", "label": "Lead-uri Meta (Manual)", "section_key": "meta_spend"},
    {"field_key": "meta_sales_manual", "label": "Vânzări Meta (Manual)", "section_key": "meta_spend"},
    {"field_key": "meta_revenue_manual", "label": "Venit Meta (Manual)", "section_key": "meta_spend"},
    {"field_key": "tiktok_leads_manual", "label": "Lead-uri TikTok (Manual)", "section_key": "tiktok_spend"},
    {"field_key": "tiktok_sales_manual", "label": "Vânzări TikTok (Manual)", "section_key": "tiktok_spend"},
    {"field_key": "tiktok_revenue_manual", "label": "Venit TikTok (Manual)", "section_key": "tiktok_spend"},
)
_MANUAL_FIELD_KEYS = {item["field_key"] for item in _MANUAL_FIELDS}


class MediaTrackerWorksheetService:
    def __init__(self) -> None:
        self._schema_lock = Lock()
        self._schema_initialized = False
        self._memory_lock = Lock()
        self._memory_manual_values: dict[tuple[int, str, str], float] = {}
        self._memory_scope_rates: dict[tuple[int, str, str, str], float] = {}

    def _is_test_mode(self) -> bool:
        return load_settings().app_env == "test"

    def _connect(self):
        settings = load_settings()
        if psycopg is None:
            raise RuntimeError("psycopg is required for media tracker worksheet persistence")
        return psycopg.connect(settings.database_url)

    def _ensure_schema(self) -> None:
        if self._is_test_mode() or self._schema_initialized:
            return
        with self._schema_lock:
            if self._schema_initialized:
                return
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_xact_lock(1, hashtext(%s))", ("ensure_schema_" + self.__class__.__name__,))
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS media_tracker_weekly_manual_values (
                            id BIGSERIAL PRIMARY KEY,
                            client_id BIGINT NOT NULL,
                            week_start DATE NOT NULL,
                            field_key TEXT NOT NULL,
                            value NUMERIC(18, 4) NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            UNIQUE (client_id, week_start, field_key)
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS media_tracker_scope_fx_rates (
                            id BIGSERIAL PRIMARY KEY,
                            client_id BIGINT NOT NULL,
                            granularity TEXT NOT NULL,
                            period_start DATE NOT NULL,
                            period_end DATE NOT NULL,
                            value NUMERIC(18, 6) NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            UNIQUE (client_id, granularity, period_start, period_end)
                        )
                        """
                    )
                conn.commit()
            self._schema_initialized = True

    def reset_test_state(self) -> None:
        if not self._is_test_mode():
            return
        with self._memory_lock:
            self._memory_manual_values = {}
            self._memory_scope_rates = {}

    def _resolve_calendar_period(self, *, granularity: WorksheetGranularity, anchor_date: date) -> tuple[date, date]:
        if granularity == "month":
            period_start = date(anchor_date.year, anchor_date.month, 1)
            if anchor_date.month == 12:
                next_month_start = date(anchor_date.year + 1, 1, 1)
            else:
                next_month_start = date(anchor_date.year, anchor_date.month + 1, 1)
            return period_start, next_month_start - timedelta(days=1)

        if granularity == "quarter":
            quarter_start_month = ((anchor_date.month - 1) // 3) * 3 + 1
            period_start = date(anchor_date.year, quarter_start_month, 1)
            quarter_end_month = quarter_start_month + 2
            if quarter_end_month == 12:
                next_period_start = date(anchor_date.year + 1, 1, 1)
            else:
                next_period_start = date(anchor_date.year, quarter_end_month + 1, 1)
            return period_start, next_period_start - timedelta(days=1)

        period_start = date(anchor_date.year, 1, 1)
        period_end = date(anchor_date.year, 12, 31)
        return period_start, period_end

    def _build_visible_weeks(self, *, period_start: date, period_end: date) -> list[dict[str, object]]:
        first_monday = period_start - timedelta(days=period_start.weekday())
        last_sunday = period_end + timedelta(days=(6 - period_end.weekday()))

        weeks: list[dict[str, object]] = []
        current = first_monday
        index = 1
        while current <= last_sunday:
            week_start = current
            week_end = current + timedelta(days=6)
            weeks.append(
                {
                    "index": index,
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "label": week_start.isoformat(),
                    "is_first_visible_week": index == 1,
                    "intersects_period_start": week_start <= period_start <= week_end,
                    "intersects_period_end": week_start <= period_end <= week_end,
                }
            )
            index += 1
            current += timedelta(days=7)

        return weeks

    def _to_float(self, value: object) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _normalized_label(self, value: object, *, fallback: str) -> str:
        raw = str(value or "").strip()
        return raw if raw != "" else fallback

    def _safe_div(self, numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or denominator is None:
            return None
        if abs(float(denominator)) <= 0.0:
            return None
        return float(numerator) / float(denominator)

    def _sum_history_nullable(self, values: list[float | None]) -> float | None:
        seen = False
        total = 0.0
        for item in values:
            if item is None:
                continue
            seen = True
            total += float(item)
        return round(total, 2) if seen else None

    def _validate_granularity(self, *, granularity: str) -> WorksheetGranularity:
        normalized_granularity = str(granularity).strip().lower()
        if normalized_granularity not in {"month", "quarter", "year"}:
            raise ValueError("granularity must be one of: month, quarter, year")
        return normalized_granularity

    def _build_auto_metrics(self, *, weeks: list[dict[str, object]], day_rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        metrics: dict[str, dict[str, object]] = {
            "cost_total": {"aggregation": "sum", "source_field": "cost_total", "history_value": 0.0, "weekly_values": []},
            "cost_google": {"aggregation": "sum", "source_field": "cost_google", "history_value": 0.0, "weekly_values": []},
            "cost_meta": {"aggregation": "sum", "source_field": "cost_meta", "history_value": 0.0, "weekly_values": []},
            "cost_tiktok": {"aggregation": "sum", "source_field": "cost_tiktok", "history_value": 0.0, "weekly_values": []},
            "total_leads": {"aggregation": "sum", "source_field": "total_leads", "history_value": 0.0, "weekly_values": []},
            "applications": {"aggregation": "sum", "source_field": "custom_value_1_count", "history_value": 0.0, "weekly_values": []},
            "approved_applications": {"aggregation": "sum", "source_field": "custom_value_2_count", "history_value": 0.0, "weekly_values": []},
        }

        parsed_rows: list[tuple[date, dict[str, object]]] = []
        for row in day_rows:
            raw_date = row.get("date")
            if not isinstance(raw_date, str):
                continue
            try:
                row_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            parsed_rows.append((row_date, row))

        for week in weeks:
            week_start = date.fromisoformat(str(week["week_start"]))
            week_end = date.fromisoformat(str(week["week_end"]))
            in_week_rows = [item for item in parsed_rows if week_start <= item[0] <= week_end]

            weekly_values = {
                "cost_total": round(sum(self._to_float(row.get("cost_total")) for _, row in in_week_rows), 2),
                "cost_google": round(sum(self._to_float(row.get("cost_google")) for _, row in in_week_rows), 2),
                "cost_meta": round(sum(self._to_float(row.get("cost_meta")) for _, row in in_week_rows), 2),
                "cost_tiktok": round(sum(self._to_float(row.get("cost_tiktok")) for _, row in in_week_rows), 2),
                "total_leads": round(sum(self._to_float(row.get("total_leads")) for _, row in in_week_rows), 2),
                "applications": round(sum(self._to_float(row.get("custom_value_1_count")) for _, row in in_week_rows), 2),
                "approved_applications": round(sum(self._to_float(row.get("custom_value_2_count")) for _, row in in_week_rows), 2),
            }

            for key, value in weekly_values.items():
                metrics[key]["weekly_values"].append(
                    {
                        "week_start": week["week_start"],
                        "week_end": week["week_end"],
                        "value": value,
                    }
                )

        for payload in metrics.values():
            payload["history_value"] = round(sum(self._to_float(item.get("value")) for item in payload["weekly_values"]), 2)

        return metrics

    def _list_manual_values_for_weeks(self, *, client_id: int, week_starts: list[date]) -> dict[tuple[str, str], float]:
        if len(week_starts) <= 0:
            return {}
        if self._is_test_mode():
            week_start_set = set(week_starts)
            with self._memory_lock:
                return {
                    (week_start_iso, field_key): value
                    for (stored_client_id, week_start_iso, field_key), value in self._memory_manual_values.items()
                    if int(stored_client_id) == int(client_id) and date.fromisoformat(week_start_iso) in week_start_set
                }

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT week_start, field_key, value
                    FROM media_tracker_weekly_manual_values
                    WHERE client_id = %s
                      AND week_start = ANY(%s::date[])
                    """,
                    (int(client_id), week_starts),
                )
                rows = cur.fetchall() or []
        return {
            (row[0].isoformat(), str(row[1])): float(row[2])
            for row in rows
        }

    def _get_scope_eur_ron_rate(self, *, client_id: int, granularity: WorksheetGranularity, period_start: date, period_end: date) -> float | None:
        if self._is_test_mode():
            with self._memory_lock:
                return self._memory_scope_rates.get((int(client_id), str(granularity), period_start.isoformat(), period_end.isoformat()))

        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value
                    FROM media_tracker_scope_fx_rates
                    WHERE client_id = %s
                      AND granularity = %s
                      AND period_start = %s
                      AND period_end = %s
                    """,
                    (int(client_id), str(granularity), period_start, period_end),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return float(row[0])

    def _build_manual_field_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "field_key": item["field_key"],
                "label": item["label"],
                "section_key": item["section_key"],
                "value_kind": "manual_number",
                "scope": "week",
            }
            for item in _MANUAL_FIELDS
        ]

    def _build_manual_metrics(self, *, weeks: list[dict[str, object]], manual_values_map: dict[tuple[str, str], float]) -> dict[str, dict[str, object]]:
        metrics: dict[str, dict[str, object]] = {
            field_key: {"aggregation": "sum", "history_value": 0.0, "weekly_values": []}
            for field_key in _MANUAL_FIELD_KEYS
        }

        for week in weeks:
            week_start = str(week["week_start"])
            week_end = str(week["week_end"])
            for field_key in _MANUAL_FIELD_KEYS:
                value = manual_values_map.get((week_start, field_key))
                metrics[field_key]["weekly_values"].append(
                    {
                        "week_start": week_start,
                        "week_end": week_end,
                        "value": value if value is not None else None,
                    }
                )

        for payload in metrics.values():
            payload["history_value"] = round(
                sum(self._to_float(item.get("value")) for item in payload["weekly_values"] if item.get("value") is not None),
                2,
            )

        return metrics

    def _extract_weekly_values(self, *, metrics: dict[str, dict[str, object]], key: str) -> list[float | None]:
        payload = metrics.get(key) if isinstance(metrics.get(key), dict) else {}
        weekly_values = payload.get("weekly_values") if isinstance(payload.get("weekly_values"), list) else []
        return [
            (float(item.get("value")) if isinstance(item, dict) and item.get("value") is not None else None)
            for item in weekly_values
        ]

    def _build_row(
        self,
        *,
        weeks: list[dict[str, object]],
        row_key: str,
        label: str,
        value_kind: str,
        weekly_values: list[float | None],
        history_value: float | None,
        dependencies: list[str],
        requires_eur_ron_rate: bool = False,
        is_manual_input_row: bool = False,
        currency_code: str | None = None,
    ) -> dict[str, object]:
        return {
            "row_key": row_key,
            "label": label,
            "value_kind": value_kind,
            "currency_code": str(currency_code) if currency_code is not None else None,
            "source_kind": "manual" if is_manual_input_row else "computed",
            "is_manual_input_row": is_manual_input_row,
            "is_derived_row": not is_manual_input_row,
            "requires_eur_ron_rate": requires_eur_ron_rate,
            "dependencies": dependencies,
            "history_value": round(history_value, 4) if isinstance(history_value, (int, float)) else None,
            "weekly_values": [
                {
                    "week_start": week["week_start"],
                    "week_end": week["week_end"],
                    "value": round(weekly_values[idx], 4) if isinstance(weekly_values[idx], (int, float)) else None,
                }
                for idx, week in enumerate(weeks)
            ],
        }

    def _compute_week_over_week_values(self, *, source_weekly_values: list[dict[str, object]]) -> list[float | None]:
        values: list[float | None] = []
        for idx, item in enumerate(source_weekly_values):
            current_raw = item.get("value") if isinstance(item, dict) else None
            current = float(current_raw) if isinstance(current_raw, (int, float)) else None
            if idx == 0:
                values.append(None)
                continue

            previous_raw = source_weekly_values[idx - 1].get("value") if isinstance(source_weekly_values[idx - 1], dict) else None
            previous = float(previous_raw) if isinstance(previous_raw, (int, float)) else None
            if current is None or previous is None or abs(previous) <= 0.0:
                values.append(None)
                continue
            values.append((current - previous) / previous)
        return values

    def _build_wow_comparison_row(self, *, weeks: list[dict[str, object]], source_row: dict[str, object]) -> dict[str, object]:
        source_row_key = str(source_row.get("row_key") or "")
        source_weekly_values = source_row.get("weekly_values") if isinstance(source_row.get("weekly_values"), list) else []
        wow_values = self._compute_week_over_week_values(source_weekly_values=source_weekly_values)
        return {
            "row_key": f"{source_row_key}_wow_pct",
            "label": "%",
            "value_kind": "percent_ratio",
            "source_kind": "comparison",
            "is_manual_input_row": False,
            "is_derived_row": True,
            "requires_eur_ron_rate": False,
            "dependencies": [source_row_key],
            "comparison_kind": "week_over_week",
            "compares_row_key": source_row_key,
            "history_value": None,
            "weekly_values": [
                {
                    "week_start": week["week_start"],
                    "week_end": week["week_end"],
                    "value": round(wow_values[idx], 4) if isinstance(wow_values[idx], (int, float)) else None,
                }
                for idx, week in enumerate(weeks)
            ],
        }

    def _insert_wow_rows(
        self,
        *,
        weeks: list[dict[str, object]],
        rows: list[dict[str, object]],
        source_row_keys: set[str],
    ) -> list[dict[str, object]]:
        enriched_rows: list[dict[str, object]] = []
        for row in rows:
            enriched_rows.append(row)
            row_key = str(row.get("row_key") or "")
            if row_key in source_row_keys:
                enriched_rows.append(self._build_wow_comparison_row(weeks=weeks, source_row=row))
        return enriched_rows

    def _build_computed_sections(
        self,
        *,
        weeks: list[dict[str, object]],
        auto_metrics: dict[str, dict[str, object]],
        manual_metrics: dict[str, dict[str, object]],
        source_weekly_metrics: dict[str, dict[str, object]],
        eur_ron_rate: float | None,
        display_currency: str,
        custom_label_1: str,
        custom_label_2: str,
    ) -> list[dict[str, object]]:
        week_count = len(weeks)
        auto_cost_total = self._extract_weekly_values(metrics=auto_metrics, key="cost_total")
        auto_cost_google = self._extract_weekly_values(metrics=auto_metrics, key="cost_google")
        auto_cost_meta = self._extract_weekly_values(metrics=auto_metrics, key="cost_meta")
        auto_cost_tiktok = self._extract_weekly_values(metrics=auto_metrics, key="cost_tiktok")
        auto_leads = self._extract_weekly_values(metrics=auto_metrics, key="total_leads")
        auto_apps = self._extract_weekly_values(metrics=auto_metrics, key="applications")
        auto_approved = self._extract_weekly_values(metrics=auto_metrics, key="approved_applications")

        def source_metric_values(source_key: str, metric_key: str) -> list[float | None]:
            payload = source_weekly_metrics.get(source_key) if isinstance(source_weekly_metrics.get(source_key), dict) else {}
            values = payload.get(metric_key) if isinstance(payload.get(metric_key), list) else []
            if len(values) == week_count:
                return [float(item) if isinstance(item, (int, float)) else 0.0 for item in values]
            return [0.0 for _ in range(week_count)]

        g_leads = source_metric_values("google_ads", "leads_values")
        g_sales = source_metric_values("google_ads", "sales_values")
        g_revenue = source_metric_values("google_ads", "revenue_values")
        m_leads = source_metric_values("meta_ads", "leads_values")
        m_sales = source_metric_values("meta_ads", "sales_values")
        m_revenue = source_metric_values("meta_ads", "revenue_values")
        t_leads = source_metric_values("tiktok_ads", "leads_values")
        t_sales = source_metric_values("tiktok_ads", "sales_values")
        t_revenue = source_metric_values("tiktok_ads", "revenue_values")
        cogs = self._extract_weekly_values(metrics=manual_metrics, key="weekly_cogs_taxes")

        summary_cost = [self._to_float(item) for item in auto_cost_total]
        summary_revenue = [
            round(
                sum(
                    self._to_float((source_weekly_metrics.get(source_key) or {}).get("revenue_values", [0.0] * week_count)[i])
                    for source_key in source_weekly_metrics.keys()
                ),
                4,
            )
            for i in range(week_count)
        ]
        summary_sales = [
            round(
                sum(
                    self._to_float((source_weekly_metrics.get(source_key) or {}).get("sales_values", [0.0] * week_count)[i])
                    for source_key in source_weekly_metrics.keys()
                ),
                4,
            )
            for i in range(week_count)
        ]
        summary_leads = [self._to_float(item) for item in auto_leads]
        summary_apps = [self._to_float(item) for item in auto_apps]
        summary_approved = [self._to_float(item) for item in auto_approved]

        summary_avg_daily_spend = [self._safe_div(summary_cost[i], 7.0) for i in range(week_count)]
        summary_revenue_target_per_day = [self._safe_div(summary_revenue[i], 7.0) for i in range(week_count)]
        summary_aov = [self._safe_div(summary_revenue[i], summary_sales[i]) for i in range(week_count)]
        summary_cpa_leads = [self._safe_div(summary_cost[i], summary_leads[i]) for i in range(week_count)]
        summary_cpa_apps = [self._safe_div(summary_cost[i], summary_apps[i]) for i in range(week_count)]
        summary_cpa_approved = [self._safe_div(summary_cost[i], summary_approved[i]) for i in range(week_count)]
        summary_cost_vs_revenue = [self._safe_div(summary_cost[i], summary_revenue[i]) for i in range(week_count)]
        summary_mer = [self._safe_div(summary_revenue[i], summary_cost[i]) for i in range(week_count)]

        summary_gross_profit: list[float | None] = []
        summary_profit_contribution: list[float | None] = []
        for idx in range(week_count):
            if cogs[idx] is None:
                summary_gross_profit.append(None)
                summary_profit_contribution.append(None)
                continue
            gross = summary_revenue[idx] - self._to_float(cogs[idx])
            summary_gross_profit.append(gross)
            summary_profit_contribution.append(gross - summary_cost[idx])

        new_clients_combined_spend = list(summary_cost)
        new_clients_cost_per_new_client = [self._safe_div(new_clients_combined_spend[i], summary_sales[i]) for i in range(week_count)]
        new_clients_cost_per_new_client_eur = [
            self._safe_div(new_clients_cost_per_new_client[i], eur_ron_rate) if eur_ron_rate not in {None, 0} else None
            for i in range(week_count)
        ]

        summary_gpt: list[float | None] = []
        for idx in range(week_count):
            if summary_aov[idx] is None or new_clients_cost_per_new_client[idx] is None:
                summary_gpt.append(None)
            else:
                summary_gpt.append(summary_aov[idx] - new_clients_cost_per_new_client[idx])

        summary_mer_net = [self._safe_div(summary_gross_profit[i], summary_cost[i]) for i in range(week_count)]
        summary_apps_per_sale = [self._safe_div(summary_apps[i], summary_sales[i]) for i in range(week_count)]
        summary_apps_per_approved = [self._safe_div(summary_apps[i], summary_approved[i]) for i in range(week_count)]
        summary_approved_per_sale = [self._safe_div(summary_approved[i], summary_sales[i]) for i in range(week_count)]

        def additive(values: list[float | None]) -> float | None:
            return round(sum(self._to_float(item) for item in values if item is not None), 4)

        cost_h = additive(summary_cost)
        revenue_h = additive(summary_revenue)
        sales_h = additive(summary_sales)
        leads_h = additive(summary_leads)
        apps_h = additive(summary_apps)
        approved_h = additive(summary_approved)
        cogs_h = self._sum_history_nullable(cogs)
        has_missing_cogs = any(item is None for item in cogs)
        gross_h = None if cogs_h is None or has_missing_cogs else revenue_h - cogs_h

        summary_rows = [
            self._build_row(weeks=weeks, row_key="cost", label="Cost", value_kind="currency_display", weekly_values=summary_cost, currency_code=display_currency, history_value=cost_h, dependencies=["auto_metrics.cost_total"]),
            self._build_row(weeks=weeks, row_key="avg_daily_spend", label="Cheltuială medie zilnică", value_kind="currency_display", weekly_values=summary_avg_daily_spend, currency_code=display_currency, history_value=self._safe_div(cost_h, float(week_count)) if week_count > 0 else None, dependencies=["summary.cost"]),
            self._build_row(weeks=weeks, row_key="revenue", label="Venit", value_kind="currency_display", weekly_values=summary_revenue, currency_code=display_currency, history_value=revenue_h, dependencies=["manual_metrics.google_revenue_manual", "manual_metrics.meta_revenue_manual", "manual_metrics.tiktok_revenue_manual"]),
            self._build_row(weeks=weeks, row_key="revenue_target_per_day", label="Venit Țintă / Zi", value_kind="currency_display", weekly_values=summary_revenue_target_per_day, currency_code=display_currency, history_value=self._safe_div(revenue_h, float(week_count)) if week_count > 0 else None, dependencies=["summary.revenue"]),
            self._build_row(weeks=weeks, row_key="sales", label="Vânzări", value_kind="integer", weekly_values=summary_sales, history_value=sales_h, dependencies=["manual_metrics.google_sales_manual", "manual_metrics.meta_sales_manual", "manual_metrics.tiktok_sales_manual"]),
            self._build_row(weeks=weeks, row_key="aov", label="AOV", value_kind="currency_display", weekly_values=summary_aov, currency_code=display_currency, history_value=self._safe_div(revenue_h, sales_h), dependencies=["summary.revenue", "summary.sales"]),
            self._build_row(weeks=weeks, row_key="leads", label="Lead-uri", value_kind="integer", weekly_values=summary_leads, history_value=leads_h, dependencies=["auto_metrics.total_leads"]),
            self._build_row(weeks=weeks, row_key="cpa_leads", label="CPA", value_kind="currency_display", weekly_values=summary_cpa_leads, currency_code=display_currency, history_value=self._safe_div(cost_h, leads_h), dependencies=["summary.cost", "summary.leads"]),
            self._build_row(weeks=weeks, row_key="applications", label=custom_label_1, value_kind="integer", weekly_values=summary_apps, history_value=apps_h, dependencies=["auto_metrics.applications"]),
            self._build_row(weeks=weeks, row_key="cpa_applications", label="CPA", value_kind="currency_display", weekly_values=summary_cpa_apps, currency_code=display_currency, history_value=self._safe_div(cost_h, apps_h), dependencies=["summary.cost", "summary.applications"]),
            self._build_row(weeks=weeks, row_key="approved_applications", label=custom_label_2, value_kind="integer", weekly_values=summary_approved, history_value=approved_h, dependencies=["auto_metrics.approved_applications"]),
            self._build_row(weeks=weeks, row_key="cpa_approved_applications", label="CPA", value_kind="currency_display", weekly_values=summary_cpa_approved, currency_code=display_currency, history_value=self._safe_div(cost_h, approved_h), dependencies=["summary.cost", "summary.approved_applications"]),
            self._build_row(weeks=weeks, row_key="cost_vs_revenue", label="Cost vs Venit", value_kind="percent_ratio", weekly_values=summary_cost_vs_revenue, history_value=self._safe_div(cost_h, revenue_h), dependencies=["summary.cost", "summary.revenue"]),
            self._build_row(weeks=weeks, row_key="mer", label="MER", value_kind="decimal", weekly_values=summary_mer, history_value=self._safe_div(revenue_h, cost_h), dependencies=["summary.revenue", "summary.cost"]),
            self._build_row(weeks=weeks, row_key="mer_net", label="MER NET", value_kind="decimal", weekly_values=summary_mer_net, history_value=self._safe_div(gross_h, cost_h) if gross_h is not None else None, dependencies=["summary.gross_profit", "summary.cost"]),
            self._build_row(weeks=weeks, row_key="weekly_cogs_taxes", label="Total COGS + Taxe", value_kind="currency_ron", weekly_values=cogs, history_value=cogs_h, dependencies=["manual_metrics.weekly_cogs_taxes"], is_manual_input_row=True),
            self._build_row(weeks=weeks, row_key="gross_profit", label="Profit Brut", value_kind="currency_display", weekly_values=summary_gross_profit, currency_code=display_currency, history_value=gross_h, dependencies=["summary.revenue", "summary.weekly_cogs_taxes"]),
            self._build_row(weeks=weeks, row_key="gpt", label="GPT", value_kind="currency_display", weekly_values=summary_gpt, currency_code=display_currency, history_value=(self._safe_div(revenue_h, sales_h) - self._safe_div(cost_h, sales_h)) if self._safe_div(revenue_h, sales_h) is not None and self._safe_div(cost_h, sales_h) is not None else None, dependencies=["summary.aov", "new_clients.cost_per_new_client"]),
            self._build_row(weeks=weeks, row_key="profit_contribution", label="Contribuție profit", value_kind="currency_display", weekly_values=summary_profit_contribution, currency_code=display_currency, history_value=(gross_h - cost_h) if gross_h is not None else None, dependencies=["summary.gross_profit", "summary.cost"]),
            self._build_row(weeks=weeks, row_key="applications_per_sale", label=f"{custom_label_1} / Vânzări", value_kind="decimal", weekly_values=summary_apps_per_sale, history_value=self._safe_div(apps_h, sales_h), dependencies=["summary.applications", "summary.sales"]),
            self._build_row(weeks=weeks, row_key="applications_per_approved_application", label=f"{custom_label_1} / {custom_label_2}", value_kind="decimal", weekly_values=summary_apps_per_approved, history_value=self._safe_div(apps_h, approved_h), dependencies=["summary.applications", "summary.approved_applications"]),
            self._build_row(weeks=weeks, row_key="approved_applications_per_sale", label=f"{custom_label_2} / Vânzări", value_kind="decimal", weekly_values=summary_approved_per_sale, history_value=self._safe_div(approved_h, sales_h), dependencies=["summary.approved_applications", "summary.sales"]),
        ]

        def platform_rows(prefix: str, label_prefix: str, cost_values: list[float | None], leads_values: list[float | None], sales_values: list[float | None], revenue_values: list[float | None]) -> list[dict[str, object]]:
            cpa_values = [self._safe_div(self._to_float(cost_values[i]), self._to_float(leads_values[i])) for i in range(week_count)]
            ncac_values = [self._safe_div(self._to_float(cost_values[i]), self._to_float(sales_values[i])) for i in range(week_count)]
            ncac_eur_values = [self._safe_div(ncac_values[i], eur_ron_rate) if eur_ron_rate not in {None, 0} else None for i in range(week_count)]
            cost_h_local = additive(cost_values)
            leads_h_local = additive(leads_values)
            sales_h_local = additive(sales_values)
            revenue_h_local = self._sum_history_nullable(revenue_values)
            return [
                self._build_row(weeks=weeks, row_key="cost", label="Cost", value_kind="currency_display", weekly_values=[self._to_float(v) for v in cost_values], currency_code=display_currency, history_value=cost_h_local, dependencies=[f"auto_metrics.cost_{prefix}"]),
                self._build_row(weeks=weeks, row_key="leads_manual", label="Lead-uri", value_kind="integer", weekly_values=leads_values, history_value=leads_h_local, dependencies=[f"manual_metrics.{prefix}_leads_manual"], is_manual_input_row=True),
                self._build_row(weeks=weeks, row_key="cpa", label="CPA", value_kind="currency_display", weekly_values=cpa_values, currency_code=display_currency, history_value=self._safe_div(cost_h_local, leads_h_local), dependencies=["cost", "leads_manual"]),
                self._build_row(weeks=weeks, row_key="sales_manual", label="Vânzări", value_kind="integer", weekly_values=sales_values, history_value=sales_h_local, dependencies=[f"manual_metrics.{prefix}_sales_manual"], is_manual_input_row=True),
                self._build_row(weeks=weeks, row_key="revenue_manual", label="Val. Vânzare", value_kind="currency_display", weekly_values=revenue_values, currency_code=display_currency, history_value=revenue_h_local, dependencies=[f"manual_metrics.{prefix}_revenue_manual"], is_manual_input_row=True),
                self._build_row(weeks=weeks, row_key="ncac", label="nCAC", value_kind="currency_display", weekly_values=ncac_values, currency_code=display_currency, history_value=self._safe_div(cost_h_local, sales_h_local), dependencies=["cost", "sales_manual"]),
                self._build_row(weeks=weeks, row_key="ncac_eur", label="nCAC EUR", value_kind="currency_eur", weekly_values=ncac_eur_values, currency_code="EUR", history_value=(self._safe_div(self._safe_div(cost_h_local, sales_h_local), eur_ron_rate) if eur_ron_rate not in {None, 0} else None), dependencies=["ncac", "eur_ron_rate"], requires_eur_ron_rate=True),
            ]

        new_clients_rows = [
            self._build_row(weeks=weeks, row_key="combined_spend", label="Cheltuieli Google + Meta + TikTok", value_kind="currency_display", weekly_values=new_clients_combined_spend, currency_code=display_currency, history_value=cost_h, dependencies=["summary.cost"]),
            self._build_row(weeks=weeks, row_key="cost_per_new_client", label="Cost per Client Nou", value_kind="currency_display", weekly_values=new_clients_cost_per_new_client, currency_code=display_currency, history_value=self._safe_div(cost_h, sales_h), dependencies=["new_clients.combined_spend", "summary.sales"]),
            self._build_row(weeks=weeks, row_key="cost_per_new_client_eur", label="Cost per Client Nou EUR", value_kind="currency_eur", weekly_values=new_clients_cost_per_new_client_eur, currency_code="EUR", history_value=(self._safe_div(self._safe_div(cost_h, sales_h), eur_ron_rate) if eur_ron_rate not in {None, 0} else None), dependencies=["new_clients.cost_per_new_client", "eur_ron_rate"], requires_eur_ron_rate=True),
        ]

        google_rows = platform_rows("google", "Google", auto_cost_google, g_leads, g_sales, g_revenue)
        meta_rows = platform_rows("meta", "Meta", auto_cost_meta, m_leads, m_sales, m_revenue)
        tiktok_rows = platform_rows("tiktok", "TikTok", auto_cost_tiktok, t_leads, t_sales, t_revenue)

        summary_rows_with_wow = self._insert_wow_rows(
            weeks=weeks,
            rows=summary_rows,
            source_row_keys={
                "cost",
                "avg_daily_spend",
                "revenue",
                "sales",
                "aov",
                "leads",
                "cpa_leads",
                "applications",
                "cpa_applications",
                "approved_applications",
                "cpa_approved_applications",
            },
        )
        google_rows_with_wow = self._insert_wow_rows(
            weeks=weeks,
            rows=google_rows,
            source_row_keys={"cost", "leads_manual", "cpa", "sales_manual", "revenue_manual"},
        )
        meta_rows_with_wow = self._insert_wow_rows(
            weeks=weeks,
            rows=meta_rows,
            source_row_keys={"cost", "leads_manual", "cpa", "sales_manual", "revenue_manual"},
        )
        tiktok_rows_with_wow = self._insert_wow_rows(
            weeks=weeks,
            rows=tiktok_rows,
            source_row_keys={"cost", "leads_manual", "cpa", "sales_manual", "revenue_manual"},
        )

        sections: list[dict[str, object]] = [
            {"key": "summary", "label": "Rezumat", "rows": summary_rows_with_wow},
            {"key": "new_clients", "label": "Clienti Noi", "rows": new_clients_rows},
            {"key": "google_spend", "label": "Cheltuieli Google", "rows": google_rows_with_wow},
            {"key": "meta_spend", "label": "Cheltuieli Meta", "rows": meta_rows_with_wow},
            {"key": "tiktok_spend", "label": "Cheltuieli TikTok", "rows": tiktok_rows_with_wow},
        ]

        for source_key in sorted(source_weekly_metrics.keys()):
            if source_key in {"google_ads", "meta_ads", "tiktok_ads"}:
                continue
            source_payload = source_weekly_metrics.get(source_key) or {}
            source_label = str(source_payload.get("label") or source_key)
            source_rows = platform_rows(
                source_key,
                source_label,
                source_metric_values(source_key, "cost_values"),
                source_metric_values(source_key, "leads_values"),
                source_metric_values(source_key, "sales_values"),
                source_metric_values(source_key, "revenue_values"),
            )
            sections.append(
                {
                    "key": f"{source_key}_spend",
                    "label": f"Cheltuieli {source_label}",
                    "rows": self._insert_wow_rows(
                        weeks=weeks,
                        rows=source_rows,
                        source_row_keys={"cost", "leads_manual", "cpa", "sales_manual", "revenue_manual"},
                    ),
                }
            )
        return sections

    def upsert_weekly_manual_values(
        self,
        *,
        client_id: int,
        granularity: WorksheetGranularity,
        anchor_date: date,
        entries: list[dict[str, object]],
    ) -> dict[str, object]:
        normalized_granularity = self._validate_granularity(granularity=granularity)
        period_start, period_end = self._resolve_calendar_period(granularity=normalized_granularity, anchor_date=anchor_date)
        weeks = self._build_visible_weeks(period_start=period_start, period_end=period_end)
        visible_week_starts = {str(item["week_start"]) for item in weeks}

        normalized_entries: list[tuple[str, str, float | None]] = []
        for raw_entry in entries:
            week_start_raw = raw_entry.get("week_start")
            if isinstance(week_start_raw, date):
                week_start = week_start_raw
            elif isinstance(week_start_raw, str):
                try:
                    week_start = date.fromisoformat(week_start_raw)
                except ValueError as exc:
                    raise ValueError("week_start must be a valid ISO date") from exc
            else:
                raise ValueError("week_start is required")

            if week_start.weekday() != 0:
                raise ValueError("week_start must be a Monday")
            if week_start.isoformat() not in visible_week_starts:
                raise ValueError("week_start must be inside visible weeks for the requested scope")

            field_key = str(raw_entry.get("field_key") or "").strip()
            if field_key not in _MANUAL_FIELD_KEYS:
                raise ValueError("field_key is not supported")

            value = raw_entry.get("value")
            if value is None:
                normalized_value: float | None = None
            elif isinstance(value, (int, float)):
                normalized_value = float(value)
            else:
                raise ValueError("value must be numeric or null")

            normalized_entries.append((week_start.isoformat(), field_key, normalized_value))

        if self._is_test_mode():
            with self._memory_lock:
                for week_start_iso, field_key, value in normalized_entries:
                    key = (int(client_id), week_start_iso, field_key)
                    if value is None:
                        self._memory_manual_values.pop(key, None)
                    else:
                        self._memory_manual_values[key] = value
        else:
            self._ensure_schema()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    for week_start_iso, field_key, value in normalized_entries:
                        if value is None:
                            cur.execute(
                                """
                                DELETE FROM media_tracker_weekly_manual_values
                                WHERE client_id = %s AND week_start = %s AND field_key = %s
                                """,
                                (int(client_id), week_start_iso, field_key),
                            )
                        else:
                            cur.execute(
                                """
                                INSERT INTO media_tracker_weekly_manual_values (client_id, week_start, field_key, value)
                                VALUES (%s, %s, %s, %s)
                                ON CONFLICT (client_id, week_start, field_key)
                                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                                """,
                                (int(client_id), week_start_iso, field_key, value),
                            )
                conn.commit()

        return self.build_weekly_worksheet_foundation(
            granularity=normalized_granularity,
            anchor_date=anchor_date,
            client_id=client_id,
        )

    def upsert_scope_eur_ron_rate(
        self,
        *,
        client_id: int,
        granularity: WorksheetGranularity,
        anchor_date: date,
        value: float | None,
    ) -> dict[str, object]:
        normalized_granularity = self._validate_granularity(granularity=granularity)
        period_start, period_end = self._resolve_calendar_period(granularity=normalized_granularity, anchor_date=anchor_date)

        normalized_value: float | None
        if value is None:
            normalized_value = None
        elif isinstance(value, (int, float)):
            normalized_value = float(value)
        else:
            raise ValueError("value must be numeric or null")

        if self._is_test_mode():
            key = (int(client_id), normalized_granularity, period_start.isoformat(), period_end.isoformat())
            with self._memory_lock:
                if normalized_value is None:
                    self._memory_scope_rates.pop(key, None)
                else:
                    self._memory_scope_rates[key] = normalized_value
        else:
            self._ensure_schema()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    if normalized_value is None:
                        cur.execute(
                            """
                            DELETE FROM media_tracker_scope_fx_rates
                            WHERE client_id = %s AND granularity = %s AND period_start = %s AND period_end = %s
                            """,
                            (int(client_id), normalized_granularity, period_start, period_end),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO media_tracker_scope_fx_rates (client_id, granularity, period_start, period_end, value)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (client_id, granularity, period_start, period_end)
                            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                            """,
                            (int(client_id), normalized_granularity, period_start, period_end, normalized_value),
                        )
                conn.commit()

        return self.build_weekly_worksheet_foundation(
            granularity=normalized_granularity,
            anchor_date=anchor_date,
            client_id=client_id,
        )

    def build_weekly_worksheet_foundation(self, *, granularity: WorksheetGranularity, anchor_date: date, client_id: int) -> dict[str, object]:
        normalized_granularity = self._validate_granularity(granularity=granularity)
        period_start, period_end = self._resolve_calendar_period(granularity=normalized_granularity, anchor_date=anchor_date)
        weeks = self._build_visible_weeks(period_start=period_start, period_end=period_end)

        first_week_start = date.fromisoformat(str(weeks[0]["week_start"])) if len(weeks) > 0 else period_start
        last_week_end = date.fromisoformat(str(weeks[-1]["week_end"])) if len(weeks) > 0 else period_end

        lead_table = media_buying_store.get_lead_table(client_id=int(client_id), date_from=first_week_start, date_to=last_week_end)
        lead_meta = lead_table.get("meta") if isinstance(lead_table.get("meta"), dict) else {}
        display_currency = str(lead_meta.get("display_currency") or "USD").strip().upper() or "USD"
        display_currency_source = str(lead_meta.get("display_currency_source") or "safe_fallback")
        custom_label_1 = self._normalized_label(lead_meta.get("custom_label_1"), fallback="Custom Value 1")
        custom_label_2 = self._normalized_label(lead_meta.get("custom_label_2"), fallback="Custom Value 2")
        day_rows = lead_table.get("days") if isinstance(lead_table.get("days"), list) else []
        auto_metrics = self._build_auto_metrics(weeks=weeks, day_rows=day_rows)

        if hasattr(media_buying_store, "get_source_daily_rows"):
            source_daily_rows = media_buying_store.get_source_daily_rows(
                client_id=int(client_id),
                date_from=first_week_start,
                date_to=last_week_end,
            )
        else:
            source_daily_rows = []

        if hasattr(media_buying_store, "_list_data_layer_source_daily_business_rows"):
            data_layer_source_daily_rows = media_buying_store._list_data_layer_source_daily_business_rows(  # type: ignore[attr-defined]
                client_id=int(client_id),
                date_from=first_week_start,
                date_to=last_week_end,
            )
        else:
            data_layer_source_daily_rows = []

        week_starts = [date.fromisoformat(str(week["week_start"])) for week in weeks]
        manual_values_map = self._list_manual_values_for_weeks(client_id=int(client_id), week_starts=week_starts)
        manual_metrics = self._build_manual_metrics(weeks=weeks, manual_values_map=manual_values_map)

        week_ranges = [
            (idx, date.fromisoformat(str(week["week_start"])), date.fromisoformat(str(week["week_end"])))
            for idx, week in enumerate(weeks)
        ]
        week_has_data_layer_rows = [False for _ in weeks]

        source_weekly_metrics: dict[str, dict[str, object]] = {}
        for source_row in source_daily_rows:
            raw_date = source_row.get("date")
            if not isinstance(raw_date, str):
                continue
            try:
                row_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            source_key = str(source_row.get("source") or "unknown")
            source_payload = source_weekly_metrics.setdefault(
                source_key,
                {
                    "label": str(source_row.get("source_label") or source_key),
                    "cost_values": [0.0 for _ in weeks],
                    "leads_values": [0.0 for _ in weeks],
                    "sales_values": [0.0 for _ in weeks],
                    "revenue_values": [0.0 for _ in weeks],
                    "cogs_values": [0.0 for _ in weeks],
                },
            )
            for idx, week_start, week_end in week_ranges:
                if not (week_start <= row_date <= week_end):
                    continue
                source_payload["cost_values"][idx] = float(source_payload["cost_values"][idx]) + float(source_row.get("cost_amount") or 0.0)

        for source_row in data_layer_source_daily_rows:
            raw_date = source_row.get("date")
            if not isinstance(raw_date, date):
                continue
            source_key = str(source_row.get("source") or "unknown")
            source_payload = source_weekly_metrics.setdefault(
                source_key,
                {
                    "label": str(source_row.get("source_label") or source_key),
                    "cost_values": [0.0 for _ in weeks],
                    "leads_values": [0.0 for _ in weeks],
                    "sales_values": [0.0 for _ in weeks],
                    "revenue_values": [0.0 for _ in weeks],
                    "cogs_values": [0.0 for _ in weeks],
                },
            )
            for idx, week_start, week_end in week_ranges:
                if not (week_start <= raw_date <= week_end):
                    continue
                week_has_data_layer_rows[idx] = True
                source_payload["leads_values"][idx] = float(source_payload["leads_values"][idx]) + float(source_row.get("leads") or 0.0)
                source_payload["sales_values"][idx] = float(source_payload["sales_values"][idx]) + float(source_row.get("sales_count") or 0.0)
                source_payload["revenue_values"][idx] = float(source_payload["revenue_values"][idx]) + float(source_row.get("custom_value_4_amount_ron") or 0.0)
                source_payload["cogs_values"][idx] = float(source_payload["cogs_values"][idx]) + float(source_row.get("cogs_amount_ron") or 0.0)

        legacy_manual_source_map = {
            "google": "google_ads",
            "meta": "meta_ads",
            "tiktok": "tiktok_ads",
        }
        for idx in range(len(weeks)):
            if week_has_data_layer_rows[idx]:
                continue
            for legacy_prefix, source_key in legacy_manual_source_map.items():
                source_payload = source_weekly_metrics.setdefault(
                    source_key,
                    {
                        "label": source_key,
                        "cost_values": [0.0 for _ in weeks],
                        "leads_values": [0.0 for _ in weeks],
                        "sales_values": [0.0 for _ in weeks],
                        "revenue_values": [0.0 for _ in weeks],
                        "cogs_values": [0.0 for _ in weeks],
                    },
                )
                source_payload["leads_values"][idx] = float((manual_metrics.get(f"{legacy_prefix}_leads_manual") or {}).get("weekly_values", [{}])[idx].get("value") or 0.0)
                source_payload["sales_values"][idx] = float((manual_metrics.get(f"{legacy_prefix}_sales_manual") or {}).get("weekly_values", [{}])[idx].get("value") or 0.0)
                source_payload["revenue_values"][idx] = float((manual_metrics.get(f"{legacy_prefix}_revenue_manual") or {}).get("weekly_values", [{}])[idx].get("value") or 0.0)

        weekly_cogs_values: list[float | None] = []
        for idx, week in enumerate(weeks):
            if week_has_data_layer_rows[idx]:
                cogs_value = round(
                    sum(float((source_weekly_metrics.get(source_key) or {}).get("cogs_values", [0.0] * len(weeks))[idx]) for source_key in source_weekly_metrics.keys()),
                    4,
                )
                weekly_cogs_values.append(cogs_value)
            else:
                legacy_cogs = (manual_metrics.get("weekly_cogs_taxes") or {}).get("weekly_values", [{}])[idx].get("value")
                weekly_cogs_values.append(float(legacy_cogs) if isinstance(legacy_cogs, (int, float)) else None)
            manual_metrics["weekly_cogs_taxes"]["weekly_values"][idx] = {
                "week_start": week["week_start"],
                "week_end": week["week_end"],
                "value": weekly_cogs_values[idx],
            }
        manual_metrics["weekly_cogs_taxes"]["history_value"] = round(sum(self._to_float(item) for item in weekly_cogs_values if item is not None), 2)

        for legacy_prefix, source_key in legacy_manual_source_map.items():
            for field_suffix, value_key in (("leads_manual", "leads_values"), ("sales_manual", "sales_values"), ("revenue_manual", "revenue_values")):
                metric_key = f"{legacy_prefix}_{field_suffix}"
                values = list((source_weekly_metrics.get(source_key) or {}).get(value_key, [0.0 for _ in weeks]))
                manual_metrics[metric_key] = {
                    "aggregation": "sum",
                    "history_value": round(sum(float(item or 0.0) for item in values), 2),
                    "weekly_values": [
                        {"week_start": week["week_start"], "week_end": week["week_end"], "value": float(values[idx] or 0.0)}
                        for idx, week in enumerate(weeks)
                    ],
                }

        eur_ron_rate = self._get_scope_eur_ron_rate(
            client_id=client_id,
            granularity=normalized_granularity,
            period_start=period_start,
            period_end=period_end,
        )

        return {
            "requested_scope": {
                "granularity": normalized_granularity,
                "anchor_date": anchor_date.isoformat(),
            },
            "resolved_period": {
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
            "history": {
                "visible_week_count": len(weeks),
                "definition": "aggregate_of_all_visible_week_columns",
            },
            "weeks": weeks,
            "display_currency": display_currency,
            "display_currency_source": display_currency_source,
            "eur_ron_rate": eur_ron_rate,
            "eur_ron_rate_scope": {
                "granularity": normalized_granularity,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
            "manual_field_definitions": self._build_manual_field_definitions(),
            "manual_metrics": manual_metrics,
            "auto_metrics": auto_metrics,
            "sections": self._build_computed_sections(
                weeks=weeks,
                auto_metrics=auto_metrics,
                manual_metrics=manual_metrics,
                source_weekly_metrics=source_weekly_metrics,
                eur_ron_rate=eur_ron_rate,
                display_currency=display_currency,
                custom_label_1=custom_label_1,
                custom_label_2=custom_label_2,
            ),
        }

    def build_overview_charts_payload(self, *, granularity: WorksheetGranularity, anchor_date: date, client_id: int) -> dict[str, object]:
        foundation = self.build_weekly_worksheet_foundation(
            granularity=granularity,
            anchor_date=anchor_date,
            client_id=client_id,
        )

        weeks = foundation.get("weeks") if isinstance(foundation.get("weeks"), list) else []
        sections = foundation.get("sections") if isinstance(foundation.get("sections"), list) else []

        def get_section(section_key: str) -> dict[str, object]:
            for section in sections:
                if isinstance(section, dict) and str(section.get("key")) == section_key:
                    return section
            return {}

        def get_row(section_key: str, row_key: str) -> dict[str, object]:
            section = get_section(section_key)
            rows = section.get("rows") if isinstance(section.get("rows"), list) else []
            for row in rows:
                if isinstance(row, dict) and str(row.get("row_key")) == row_key:
                    return row
            return {}

        def values_from_row(section_key: str, row_key: str) -> list[float]:
            row = get_row(section_key, row_key)
            weekly_values = row.get("weekly_values") if isinstance(row.get("weekly_values"), list) else []
            normalized: list[float] = []
            for idx in range(len(weeks)):
                weekly_value = weekly_values[idx] if idx < len(weekly_values) and isinstance(weekly_values[idx], dict) else {}
                raw = weekly_value.get("value")
                normalized.append(float(raw) if isinstance(raw, (int, float)) else 0.0)
            return normalized

        summary_revenue = values_from_row("summary", "revenue")
        summary_sales = values_from_row("summary", "sales")
        summary_leads = values_from_row("summary", "leads")
        summary_custom_1 = values_from_row("summary", "applications")
        summary_custom_2 = values_from_row("summary", "approved_applications")
        summary_gross_profit = values_from_row("summary", "gross_profit")
        summary_cogs_taxes = values_from_row("summary", "weekly_cogs_taxes")
        new_clients_cost_per_client = values_from_row("new_clients", "cost_per_new_client")

        google_cost = values_from_row("google_spend", "cost")
        meta_cost = values_from_row("meta_spend", "cost")
        tiktok_cost = values_from_row("tiktok_spend", "cost")
        google_revenue = values_from_row("google_spend", "revenue_manual")
        meta_revenue = values_from_row("meta_spend", "revenue_manual")
        tiktok_revenue = values_from_row("tiktok_spend", "revenue_manual")
        google_sales = values_from_row("google_spend", "sales_manual")
        meta_sales = values_from_row("meta_spend", "sales_manual")
        tiktok_sales = values_from_row("tiktok_spend", "sales_manual")
        google_leads = values_from_row("google_spend", "leads_manual")
        meta_leads = values_from_row("meta_spend", "leads_manual")
        tiktok_leads = values_from_row("tiktok_spend", "leads_manual")
        google_cpa = values_from_row("google_spend", "cpa")
        meta_cpa = values_from_row("meta_spend", "cpa")
        tiktok_cpa = values_from_row("tiktok_spend", "cpa")
        google_ncac = values_from_row("google_spend", "ncac")
        meta_ncac = values_from_row("meta_spend", "ncac")
        tiktok_ncac = values_from_row("tiktok_spend", "ncac")

        scope_weeks: list[dict[str, object]] = []
        sales_total_trend: list[dict[str, object]] = []
        sales_channel_composition: list[dict[str, object]] = []
        sales_efficiency_scatter: list[dict[str, object]] = []
        financial_cost_efficiency: list[dict[str, object]] = []
        financial_mix_vs_revenue: list[dict[str, object]] = []
        financial_conversion_funnel: list[dict[str, object]] = []
        financial_profitability: list[dict[str, object]] = []
        financial_cost_per_new_client: list[dict[str, object]] = []

        for idx, week in enumerate(weeks):
            week_start = str((week if isinstance(week, dict) else {}).get("week_start") or "")
            week_end = str((week if isinstance(week, dict) else {}).get("week_end") or "")
            label = str((week if isinstance(week, dict) else {}).get("label") or week_start)
            scope_weeks.append({"week_start": week_start, "week_end": week_end, "label": label})
            sales_total_trend.append({"week_start": week_start, "week_end": week_end, "label": label, "revenue_total": summary_revenue[idx] if idx < len(summary_revenue) else 0.0})
            sales_channel_composition.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "google": google_revenue[idx] if idx < len(google_revenue) else 0.0,
                    "meta": meta_revenue[idx] if idx < len(meta_revenue) else 0.0,
                    "tiktok": tiktok_revenue[idx] if idx < len(tiktok_revenue) else 0.0,
                }
            )
            financial_cost_efficiency.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "google_cpa": google_cpa[idx] if idx < len(google_cpa) else 0.0,
                    "google_ncac": google_ncac[idx] if idx < len(google_ncac) else 0.0,
                    "meta_cpa": meta_cpa[idx] if idx < len(meta_cpa) else 0.0,
                    "meta_ncac": meta_ncac[idx] if idx < len(meta_ncac) else 0.0,
                    "tiktok_cpa": tiktok_cpa[idx] if idx < len(tiktok_cpa) else 0.0,
                    "tiktok_ncac": tiktok_ncac[idx] if idx < len(tiktok_ncac) else 0.0,
                }
            )
            financial_mix_vs_revenue.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "google_cost": google_cost[idx] if idx < len(google_cost) else 0.0,
                    "meta_cost": meta_cost[idx] if idx < len(meta_cost) else 0.0,
                    "tiktok_cost": tiktok_cost[idx] if idx < len(tiktok_cost) else 0.0,
                    "revenue_total": summary_revenue[idx] if idx < len(summary_revenue) else 0.0,
                }
            )
            financial_conversion_funnel.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "leads": summary_leads[idx] if idx < len(summary_leads) else 0.0,
                    "custom_value_1_count": summary_custom_1[idx] if idx < len(summary_custom_1) else 0.0,
                    "custom_value_2_count": summary_custom_2[idx] if idx < len(summary_custom_2) else 0.0,
                    "sales": summary_sales[idx] if idx < len(summary_sales) else 0.0,
                }
            )
            financial_profitability.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "gross_profit": summary_gross_profit[idx] if idx < len(summary_gross_profit) else 0.0,
                    "cogs_taxes": summary_cogs_taxes[idx] if idx < len(summary_cogs_taxes) else 0.0,
                }
            )
            financial_cost_per_new_client.append(
                {
                    "week_start": week_start,
                    "week_end": week_end,
                    "label": label,
                    "cost_per_new_client": new_clients_cost_per_client[idx] if idx < len(new_clients_cost_per_client) else 0.0,
                }
            )

            channel_points = (
                ("google", google_cost, google_revenue),
                ("meta", meta_cost, meta_revenue),
                ("tiktok", tiktok_cost, tiktok_revenue),
            )
            for channel, costs, sold_values in channel_points:
                sales_efficiency_scatter.append(
                    {
                        "week_start": week_start,
                        "week_end": week_end,
                        "label": label,
                        "channel": channel,
                        "cost": costs[idx] if idx < len(costs) else 0.0,
                        "sold_value": sold_values[idx] if idx < len(sold_values) else 0.0,
                    }
                )

        channel_performance: list[dict[str, object]] = []
        for channel, cpa_values, leads_values, sales_values in (
            ("google", google_cpa, google_leads, google_sales),
            ("meta", meta_cpa, meta_leads, meta_sales),
            ("tiktok", tiktok_cpa, tiktok_leads, tiktok_sales),
        ):
            total_sales = round(sum(sales_values), 4)
            total_leads = round(sum(leads_values), 4)
            conversion_rate = self._safe_div(total_sales, total_leads)
            avg_cpa = self._safe_div(sum(cpa_values), float(len(cpa_values))) if len(cpa_values) > 0 else None
            channel_performance.append(
                {
                    "channel": channel,
                    "cpa": round(float(avg_cpa or 0.0), 4),
                    "conversion_rate": round(float(conversion_rate or 0.0), 6),
                    "sales_volume": total_sales,
                }
            )

        config = media_buying_store.get_config(client_id=int(client_id))
        custom_labels = {
            "custom_label_1": self._normalized_label((config or {}).get("custom_label_1"), fallback="Custom Value 1"),
            "custom_label_2": self._normalized_label((config or {}).get("custom_label_2"), fallback="Custom Value 2"),
            "custom_label_3": self._normalized_label((config or {}).get("custom_label_3"), fallback="Custom Value 3"),
            "custom_label_4": self._normalized_label((config or {}).get("custom_label_4"), fallback="Custom Value 4"),
            "custom_label_5": self._normalized_label((config or {}).get("custom_label_5"), fallback="Custom Value 5"),
        }

        return {
            "requested_scope": foundation.get("requested_scope"),
            "resolved_period": foundation.get("resolved_period"),
            "display_currency": foundation.get("display_currency"),
            "eur_ron_rate": foundation.get("eur_ron_rate"),
            "weeks": scope_weeks,
            "custom_labels": custom_labels,
            "formulas": {
                "ncac": "cost / sales",
                "conversion_rate": "sales / leads",
                "sales_efficiency_scatter": "x=cost, y=sold_value",
            },
            "sales": {
                "total_sales_trend": sales_total_trend,
                "channel_sales_composition": sales_channel_composition,
                "sales_efficiency_scatter": sales_efficiency_scatter,
            },
            "financial": {
                "cost_efficiency": financial_cost_efficiency,
                "spend_vs_revenue_mix": financial_mix_vs_revenue,
                "conversion_funnel": financial_conversion_funnel,
                "profitability": financial_profitability,
                "cost_per_new_client": financial_cost_per_new_client,
                "channel_performance": channel_performance,
            },
        }


media_tracker_worksheet_service = MediaTrackerWorksheetService()
