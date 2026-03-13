from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

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

    def build_weekly_worksheet_foundation(self, *, granularity: WorksheetGranularity, anchor_date: date) -> dict[str, object]:
        normalized_granularity = str(granularity).strip().lower()
        if normalized_granularity not in {"month", "quarter", "year"}:
            raise ValueError("granularity must be one of: month, quarter, year")

        period_start, period_end = self._resolve_calendar_period(granularity=normalized_granularity, anchor_date=anchor_date)
        weeks = self._build_visible_weeks(period_start=period_start, period_end=period_end)

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
            "sections": [
                {"key": "summary", "label": "Rezumat", "rows": []},
                {"key": "new_clients", "label": "Clienti Noi", "rows": []},
                {"key": "google_spend", "label": "Google Spend", "rows": []},
                {"key": "meta_spend", "label": "Meta Spend", "rows": []},
                {"key": "tiktok_spend", "label": "TikTok Spend", "rows": []},
            ],
        }


media_tracker_worksheet_service = MediaTrackerWorksheetService()
