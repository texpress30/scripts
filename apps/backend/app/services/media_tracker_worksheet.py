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
    {"field_key": "google_leads_manual", "label": "Google Leads (Manual)", "section_key": "google_spend"},
    {"field_key": "google_sales_manual", "label": "Google Sales (Manual)", "section_key": "google_spend"},
    {"field_key": "google_revenue_manual", "label": "Google Revenue (Manual)", "section_key": "google_spend"},
    {"field_key": "meta_leads_manual", "label": "Meta Leads (Manual)", "section_key": "meta_spend"},
    {"field_key": "meta_sales_manual", "label": "Meta Sales (Manual)", "section_key": "meta_spend"},
    {"field_key": "meta_revenue_manual", "label": "Meta Revenue (Manual)", "section_key": "meta_spend"},
    {"field_key": "tiktok_leads_manual", "label": "TikTok Leads (Manual)", "section_key": "tiktok_spend"},
    {"field_key": "tiktok_sales_manual", "label": "TikTok Sales (Manual)", "section_key": "tiktok_spend"},
    {"field_key": "tiktok_revenue_manual", "label": "TikTok Revenue (Manual)", "section_key": "tiktok_spend"},
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
            "approved_applications": {"aggregation": "sum", "source_field": "sales_count", "history_value": 0.0, "weekly_values": []},
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
                "approved_applications": round(sum(self._to_float(row.get("sales_count")) for _, row in in_week_rows), 2),
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
            with self._memory_lock:
                return {
                    (week_start_iso, field_key): value
                    for (stored_client_id, week_start_iso, field_key), value in self._memory_manual_values.items()
                    if int(stored_client_id) == int(client_id) and date.fromisoformat(week_start_iso) in set(week_starts)
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
        day_rows = lead_table.get("days") if isinstance(lead_table.get("days"), list) else []
        auto_metrics = self._build_auto_metrics(weeks=weeks, day_rows=day_rows)

        week_starts = [date.fromisoformat(str(item["week_start"])) for item in weeks]
        manual_values_map = self._list_manual_values_for_weeks(client_id=client_id, week_starts=week_starts)
        manual_metrics = self._build_manual_metrics(weeks=weeks, manual_values_map=manual_values_map)
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
            "eur_ron_rate": eur_ron_rate,
            "eur_ron_rate_scope": {
                "granularity": normalized_granularity,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
            "manual_field_definitions": self._build_manual_field_definitions(),
            "manual_metrics": manual_metrics,
            "auto_metrics": auto_metrics,
            "sections": [
                {"key": "summary", "label": "Rezumat", "rows": []},
                {"key": "new_clients", "label": "Clienti Noi", "rows": []},
                {"key": "google_spend", "label": "Google Spend", "rows": []},
                {"key": "meta_spend", "label": "Meta Spend", "rows": []},
                {"key": "tiktok_spend", "label": "TikTok Spend", "rows": []},
            ],
        }


media_tracker_worksheet_service = MediaTrackerWorksheetService()
