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
            created_at = previous[9] if previous else "2026-03-11T10:00:00+00:00"
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
                bool(params[8]),
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
        self.assertEqual(result["display_currency"], "RON")
        self.assertEqual(result["custom_label_1"], "Apeluri")
        self.assertEqual(result["custom_label_5"], "Refund")

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


class MediaBuyingLeadTableReadTests(unittest.TestCase):
    def _build_store(self):
        store = MediaBuyingStore()
        store._ensure_schema = lambda: None
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
        self.assertIsNone(row["percent_change"])

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
        self.assertIsNone(totals["percent_change"])

    def test_non_lead_template_is_not_implemented(self):
        store = self._build_store()
        store.get_config = lambda **kwargs: {"client_id": 12, "template_type": "ecommerce", "display_currency": "RON"}
        store.list_lead_daily_manual_values = lambda **kwargs: []
        store._list_automated_daily_costs = lambda **kwargs: []

        with self.assertRaises(NotImplementedError):
            store.get_lead_table(client_id=12, date_from=date(2026, 3, 1), date_to=date(2026, 3, 2))


if __name__ == "__main__":
    unittest.main()
