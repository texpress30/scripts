import os
import unittest
from datetime import date

from fastapi import HTTPException

from app.api import clients as clients_api
from app.schemas.client import (
    MediaBuyingConfigUpdateRequest,
    MediaBuyingLeadDailyValueUpsertRequest,
    MediaTrackerWorksheetManualValuesUpsertRequest,
    MediaTrackerWorksheetEurRonRateUpsertRequest,
)
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services import media_tracker_worksheet as worksheet_module


class ClientsMediaBuyingApiTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"

        self.original_is_test_mode = client_registry_service._is_test_mode
        client_registry_service._is_test_mode = lambda: True
        client_registry_service._clients = []
        client_registry_service._next_id = 1

        self.original_enforce = clients_api.enforce_action_scope
        clients_api.enforce_action_scope = lambda **kwargs: None

        self.user = AuthUser(email="owner@example.com", role="admin")
        self.client_id = int(client_registry_service.create_client(name="Client A", owner_email="owner@example.com")["id"])

        self.original_store = clients_api.media_buying_store

        class _StoreStub:
            def __init__(self):
                self.config = {
                    "client_id": 1,
                    "template_type": "lead",
                    "display_currency": "RON",
                    "custom_label_1": "Custom Value 1",
                    "custom_label_2": "Custom Value 2",
                    "custom_label_3": "Custom Value 3",
                    "custom_label_4": "Custom Value 4",
                    "custom_label_5": "Custom Value 5",
                    "custom_rate_label_1": "Custom Value Rate 1",
                    "custom_rate_label_2": "Custom Value Rate 2",
                    "custom_cost_label_1": "Cost Custom Value 1",
                    "custom_cost_label_2": "Cost Custom Value 2",
                    "visible_columns": ["date", "cost_total"],
                    "enabled": True,
                    "created_at": None,
                    "updated_at": None,
                }
                self.daily = []

            def get_config(self, *, client_id: int):
                cfg = dict(self.config)
                cfg["client_id"] = client_id
                return cfg

            def upsert_config(self, **kwargs):
                if kwargs.get("template_type") == "invalid":
                    raise ValueError("template_type must be one of: lead, ecommerce, programmatic")
                for key, value in kwargs.items():
                    if key in self.config and value is not None:
                        self.config[key] = value
                self.config["client_id"] = kwargs["client_id"]
                return dict(self.config)

            def list_lead_daily_manual_values(self, **kwargs):
                if kwargs["date_from"] > kwargs["date_to"]:
                    raise ValueError("date_from must be less than or equal to date_to")
                return [row for row in self.daily if kwargs["date_from"] <= date.fromisoformat(row["date"]) <= kwargs["date_to"]]

            def get_lead_table(self, **kwargs):
                if self.config.get("template_type") != "lead":
                    raise NotImplementedError("Media Buying table is implemented only for template_type=lead in this task")
                include_days = bool(kwargs.get("include_days", True))
                date_from = kwargs.get("date_from")
                date_to = kwargs.get("date_to")
                if date_from is not None and date_to is not None and date_from > date_to:
                    raise ValueError("date_from must be less than or equal to date_to")
                if date_from is None and date_to is None:
                    date_from = date(2026, 3, 11)
                    date_to = date(2026, 3, 11)
                month_payload = {"month": "2026-03", "totals": {"percent_change": None}, "days": [{"date": "2026-03-11"}]}
                if not include_days:
                    month_payload = {"month": "2026-03", "totals": {"percent_change": None}, "day_count": 1, "has_days": True}

                return {
                    "meta": {
                        "client_id": kwargs["client_id"],
                        "template_type": "lead",
                        "display_currency": "RON",
                        "custom_label_1": "Custom Value 1",
                        "custom_label_2": "Custom Value 2",
                        "custom_label_3": "Custom Value 3",
                        "custom_label_4": "Custom Value 4",
                        "custom_label_5": "Custom Value 5",
                        "custom_rate_label_1": "Custom Value Rate 1",
                        "custom_rate_label_2": "Custom Value Rate 2",
                        "custom_cost_label_1": "Cost Custom Value 1",
                        "custom_cost_label_2": "Cost Custom Value 2",
                        "visible_columns": ["date", "cost_total"],
                        "date_from": date_from.isoformat(),
                        "date_to": date_to.isoformat(),
                        "effective_date_from": "2026-03-11",
                        "effective_date_to": "2026-03-11",
                        "earliest_data_date": "2026-03-11",
                        "latest_data_date": "2026-03-11",
                        "available_months": ["2026-03"],
                    },
                    "days": [{"date": "2026-03-11", "percent_change": None}] if include_days else [],
                    "months": [month_payload],
                }

            def get_lead_month_days(self, **kwargs):
                if kwargs["month_start"] != date(2026, 3, 1):
                    raise ValueError("month_start is outside available media buying range")
                return {
                    "meta": {"client_id": kwargs["client_id"], "display_currency": "RON", "display_currency_source": "agency_client_currency"},
                    "month_start": "2026-03-01",
                    "days": [{"date": "2026-03-11", "percent_change": None, "display_currency": "RON"}],
                }

            def get_source_daily_rows(self, **kwargs):
                return [
                    {"date": "2026-03-11", "source": "google_ads", "source_label": "Google", "cost_amount": 1200},
                    {"date": "2026-03-11", "source": "meta_ads", "source_label": "Meta", "cost_amount": 900},
                    {"date": "2026-03-11", "source": "tiktok_ads", "source_label": "TikTok", "cost_amount": 700},
                ]

            def _list_data_layer_source_daily_business_rows(self, **kwargs):
                return [
                    {"date": date(2026, 3, 11), "source": "google_ads", "source_label": "Google", "leads": 40, "sales_count": 10, "custom_value_4_amount_ron": 8000, "cogs_amount_ron": 2200},
                    {"date": date(2026, 3, 11), "source": "meta_ads", "source_label": "Meta", "leads": 30, "sales_count": 7, "custom_value_4_amount_ron": 5500, "cogs_amount_ron": 1800},
                    {"date": date(2026, 3, 11), "source": "tiktok_ads", "source_label": "TikTok", "leads": 20, "sales_count": 5, "custom_value_4_amount_ron": 4200, "cogs_amount_ron": 1300},
                ]

            def upsert_lead_daily_manual_value(self, **kwargs):
                if kwargs["leads"] < 0:
                    raise ValueError("leads must be an integer >= 0")
                payload = {
                    "client_id": kwargs["client_id"],
                    "date": kwargs["metric_date"].isoformat(),
                    "leads": kwargs["leads"],
                    "phones": kwargs["phones"],
                    "custom_value_1_count": kwargs["custom_value_1_count"],
                    "custom_value_2_count": kwargs["custom_value_2_count"],
                    "custom_value_3_amount_ron": float(kwargs["custom_value_3_amount_ron"]),
                    "custom_value_4_amount_ron": float(kwargs["custom_value_4_amount_ron"]),
                    "custom_value_5_amount_ron": float(kwargs["custom_value_5_amount_ron"]),
                    "sales_count": kwargs["sales_count"],
                    "created_at": None,
                    "updated_at": None,
                }
                self.daily = [row for row in self.daily if row["date"] != payload["date"]]
                self.daily.append(payload)
                return payload

        clients_api.media_buying_store = _StoreStub()
        self.original_worksheet_store = worksheet_module.media_buying_store
        worksheet_module.media_buying_store = clients_api.media_buying_store
        worksheet_module.media_tracker_worksheet_service.reset_test_state()

    def tearDown(self):
        clients_api.media_buying_store = self.original_store
        worksheet_module.media_buying_store = self.original_worksheet_store
        clients_api.enforce_action_scope = self.original_enforce
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_and_update_media_buying_config(self):
        cfg = clients_api.get_media_buying_config(client_id=self.client_id, user=self.user)
        self.assertEqual(cfg["template_type"], "lead")
        self.assertEqual(cfg["display_currency"], "RON")

        updated = clients_api.upsert_media_buying_config(
            client_id=self.client_id,
            payload=MediaBuyingConfigUpdateRequest(template_type="lead", custom_label_1="Leads calificate", custom_label_5="Refund", custom_rate_label_1="Rata 1", custom_cost_label_1="Cost CV1", visible_columns=["date", "cost_total", "leads"]),
            user=self.user,
        )

        self.assertEqual(updated["custom_label_1"], "Leads calificate")
        self.assertEqual(updated["custom_label_5"], "Refund")
        self.assertEqual(updated["custom_rate_label_1"], "Rata 1")
        self.assertEqual(updated["custom_cost_label_1"], "Cost CV1")
        self.assertEqual(updated["visible_columns"], ["date", "cost_total", "leads"])

    def test_upsert_and_list_daily_values(self):
        row = clients_api.upsert_media_buying_lead_daily_value(
            client_id=self.client_id,
            payload=MediaBuyingLeadDailyValueUpsertRequest(
                date=date(2026, 3, 11),
                leads=12,
                phones=6,
                custom_value_1_count=2,
                custom_value_2_count=1,
                custom_value_3_amount_ron=120,
                custom_value_4_amount_ron=20,
                custom_value_5_amount_ron=-5,
                sales_count=3,
            ),
            user=self.user,
        )
        self.assertEqual(row["date"], "2026-03-11")

        listed = clients_api.list_media_buying_lead_daily_values(
            client_id=self.client_id,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            user=self.user,
        )
        self.assertEqual(listed["count"], 1)

    def test_validation_errors_are_returned_as_422(self):
        with self.assertRaises(HTTPException) as ctx:
            clients_api.upsert_media_buying_lead_daily_value(
                client_id=self.client_id,
                payload=MediaBuyingLeadDailyValueUpsertRequest(
                    date=date(2026, 3, 11),
                    leads=-1,
                    phones=0,
                    custom_value_1_count=0,
                    custom_value_2_count=0,
                    custom_value_3_amount_ron=0,
                    custom_value_4_amount_ron=0,
                    custom_value_5_amount_ron=0,
                    sales_count=0,
                ),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 422)

        with self.assertRaises(HTTPException) as range_ctx:
            clients_api.list_media_buying_lead_daily_values(
                client_id=self.client_id,
                date_from=date(2026, 3, 12),
                date_to=date(2026, 3, 11),
                user=self.user,
            )
        self.assertEqual(range_ctx.exception.status_code, 422)

    def test_missing_client_returns_404(self):
        with self.assertRaises(HTTPException) as ctx:
            clients_api.get_media_buying_config(client_id=999999, user=self.user)
        self.assertEqual(ctx.exception.status_code, 404)


    def test_get_lead_table_endpoint(self):
        payload = clients_api.get_media_buying_lead_table(
            client_id=self.client_id,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            user=self.user,
        )
        self.assertEqual(payload["meta"]["template_type"], "lead")
        self.assertEqual(payload["days"][0]["percent_change"], None)

    def test_get_lead_table_non_lead_returns_501(self):
        clients_api.media_buying_store.config["template_type"] = "ecommerce"
        with self.assertRaises(HTTPException) as ctx:
            clients_api.get_media_buying_lead_table(
                client_id=self.client_id,
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 31),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 501)

    def test_get_lead_table_endpoint_supports_missing_range(self):
        payload = clients_api.get_media_buying_lead_table(
            client_id=self.client_id,
            date_from=None,
            date_to=None,
            user=self.user,
        )
        self.assertEqual(payload["meta"]["effective_date_from"], "2026-03-11")

    def test_get_lead_table_endpoint_supports_include_days_false(self):
        payload = clients_api.get_media_buying_lead_table(
            client_id=self.client_id,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            include_days=False,
            user=self.user,
        )
        self.assertEqual(payload["days"], [])
        self.assertEqual(payload["months"][0]["day_count"], 1)
        self.assertTrue(payload["months"][0]["has_days"])

    def test_get_lead_month_days_endpoint(self):
        payload = clients_api.get_media_buying_lead_month_days(
            client_id=self.client_id,
            month_start=date(2026, 3, 1),
            user=self.user,
        )
        self.assertEqual(payload["month_start"], "2026-03-01")
        self.assertEqual(payload["days"][0]["display_currency"], "RON")

    def test_get_lead_month_days_validation_error(self):
        with self.assertRaises(HTTPException) as ctx:
            clients_api.get_media_buying_lead_month_days(
                client_id=self.client_id,
                month_start=date(2026, 4, 1),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 422)

    def test_get_media_tracker_weekly_worksheet_foundation_endpoint(self):
        payload = clients_api.get_media_tracker_weekly_worksheet_foundation(
            client_id=self.client_id,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            user=self.user,
        )
        self.assertEqual(payload["requested_scope"]["granularity"], "month")
        self.assertEqual(payload["resolved_period"]["period_start"], "2026-03-01")
        self.assertEqual(payload["history"]["visible_week_count"], len(payload["weeks"]))

    def test_get_media_tracker_weekly_worksheet_foundation_validation(self):
        with self.assertRaises(HTTPException) as ctx:
            clients_api.get_media_tracker_weekly_worksheet_foundation(
                client_id=self.client_id,
                granularity="week",
                anchor_date=date(2026, 3, 15),
                user=self.user,
            )
        self.assertEqual(ctx.exception.status_code, 422)


    def test_upsert_media_tracker_manual_values_and_get_readback(self):
        payload = clients_api.upsert_media_tracker_weekly_manual_values(
            client_id=self.client_id,
            payload=MediaTrackerWorksheetManualValuesUpsertRequest(
                granularity="month",
                anchor_date=date(2026, 3, 15),
                entries=[
                    {"week_start": date(2026, 3, 2), "field_key": "google_leads_manual", "value": 12},
                    {"week_start": date(2026, 3, 2), "field_key": "weekly_cogs_taxes", "value": 25450},
                ],
            ),
            user=self.user,
        )
        google_week = next(item for item in payload["manual_metrics"]["google_leads_manual"]["weekly_values"] if item["week_start"] == "2026-03-02")
        assert google_week["value"] == 12.0

        updated = clients_api.upsert_media_tracker_weekly_manual_values(
            client_id=self.client_id,
            payload=MediaTrackerWorksheetManualValuesUpsertRequest(
                granularity="month",
                anchor_date=date(2026, 3, 18),
                entries=[
                    {"week_start": date(2026, 3, 2), "field_key": "google_leads_manual", "value": 13},
                ],
            ),
            user=self.user,
        )
        google_week_updated = next(item for item in updated["manual_metrics"]["google_leads_manual"]["weekly_values"] if item["week_start"] == "2026-03-02")
        assert google_week_updated["value"] == 13.0

    def test_upsert_media_tracker_manual_values_validation(self):
        with self.assertRaises(HTTPException) as ctx_field:
            clients_api.upsert_media_tracker_weekly_manual_values(
                client_id=self.client_id,
                payload=MediaTrackerWorksheetManualValuesUpsertRequest(
                    granularity="month",
                    anchor_date=date(2026, 3, 15),
                    entries=[{"week_start": date(2026, 3, 2), "field_key": "bad_field", "value": 1}],
                ),
                user=self.user,
            )
        self.assertEqual(ctx_field.exception.status_code, 422)

        with self.assertRaises(HTTPException) as ctx_monday:
            clients_api.upsert_media_tracker_weekly_manual_values(
                client_id=self.client_id,
                payload=MediaTrackerWorksheetManualValuesUpsertRequest(
                    granularity="month",
                    anchor_date=date(2026, 3, 15),
                    entries=[{"week_start": date(2026, 3, 3), "field_key": "google_leads_manual", "value": 1}],
                ),
                user=self.user,
            )
        self.assertEqual(ctx_monday.exception.status_code, 422)

    def test_upsert_media_tracker_eur_ron_rate_and_clear(self):
        payload = clients_api.upsert_media_tracker_scope_eur_ron_rate(
            client_id=self.client_id,
            payload=MediaTrackerWorksheetEurRonRateUpsertRequest(
                granularity="month",
                anchor_date=date(2026, 3, 15),
                value=5.09,
            ),
            user=self.user,
        )
        self.assertEqual(payload["eur_ron_rate"], 5.09)
        foundation_after_first_save = clients_api.get_media_tracker_weekly_worksheet_foundation(
            client_id=self.client_id,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            user=self.user,
        )
        self.assertEqual(foundation_after_first_save["eur_ron_rate"], 5.09)

        updated = clients_api.upsert_media_tracker_scope_eur_ron_rate(
            client_id=self.client_id,
            payload=MediaTrackerWorksheetEurRonRateUpsertRequest(
                granularity="month",
                anchor_date=date(2026, 3, 1),
                value=5.11,
            ),
            user=self.user,
        )
        self.assertEqual(updated["eur_ron_rate"], 5.11)
        foundation_after_update = clients_api.get_media_tracker_weekly_worksheet_foundation(
            client_id=self.client_id,
            granularity="month",
            anchor_date=date(2026, 3, 20),
            user=self.user,
        )
        self.assertEqual(foundation_after_update["eur_ron_rate"], 5.11)

        cleared = clients_api.upsert_media_tracker_scope_eur_ron_rate(
            client_id=self.client_id,
            payload=MediaTrackerWorksheetEurRonRateUpsertRequest(
                granularity="month",
                anchor_date=date(2026, 3, 20),
                value=None,
            ),
            user=self.user,
        )
        self.assertIsNone(cleared["eur_ron_rate"])
        foundation_after_clear = clients_api.get_media_tracker_weekly_worksheet_foundation(
            client_id=self.client_id,
            granularity="month",
            anchor_date=date(2026, 3, 10),
            user=self.user,
        )
        self.assertIsNone(foundation_after_clear["eur_ron_rate"])

    def test_get_media_tracker_overview_charts_payload_includes_weeks_datasets_and_custom_labels(self):
        clients_api.upsert_media_buying_config(
            client_id=self.client_id,
            payload=MediaBuyingConfigUpdateRequest(
                template_type="lead",
                custom_label_1="Aplicații",
                custom_label_2="Aplicații Aprobate",
                custom_label_3="Val. Aprobată",
                custom_label_4="Val. Vândută",
                custom_label_5="Val. Nerealizată",
            ),
            user=self.user,
        )
        payload = clients_api.get_media_tracker_overview_charts(
            client_id=self.client_id,
            granularity="month",
            anchor_date=date(2026, 3, 15),
            user=self.user,
        )
        self.assertGreaterEqual(len(payload["weeks"]), 4)
        self.assertIn("sales", payload)
        self.assertIn("financial", payload)
        self.assertIn("total_sales_trend", payload["sales"])
        self.assertIn("cost_efficiency", payload["financial"])
        self.assertEqual(payload["custom_labels"]["custom_label_1"], "Aplicații")
        self.assertEqual(payload["custom_labels"]["custom_label_4"], "Val. Vândută")


if __name__ == "__main__":
    unittest.main()
