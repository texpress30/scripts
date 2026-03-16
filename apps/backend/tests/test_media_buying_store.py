import unittest
from datetime import date
from decimal import Decimal

from app.services.media_buying_store import MediaBuyingStore


class _MediaBuyingCursor:
    def __init__(self, state: dict[str, object]):
        self.state = state
        self._fetchone = None
        self._fetchall = None

    def execute(self, query, params=None):
        q = " ".join(str(query).split())
        params = params or ()
        self._fetchone = None
        self._fetchall = None

        if "FROM media_buying_configs" in q and "WHERE client_id = %s" in q and q.startswith("SELECT"):
            row = self.state.get("configs", {}).get(int(params[0]))
            self._fetchone = row
            return

        if q.startswith("INSERT INTO media_buying_configs"):
            client_id = int(params[0])
            configs = self.state.setdefault("configs", {})
            previous = configs.get(client_id)
            created_at = previous[14] if previous else "2026-03-11T10:00:00+00:00"
            updated_at = "2026-03-11T11:00:00+00:00"
            configs[client_id] = (
                client_id,
                params[1],
                params[2],
                params[3],
                params[4],
                params[5],
                params[6],
                params[7],
                params[8],
                params[9],
                params[10],
                params[11],
                params[12],
                bool(params[13]),
                created_at,
                updated_at,
            )
            return

        if q.startswith("INSERT INTO media_buying_lead_daily_manual_values"):
            client_id = int(params[0])
            metric_date = params[1]
            values = self.state.setdefault("daily", {})
            key = (client_id, metric_date)
            previous = values.get(key)
            created_at = previous[10] if previous else "2026-03-11T10:00:00+00:00"
            updated_at = "2026-03-11T11:00:00+00:00"
            values[key] = (
                client_id,
                metric_date,
                int(params[2]),
                int(params[3]),
                int(params[4]),
                int(params[5]),
                Decimal(str(params[6])),
                Decimal(str(params[7])),
                Decimal(str(params[8])),
                int(params[9]),
                created_at,
                updated_at,
            )
            return

        if "FROM media_buying_lead_daily_manual_values" in q and "WHERE client_id = %s AND metric_date = %s" in q:
            key = (int(params[0]), params[1])
            self._fetchone = self.state.get("daily", {}).get(key)
            return

        if "FROM media_buying_lead_daily_manual_values" in q and "metric_date >= %s" in q:
            client_id = int(params[0])
            date_from = params[1]
            date_to = params[2]
            rows = []
            for (cid, d), row in self.state.get("daily", {}).items():
                if cid == client_id and date_from <= d <= date_to:
                    rows.append(row)
            rows.sort(key=lambda r: r[1])
            self._fetchall = rows
            return

        if "FROM media_buying_lead_daily_manual_values" in q and "WHERE client_id = %s" in q and "metric_date >= %s" not in q:
            client_id = int(params[0])
            rows = []
            for (cid, _), row in self.state.get("daily", {}).items():
                if cid == client_id:
                    rows.append(row)
            rows.sort(key=lambda r: r[1])
            self._fetchall = rows
            return

        raise AssertionError(f"Unexpected query: {q}")

    def fetchone(self):
        return self._fetchone

    def fetchall(self):
        return self._fetchall or []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _MediaBuyingConn:
    def __init__(self, cursor: _MediaBuyingCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class MediaBuyingStoreTests(unittest.TestCase):
    def _build_store(self):
        state: dict[str, object] = {"configs": {}, "daily": {}}
        cursor = _MediaBuyingCursor(state)
        conn = _MediaBuyingConn(cursor)

        store = MediaBuyingStore()
        store._ensure_schema = lambda: None
        store._connect = lambda: conn
        store._resolve_client_template_type = lambda **kwargs: "lead"
        return store, state

    def test_upsert_config_persists_template_type_and_custom_labels(self):
        store, _ = self._build_store()

        result = store.upsert_config(
            client_id=12,
            template_type="lead",
            custom_label_1="Apeluri",
            custom_label_2="Programări",
            custom_label_3="Încasări",
            custom_label_4="Taxe",
            custom_label_5="Refund",
            enabled=True,
        )

        self.assertEqual(result["client_id"], 12)
        self.assertEqual(result["template_type"], "lead")
        self.assertEqual(result["display_currency"], "USD")
        self.assertEqual(result["display_currency_source"], "safe_fallback")
        self.assertEqual(result["custom_label_1"], "Apeluri")
        self.assertEqual(result["custom_label_5"], "Refund")


    def test_config_includes_extended_inline_header_labels(self):
        store, _ = self._build_store()
        store._resolve_client_template_type = lambda **kwargs: "programmatic"

        cfg = store.upsert_config(
            client_id=12,
            custom_rate_label_1="Rate A",
            custom_rate_label_2="Rate B",
            custom_cost_label_1="Cost A",
            custom_cost_label_2="Cost B",
            visible_columns=["date", "cost_total"],
        )

        self.assertEqual(cfg["template_type"], "programmatic")
        self.assertEqual(cfg["custom_rate_label_1"], "Rate A")
        self.assertEqual(cfg["custom_rate_label_2"], "Rate B")
        self.assertEqual(cfg["custom_cost_label_1"], "Cost A")
        self.assertEqual(cfg["custom_cost_label_2"], "Cost B")
        self.assertEqual(cfg["visible_columns"], ["date", "cost_total"])


    def test_get_config_overrides_stale_local_display_currency_with_client_display_currency(self):
        store, state = self._build_store()
        state["configs"][12] = (
            12,
            "lead",
            "RON",
            "Custom Value 1",
            "Custom Value 2",
            "Custom Value 3",
            "Custom Value 4",
            "Custom Value 5",
            "Custom Value Rate 1",
            "Custom Value Rate 2",
            "Cost Custom Value 1",
            "Cost Custom Value 2",
            ["date", "cost_total"],
            True,
            "2026-03-11T10:00:00+00:00",
            "2026-03-11T11:00:00+00:00",
        )
        store._resolve_client_display_currency_decision = lambda **kwargs: ("USD", "agency_client_currency")

        cfg = store.get_config(client_id=12)

        self.assertEqual(cfg["display_currency"], "USD")
        self.assertEqual(cfg["display_currency_source"], "agency_client_currency")

    def test_upsert_config_ignores_incoming_display_currency_and_syncs_to_client_display_currency(self):
        store, state = self._build_store()
        store._resolve_client_display_currency_decision = lambda **kwargs: ("EUR", "agency_client_currency")

        cfg = store.upsert_config(client_id=12, display_currency="RON", custom_label_1="Apeluri")

        self.assertEqual(cfg["display_currency"], "EUR")
        self.assertEqual(cfg["display_currency_source"], "agency_client_currency")
        self.assertEqual(state["configs"][12][2], "EUR")

    def test_upsert_lead_daily_values_is_idempotent_for_same_day(self):
        store, state = self._build_store()

        first = store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 10),
            leads=10,
            phones=5,
            custom_value_1_count=2,
            custom_value_2_count=1,
            custom_value_3_amount_ron=100,
            custom_value_4_amount_ron=20,
            custom_value_5_amount_ron=-5,
            sales_count=3,
        )
        second = store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 10),
            leads=11,
            phones=6,
            custom_value_1_count=3,
            custom_value_2_count=2,
            custom_value_3_amount_ron=110,
            custom_value_4_amount_ron=22,
            custom_value_5_amount_ron=-7,
            sales_count=4,
        )

        self.assertEqual(first["date"], "2026-03-10")
        self.assertEqual(second["leads"], 11)
        self.assertEqual(len(state["daily"]), 1)

    def test_validations_for_counts_amounts_and_dates(self):
        store, _ = self._build_store()

        with self.assertRaisesRegex(ValueError, "leads"):
            store.upsert_lead_daily_manual_value(
                client_id=12,
                metric_date=date(2026, 3, 11),
                leads=-1,
                phones=0,
                custom_value_1_count=0,
                custom_value_2_count=0,
                custom_value_3_amount_ron=0,
                custom_value_4_amount_ron=0,
                custom_value_5_amount_ron=0,
                sales_count=0,
            )

        with self.assertRaisesRegex(ValueError, "custom_value_3_amount_ron"):
            store.upsert_lead_daily_manual_value(
                client_id=12,
                metric_date=date(2026, 3, 11),
                leads=1,
                phones=0,
                custom_value_1_count=0,
                custom_value_2_count=0,
                custom_value_3_amount_ron=-1,
                custom_value_4_amount_ron=0,
                custom_value_5_amount_ron=0,
                sales_count=0,
            )

        with self.assertRaisesRegex(ValueError, "date_from"):
            store.list_lead_daily_manual_values(client_id=12, date_from=date(2026, 3, 12), date_to=date(2026, 3, 11))

    def test_list_interval_returns_expected_rows(self):
        store, _ = self._build_store()

        store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 9),
            leads=9,
            phones=1,
            custom_value_1_count=1,
            custom_value_2_count=1,
            custom_value_3_amount_ron=90,
            custom_value_4_amount_ron=10,
            custom_value_5_amount_ron=0,
            sales_count=1,
        )
        store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 10),
            leads=10,
            phones=2,
            custom_value_1_count=1,
            custom_value_2_count=1,
            custom_value_3_amount_ron=100,
            custom_value_4_amount_ron=20,
            custom_value_5_amount_ron=-2,
            sales_count=2,
        )

        rows = store.list_lead_daily_manual_values(
            client_id=12,
            date_from=date(2026, 3, 10),
            date_to=date(2026, 3, 10),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-03-10")
        self.assertEqual(rows[0]["custom_value_5_amount_ron"], -2.0)

    def test_list_manual_values_is_null_safe_when_both_dates_missing(self):
        store, _ = self._build_store()
        store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 9),
            leads=1,
            phones=0,
            custom_value_1_count=0,
            custom_value_2_count=0,
            custom_value_3_amount_ron=10,
            custom_value_4_amount_ron=0,
            custom_value_5_amount_ron=0,
            sales_count=0,
        )

        rows = store.list_lead_daily_manual_values(client_id=12, date_from=None, date_to=None)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-03-09")

    def test_list_manual_values_requires_both_dates_or_none(self):
        store, _ = self._build_store()
        with self.assertRaisesRegex(ValueError, "provided together"):
            store.list_lead_daily_manual_values(client_id=12, date_from=date(2026, 3, 1), date_to=None)

    def test_get_lead_table_no_range_automated_only_no_crash(self):
        store, _ = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 10), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12)

        self.assertEqual(payload["meta"]["date_from"], "2026-03-10")
        self.assertEqual(payload["days"][0]["date"], "2026-03-10")

    def test_get_lead_table_no_range_automated_and_manual_no_crash(self):
        store, _ = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 11),
            leads=3,
            phones=0,
            custom_value_1_count=0,
            custom_value_2_count=0,
            custom_value_3_amount_ron=0,
            custom_value_4_amount_ron=0,
            custom_value_5_amount_ron=0,
            sales_count=0,
        )
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 10), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12)

        self.assertEqual(payload["meta"]["date_from"], "2026-03-10")
        self.assertEqual(payload["meta"]["date_to"], "2026-03-11")
        self.assertEqual([row["date"] for row in payload["days"]], ["2026-03-10", "2026-03-11"])

    def test_get_lead_table_no_range_manual_only_no_crash_and_include_days_false(self):
        store, _ = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "display_currency_source": "agency_client_currency"}
        store.upsert_lead_daily_manual_value(
            client_id=12,
            metric_date=date(2026, 3, 12),
            leads=2,
            phones=0,
            custom_value_1_count=0,
            custom_value_2_count=0,
            custom_value_3_amount_ron=0,
            custom_value_4_amount_ron=0,
            custom_value_5_amount_ron=0,
            sales_count=0,
        )
        store._list_automated_daily_costs = lambda **kwargs: []
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, include_days=False)

        self.assertEqual(payload["meta"]["date_from"], "2026-03-12")
        self.assertEqual(payload["days"], [])
        self.assertEqual(payload["months"][0]["day_count"], 1)



class MediaBuyingLeadTableReadTests(unittest.TestCase):
    def _build_store(self):
        store = MediaBuyingStore()
        store._ensure_schema = lambda: None
        store._resolve_client_template_type = lambda **kwargs: "lead"
        store._get_lead_table_data_bounds = lambda **kwargs: (None, None)
        return store

    def test_get_lead_table_merges_costs_manual_and_fx_and_formulas(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {
            "client_id": 12,
            "template_type": "lead",
            "display_currency": "RON",
            "custom_label_1": "CV1",
            "custom_label_2": "CV2",
            "custom_label_3": "CV3",
            "custom_label_4": "CV4",
            "custom_label_5": "CV5",
        }
        store.list_lead_daily_manual_values = lambda **kwargs: [
            {
                "date": "2026-03-10",
                "leads": 10,
                "phones": 5,
                "custom_value_1_count": 3,
                "custom_value_2_count": 2,
                "custom_value_3_amount_ron": 100,
                "custom_value_4_amount_ron": 20,
                "custom_value_5_amount_ron": -5,
                "sales_count": 2,
            }
        ]
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 10), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
            {"date": date(2026, 3, 10), "platform": "meta_ads", "account_currency": "USD", "spend": 10.0},
            {"date": date(2026, 3, 10), "platform": "tiktok_ads", "account_currency": "RON", "spend": 50.0},
        ]

        def _fake_normalize(*, amount, from_currency, display_currency, rate_date):
            if from_currency == "USD" and display_currency == "RON":
                return amount * 5
            return amount

        store._normalize_money_to_display_currency = _fake_normalize

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 10), date_to=date(2026, 3, 10))

        self.assertEqual(payload["meta"]["template_type"], "lead")
        self.assertEqual(payload["meta"]["available_months"], ["2026-03"])
        row = payload["days"][0]
        self.assertEqual(row["cost_google"], 100.0)
        self.assertEqual(row["cost_meta"], 50.0)
        self.assertEqual(row["cost_tiktok"], 50.0)
        self.assertEqual(row["cost_total"], 200.0)
        self.assertEqual(row["total_leads"], 15)
        self.assertAlmostEqual(float(row["custom_value_rate_1"]), 2 / 3)
        self.assertAlmostEqual(float(row["cost_per_lead"]), 200 / 15)
        self.assertAlmostEqual(float(row["cost_per_sale"]), 100.0)
        self.assertEqual(row["custom_value_4_amount_ron"], 105.0)
        self.assertEqual(row["custom_value_5_amount_ron"], -5.0)
        self.assertIsNone(row["percent_change"])


    def test_lead_table_uses_client_display_currency_not_stale_local_config_currency(self):
        store, state = MediaBuyingStoreTests()._build_store()
        state["configs"][12] = (
            12,
            "lead",
            "RON",
            "Custom Value 1",
            "Custom Value 2",
            "Custom Value 3",
            "Custom Value 4",
            "Custom Value 5",
            "Custom Value Rate 1",
            "Custom Value Rate 2",
            "Cost Custom Value 1",
            "Cost Custom Value 2",
            ["date", "cost_total"],
            True,
            "2026-03-11T10:00:00+00:00",
            "2026-03-11T11:00:00+00:00",
        )
        store._resolve_client_display_currency_decision = lambda **kwargs: ("USD", "agency_client_currency")
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 10), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"] / 5.0 if kwargs["display_currency"] == "USD" else kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 10), date_to=date(2026, 3, 10))

        self.assertEqual(payload["meta"]["display_currency"], "USD")
        self.assertEqual(payload["meta"]["display_currency_source"], "agency_client_currency")
        self.assertAlmostEqual(float(payload["days"][0]["cost_google"]), 20.0)

    def test_lead_table_display_currency_is_client_specific_for_multiple_clients(self):
        store = self._build_store()
        currency_by_client = {
            10: ("USD", 1.0),
            20: ("RON", 5.0),
            30: ("EUR", 0.9),
        }

        def _config(*, client_id: int):
            code, _ = currency_by_client[int(client_id)]
            return {
                "client_id": client_id,
                "template_type": "lead",
                "display_currency": code,
                "display_currency_source": "agency_client_currency",
            }

        store.get_config = _config
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 10), "platform": "google_ads", "account_currency": "USD", "spend": 10.0},
        ]

        def _normalize(*, amount: float, from_currency: str, display_currency: str, rate_date: date):
            if display_currency == "USD":
                return amount
            if display_currency == "RON":
                return amount * 5.0
            if display_currency == "EUR":
                return amount * 0.9
            return amount

        store._normalize_money_to_display_currency = _normalize

        usd = store.get_lead_table(client_id=10, date_from=date(2026, 3, 10), date_to=date(2026, 3, 10))
        ron = store.get_lead_table(client_id=20, date_from=date(2026, 3, 10), date_to=date(2026, 3, 10))
        eur = store.get_lead_table(client_id=30, date_from=date(2026, 3, 10), date_to=date(2026, 3, 10))

        self.assertEqual(usd["meta"]["display_currency"], "USD")
        self.assertEqual(ron["meta"]["display_currency"], "RON")
        self.assertEqual(eur["meta"]["display_currency"], "EUR")

        self.assertAlmostEqual(float(usd["days"][0]["cost_total"]), 10.0)
        self.assertAlmostEqual(float(ron["days"][0]["cost_total"]), 50.0)
        self.assertAlmostEqual(float(eur["days"][0]["cost_total"]), 9.0)

    def test_monthly_totals_are_recomputed_from_month_sums_and_missing_manual_is_zero(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "custom_label_1": "a", "custom_label_2": "b", "custom_label_3": "c", "custom_label_4": "d", "custom_label_5": "e"}
        store.list_lead_daily_manual_values = lambda **kwargs: [
            {"date": "2026-03-01", "leads": 1, "phones": 1, "custom_value_1_count": 1, "custom_value_2_count": 1, "custom_value_3_amount_ron": 10, "custom_value_4_amount_ron": 1, "custom_value_5_amount_ron": 0, "sales_count": 1},
            {"date": "2026-03-02", "leads": 2, "phones": 0, "custom_value_1_count": 2, "custom_value_2_count": 1, "custom_value_3_amount_ron": 20, "custom_value_4_amount_ron": 2, "custom_value_5_amount_ron": 0, "sales_count": 1},
        ]
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 1), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
            {"date": date(2026, 3, 2), "platform": "google_ads", "account_currency": "RON", "spend": 200.0},
            {"date": date(2026, 3, 3), "platform": "google_ads", "account_currency": "RON", "spend": 300.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 3, 3))

        self.assertEqual(len(payload["days"]), 3)
        self.assertEqual(payload["days"][2]["leads"], 0)
        self.assertIsNone(payload["days"][2]["cost_per_sale"])

        month = payload["months"][0]
        totals = month["totals"]
        self.assertEqual(totals["cost_total"], 600.0)
        self.assertEqual(totals["leads"], 3)
        self.assertEqual(totals["phones"], 1)
        self.assertEqual(totals["total_leads"], 4)
        self.assertAlmostEqual(float(totals["cost_per_lead"]), 150.0)
        self.assertAlmostEqual(float(totals["cost_per_sale"]), 300.0)
        self.assertEqual(totals["custom_value_4_amount_ron"], 30.0)
        self.assertIsNone(totals["percent_change"])


    def test_percent_change_daily_and_monthly_follow_chronological_cost_totals(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "custom_label_1": "a", "custom_label_2": "b", "custom_label_3": "c", "custom_label_4": "d", "custom_label_5": "e"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 2, 28), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
            {"date": date(2026, 3, 1), "platform": "google_ads", "account_currency": "RON", "spend": 200.0},
            {"date": date(2026, 3, 2), "platform": "google_ads", "account_currency": "RON", "spend": 50.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 2, 28), date_to=date(2026, 3, 2))

        self.assertIsNone(payload["days"][0]["percent_change"])
        self.assertAlmostEqual(float(payload["days"][1]["percent_change"]), 1.0)
        self.assertAlmostEqual(float(payload["days"][2]["percent_change"]), -0.75)

        self.assertEqual([item["month"] for item in payload["months"]], ["2026-02", "2026-03"])
        self.assertIsNone(payload["months"][0]["totals"]["percent_change"])
        self.assertAlmostEqual(float(payload["months"][1]["totals"]["percent_change"]), 1.5)

    def test_percent_change_returns_null_when_previous_total_missing_or_zero(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "custom_label_1": "a", "custom_label_2": "b", "custom_label_3": "c", "custom_label_4": "d", "custom_label_5": "e"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 2, 1), "platform": "google_ads", "account_currency": "RON", "spend": 0.0},
            {"date": date(2026, 2, 2), "platform": "google_ads", "account_currency": "RON", "spend": 50.0},
            {"date": date(2026, 2, 3), "platform": "google_ads", "account_currency": "RON", "spend": 10.0},
            {"date": date(2026, 3, 1), "platform": "google_ads", "account_currency": "RON", "spend": 0.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 2, 1), date_to=date(2026, 3, 1))

        self.assertIsNone(payload["days"][0]["percent_change"])
        self.assertAlmostEqual(float(payload["days"][1]["percent_change"]), -0.8)

        self.assertEqual([item["month"] for item in payload["months"]], ["2026-02"])
        self.assertIsNone(payload["months"][0]["totals"]["percent_change"])


    def test_monthly_percent_change_is_null_when_previous_month_total_is_zero(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "custom_label_1": "a", "custom_label_2": "b", "custom_label_3": "c", "custom_label_4": "d", "custom_label_5": "e"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 1), "platform": "google_ads", "account_currency": "RON", "spend": 0.0},
            {"date": date(2026, 4, 1), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 4, 1))

        self.assertEqual([item["month"] for item in payload["months"]], ["2026-04"])
        self.assertIsNone(payload["months"][0]["totals"]["percent_change"])

    def test_default_range_uses_real_data_bounds_and_skips_months_without_data(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store._get_lead_table_data_bounds = lambda **kwargs: (date(2025, 8, 4), date(2025, 8, 5))
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2025, 8, 4), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
            {"date": date(2025, 8, 5), "platform": "google_ads", "account_currency": "RON", "spend": 50.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12)

        self.assertEqual(payload["meta"]["date_from"], "2025-08-04")
        self.assertEqual(payload["meta"]["date_to"], "2025-08-05")
        self.assertEqual(payload["meta"]["effective_date_from"], "2025-08-04")
        self.assertEqual(payload["meta"]["effective_date_to"], "2025-08-05")
        self.assertEqual(payload["meta"]["earliest_data_date"], "2025-08-04")
        self.assertEqual(payload["meta"]["latest_data_date"], "2025-08-05")
        self.assertEqual(payload["meta"]["available_months"], ["2025-08"])
        self.assertEqual([row["date"] for row in payload["days"]], ["2025-08-04", "2025-08-05"])

    def test_explicit_range_keeps_support_but_removes_empty_days_and_months(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 12), "platform": "google_ads", "account_currency": "RON", "spend": 120.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 4, 10))

        self.assertEqual(payload["meta"]["date_from"], "2026-03-01")
        self.assertEqual(payload["meta"]["date_to"], "2026-04-10")
        self.assertEqual(payload["meta"]["effective_date_from"], "2026-03-12")
        self.assertEqual(payload["meta"]["effective_date_to"], "2026-03-12")
        self.assertEqual([item["month"] for item in payload["months"]], ["2026-03"])
        self.assertEqual([row["date"] for row in payload["days"]], ["2026-03-12"])

    def test_manual_values_alone_activate_day_even_when_costs_are_zero(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store.list_lead_daily_manual_values = lambda **kwargs: [
            {
                "date": "2026-03-14",
                "leads": 1,
                "phones": 0,
                "custom_value_1_count": 0,
                "custom_value_2_count": 0,
                "custom_value_3_amount_ron": 0,
                "custom_value_4_amount_ron": 0,
                "custom_value_5_amount_ron": 0,
                "sales_count": 0,
            }
        ]
        store._list_automated_daily_costs = lambda **kwargs: []
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 10), date_to=date(2026, 3, 20))

        self.assertEqual([row["date"] for row in payload["days"]], ["2026-03-14"])
        self.assertEqual(payload["months"][0]["totals"]["leads"], 1)

    def test_default_range_does_not_call_bounds_query_and_uses_full_scan_rows(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store._get_lead_table_data_bounds = lambda **kwargs: (_ for _ in ()).throw(AssertionError("bounds query should not be used"))

        automated_call = {}
        manual_call = {}

        def _auto(**kwargs):
            automated_call.update(kwargs)
            return [{"date": date(2026, 1, 2), "platform": "google_ads", "account_currency": "RON", "spend": 10.0}]

        def _manual(**kwargs):
            manual_call.update(kwargs)
            return []

        store._list_automated_daily_costs = _auto
        store.list_lead_daily_manual_values = _manual
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12)

        self.assertEqual(payload["meta"]["date_from"], "2026-01-02")
        self.assertEqual(payload["meta"]["date_to"], "2026-01-02")
        self.assertIsNone(automated_call["date_from"])
        self.assertIsNone(automated_call["date_to"])
        self.assertIsNone(manual_call["date_from"])
        self.assertIsNone(manual_call["date_to"])

    def test_explicit_range_passes_date_filters_to_queries(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}

        automated_call = {}
        manual_call = {}

        def _auto(**kwargs):
            automated_call.update(kwargs)
            return []

        def _manual(**kwargs):
            manual_call.update(kwargs)
            return []

        store._list_automated_daily_costs = _auto
        store.list_lead_daily_manual_values = _manual

        _ = store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 3, 31))

        self.assertEqual(automated_call["date_from"], date(2026, 3, 1))
        self.assertEqual(automated_call["date_to"], date(2026, 3, 31))
        self.assertEqual(manual_call["date_from"], date(2026, 3, 1))
        self.assertEqual(manual_call["date_to"], date(2026, 3, 31))

    def test_get_lead_table_logs_timing_once_per_call(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store._list_automated_daily_costs = lambda **kwargs: [{"date": date(2026, 3, 12), "platform": "google_ads", "account_currency": "RON", "spend": 10.0}]
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        import app.services.media_buying_store as media_buying_module

        captured = []
        original_info = media_buying_module.logger.info
        try:
            media_buying_module.logger.info = lambda message, extra=None: captured.append((message, extra))
            _ = store.get_lead_table(client_id=12)
        finally:
            media_buying_module.logger.info = original_info

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "media_buying_lead_table_timing")
        self.assertEqual(captured[0][1]["client_id"], 12)
        self.assertIn("automated_query_ms", captured[0][1])
        self.assertIn("manual_query_ms", captured[0][1])
        self.assertIn("total_ms", captured[0][1])

    def test_get_lead_table_include_days_false_returns_months_without_eager_days(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON", "display_currency_source": "agency_client_currency"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 12), "platform": "google_ads", "account_currency": "RON", "spend": 120.0},
            {"date": date(2026, 3, 13), "platform": "google_ads", "account_currency": "RON", "spend": 50.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 3, 31), include_days=False)

        self.assertEqual(payload["days"], [])
        self.assertEqual(payload["meta"]["display_currency"], "RON")
        self.assertEqual(payload["months"][0]["month"], "2026-03")
        self.assertEqual(payload["months"][0]["day_count"], 2)
        self.assertTrue(payload["months"][0]["has_days"])
        self.assertNotIn("days", payload["months"][0])

    def test_get_lead_month_days_returns_single_month_rows(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "USD", "display_currency_source": "agency_client_currency"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 3, 12), "platform": "google_ads", "account_currency": "USD", "spend": 20.0},
            {"date": date(2026, 4, 2), "platform": "google_ads", "account_currency": "USD", "spend": 30.0},
        ]
        store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

        payload = store.get_lead_month_days(client_id=12, month_start=date(2026, 3, 1))

        self.assertEqual(payload["month_start"], "2026-03-01")
        self.assertEqual([item["date"] for item in payload["days"]], ["2026-03-12"])
        self.assertEqual(payload["days"][0]["display_currency"], "USD")

    def test_get_lead_month_days_validation(self):
        store = self._build_store()
        with self.assertRaisesRegex(ValueError, "first day of month"):
            store.get_lead_month_days(client_id=12, month_start=date(2026, 3, 2))

    def test_non_lead_template_is_not_implemented(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "lead", "display_currency": "RON"}
        store._resolve_client_template_type = lambda **kwargs: "ecommerce"
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: []

        with self.assertRaises(NotImplementedError):
            store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 3, 2))


if __name__ == "__main__":
    unittest.main()


class MediaBuyingStoreBoundsQueryTests(unittest.TestCase):
    def test_bounds_query_uses_ad_performance_reports_source(self):
        captured_queries: list[str] = []

        class _Cursor:
            def __init__(self):
                self._idx = 0

            def execute(self, query, params=None):
                captured_queries.append(" ".join(str(query).split()))

            def fetchone(self):
                self._idx += 1
                if self._idx == 1:
                    return (date(2026, 1, 10), date(2026, 3, 1))
                return (None, None)

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

        earliest, latest = store._get_lead_table_data_bounds(client_id=12)

        self.assertEqual(earliest, date(2026, 1, 10))
        self.assertEqual(latest, date(2026, 3, 1))
        all_sql = "\n".join(captured_queries)
        self.assertIn("FROM ad_performance_reports apr", all_sql)
        self.assertIn("mapped.client_id = %s", all_sql)
        self.assertNotIn("mapped.created_at::date <= apr.report_date", all_sql)
        self.assertIn("'account_daily'", all_sql)
        self.assertNotIn("ads_platform_reporting", all_sql)

    def test_automated_costs_query_uses_account_daily_and_mapping_membership(self):
        captured_query = ""

        class _Cursor:
            def execute(self, query, params=None):
                nonlocal captured_query
                captured_query = " ".join(str(query).split())

            def fetchall(self):
                return [(date(2026, 2, 1), "tiktok_ads", "RON", 805.85)]

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

        rows = store._list_automated_daily_costs(client_id=97, date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))

        self.assertEqual(rows[0]["platform"], "tiktok_ads")
        self.assertEqual(rows[0]["account_currency"], "RON")
        self.assertAlmostEqual(float(rows[0]["spend"]), 805.85)
        self.assertIn("FROM ad_performance_reports apr", captured_query)
        self.assertIn("mapped.client_id = %s", captured_query)
        self.assertNotIn("mapped.created_at::date <= apr.report_date", captured_query)
        self.assertIn("agency_platform_accounts apa", captured_query)
        self.assertIn("scoped_mapped", captured_query)
        self.assertIn("account_id_digits", captured_query)
        self.assertIn("apa.currency_code", captured_query)
        self.assertNotIn("apa.account_currency", captured_query)
        self.assertIn("'account_daily'", captured_query)

    def test_automated_costs_query_placeholder_count_matches_params_for_explicit_range(self):
        class _Cursor:
            def execute(self, query, params=None):
                query_text = str(query)
                placeholder_count = query_text.count("%s")
                provided_count = len(tuple(params or ()))
                if placeholder_count != provided_count:
                    raise AssertionError(f"placeholder mismatch: {placeholder_count} vs {provided_count}")

            def fetchall(self):
                return [(date(2026, 2, 1), "meta_ads", "USD", 125.0)]

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

        rows = store._list_automated_daily_costs(client_id=97, date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "meta_ads")

    def test_automated_costs_query_keeps_date_predicates_only_in_scoped_reports(self):
        captured_query = ""

        class _Cursor:
            def execute(self, query, params=None):
                nonlocal captured_query
                captured_query = " ".join(str(query).split())

            def fetchall(self):
                return []

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

        _ = store._list_automated_daily_costs(client_id=97, date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))

        self.assertEqual(captured_query.count("apr.report_date >= %s::date"), 1)
        self.assertEqual(captured_query.count("apr.report_date <= %s::date"), 1)
        perf_section = captured_query.split("perf AS", maxsplit=1)[1]
        self.assertNotIn("apr.report_date >= %s::date", perf_section)
        self.assertNotIn("apr.report_date <= %s::date", perf_section)

    def test_get_lead_table_include_days_false_does_not_hit_placeholder_mismatch(self):
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

        payload = store.get_lead_table(
            client_id=97,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            include_days=False,
        )

        self.assertEqual(payload["days"], [])
        self.assertEqual(len(payload["months"]), 1)
        self.assertEqual(payload["months"][0]["day_count"], 1)

    def test_tiktok_ron_costs_do_not_get_reconverted_when_display_currency_is_ron(self):
        store = MediaBuyingStore()
        store._ensure_schema = lambda: None
        store.get_config = lambda **kwargs: {"client_id": 97, "template_type": "lead", "display_currency": "RON"}
        store._resolve_client_template_type = lambda **kwargs: "lead"
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: [
            {"date": date(2026, 2, 1), "platform": "tiktok_ads", "account_currency": "RON", "spend": 805.85},
            {"date": date(2026, 3, 11), "platform": "tiktok_ads", "account_currency": "RON", "spend": 50.40},
        ]

        def _normalize(amount: float, from_currency: str, display_currency: str, rate_date: date):
            if from_currency == display_currency:
                return amount
            return amount * 4.4

        store._normalize_money_to_display_currency = _normalize

        payload = store.get_lead_table(client_id=97, date_from=date(2026, 2, 1), date_to=date(2026, 3, 31))

        per_day = {row["date"]: row for row in payload["days"]}
        self.assertAlmostEqual(float(per_day["2026-02-01"]["cost_tiktok"]), 805.85, places=2)
        self.assertAlmostEqual(float(per_day["2026-03-11"]["cost_tiktok"]), 50.40, places=2)

    def test_automated_costs_query_does_not_clamp_history_by_mapping_created_at(self):
        captured_query = ""

        class _Cursor:
            def execute(self, query, params=None):
                nonlocal captured_query
                captured_query = " ".join(str(query).split())

            def fetchall(self):
                return []

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

        _ = store._list_automated_daily_costs(client_id=97, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))

        self.assertNotIn("mapped.created_at::date <= apr.report_date", captured_query)

    def test_automated_costs_falls_back_to_usd_when_currency_missing(self):
        class _Cursor:
            def execute(self, query, params=None):
                return None

            def fetchall(self):
                return [(date(2026, 2, 1), "meta_ads", None, 125.0)]

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

        rows = store._list_automated_daily_costs(client_id=97, date_from=date(2026, 2, 1), date_to=date(2026, 2, 28))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account_currency"], "USD")
        self.assertEqual(rows[0]["platform"], "meta_ads")

    def test_bounds_merge_manual_and_automated_dates(self):
        class _Cursor:
            def __init__(self):
                self._idx = 0

            def execute(self, query, params=None):
                return None

            def fetchone(self):
                self._idx += 1
                if self._idx == 1:
                    return (date(2025, 8, 1), date(2026, 3, 11))
                return (date(2024, 6, 15), date(2024, 6, 20))

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

        earliest, latest = store._get_lead_table_data_bounds(client_id=97)

        self.assertEqual(earliest, date(2024, 6, 15))
        self.assertEqual(latest, date(2026, 3, 11))
