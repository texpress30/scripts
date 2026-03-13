from datetime import date

from app.services.media_tracker_worksheet import media_tracker_worksheet_service


def test_month_scope_resolution_and_visible_weeks_are_monday_sunday_oldest_first() -> None:
    payload = media_tracker_worksheet_service.build_weekly_worksheet_foundation(
        granularity="month",
        anchor_date=date(2026, 3, 15),
    )

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
    payload = media_tracker_worksheet_service.build_weekly_worksheet_foundation(
        granularity="quarter",
        anchor_date=date(2026, 5, 10),
    )

    assert payload["resolved_period"] == {"period_start": "2026-04-01", "period_end": "2026-06-30"}
    weeks = payload["weeks"]
    assert weeks[0]["week_start"] == "2026-03-30"
    assert weeks[0]["week_end"] == "2026-04-05"
    assert weeks[0]["intersects_period_start"] is True

    assert weeks[-1]["week_start"] == "2026-06-29"
    assert weeks[-1]["week_end"] == "2026-07-05"
    assert weeks[-1]["intersects_period_end"] is True


def test_year_scope_resolution_and_visible_week_count_matches_history() -> None:
    payload = media_tracker_worksheet_service.build_weekly_worksheet_foundation(
        granularity="year",
        anchor_date=date(2026, 8, 19),
    )

    assert payload["resolved_period"] == {"period_start": "2026-01-01", "period_end": "2026-12-31"}
    weeks = payload["weeks"]
    assert payload["history"]["visible_week_count"] == len(weeks)

    assert weeks[0]["week_start"] == "2025-12-29"
    assert weeks[0]["week_end"] == "2026-01-04"
    assert weeks[0]["intersects_period_start"] is True

    assert weeks[-1]["week_start"] == "2026-12-28"
    assert weeks[-1]["week_end"] == "2027-01-03"
    assert weeks[-1]["intersects_period_end"] is True
