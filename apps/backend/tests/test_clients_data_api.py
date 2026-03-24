import os
import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.api import clients as clients_api
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service


class ClientsDataApiTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"

        self.original_is_test_mode = client_registry_service._is_test_mode
        client_registry_service._is_test_mode = lambda: True
        client_registry_service._clients = []
        client_registry_service._next_id = 1

        self.original_enforce_action_scope = clients_api.enforce_action_scope
        self.original_enforce_nav = clients_api.enforce_agency_navigation_access
        clients_api.enforce_action_scope = lambda **kwargs: None
        clients_api.enforce_agency_navigation_access = lambda **kwargs: None

        self.user = AuthUser(email="owner@example.com", role="admin")
        created = client_registry_service.create_client(name="Client A", owner_email="owner@example.com")
        self.client_id = int(created["id"])

        self.original_store = clients_api.client_data_store

        class _StoreStub:
            def list_supported_sources(self):
                return [
                    {"key": "meta_ads", "label": "Meta"},
                    {"key": "google_ads", "label": "Google"},
                ]

            def list_custom_fields(self, *, client_id: int, include_inactive: bool = False):
                _ = client_id
                _ = include_inactive
                return [
                    {
                        "id": 11,
                        "field_key": "appointments",
                        "label": "Appointments",
                        "value_kind": "count",
                        "sort_order": 1,
                        "is_active": True,
                    },
                    {
                        "id": 12,
                        "field_key": "blank_label",
                        "label": "   ",
                        "value_kind": "amount",
                        "sort_order": 2,
                        "is_active": False,
                    },
                ]

            def list_daily_inputs(self, *, client_id: int, date_from, date_to):
                _ = client_id
                if date_from > date_to:
                    raise ValueError("date_from must be <= date_to")
                return [
                    {
                        "id": 102,
                        "metric_date": "2026-03-24",
                        "source": "mystery",
                        "leads": 3,
                        "phones": 1,
                        "custom_value_1_count": 0,
                        "custom_value_2_count": 2,
                        "custom_value_3_amount": Decimal("5.00"),
                        "custom_value_5_amount": Decimal("1.00"),
                        "notes": None,
                    },
                    {
                        "id": 101,
                        "metric_date": "2026-03-24",
                        "source": "meta_ads",
                        "leads": 5,
                        "phones": 2,
                        "custom_value_1_count": 1,
                        "custom_value_2_count": 0,
                        "custom_value_3_amount": Decimal("10.50"),
                        "custom_value_5_amount": Decimal("2.00"),
                        "notes": "ok",
                    },
                ]

            def list_daily_custom_values(self, *, client_id: int, date_from, date_to):
                _ = client_id
                if date_from > date_to:
                    raise ValueError("date_from must be <= date_to")
                return [
                    {
                        "daily_input_id": 101,
                        "custom_field_id": 12,
                        "field_key": "blank_label",
                        "label": "   ",
                        "value_kind": "amount",
                        "sort_order": 2,
                        "numeric_value": Decimal("9.99"),
                    },
                    {
                        "daily_input_id": 101,
                        "custom_field_id": 11,
                        "field_key": "appointments",
                        "label": "Appointments",
                        "value_kind": "count",
                        "sort_order": 1,
                        "numeric_value": Decimal("4"),
                    },
                ]

            def list_sale_entries_for_daily_input(self, *, daily_input_id: int):
                if daily_input_id == 101:
                    return [
                        {"sale_price_amount": Decimal("100"), "actual_price_amount": Decimal("70")},
                        {"sale_price_amount": Decimal("50"), "actual_price_amount": Decimal("20")},
                    ]
                if daily_input_id == 102:
                    return []
                raise LookupError("Daily input not found")

            def get_source_label(self, source_key: str | None):
                return {"meta_ads": "Meta"}.get((source_key or "").strip().lower())

            def compute_sales_count(self, sale_entries):
                return len(sale_entries)

            def compute_revenue(self, sale_entries):
                return sum((Decimal(str(row.get("sale_price_amount", 0))) for row in sale_entries), Decimal("0"))

            def compute_cogs(self, sale_entries):
                return sum((Decimal(str(row.get("actual_price_amount", 0))) for row in sale_entries), Decimal("0"))

            def compute_custom_value_4(self, sale_entries):
                return self.compute_revenue(sale_entries)

            def compute_gross_profit(self, sale_entries):
                return self.compute_revenue(sale_entries) - self.compute_cogs(sale_entries)

        clients_api.client_data_store = _StoreStub()

    def tearDown(self):
        clients_api.client_data_store = self.original_store
        clients_api.enforce_action_scope = self.original_enforce_action_scope
        clients_api.enforce_agency_navigation_access = self.original_enforce_nav
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_client_data_config_includes_sources_custom_fields_and_derived_fields(self):
        payload = clients_api.get_client_data_config(client_id=self.client_id, user=self.user)

        self.assertEqual(payload["client_id"], self.client_id)
        self.assertEqual(payload["sources"][0]["key"], "meta_ads")
        self.assertEqual(payload["custom_fields"][0]["label"], "Appointments")
        self.assertEqual(payload["custom_fields"][1]["label"], "Custom Field 12")
        self.assertEqual(payload["derived_fields"][0], {"key": "sales_count", "label": "Sales Count", "value_kind": "count"})

    def test_get_client_data_table_resolves_source_labels_custom_value_sort_and_derived_metrics(self):
        payload = clients_api.get_client_data_table(
            client_id=self.client_id,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            user=self.user,
        )

        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["rows"][0]["daily_input_id"], 102)
        self.assertEqual(payload["rows"][0]["source_label"], "Unknown")
        self.assertEqual(payload["rows"][1]["daily_input_id"], 101)
        self.assertEqual(payload["rows"][1]["source_label"], "Meta")
        self.assertEqual(payload["rows"][1]["sales_count"], 2)
        self.assertEqual(payload["rows"][1]["revenue_amount"], "150")
        self.assertEqual(payload["rows"][1]["cogs_amount"], "90")
        self.assertEqual(payload["rows"][1]["gross_profit_amount"], "60")
        self.assertEqual(payload["rows"][1]["custom_values"][0]["custom_field_id"], 11)
        self.assertEqual(payload["rows"][1]["custom_values"][1]["custom_field_id"], 12)
        self.assertEqual(payload["rows"][1]["custom_values"][1]["label"], "Custom Field 12")

    def test_get_client_data_table_maps_store_validation_error_to_422(self):
        with self.assertRaises(HTTPException) as ctx:
            clients_api.get_client_data_table(
                client_id=self.client_id,
                date_from=date(2026, 3, 31),
                date_to=date(2026, 3, 1),
                user=self.user,
            )

        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
