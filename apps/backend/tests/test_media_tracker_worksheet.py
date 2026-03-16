import os
from datetime import date

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_AUTH_SECRET", "test-secret")

from app.services import media_tracker_worksheet as worksheet_module
from app.services.media_buying_store import MediaBuyingStore


class _MediaBuyingStoreStub:
    def __init__(self, days: list[dict[str, object]], *, display_currency: str = "USD", display_currency_source: str = "agency_client_currency") -> None:
        self.days = days
        self.display_currency = display_currency
        self.display_currency_source = display_currency_source

    def get_lead_table(self, *, client_id: int, date_from: date, date_to: date) -> dict[str, object]:
        return {
            "days": self.days,
            "meta": {
                "client_id": client_id,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "display_currency": self.display_currency,
                "display_currency_source": self.display_currency_source,
            },
        }


def _set_store(days: list[dict[str, object]], *, display_currency: str = "USD", display_currency_source: str = "agency_client_currency"):

    original = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = _MediaBuyingStoreStub(days=days, display_currency=display_currency, display_currency_source=display_currency_source)
    worksheet_module.media_tracker_worksheet_service._is_test_mode = lambda: True
    worksheet_module.media_tracker_worksheet_service.reset_test_state()
    return original


def test_month_scope_resolution_and_visible_weeks_are_monday_sunday_oldest_first() -> None:
    original_store = _set_store(days=[])
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
    assert payload["eur_ron_rate_scope"] == {"granularity": "month", "period_start": "2026-03-01", "period_end": "2026-03-31"}
    assert payload["display_currency"] == "USD"
    assert payload["display_currency_source"] == "agency_client_currency"

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
    original_store = _set_store(days=[])
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
    original_store = _set_store(days=[])
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
    original_store = _set_store(days=days)
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


def test_approved_applications_uses_custom_value_2_not_sales_count_and_ratios_follow_new_source() -> None:
    days = [
        {
            "date": "2026-03-02",
            "cost_total": 100,
            "cost_google": 30,
            "cost_meta": 40,
            "cost_tiktok": 30,
            "total_leads": 10,
            "custom_value_1_count": 8,
            "custom_value_2_count": 2,
            "sales_count": 99,
        },
    ]
    original_store = _set_store(days=days)
    service = worksheet_module.media_tracker_worksheet_service
    try:
        payload = service.upsert_weekly_manual_values(
            client_id=334,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 4},
            ],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    auto = payload["auto_metrics"]
    assert auto["approved_applications"]["source_field"] == "custom_value_2_count"
    approved_week = next(item for item in auto["approved_applications"]["weekly_values"] if item["week_start"] == "2026-03-02")
    assert approved_week["value"] == 2.0
    assert auto["approved_applications"]["history_value"] == 2.0

    summary = _row_map(payload, "summary")
    apps_week = next(item for item in summary["applications"]["weekly_values"] if item["week_start"] == "2026-03-02")
    approved_summary_week = next(item for item in summary["approved_applications"]["weekly_values"] if item["week_start"] == "2026-03-02")
    apps_per_sale_week = next(item for item in summary["applications_per_sale"]["weekly_values"] if item["week_start"] == "2026-03-02")
    apps_per_approved_week = next(item for item in summary["applications_per_approved_application"]["weekly_values"] if item["week_start"] == "2026-03-02")
    approved_per_sale_week = next(item for item in summary["approved_applications_per_sale"]["weekly_values"] if item["week_start"] == "2026-03-02")

    assert apps_week["value"] == 8.0
    assert approved_summary_week["value"] == 2.0
    assert apps_per_sale_week["value"] == 2.0
    assert apps_per_approved_week["value"] == 4.0
    assert approved_per_sale_week["value"] == 0.5


def test_approved_applications_custom_value_2_is_null_safe() -> None:
    days = [
        {
            "date": "2026-03-11",
            "cost_total": 5.0,
            "cost_google": 2.0,
            "cost_meta": 2.0,
            "cost_tiktok": 1.0,
            "total_leads": 2,
            "custom_value_1_count": 1,
            "custom_value_2_count": None,
            "sales_count": 7,
        },
    ]
    original_store = _set_store(days=days)
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="month",
            anchor_date=date(2026, 3, 15),
            client_id=335,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    auto = payload["auto_metrics"]
    approved_week = next(item for item in auto["approved_applications"]["weekly_values"] if item["week_start"] == "2026-03-09")
    assert approved_week["value"] == 0.0
    assert auto["approved_applications"]["history_value"] == 0.0

def test_weekly_auto_metrics_are_null_safe() -> None:
    days = [
        {"date": "2026-03-10", "cost_total": None, "cost_google": 1.5, "cost_meta": None, "cost_tiktok": 2.5, "total_leads": None, "custom_value_1_count": None, "sales_count": 1},
        {"date": "2026-03-11", "cost_total": 5.0, "cost_google": None, "cost_meta": 3.0, "cost_tiktok": None, "total_leads": 2, "custom_value_1_count": 1, "sales_count": None},
    ]
    original_store = _set_store(days=days)
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


def test_manual_upsert_is_idempotent_and_readback_history_aligns() -> None:
    original_store = _set_store(days=[])
    try:
        service = worksheet_module.media_tracker_worksheet_service
        service.upsert_weekly_manual_values(
            client_id=44,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[{"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 12}],
        )
        payload = service.upsert_weekly_manual_values(
            client_id=44,
            granularity="month",
            anchor_date=date(2026, 3, 20),
            entries=[{"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 14}],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    weekly_values = payload["manual_metrics"]["google_leads_manual"]["weekly_values"]
    target = next(item for item in weekly_values if item["week_start"] == "2026-03-02")
    assert target["value"] == 14.0
    assert payload["manual_metrics"]["google_leads_manual"]["history_value"] == 14.0
    assert [item["week_start"] for item in weekly_values] == [item["week_start"] for item in payload["weeks"]]


def test_manual_validation_invalid_field_non_monday_and_outside_scope() -> None:
    original_store = _set_store(days=[])
    service = worksheet_module.media_tracker_worksheet_service
    try:
        try:
            service.upsert_weekly_manual_values(
                client_id=55,
                granularity="month",
                anchor_date=date(2026, 3, 15),
                entries=[{"week_start": "2026-03-02", "field_key": "bad_field", "value": 1}],
            )
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "field_key" in str(exc)

        try:
            service.upsert_weekly_manual_values(
                client_id=55,
                granularity="month",
                anchor_date=date(2026, 3, 15),
                entries=[{"week_start": "2026-03-03", "field_key": "google_leads_manual", "value": 1}],
            )
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "Monday" in str(exc)

        try:
            service.upsert_weekly_manual_values(
                client_id=55,
                granularity="month",
                anchor_date=date(2026, 3, 15),
                entries=[{"week_start": "2026-04-13", "field_key": "google_leads_manual", "value": 1}],
            )
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "visible weeks" in str(exc)
    finally:
        worksheet_module.media_buying_store = original_store


def test_manual_weekly_value_reused_across_scopes_when_visible() -> None:
    original_store = _set_store(days=[])
    service = worksheet_module.media_tracker_worksheet_service
    try:
        service.upsert_weekly_manual_values(
            client_id=66,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[{"week_start": "2026-03-02", "field_key": "meta_sales_manual", "value": 5}],
        )
        quarter_payload = service.build_weekly_worksheet_foundation(
            granularity="quarter",
            anchor_date=date(2026, 3, 1),
            client_id=66,
        )
        year_payload = service.build_weekly_worksheet_foundation(
            granularity="year",
            anchor_date=date(2026, 11, 1),
            client_id=66,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    q_value = next(item for item in quarter_payload["manual_metrics"]["meta_sales_manual"]["weekly_values"] if item["week_start"] == "2026-03-02")
    y_value = next(item for item in year_payload["manual_metrics"]["meta_sales_manual"]["weekly_values"] if item["week_start"] == "2026-03-02")
    assert q_value["value"] == 5.0
    assert y_value["value"] == 5.0


def test_eur_ron_rate_scope_upsert_readback_and_clear() -> None:
    original_store = _set_store(days=[])
    service = worksheet_module.media_tracker_worksheet_service
    try:
        service.upsert_scope_eur_ron_rate(
            client_id=77,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            value=5.09,
        )
        payload = service.upsert_scope_eur_ron_rate(
            client_id=77,
            granularity="month",
            anchor_date=date(2026, 3, 1),
            value=5.11,
        )
        assert payload["eur_ron_rate"] == 5.11

        cleared = service.upsert_scope_eur_ron_rate(
            client_id=77,
            granularity="month",
            anchor_date=date(2026, 3, 30),
            value=None,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert cleared["eur_ron_rate"] is None


def test_manual_value_clear_semantics_delete_stored_value() -> None:
    original_store = _set_store(days=[])
    service = worksheet_module.media_tracker_worksheet_service
    try:
        service.upsert_weekly_manual_values(
            client_id=88,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[{"week_start": "2026-03-09", "field_key": "weekly_cogs_taxes", "value": 1000}],
        )
        payload = service.upsert_weekly_manual_values(
            client_id=88,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[{"week_start": "2026-03-09", "field_key": "weekly_cogs_taxes", "value": None}],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    target = next(item for item in payload["manual_metrics"]["weekly_cogs_taxes"]["weekly_values"] if item["week_start"] == "2026-03-09")
    assert target["value"] is None
    assert payload["manual_metrics"]["weekly_cogs_taxes"]["history_value"] == 0.0



def test_display_currency_metadata_follows_media_buying_source_for_multiple_clients() -> None:
    service = worksheet_module.media_tracker_worksheet_service

    original_store = _set_store(days=[], display_currency="USD")
    try:
        usd_payload = service.build_weekly_worksheet_foundation(granularity="month", anchor_date=date(2026, 3, 15), client_id=1)
    finally:
        worksheet_module.media_buying_store = original_store

    original_store = _set_store(days=[], display_currency="RON")
    try:
        ron_payload = service.build_weekly_worksheet_foundation(granularity="month", anchor_date=date(2026, 3, 15), client_id=2)
    finally:
        worksheet_module.media_buying_store = original_store

    original_store = _set_store(days=[], display_currency="EUR")
    try:
        eur_payload = service.build_weekly_worksheet_foundation(granularity="month", anchor_date=date(2026, 3, 15), client_id=3)
    finally:
        worksheet_module.media_buying_store = original_store

    assert usd_payload["display_currency"] == "USD"
    assert ron_payload["display_currency"] == "RON"
    assert eur_payload["display_currency"] == "EUR"


def test_primary_monetary_rows_use_display_currency_metadata_and_eur_rows_stay_eur() -> None:
    days = [
        {"date": "2026-03-02", "cost_total": 100, "cost_google": 30, "cost_meta": 40, "cost_tiktok": 30, "total_leads": 14, "custom_value_1_count": 7, "sales_count": 3},
    ]
    original_store = _set_store(days=days, display_currency="USD")
    service = worksheet_module.media_tracker_worksheet_service
    try:
        payload = service.upsert_weekly_manual_values(
            client_id=220,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_revenue_manual", "value": 100},
                {"week_start": "2026-03-02", "field_key": "meta_revenue_manual", "value": 200},
                {"week_start": "2026-03-02", "field_key": "tiktok_revenue_manual", "value": 300},
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 2},
                {"week_start": "2026-03-02", "field_key": "meta_sales_manual", "value": 2},
                {"week_start": "2026-03-02", "field_key": "tiktok_sales_manual", "value": 2},
                {"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 5},
                {"week_start": "2026-03-02", "field_key": "meta_leads_manual", "value": 5},
                {"week_start": "2026-03-02", "field_key": "tiktok_leads_manual", "value": 5},
            ],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert payload["display_currency"] == "USD"
    summary = _row_map(payload, "summary")
    google = _row_map(payload, "google_spend")
    new_clients = _row_map(payload, "new_clients")

    for key in (
        "cost",
        "avg_daily_spend",
        "revenue",
        "revenue_target_per_day",
        "aov",
        "cpa_leads",
        "cpa_applications",
        "cpa_approved_applications",
        "gross_profit",
        "gpt",
        "profit_contribution",
    ):
        assert summary[key]["value_kind"] == "currency_display"
        assert summary[key]["currency_code"] == "USD"

    for key in ("cost", "cpa", "revenue_manual", "ncac"):
        assert google[key]["value_kind"] == "currency_display"
        assert google[key]["currency_code"] == "USD"

    assert new_clients["combined_spend"]["value_kind"] == "currency_display"
    assert new_clients["combined_spend"]["currency_code"] == "USD"
    assert new_clients["cost_per_new_client"]["value_kind"] == "currency_display"
    assert new_clients["cost_per_new_client"]["currency_code"] == "USD"

    assert new_clients["cost_per_new_client_eur"]["value_kind"] == "currency_eur"
    assert new_clients["cost_per_new_client_eur"]["currency_code"] == "EUR"


def test_eur_rows_are_safe_null_when_no_eur_ron_rate() -> None:
    days = [
        {"date": "2026-03-02", "cost_total": 100, "cost_google": 30, "cost_meta": 40, "cost_tiktok": 30, "total_leads": 14, "custom_value_1_count": 7, "sales_count": 3},
    ]
    original_store = _set_store(days=days, display_currency="USD")
    service = worksheet_module.media_tracker_worksheet_service
    try:
        payload = service.upsert_weekly_manual_values(
            client_id=221,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 2},
                {"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 5},
            ],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    new_clients = _row_map(payload, "new_clients")
    google = _row_map(payload, "google_spend")

    assert all(item["value"] is None for item in new_clients["cost_per_new_client_eur"]["weekly_values"])
    assert all(item["value"] is None for item in google["ncac_eur"]["weekly_values"])


def _row_map(payload: dict[str, object], section_key: str) -> dict[str, dict[str, object]]:
    section = next(item for item in payload["sections"] if item["key"] == section_key)
    return {row["row_key"]: row for row in section["rows"]}


def test_formula_engine_core_rows_and_ratio_history_recompute() -> None:
    days = [
        {"date": "2026-03-02", "cost_total": 70, "cost_google": 30, "cost_meta": 20, "cost_tiktok": 20, "total_leads": 14, "custom_value_1_count": 7, "sales_count": 3},
        {"date": "2026-03-09", "cost_total": 140, "cost_google": 60, "cost_meta": 40, "cost_tiktok": 40, "total_leads": 28, "custom_value_1_count": 14, "sales_count": 6},
    ]
    original_store = _set_store(days=days)
    service = worksheet_module.media_tracker_worksheet_service
    try:
        service.upsert_weekly_manual_values(
            client_id=99,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_revenue_manual", "value": 1000},
                {"week_start": "2026-03-02", "field_key": "meta_revenue_manual", "value": 500},
                {"week_start": "2026-03-02", "field_key": "tiktok_revenue_manual", "value": 500},
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 10},
                {"week_start": "2026-03-02", "field_key": "meta_sales_manual", "value": 5},
                {"week_start": "2026-03-02", "field_key": "tiktok_sales_manual", "value": 5},
                {"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 50},
                {"week_start": "2026-03-02", "field_key": "meta_leads_manual", "value": 30},
                {"week_start": "2026-03-02", "field_key": "tiktok_leads_manual", "value": 20},
                {"week_start": "2026-03-02", "field_key": "weekly_cogs_taxes", "value": 600},
                {"week_start": "2026-03-09", "field_key": "google_revenue_manual", "value": 500},
                {"week_start": "2026-03-09", "field_key": "meta_revenue_manual", "value": 250},
                {"week_start": "2026-03-09", "field_key": "tiktok_revenue_manual", "value": 250},
                {"week_start": "2026-03-09", "field_key": "google_sales_manual", "value": 5},
                {"week_start": "2026-03-09", "field_key": "meta_sales_manual", "value": 2},
                {"week_start": "2026-03-09", "field_key": "tiktok_sales_manual", "value": 3},
                {"week_start": "2026-03-09", "field_key": "google_leads_manual", "value": 25},
                {"week_start": "2026-03-09", "field_key": "meta_leads_manual", "value": 15},
                {"week_start": "2026-03-09", "field_key": "tiktok_leads_manual", "value": 10},
                {"week_start": "2026-03-09", "field_key": "weekly_cogs_taxes", "value": 300},
            ],
        )
        payload = service.upsert_scope_eur_ron_rate(
            client_id=99,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            value=5.0,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    summary = _row_map(payload, "summary")
    new_clients = _row_map(payload, "new_clients")
    google = _row_map(payload, "google_spend")

    assert summary["cpa_leads"]["label"] == "CPA"
    assert summary["cpa_applications"]["label"] == "CPA"
    assert summary["cpa_approved_applications"]["label"] == "CPA"

    cost_week = next(x for x in summary["cost"]["weekly_values"] if x["week_start"] == "2026-03-02")
    assert cost_week["value"] == 70.0

    avg_daily_week = next(x for x in summary["avg_daily_spend"]["weekly_values"] if x["week_start"] == "2026-03-02")
    assert avg_daily_week["value"] == 10.0

    revenue_week = next(x for x in summary["revenue"]["weekly_values"] if x["week_start"] == "2026-03-02")
    assert revenue_week["value"] == 2000.0

    aov_history = summary["aov"]["history_value"]
    assert aov_history == 100.0

    cost_vs_revenue_history = summary["cost_vs_revenue"]["history_value"]
    assert round(cost_vs_revenue_history, 4) == round((210.0 / 3000.0), 4)

    cost_per_new_client = new_clients["cost_per_new_client"]["history_value"]
    assert cost_per_new_client == 7.0
    assert new_clients["cost_per_new_client_eur"]["history_value"] == 1.4

    google_ncac_week = next(x for x in google["ncac"]["weekly_values"] if x["week_start"] == "2026-03-02")
    assert google_ncac_week["value"] == 3.0


def test_formula_engine_null_handling_for_cogs_and_eur_rate() -> None:
    days = [{"date": "2026-03-02", "cost_total": 70, "cost_google": 30, "cost_meta": 20, "cost_tiktok": 20, "total_leads": 14, "custom_value_1_count": 7, "sales_count": 3}]
    original_store = _set_store(days=days)
    service = worksheet_module.media_tracker_worksheet_service
    try:
        payload = service.upsert_weekly_manual_values(
            client_id=109,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_revenue_manual", "value": 100},
                {"week_start": "2026-03-02", "field_key": "meta_revenue_manual", "value": 100},
                {"week_start": "2026-03-02", "field_key": "tiktok_revenue_manual", "value": 100},
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 3},
            ],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    summary = _row_map(payload, "summary")
    new_clients = _row_map(payload, "new_clients")

    gross_week = next(x for x in summary["gross_profit"]["weekly_values"] if x["week_start"] == "2026-03-02")
    assert gross_week["value"] is None
    assert summary["gross_profit"]["history_value"] is None
    assert summary["mer_net"]["history_value"] is None
    assert summary["profit_contribution"]["history_value"] is None
    assert new_clients["cost_per_new_client_eur"]["history_value"] is None


def test_week_over_week_comparison_rows_insertion_and_rules() -> None:
    days = [
        {"date": "2026-03-02", "cost_total": 100, "cost_google": 30, "cost_meta": 40, "cost_tiktok": 30, "total_leads": 14, "custom_value_1_count": 7, "sales_count": 3},
        {"date": "2026-03-09", "cost_total": 200, "cost_google": 40, "cost_meta": 80, "cost_tiktok": 80, "total_leads": 21, "custom_value_1_count": 14, "sales_count": 6},
        {"date": "2026-03-16", "cost_total": 75, "cost_google": 10, "cost_meta": 30, "cost_tiktok": 35, "total_leads": 7, "custom_value_1_count": 3, "sales_count": 2},
    ]
    original_store = _set_store(days=days)
    service = worksheet_module.media_tracker_worksheet_service
    try:
        payload = service.upsert_weekly_manual_values(
            client_id=120,
            granularity="month",
            anchor_date=date(2026, 3, 20),
            entries=[
                {"week_start": "2026-03-02", "field_key": "google_revenue_manual", "value": 200},
                {"week_start": "2026-03-09", "field_key": "google_revenue_manual", "value": 300},
                {"week_start": "2026-03-16", "field_key": "google_revenue_manual", "value": 300},
                {"week_start": "2026-03-02", "field_key": "meta_revenue_manual", "value": 100},
                {"week_start": "2026-03-09", "field_key": "meta_revenue_manual", "value": 0},
                {"week_start": "2026-03-02", "field_key": "tiktok_revenue_manual", "value": 50},
                {"week_start": "2026-03-09", "field_key": "tiktok_revenue_manual", "value": 75},
                {"week_start": "2026-03-16", "field_key": "tiktok_revenue_manual", "value": 50},
                {"week_start": "2026-03-02", "field_key": "google_sales_manual", "value": 2},
                {"week_start": "2026-03-09", "field_key": "google_sales_manual", "value": 4},
                {"week_start": "2026-03-16", "field_key": "google_sales_manual", "value": 3},
                {"week_start": "2026-03-02", "field_key": "meta_sales_manual", "value": 1},
                {"week_start": "2026-03-09", "field_key": "meta_sales_manual", "value": 1},
                {"week_start": "2026-03-16", "field_key": "meta_sales_manual", "value": 1},
                {"week_start": "2026-03-02", "field_key": "tiktok_sales_manual", "value": 1},
                {"week_start": "2026-03-09", "field_key": "tiktok_sales_manual", "value": 1},
                {"week_start": "2026-03-16", "field_key": "tiktok_sales_manual", "value": 0},
                {"week_start": "2026-03-02", "field_key": "google_leads_manual", "value": 10},
                {"week_start": "2026-03-09", "field_key": "google_leads_manual", "value": 20},
                {"week_start": "2026-03-16", "field_key": "google_leads_manual", "value": 5},
                {"week_start": "2026-03-02", "field_key": "meta_leads_manual", "value": 10},
                {"week_start": "2026-03-09", "field_key": "meta_leads_manual", "value": 0},
                {"week_start": "2026-03-16", "field_key": "meta_leads_manual", "value": 5},
                {"week_start": "2026-03-09", "field_key": "tiktok_leads_manual", "value": 10},
            ],
        )
    finally:
        worksheet_module.media_buying_store = original_store

    weeks = payload["weeks"]
    summary_section = next(item for item in payload["sections"] if item["key"] == "summary")
    summary_keys = [row["row_key"] for row in summary_section["rows"]]
    assert summary_keys[summary_keys.index("cost") + 1] == "cost_wow_pct"
    assert summary_keys[summary_keys.index("approved_applications") + 1] == "approved_applications_wow_pct"
    assert "revenue_target_per_day_wow_pct" not in summary_keys
    assert "gross_profit_wow_pct" not in summary_keys

    google_section = next(item for item in payload["sections"] if item["key"] == "google_spend")
    google_keys = [row["row_key"] for row in google_section["rows"]]
    assert google_keys[google_keys.index("cost") + 1] == "cost_wow_pct"
    assert google_keys[google_keys.index("revenue_manual") + 1] == "revenue_manual_wow_pct"
    assert "ncac_wow_pct" not in google_keys
    assert "ncac_eur_wow_pct" not in google_keys

    for section_key in ("meta_spend", "tiktok_spend"):
        section = next(item for item in payload["sections"] if item["key"] == section_key)
        keys = [row["row_key"] for row in section["rows"]]
        assert "cost_wow_pct" in keys
        assert "revenue_manual_wow_pct" in keys
        assert "ncac_wow_pct" not in keys

    new_clients_section = next(item for item in payload["sections"] if item["key"] == "new_clients")
    assert all(not str(row["row_key"]).endswith("_wow_pct") for row in new_clients_section["rows"])

    summary = _row_map(payload, "summary")
    cost_wow = summary["cost_wow_pct"]
    assert cost_wow["history_value"] is None
    assert cost_wow["value_kind"] == "percent_ratio"
    assert cost_wow["source_kind"] == "comparison"
    assert cost_wow["compares_row_key"] == "cost"
    assert [item["week_start"] for item in cost_wow["weekly_values"]] == [item["week_start"] for item in weeks]

    values_by_week = {item["week_start"]: item["value"] for item in cost_wow["weekly_values"]}
    assert values_by_week["2026-03-02"] is None
    assert values_by_week["2026-03-09"] == 1.0
    assert values_by_week["2026-03-16"] == -0.625

    meta = _row_map(payload, "meta_spend")
    meta_revenue_wow = {item["week_start"]: item["value"] for item in meta["revenue_manual_wow_pct"]["weekly_values"]}
    assert meta_revenue_wow["2026-03-16"] is None

    tiktok = _row_map(payload, "tiktok_spend")
    tiktok_leads_wow = {item["week_start"]: item["value"] for item in tiktok["leads_manual_wow_pct"]["weekly_values"]}
    assert tiktok_leads_wow["2026-03-02"] is None
    assert tiktok_leads_wow["2026-03-16"] is None

    summary_revenue = summary["revenue"]
    first_week_revenue = next(x for x in summary_revenue["weekly_values"] if x["week_start"] == "2026-03-02")
    assert first_week_revenue["value"] == 350.0


def test_worksheet_foundation_works_with_real_media_buying_store_automated_sql_placeholder_contract() -> None:
    class _Cursor:
        def execute(self, query, params=None):
            query_text = str(query)
            placeholder_count = query_text.count("%s")
            provided_count = len(tuple(params or ()))
            if placeholder_count != provided_count:
                raise AssertionError(f"placeholder mismatch: {placeholder_count} vs {provided_count}")

        def fetchall(self):
            return [(date(2026, 3, 11), "google_ads", "USD", 100.0)]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    store = MediaBuyingStore()
    store._ensure_schema = lambda: None
    store._connect = lambda: _Conn()
    store.get_config = lambda **kwargs: {"client_id": kwargs["client_id"], "template_type": "lead", "display_currency": "USD"}
    store._resolve_client_template_type = lambda **kwargs: "lead"
    store.list_lead_daily_manual_values = lambda **kwargs: []
    store._normalize_money_to_display_currency = lambda **kwargs: float(kwargs["amount"])

    original_store = worksheet_module.media_buying_store
    worksheet_module.media_buying_store = store
    worksheet_module.media_tracker_worksheet_service._is_test_mode = lambda: True
    worksheet_module.media_tracker_worksheet_service.reset_test_state()
    try:
        payload = worksheet_module.media_tracker_worksheet_service.build_weekly_worksheet_foundation(
            granularity="month",
            anchor_date=date(2026, 3, 15),
            client_id=11,
        )
    finally:
        worksheet_module.media_buying_store = original_store

    assert payload["requested_scope"]["granularity"] == "month"
    assert payload["history"]["visible_week_count"] == len(payload["weeks"])
