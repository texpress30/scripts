from __future__ import annotations

from decimal import Decimal
import unittest
from unittest import mock

from app.services import client_data_store


class _FakeDbState:
    def __init__(self):
        self.rows: list[dict[str, object]] = []
        self.next_id = 1
        self.daily_rows: list[dict[str, object]] = []
        self.next_daily_id = 1


class _FakeCursor:
    def __init__(self, state: _FakeDbState):
        self._state = state
        self._fetchone: tuple[object, ...] | None = None
        self._fetchall: list[tuple[object, ...]] = []

    def execute(self, query: str, params=None):
        query_str = str(query)
        q = " ".join(query_str.split()).lower()
        self._fetchone = None
        self._fetchall = []

        if "select 1 from client_data_custom_fields" in q:
            client_id, field_key = int(params[0]), str(params[1])
            exists = any(r["client_id"] == client_id and r["field_key"] == field_key for r in self._state.rows)
            self._fetchone = (1,) if exists else None
            return

        if "select coalesce(max(sort_order), -1) + 1" in q:
            client_id = int(params[0])
            values = [int(r["sort_order"]) for r in self._state.rows if r["client_id"] == client_id]
            self._fetchone = ((max(values) + 1) if values else 0,)
            return

        if "from client_data_custom_fields where client_id = %s and is_active = true" in q:
            client_id = int(params[0])
            selected = [r for r in self._state.rows if r["client_id"] == client_id and bool(r["is_active"])]
            selected.sort(key=lambda r: (int(r["sort_order"]), int(r["id"])))
            self._fetchall = [_row_tuple(r) for r in selected]
            return

        if "from client_data_custom_fields where client_id = %s" in q and "is_active = true" not in q:
            client_id = int(params[0])
            selected = [r for r in self._state.rows if r["client_id"] == client_id]
            selected.sort(key=lambda r: (int(r["sort_order"]), int(r["id"])))
            self._fetchall = [_row_tuple(r) for r in selected]
            return

        if "from client_data_custom_fields where id = %s and client_id = %s" in q:
            field_id, client_id = int(params[0]), int(params[1])
            row = next((r for r in self._state.rows if r["id"] == field_id and r["client_id"] == client_id), None)
            self._fetchone = _row_tuple(row) if row else None
            return

        if "from client_data_custom_fields where id = %s" in q and "client_id = %s" not in q:
            field_id = int(params[0])
            row = next((r for r in self._state.rows if r["id"] == field_id), None)
            self._fetchone = _row_tuple(row) if row else None
            return

        if "insert into client_data_custom_fields" in q:
            client_id, field_key, label, value_kind, sort_order = params
            row = {
                "id": self._state.next_id,
                "client_id": int(client_id),
                "field_key": str(field_key),
                "label": str(label),
                "value_kind": str(value_kind),
                "sort_order": int(sort_order),
                "is_active": True,
                "archived_at": None,
            }
            self._state.rows.append(row)
            self._state.next_id += 1
            self._fetchone = _row_tuple(row)
            return

        if "from client_data_daily_inputs where client_id = %s and metric_date = %s and source = %s" in q:
            client_id, metric_date, source = int(params[0]), str(params[1]), str(params[2])
            row = next(
                (
                    r
                    for r in self._state.daily_rows
                    if r["client_id"] == client_id and str(r["metric_date"]) == metric_date and r["source"] == source
                ),
                None,
            )
            self._fetchone = _daily_row_tuple(row) if row else None
            return

        if "from client_data_daily_inputs" in q and "metric_date >= %s" in q and "metric_date <= %s" in q:
            client_id, date_from, date_to = int(params[0]), str(params[1]), str(params[2])
            selected = [
                r for r in self._state.daily_rows
                if r["client_id"] == client_id and date_from <= str(r["metric_date"]) <= date_to
            ]
            selected.sort(key=lambda r: (str(r["metric_date"]), str(r["source"]), int(r["id"])))
            selected.reverse()
            # reverse makes source/id order reverse too, so apply exact key via two-step stable sorts
            selected.sort(key=lambda r: (str(r["source"]), int(r["id"])))
            selected.sort(key=lambda r: str(r["metric_date"]), reverse=True)
            self._fetchall = [_daily_row_tuple(r) for r in selected]
            return

        if "insert into client_data_daily_inputs" in q:
            client_id, metric_date, source = int(params[0]), str(params[1]), str(params[2])
            row = {
                "id": self._state.next_daily_id,
                "client_id": client_id,
                "metric_date": metric_date,
                "source": source,
                "leads": 0,
                "phones": 0,
                "custom_value_1_count": 0,
                "custom_value_2_count": 0,
                "custom_value_3_amount": "0",
                "custom_value_5_amount": "0",
                "notes": None,
            }
            self._state.daily_rows.append(row)
            self._state.next_daily_id += 1
            self._fetchone = _daily_row_tuple(row)
            return

        if "update client_data_daily_inputs set" in q:
            daily_id = int(params[-1])
            row = next((r for r in self._state.daily_rows if r["id"] == daily_id), None)
            if row is None:
                self._fetchone = None
                return

            param_index = 0
            if "notes = %s" in q:
                row["notes"] = params[param_index]
                param_index += 1
            if "leads = %s" in q:
                row["leads"] = int(params[param_index])
                param_index += 1
            if "phones = %s" in q:
                row["phones"] = int(params[param_index])
                param_index += 1
            if "custom_value_1_count = %s" in q:
                row["custom_value_1_count"] = int(params[param_index])
                param_index += 1
            if "custom_value_2_count = %s" in q:
                row["custom_value_2_count"] = int(params[param_index])
                param_index += 1
            if "custom_value_3_amount = %s" in q:
                row["custom_value_3_amount"] = str(params[param_index])
                param_index += 1
            if "custom_value_5_amount = %s" in q:
                row["custom_value_5_amount"] = str(params[param_index])
                param_index += 1

            self._fetchone = _daily_row_tuple(row)
            return

        if "update client_data_custom_fields set" in q:
            if "is_active = false" in q:
                field_id = int(params[0])
                row = next((r for r in self._state.rows if r["id"] == field_id), None)
                if row is None:
                    self._fetchone = None
                    return
                row["is_active"] = False
                if row["archived_at"] is None:
                    row["archived_at"] = "2026-03-24T00:00:00Z"
                self._fetchone = _row_tuple(row)
                return

            field_id = int(params[-1])
            row = next((r for r in self._state.rows if r["id"] == field_id), None)
            if row is None:
                self._fetchone = None
                return

            param_index = 0
            if "label = %s" in q:
                row["label"] = str(params[param_index])
                param_index += 1
            if "value_kind = %s" in q:
                row["value_kind"] = str(params[param_index])
                param_index += 1
            if "sort_order = %s" in q:
                row["sort_order"] = int(params[param_index])
                param_index += 1

            self._fetchone = _row_tuple(row)
            return

        raise AssertionError(f"Unexpected query: {query}")

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return list(self._fetchall)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, state: _FakeDbState):
        self._state = state

    def cursor(self):
        return _FakeCursor(self._state)

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _row_tuple(row: dict[str, object] | None) -> tuple[object, ...] | None:
    if row is None:
        return None
    return (
        row["id"],
        row["client_id"],
        row["field_key"],
        row["label"],
        row["value_kind"],
        row["sort_order"],
        row["is_active"],
        row["archived_at"],
    )


def _daily_row_tuple(row: dict[str, object] | None) -> tuple[object, ...] | None:
    if row is None:
        return None
    return (
        row["id"],
        row["client_id"],
        row["metric_date"],
        row["source"],
        row["leads"],
        row["phones"],
        row["custom_value_1_count"],
        row["custom_value_2_count"],
        row["custom_value_3_amount"],
        row["custom_value_5_amount"],
        row["notes"],
    )


class ClientDataStorePureTests(unittest.TestCase):
    def test_list_supported_sources_returns_exact_catalog_in_label_order(self):
        expected = [
            {"key": "call_center", "label": "Call Center"},
            {"key": "direct", "label": "Direct"},
            {"key": "google_ads", "label": "Google"},
            {"key": "linkedin_ads", "label": "LinkedIn"},
            {"key": "meta_ads", "label": "Meta"},
            {"key": "organic", "label": "Organic"},
            {"key": "pinterest_ads", "label": "Pinterest"},
            {"key": "quora_ads", "label": "Quora"},
            {"key": "reddit_ads", "label": "Reddit"},
            {"key": "referral", "label": "Referral"},
            {"key": "snapchat_ads", "label": "Snapchat"},
            {"key": "taboola_ads", "label": "Taboola"},
            {"key": "tiktok_ads", "label": "TikTok"},
            {"key": "unknown", "label": "Unknown"},
        ]
        self.assertEqual(client_data_store.list_supported_sources(), expected)

    def test_is_supported_source(self):
        self.assertTrue(client_data_store.is_supported_source("meta_ads"))
        self.assertTrue(client_data_store.is_supported_source("  TIKTOK_ADS  "))
        self.assertFalse(client_data_store.is_supported_source("facebook_ads"))
        self.assertFalse(client_data_store.is_supported_source(None))

    def test_get_source_label(self):
        self.assertEqual(client_data_store.get_source_label("google_ads"), "Google")
        self.assertEqual(client_data_store.get_source_label("  REDDIT_ADS "), "Reddit")
        self.assertIsNone(client_data_store.get_source_label("invalid"))
        self.assertIsNone(client_data_store.get_source_label(None))

    def test_formula_helpers_empty(self):
        entries: list[dict[str, object]] = []
        self.assertEqual(client_data_store.compute_sales_count(entries), 0)
        self.assertEqual(client_data_store.compute_revenue(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_cogs(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_custom_value_4(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_gross_profit(entries), Decimal("0"))

    def test_formula_helpers_simple_example(self):
        entries = [
            {"sale_price_amount": Decimal("100.50"), "actual_price_amount": Decimal("60.25")},
            {"sale_price_amount": 99, "actual_price_amount": "40.75"},
        ]
        self.assertEqual(client_data_store.compute_sales_count(entries), 2)
        self.assertEqual(client_data_store.compute_revenue(entries), Decimal("199.50"))
        self.assertEqual(client_data_store.compute_cogs(entries), Decimal("101.00"))
        self.assertEqual(client_data_store.compute_custom_value_4(entries), Decimal("199.50"))
        self.assertEqual(client_data_store.compute_gross_profit(entries), Decimal("98.50"))


class ClientDataStoreCustomFieldCrudSliceTests(unittest.TestCase):
    def setUp(self):
        self.state = _FakeDbState()
        self.connect_patch = mock.patch(
            "app.services.client_data_store._connect",
            side_effect=lambda: _FakeConnection(self.state),
        )
        self.connect_patch.start()

    def tearDown(self):
        self.connect_patch.stop()

    def test_list_custom_fields_excludes_inactive_by_default(self):
        self.state.rows.extend(
            [
                {"id": 2, "client_id": 7, "field_key": "b", "label": "B", "value_kind": "count", "sort_order": 1, "is_active": False, "archived_at": "2026-01-01"},
                {"id": 1, "client_id": 7, "field_key": "a", "label": "A", "value_kind": "count", "sort_order": 1, "is_active": True, "archived_at": None},
                {"id": 3, "client_id": 8, "field_key": "c", "label": "C", "value_kind": "amount", "sort_order": 0, "is_active": True, "archived_at": None},
            ]
        )
        rows = client_data_store.list_custom_fields(client_id=7)
        self.assertEqual([row["id"] for row in rows], [1])

    def test_list_custom_fields_include_inactive_and_sorted(self):
        self.state.rows.extend(
            [
                {"id": 5, "client_id": 7, "field_key": "z", "label": "Z", "value_kind": "count", "sort_order": 2, "is_active": True, "archived_at": None},
                {"id": 3, "client_id": 7, "field_key": "x", "label": "X", "value_kind": "amount", "sort_order": 1, "is_active": False, "archived_at": "2026-01-01"},
                {"id": 4, "client_id": 7, "field_key": "y", "label": "Y", "value_kind": "amount", "sort_order": 1, "is_active": True, "archived_at": None},
            ]
        )
        rows = client_data_store.list_custom_fields(client_id=7, include_inactive=True)
        self.assertEqual([row["id"] for row in rows], [3, 4, 5])

    def test_create_custom_field_auto_generates_key(self):
        row = client_data_store.create_custom_field(client_id=12, label="  Appointments  ", value_kind="count")
        self.assertEqual(row["field_key"], "appointments")
        self.assertEqual(row["sort_order"], 0)
        self.assertEqual(row["is_active"], True)
        self.assertIsNone(row["archived_at"])

    def test_create_custom_field_normalizes_explicit_key(self):
        row = client_data_store.create_custom_field(
            client_id=12,
            label="Revenue",
            value_kind="amount",
            field_key="  Revenue Total !! ",
            sort_order=7,
        )
        self.assertEqual(row["field_key"], "revenue_total")
        self.assertEqual(row["sort_order"], 7)

    def test_create_custom_field_resolves_key_conflicts_for_same_client(self):
        first = client_data_store.create_custom_field(client_id=99, label="Appointments", value_kind="count")
        second = client_data_store.create_custom_field(client_id=99, label="Appointments", value_kind="count")
        third = client_data_store.create_custom_field(client_id=99, label="Appointments", value_kind="count")
        self.assertEqual(first["field_key"], "appointments")
        self.assertEqual(second["field_key"], "appointments_2")
        self.assertEqual(third["field_key"], "appointments_3")

    def test_create_custom_field_accepts_both_value_kinds(self):
        row_count = client_data_store.create_custom_field(client_id=1, label="Leads", value_kind="count")
        row_amount = client_data_store.create_custom_field(client_id=1, label="Cost", value_kind="amount")
        self.assertEqual(row_count["value_kind"], "count")
        self.assertEqual(row_amount["value_kind"], "amount")

    def test_create_custom_field_rejects_invalid_value_kind(self):
        with self.assertRaises(ValueError):
            client_data_store.create_custom_field(client_id=1, label="Leads", value_kind="text")

    def test_validate_custom_field_belongs_to_client_valid(self):
        created = client_data_store.create_custom_field(client_id=5, label="Leads", value_kind="count")
        found = client_data_store.validate_custom_field_belongs_to_client(custom_field_id=created["id"], client_id=5)
        self.assertEqual(found["id"], created["id"])
        self.assertEqual(found["client_id"], 5)

    def test_validate_custom_field_belongs_to_client_invalid(self):
        created = client_data_store.create_custom_field(client_id=5, label="Leads", value_kind="count")
        with self.assertRaises(LookupError):
            client_data_store.validate_custom_field_belongs_to_client(custom_field_id=created["id"], client_id=6)

    def test_update_custom_field_label_only(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        updated = client_data_store.update_custom_field(custom_field_id=created["id"], label="  New Label  ")
        self.assertEqual(updated["label"], "New Label")
        self.assertEqual(updated["field_key"], "appointments")

    def test_update_custom_field_value_kind_only(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        updated = client_data_store.update_custom_field(custom_field_id=created["id"], value_kind="amount")
        self.assertEqual(updated["value_kind"], "amount")

    def test_update_custom_field_sort_order_only(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        updated = client_data_store.update_custom_field(custom_field_id=created["id"], sort_order=9)
        self.assertEqual(updated["sort_order"], 9)

    def test_update_custom_field_all_fields(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        updated = client_data_store.update_custom_field(
            custom_field_id=created["id"],
            label=" Qualified Leads ",
            value_kind="amount",
            sort_order=5,
        )
        self.assertEqual(updated["label"], "Qualified Leads")
        self.assertEqual(updated["value_kind"], "amount")
        self.assertEqual(updated["sort_order"], 5)
        self.assertEqual(updated["field_key"], "appointments")
        self.assertEqual(updated["client_id"], 12)

    def test_update_custom_field_rejects_no_fields(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        with self.assertRaises(ValueError):
            client_data_store.update_custom_field(custom_field_id=created["id"])

    def test_update_custom_field_rejects_empty_label(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        with self.assertRaises(ValueError):
            client_data_store.update_custom_field(custom_field_id=created["id"], label="   ")

    def test_update_custom_field_rejects_invalid_value_kind(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        with self.assertRaises(ValueError):
            client_data_store.update_custom_field(custom_field_id=created["id"], value_kind="invalid")

    def test_update_custom_field_rejects_invalid_sort_order(self):
        created = client_data_store.create_custom_field(client_id=12, label="Appointments", value_kind="count")
        with self.assertRaises(ValueError):
            client_data_store.update_custom_field(custom_field_id=created["id"], sort_order=-1)

    def test_update_custom_field_missing_id_raises_clear_error(self):
        with self.assertRaises(LookupError):
            client_data_store.update_custom_field(custom_field_id=999, label="Anything")

    def test_archive_custom_field_success(self):
        created = client_data_store.create_custom_field(client_id=30, label="Appointments", value_kind="count")
        archived = client_data_store.archive_custom_field(custom_field_id=created["id"])
        self.assertEqual(archived["id"], created["id"])
        self.assertFalse(archived["is_active"])
        self.assertIsNotNone(archived["archived_at"])

    def test_archive_custom_field_affects_list_visibility(self):
        created = client_data_store.create_custom_field(client_id=30, label="Appointments", value_kind="count")
        client_data_store.archive_custom_field(custom_field_id=created["id"])

        active_rows = client_data_store.list_custom_fields(client_id=30, include_inactive=False)
        all_rows = client_data_store.list_custom_fields(client_id=30, include_inactive=True)

        self.assertEqual(active_rows, [])
        self.assertEqual([row["id"] for row in all_rows], [created["id"]])
        self.assertFalse(all_rows[0]["is_active"])

    def test_archive_custom_field_is_idempotent(self):
        created = client_data_store.create_custom_field(client_id=30, label="Appointments", value_kind="count")
        first = client_data_store.archive_custom_field(custom_field_id=created["id"])
        second = client_data_store.archive_custom_field(custom_field_id=created["id"])
        self.assertFalse(second["is_active"])
        self.assertEqual(second["archived_at"], first["archived_at"])

    def test_archive_custom_field_missing_id_raises_clear_error(self):
        with self.assertRaises(LookupError):
            client_data_store.archive_custom_field(custom_field_id=404)


    def test_get_or_create_daily_input_creates_new_row_with_defaults(self):
        row = client_data_store.get_or_create_daily_input(client_id=10, metric_date="2026-03-24", source="META_ADS")
        self.assertEqual(row["client_id"], 10)
        self.assertEqual(row["metric_date"], "2026-03-24")
        self.assertEqual(row["source"], "meta_ads")
        self.assertEqual(row["leads"], 0)
        self.assertEqual(row["phones"], 0)
        self.assertEqual(row["custom_value_1_count"], 0)
        self.assertEqual(row["custom_value_2_count"], 0)
        self.assertEqual(str(row["custom_value_3_amount"]), "0")
        self.assertEqual(str(row["custom_value_5_amount"]), "0")
        self.assertIsNone(row["notes"])

    def test_get_or_create_daily_input_returns_existing_without_duplicates(self):
        first = client_data_store.get_or_create_daily_input(client_id=10, metric_date="2026-03-24", source="meta_ads")
        second = client_data_store.get_or_create_daily_input(client_id=10, metric_date="2026-03-24", source="meta_ads")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.state.daily_rows), 1)

    def test_get_or_create_daily_input_accepts_date_object(self):
        from datetime import date
        row = client_data_store.get_or_create_daily_input(client_id=10, metric_date=date(2026, 3, 24), source="google_ads")
        self.assertEqual(row["metric_date"], "2026-03-24")

    def test_get_or_create_daily_input_rejects_invalid_metric_date(self):
        with self.assertRaises(ValueError):
            client_data_store.get_or_create_daily_input(client_id=10, metric_date="2026-15-99", source="google_ads")

    def test_get_or_create_daily_input_rejects_invalid_source(self):
        with self.assertRaises(ValueError):
            client_data_store.get_or_create_daily_input(client_id=10, metric_date="2026-03-24", source="facebook_ads")

    def test_get_or_create_daily_input_rejects_invalid_client_id(self):
        with self.assertRaises(ValueError):
            client_data_store.get_or_create_daily_input(client_id=0, metric_date="2026-03-24", source="meta_ads")


    def test_upsert_daily_input_creates_and_updates_single_field(self):
        row = client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", leads=5)
        self.assertEqual(row["leads"], 5)
        self.assertEqual(row["phones"], 0)
        self.assertEqual(len(self.state.daily_rows), 1)

    def test_upsert_daily_input_partial_update_existing_preserves_others(self):
        first = client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", leads=5)
        second = client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", phones=3)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["leads"], 5)
        self.assertEqual(second["phones"], 3)

    def test_upsert_daily_input_updates_all_numeric_fields(self):
        row = client_data_store.upsert_daily_input(
            client_id=11,
            metric_date="2026-03-24",
            source="meta_ads",
            leads=1,
            phones=2,
            custom_value_1_count=3,
            custom_value_2_count=4,
            custom_value_3_amount="5.50",
            custom_value_5_amount="6.75",
        )
        self.assertEqual(row["leads"], 1)
        self.assertEqual(row["phones"], 2)
        self.assertEqual(row["custom_value_1_count"], 3)
        self.assertEqual(row["custom_value_2_count"], 4)
        self.assertEqual(str(row["custom_value_3_amount"]), "5.50")
        self.assertEqual(str(row["custom_value_5_amount"]), "6.75")

    def test_upsert_daily_input_custom_value_5_accepts_negative(self):
        row = client_data_store.upsert_daily_input(
            client_id=11,
            metric_date="2026-03-24",
            source="meta_ads",
            custom_value_5_amount="-10.25",
        )
        self.assertEqual(str(row["custom_value_5_amount"]), "-10.25")

    def test_upsert_daily_input_rejects_no_fields(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads")

    def test_upsert_daily_input_rejects_invalid_leads(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", leads=-1)

    def test_upsert_daily_input_rejects_invalid_phones(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", phones="a")

    def test_upsert_daily_input_rejects_invalid_custom_value_1_count(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", custom_value_1_count=-2)

    def test_upsert_daily_input_rejects_invalid_custom_value_2_count(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", custom_value_2_count="x")

    def test_upsert_daily_input_rejects_negative_custom_value_3_amount(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", custom_value_3_amount="-0.01")

    def test_upsert_daily_input_rejects_non_numeric_custom_value_5_amount(self):
        with self.assertRaises(ValueError):
            client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", custom_value_5_amount="abc")

    def test_upsert_daily_input_keeps_notes_unchanged(self):
        created = client_data_store.get_or_create_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads")
        self.state.daily_rows[0]["notes"] = "keep me"
        updated = client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source="meta_ads", leads=9)
        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["notes"], "keep me")

    def test_upsert_daily_input_keeps_source_canonical(self):
        row = client_data_store.upsert_daily_input(client_id=11, metric_date="2026-03-24", source=" META_ADS ", leads=2)
        self.assertEqual(row["source"], "meta_ads")


    def test_set_daily_input_notes_creates_row_and_sets_notes(self):
        row = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="META_ADS", notes="abc")
        self.assertEqual(row["source"], "meta_ads")
        self.assertEqual(row["notes"], "abc")
        self.assertEqual(row["leads"], 0)

    def test_set_daily_input_notes_updates_existing_and_preserves_numeric_fields(self):
        base = client_data_store.upsert_daily_input(
            client_id=21,
            metric_date="2026-03-24",
            source="meta_ads",
            leads=7,
            phones=3,
            custom_value_1_count=1,
            custom_value_2_count=2,
            custom_value_3_amount="5.25",
            custom_value_5_amount="-1.50",
        )
        updated = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes="new note")
        self.assertEqual(updated["id"], base["id"])
        self.assertEqual(updated["notes"], "new note")
        self.assertEqual(updated["leads"], 7)
        self.assertEqual(updated["phones"], 3)
        self.assertEqual(updated["custom_value_1_count"], 1)
        self.assertEqual(updated["custom_value_2_count"], 2)
        self.assertEqual(str(updated["custom_value_3_amount"]), "5.25")
        self.assertEqual(str(updated["custom_value_5_amount"]), "-1.50")

    def test_set_daily_input_notes_none_clears_notes(self):
        client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes="a")
        updated = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes=None)
        self.assertIsNone(updated["notes"])

    def test_set_daily_input_notes_empty_string_clears_notes(self):
        updated = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes="")
        self.assertIsNone(updated["notes"])

    def test_set_daily_input_notes_trims_notes(self):
        updated = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes="   text   ")
        self.assertEqual(updated["notes"], "text")

    def test_set_daily_input_notes_rejects_invalid_type(self):
        with self.assertRaises(ValueError):
            client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="meta_ads", notes=123)

    def test_set_daily_input_notes_keeps_source_canonical(self):
        updated = client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source=" META_ADS ", notes="ok")
        self.assertEqual(updated["source"], "meta_ads")

    def test_set_daily_input_notes_accepts_and_rejects_metric_date(self):
        from datetime import date
        ok = client_data_store.set_daily_input_notes(client_id=21, metric_date=date(2026, 3, 24), source="meta_ads", notes="x")
        self.assertEqual(ok["metric_date"], "2026-03-24")
        with self.assertRaises(ValueError):
            client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-99-99", source="meta_ads", notes="x")

    def test_set_daily_input_notes_rejects_invalid_client_id(self):
        with self.assertRaises(ValueError):
            client_data_store.set_daily_input_notes(client_id=0, metric_date="2026-03-24", source="meta_ads", notes="x")

    def test_set_daily_input_notes_rejects_invalid_source(self):
        with self.assertRaises(ValueError):
            client_data_store.set_daily_input_notes(client_id=21, metric_date="2026-03-24", source="facebook_ads", notes="x")


    def test_list_daily_inputs_returns_empty_when_no_data(self):
        rows = client_data_store.list_daily_inputs(client_id=44, date_from="2026-03-01", date_to="2026-03-31")
        self.assertEqual(rows, [])

    def test_list_daily_inputs_filters_by_client_and_range_and_sort(self):
        client_data_store.upsert_daily_input(client_id=44, metric_date="2026-03-20", source="tiktok_ads", leads=1)
        client_data_store.upsert_daily_input(client_id=44, metric_date="2026-03-21", source="meta_ads", leads=2)
        client_data_store.upsert_daily_input(client_id=44, metric_date="2026-03-21", source="google_ads", leads=3)
        client_data_store.upsert_daily_input(client_id=44, metric_date="2026-03-22", source="meta_ads", leads=4)
        client_data_store.upsert_daily_input(client_id=99, metric_date="2026-03-21", source="meta_ads", leads=5)

        rows = client_data_store.list_daily_inputs(client_id=44, date_from="2026-03-21", date_to="2026-03-22")
        self.assertEqual([r["metric_date"] for r in rows], ["2026-03-22", "2026-03-21", "2026-03-21"])
        self.assertEqual([r["source"] for r in rows], ["meta_ads", "google_ads", "meta_ads"])
        self.assertTrue(all(r["client_id"] == 44 for r in rows))

    def test_list_daily_inputs_returns_stable_shape(self):
        row = client_data_store.upsert_daily_input(client_id=44, metric_date="2026-03-21", source="meta_ads", leads=8)
        rows = client_data_store.list_daily_inputs(client_id=44, date_from="2026-03-21", date_to="2026-03-21")
        self.assertEqual(len(rows), 1)
        item = rows[0]
        self.assertEqual(item["id"], row["id"])
        self.assertIn("custom_value_5_amount", item)
        self.assertIn("notes", item)

    def test_list_daily_inputs_accepts_date_objects(self):
        from datetime import date
        client_data_store.upsert_daily_input(client_id=44, metric_date=date(2026, 3, 21), source="meta_ads", leads=1)
        rows = client_data_store.list_daily_inputs(client_id=44, date_from=date(2026, 3, 21), date_to=date(2026, 3, 21))
        self.assertEqual(len(rows), 1)

    def test_list_daily_inputs_rejects_invalid_date_from(self):
        with self.assertRaises(ValueError):
            client_data_store.list_daily_inputs(client_id=44, date_from="bad", date_to="2026-03-21")

    def test_list_daily_inputs_rejects_invalid_date_to(self):
        with self.assertRaises(ValueError):
            client_data_store.list_daily_inputs(client_id=44, date_from="2026-03-21", date_to="bad")

    def test_list_daily_inputs_rejects_invalid_date_range(self):
        with self.assertRaises(ValueError):
            client_data_store.list_daily_inputs(client_id=44, date_from="2026-03-22", date_to="2026-03-21")

    def test_list_daily_inputs_rejects_invalid_client_id(self):
        with self.assertRaises(ValueError):
            client_data_store.list_daily_inputs(client_id=0, date_from="2026-03-21", date_to="2026-03-21")


if __name__ == "__main__":
    unittest.main()
