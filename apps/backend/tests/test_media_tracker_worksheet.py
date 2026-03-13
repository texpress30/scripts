from datetime import date

from app.services import media_tracker_worksheet as worksheet_module


class _MediaBuyingStoreStub:
    def __init__(self, days: list[dict[str, object]]) -> None:
        self.days = days

    def get_lead_table(self, *, client_id: int, date_from: date, date_to: date) -> dict[str, object]:
        return {"days": self.days, "meta": {"client_id": client_id, "date_from": date_from.isoformat(), "date_to": date_to.isoformat()}}


def test_month_scope_resolution_and_visible_weeks_are_monday_sunday_oldest_first() -> None:
    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=[])
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="month",
            anchor_date=date(2026, 3, 15),
            client_id=11,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert payload["requested_scope"]["granularity"] == "month"
    assert payload["resolved_period"] == {"period_start": "2026-03-01", "period_end": "2026-03-31"}

    weeks = payload["weeks"]
    assert len(weeks) == 6
    assert payload["history"]["visible_week_count"] == len(weeks)

    assert weeks[0]["week_start"] == "2026-02-23"
    assert weeks[0]["week_end"] == "2026-03-01"
    assert weeks[0]["is_first_visible_week"] is True
    assert weeks[0]["intersects_period_start"] is True
    assert weeks[0]["intersects_period_end"] is False

    assert weeks[-1]["week_start"] == "2026-03-30"
    assert weeks[-1]["week_end"] == "2026-04-05"
    assert weeks[-1]["intersects_period_start"] is False
    assert weeks[-1]["intersects_period_end"] is True

    starts = [item["week_start"] for item in weeks]
    assert starts == sorted(starts)


def test_quarter_scope_resolution_and_boundary_intersections() -> None:
    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=[])
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="quarter",
            anchor_date=date(2026, 5, 10),
            client_id=11,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert payload["resolved_period"] == {"period_start": "2026-04-01", "period_end": "2026-06-30"}
    weeks = payload["weeks"]
    assert weeks[0]["week_start"] == "2026-03-30"
    assert weeks[0]["week_end"] == "2026-04-05"
    assert weeks[0]["intersects_period_start"] is True

    assert weeks[-1]["week_start"] == "2026-06-29"
    assert weeks[-1]["week_end"] == "2026-07-05"
    assert weeks[-1]["intersects_period_end"] is True


def test_year_scope_resolution_and_visible_week_count_matches_history() -> None:
    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=[])
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="year",
            anchor_date=date(2026, 8, 19),
            client_id=11,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert payload["resolved_period"] == {"period_start": "2026-01-01", "period_end": "2026-12-31"}
    weeks = payload["weeks"]
    assert payload["history"]["visible_week_count"] == len(weeks)

    assert weeks[0]["week_start"] == "2025-12-29"
    assert weeks[0]["week_end"] == "2026-01-04"
    assert weeks[0]["intersects_period_start"] is True

    assert weeks[-1]["week_start"] == "2026-12-28"
    assert weeks[-1]["week_end"] == "2027-01-03"
    assert weeks[-1]["intersects_period_end"] is True


def test_weekly_auto_metrics_aggregate_full_visible_boundary_weeks_and_history_alignment() -> None:
    days = [
        {"date": "2026-02-23", "cost_total": 10, "cost_google": 3, "cost_meta": 4, "cost_tiktok": 3, "total_leads": 5, "custom_value_1_count": 2, "sales_count": 1},
        {"date": "2026-03-01", "cost_total": 15, "cost_google": 5, "cost_meta": 5, "cost_tiktok": 5, "total_leads": 6, "custom_value_1_count": 3, "sales_count": 1},
        {"date": "2026-03-03", "cost_total": 20, "cost_google": 8, "cost_meta": 7, "cost_tiktok": 5, "total_leads": 4, "custom_value_1_count": 2, "sales_count": 1},
        {"date": "2026-03-30", "cost_total": 7, "cost_google": 2, "cost_meta": 3, "cost_tiktok": 2, "total_leads": 1, "custom_value_1_count": 1, "sales_count": 0},
        {"date": "2026-04-05", "cost_total": 9, "cost_google": 3, "cost_meta": 3, "cost_tiktok": 3, "total_leads": 2, "custom_value_1_count": 1, "sales_count": 1},
    ]
    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=days)
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="month",
            anchor_date=date(2026, 3, 15),
            client_id=22,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    weeks = payload["weeks"]
    auto = payload["auto_metrics"]

    cost_total_weekly = auto["cost_total"]["weekly_values"]
    assert [x["week_start"] for x in cost_total_weekly] == [w["week_start"] for w in weeks]

    first_week = next(item for item in cost_total_weekly if item["week_start"] == "2026-02-23")
    assert first_week["value"] == 25.0

    last_week = next(item for item in cost_total_weekly if item["week_start"] == "2026-03-30")
    assert last_week["value"] == 16.0

    assert auto["cost_total"]["history_value"] == round(sum(item["value"] for item in cost_total_weekly), 2)
    assert auto["cost_google"]["history_value"] == round(sum(item["value"] for item in auto["cost_google"]["weekly_values"]), 2)
    assert auto["cost_meta"]["history_value"] == round(sum(item["value"] for item in auto["cost_meta"]["weekly_values"]), 2)
    assert auto["cost_tiktok"]["history_value"] == round(sum(item["value"] for item in auto["cost_tiktok"]["weekly_values"]), 2)

    assert auto["total_leads"]["history_value"] == round(sum(item["value"] for item in auto["total_leads"]["weekly_values"]), 2)
    assert auto["applications"]["history_value"] == round(sum(item["value"] for item in auto["applications"]["weekly_values"]), 2)
    assert auto["approved_applications"]["history_value"] == round(sum(item["value"] for item in auto["approved_applications"]["weekly_values"]), 2)


def test_weekly_auto_metrics_are_null_safe() -> None:
    days = [
        {"date": "2026-03-10", "cost_total": None, "cost_google": 1.5, "cost_meta": None, "cost_tiktok": 2.5, "total_leads": None, "custom_value_1_count": None, "sales_count": 1},
        {"date": "2026-03-11", "cost_total": 5.0, "cost_google": None, "cost_meta": 3.0, "cost_tiktok": None, "total_leads": 2, "custom_value_1_count": 1, "sales_count": None},
    ]
    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=days)
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="month",
            anchor_date=date(2026, 3, 15),
            client_id=33,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    week = next(item for item in payload["auto_metrics"]["cost_total"]["weekly_values"] if item["week_start"] == "2026-03-09")
    assert week["value"] == 5.0

    google_week = next(item for item in payload["auto_metrics"]["cost_google"]["weekly_values"] if item["week_start"] == "2026-03-09")
    assert google_week["value"] == 1.5

    apps_week = next(item for item in payload["auto_metrics"]["applications"]["weekly_values"] if item["week_start"] == "2026-03-09")
    assert apps_week["value"] == 1.0
