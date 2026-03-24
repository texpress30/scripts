import os
import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.api import clients as clients_api
from app.schemas.client import (
    ClientDataDailyInputUpsertRequest,
    ClientDataSaleEntryCreateRequest,
    ClientDataSaleEntryUpdateRequest,
)
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
            def __init__(self):
                self.daily_inputs = {
                    101: {
                        "id": 101,
                        "client_id": 1,
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
                    102: {
                        "id": 102,
                        "client_id": 1,
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
                    201: {
                        "id": 201,
                        "client_id": 2,
                        "metric_date": "2026-03-24",
                        "source": "google_ads",
                        "leads": 1,
                        "phones": 1,
                        "custom_value_1_count": 1,
                        "custom_value_2_count": 1,
                        "custom_value_3_amount": Decimal("1.00"),
                        "custom_value_5_amount": Decimal("1.00"),
                        "notes": None,
                    },
                }
                self.next_daily_input_id = 300
                self.sale_entries = {
                    1001: {
                        "id": 1001,
                        "daily_input_id": 101,
                        "brand": "VW",
                        "model": "Golf",
                        "sale_price_amount": Decimal("100"),
                        "actual_price_amount": Decimal("70"),
                        "notes": "initial",
                        "sort_order": 0,
                        "gross_profit_amount": Decimal("30"),
                    },
                    1002: {
                        "id": 1002,
                        "daily_input_id": 101,
                        "brand": "Ford",
                        "model": "Focus",
                        "sale_price_amount": Decimal("50"),
                        "actual_price_amount": Decimal("20"),
                        "notes": None,
                        "sort_order": 1,
                        "gross_profit_amount": Decimal("30"),
                    },
                    2001: {
                        "id": 2001,
                        "daily_input_id": 201,
                        "brand": "Other",
                        "model": "Client",
                        "sale_price_amount": Decimal("40"),
                        "actual_price_amount": Decimal("20"),
                        "notes": None,
                        "sort_order": 0,
                        "gross_profit_amount": Decimal("20"),
                    },
                }
                self.next_sale_entry_id = 3000

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
                if date_from > date_to:
                    raise ValueError("date_from must be <= date_to")
                rows = [dict(row) for row in self.daily_inputs.values() if int(row["client_id"]) == int(client_id)]
                rows.sort(key=lambda row: (str(row["metric_date"]), str(row["source"]), int(row["id"])), reverse=True)
                return rows

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
                if daily_input_id not in self.daily_inputs:
                    raise LookupError("Daily input not found")
                rows = [dict(entry) for entry in self.sale_entries.values() if int(entry["daily_input_id"]) == int(daily_input_id)]
                rows.sort(key=lambda row: (int(row["sort_order"]), int(row["id"])))
                return rows

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

            def _normalize_source(self, source: str):
                normalized = str(source or "").strip().lower()
                if normalized not in {"meta_ads", "google_ads", "tiktok_ads"}:
                    raise ValueError("source must be a supported source key")
                return normalized

            def _find_daily_input_by_pair(self, *, client_id: int, metric_date: str, source: str):
                for row in self.daily_inputs.values():
                    if int(row["client_id"]) == int(client_id) and str(row["metric_date"]) == str(metric_date) and str(row["source"]) == str(source):
                        return row
                return None

            def upsert_daily_input(self, *, client_id: int, metric_date, source, **updates):
                if str(metric_date) != "2026-03-24":
                    raise ValueError("metric_date must be a valid ISO date")
                normalized_source = self._normalize_source(source)
                if not updates:
                    raise ValueError("At least one daily input numeric field must be provided")
                row = self._find_daily_input_by_pair(client_id=client_id, metric_date=str(metric_date), source=normalized_source)
                if row is None:
                    row = {
                        "id": self.next_daily_input_id,
                        "client_id": int(client_id),
                        "metric_date": str(metric_date),
                        "source": normalized_source,
                        "leads": 0,
                        "phones": 0,
                        "custom_value_1_count": 0,
                        "custom_value_2_count": 0,
                        "custom_value_3_amount": Decimal("0"),
                        "custom_value_5_amount": Decimal("0"),
                        "notes": None,
                    }
                    self.daily_inputs[self.next_daily_input_id] = row
                    self.next_daily_input_id += 1
                for key, value in updates.items():
                    if key in {"leads", "phones", "custom_value_1_count", "custom_value_2_count"}:
                        if not isinstance(value, int) or value < 0:
                            raise ValueError(f"{key} must be an integer >= 0")
                        row[key] = value
                    elif key in {"custom_value_3_amount", "custom_value_5_amount"}:
                        try:
                            parsed = Decimal(str(value))
                        except Exception as exc:  # noqa: BLE001
                            raise ValueError(f"{key} must be a decimal") from exc
                        row[key] = parsed
                    else:
                        raise ValueError(f"Unsupported field {key}")
                return dict(row)

            def set_daily_input_notes(self, *, client_id: int, metric_date, source, notes):
                if str(metric_date) != "2026-03-24":
                    raise ValueError("metric_date must be a valid ISO date")
                normalized_source = self._normalize_source(source)
                row = self._find_daily_input_by_pair(client_id=client_id, metric_date=str(metric_date), source=normalized_source)
                if row is None:
                    row = {
                        "id": self.next_daily_input_id,
                        "client_id": int(client_id),
                        "metric_date": str(metric_date),
                        "source": normalized_source,
                        "leads": 0,
                        "phones": 0,
                        "custom_value_1_count": 0,
                        "custom_value_2_count": 0,
                        "custom_value_3_amount": Decimal("0"),
                        "custom_value_5_amount": Decimal("0"),
                        "notes": None,
                    }
                    self.daily_inputs[self.next_daily_input_id] = row
                    self.next_daily_input_id += 1
                if notes is None:
                    row["notes"] = None
                else:
                    if not isinstance(notes, str):
                        raise ValueError("notes must be a string or null")
                    row["notes"] = notes.strip() or None
                return dict(row)

            def validate_daily_input_belongs_to_client(self, *, daily_input_id: int, client_id: int):
                row = self.daily_inputs.get(int(daily_input_id))
                if row is None or int(row["client_id"]) != int(client_id):
                    raise LookupError(f"Daily input {daily_input_id} not found for client {client_id}")
                return dict(row)

            def create_sale_entry(self, *, daily_input_id: int, sale_price_amount, actual_price_amount, brand=None, model=None, notes=None, sort_order=None):
                if int(daily_input_id) not in self.daily_inputs:
                    raise LookupError(f"Daily input {daily_input_id} not found")
                try:
                    sale_price = Decimal(str(sale_price_amount))
                    actual_price = Decimal(str(actual_price_amount))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError("sale_price_amount and actual_price_amount must be decimals") from exc
                if sale_price < 0 or actual_price < 0:
                    raise ValueError("sale_price_amount and actual_price_amount must be >= 0")
                row = {
                    "id": self.next_sale_entry_id,
                    "daily_input_id": int(daily_input_id),
                    "brand": (brand or "").strip() or None,
                    "model": (model or "").strip() or None,
                    "sale_price_amount": sale_price,
                    "actual_price_amount": actual_price,
                    "notes": (notes or "").strip() or None,
                    "sort_order": int(sort_order or 0),
                    "gross_profit_amount": sale_price - actual_price,
                }
                self.sale_entries[self.next_sale_entry_id] = row
                self.next_sale_entry_id += 1
                return dict(row)

            def validate_sale_entry_belongs_to_client(self, *, sale_entry_id: int, client_id: int):
                row = self.sale_entries.get(int(sale_entry_id))
                if row is None:
                    raise LookupError(f"Sale entry {sale_entry_id} not found for client {client_id}")
                daily = self.daily_inputs.get(int(row["daily_input_id"]))
                if daily is None or int(daily["client_id"]) != int(client_id):
                    raise LookupError(f"Sale entry {sale_entry_id} not found for client {client_id}")
                return dict(row)

            def update_sale_entry(self, *, sale_entry_id: int, **updates):
                row = self.sale_entries.get(int(sale_entry_id))
                if row is None:
                    raise LookupError(f"Sale entry {sale_entry_id} not found")
                if not updates:
                    raise ValueError("At least one sale entry field must be provided for update")
                for key, value in updates.items():
                    if key in {"sale_price_amount", "actual_price_amount"}:
                        try:
                            parsed = Decimal(str(value))
                        except Exception as exc:  # noqa: BLE001
                            raise ValueError(f"{key} must be a decimal") from exc
                        if parsed < 0:
                            raise ValueError(f"{key} must be >= 0")
                        row[key] = parsed
                    elif key == "sort_order":
                        if value is None or int(value) < 0:
                            raise ValueError("sort_order must be an integer >= 0")
                        row[key] = int(value)
                    elif key in {"brand", "model", "notes"}:
                        if value is None:
                            row[key] = None
                        else:
                            row[key] = str(value).strip() or None
                    else:
                        raise ValueError(f"Unsupported field {key}")
                row["gross_profit_amount"] = Decimal(str(row["sale_price_amount"])) - Decimal(str(row["actual_price_amount"]))
                return dict(row)

            def delete_sale_entry(self, *, sale_entry_id: int):
                row = self.sale_entries.pop(int(sale_entry_id), None)
                if row is None:
                    raise LookupError(f"Sale entry {sale_entry_id} not found")
                return dict(row)

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

    def test_put_daily_input_supports_numeric_only_notes_only_and_mixed(self):
        numeric = clients_api.upsert_client_data_daily_input(
            client_id=self.client_id,
            payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="meta_ads", leads=9, phones=3),
            user=self.user,
        )
        self.assertEqual(numeric["leads"], 9)
        self.assertEqual(numeric["phones"], 3)

        notes_only = clients_api.upsert_client_data_daily_input(
            client_id=self.client_id,
            payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="meta_ads", notes="   hello  "),
            user=self.user,
        )
        self.assertEqual(notes_only["notes"], "hello")

        mixed = clients_api.upsert_client_data_daily_input(
            client_id=self.client_id,
            payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="meta_ads", leads=11, notes="  mixed "),
            user=self.user,
        )
        self.assertEqual(mixed["leads"], 11)
        self.assertEqual(mixed["notes"], "mixed")

    def test_put_daily_input_validates_empty_payload_date_source_and_numeric_values(self):
        with self.assertRaises(HTTPException) as empty_ctx:
            clients_api.upsert_client_data_daily_input(
                client_id=self.client_id,
                payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="meta_ads"),
                user=self.user,
            )
        self.assertEqual(empty_ctx.exception.status_code, 422)

        with self.assertRaises(HTTPException) as bad_date_ctx:
            clients_api.upsert_client_data_daily_input(
                client_id=self.client_id,
                payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 25), source="meta_ads", leads=1),
                user=self.user,
            )
        self.assertEqual(bad_date_ctx.exception.status_code, 422)

        with self.assertRaises(HTTPException) as bad_source_ctx:
            clients_api.upsert_client_data_daily_input(
                client_id=self.client_id,
                payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="facebook_ads", leads=1),
                user=self.user,
            )
        self.assertEqual(bad_source_ctx.exception.status_code, 422)

        with self.assertRaises(HTTPException) as bad_numeric_ctx:
            clients_api.upsert_client_data_daily_input(
                client_id=self.client_id,
                payload=ClientDataDailyInputUpsertRequest(metric_date=date(2026, 3, 24), source="meta_ads", leads=-1),
                user=self.user,
            )
        self.assertEqual(bad_numeric_ctx.exception.status_code, 422)

    def test_post_sale_entry_create_success_scoping_and_validation(self):
        created = clients_api.create_client_data_sale_entry(
            client_id=self.client_id,
            payload=ClientDataSaleEntryCreateRequest(
                daily_input_id=101,
                sale_price_amount="250",
                actual_price_amount="200",
                brand="  Opel ",
                model=" Zafira ",
                notes=" test ",
                sort_order=2,
            ),
            user=self.user,
        )
        self.assertEqual(created["brand"], "Opel")
        self.assertEqual(created["model"], "Zafira")
        self.assertEqual(created["notes"], "test")
        self.assertEqual(created["gross_profit_amount"], "50")

        with self.assertRaises(HTTPException) as wrong_client_ctx:
            clients_api.create_client_data_sale_entry(
                client_id=self.client_id,
                payload=ClientDataSaleEntryCreateRequest(
                    daily_input_id=201,
                    sale_price_amount=100,
                    actual_price_amount=10,
                ),
                user=self.user,
            )
        self.assertEqual(wrong_client_ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as bad_amount_ctx:
            clients_api.create_client_data_sale_entry(
                client_id=self.client_id,
                payload=ClientDataSaleEntryCreateRequest(
                    daily_input_id=101,
                    sale_price_amount="abc",
                    actual_price_amount=10,
                ),
                user=self.user,
            )
        self.assertEqual(bad_amount_ctx.exception.status_code, 422)

    def test_patch_sale_entry_update_success_scoping_empty_payload_and_recalc(self):
        updated = clients_api.update_client_data_sale_entry(
            client_id=self.client_id,
            sale_entry_id=1001,
            payload=ClientDataSaleEntryUpdateRequest(actual_price_amount=80, notes=" updated "),
            user=self.user,
        )
        self.assertEqual(updated["actual_price_amount"], "80")
        self.assertEqual(updated["notes"], "updated")
        self.assertEqual(updated["gross_profit_amount"], "20")

        with self.assertRaises(HTTPException) as wrong_client_ctx:
            clients_api.update_client_data_sale_entry(
                client_id=self.client_id,
                sale_entry_id=2001,
                payload=ClientDataSaleEntryUpdateRequest(notes="nope"),
                user=self.user,
            )
        self.assertEqual(wrong_client_ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as empty_ctx:
            clients_api.update_client_data_sale_entry(
                client_id=self.client_id,
                sale_entry_id=1001,
                payload=ClientDataSaleEntryUpdateRequest(),
                user=self.user,
            )
        self.assertEqual(empty_ctx.exception.status_code, 422)

    def test_delete_sale_entry_success_and_client_scoping(self):
        deleted = clients_api.delete_client_data_sale_entry(
            client_id=self.client_id,
            sale_entry_id=1002,
            user=self.user,
        )
        self.assertEqual(deleted["id"], 1002)
        self.assertEqual(deleted["daily_input_id"], 101)

        with self.assertRaises(HTTPException) as wrong_client_ctx:
            clients_api.delete_client_data_sale_entry(
                client_id=self.client_id,
                sale_entry_id=2001,
                user=self.user,
            )
        self.assertEqual(wrong_client_ctx.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
