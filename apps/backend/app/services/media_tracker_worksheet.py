from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from app.services.media_buying_store import media_buying_store

WorksheetGranularity = Literal["month", "quarter", "year"]


class MediaTrackerWorksheetService:
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

        for key, payload in metrics.items():
            payload["history_value"] = round(sum(self._to_float(item.get("value")) for item in payload["weekly_values"]), 2)

        return metrics

    def build_weekly_worksheet_foundation(self, *, granularity: WorksheetGranularity, anchor_date: date, client_id: int) -> dict[str, object]:
        normalized_granularity = str(granularity).strip().lower()
        if normalized_granularity not in {"month", "quarter", "year"}:
            raise ValueError("granularity must be one of: month, quarter, year")

        period_start, period_end = self._resolve_calendar_period(granularity=normalized_granularity, anchor_date=anchor_date)
        weeks = self._build_visible_weeks(period_start=period_start, period_end=period_end)

        first_week_start = date.fromisoformat(str(weeks[0]["week_start"])) if len(weeks) > 0 else period_start
        last_week_end = date.fromisoformat(str(weeks[-1]["week_end"])) if len(weeks) > 0 else period_end

        lead_table = media_buying_store.get_lead_table(client_id=int(client_id), date_from=first_week_start, date_to=last_week_end)
        day_rows = lead_table.get("days") if isinstance(lead_table.get("days"), list) else []
        auto_metrics = self._build_auto_metrics(weeks=weeks, day_rows=day_rows)

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
            "eur_ron_rate": None,
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
