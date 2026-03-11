import os
import unittest
from datetime import date

from fastapi import HTTPException

from app.api import clients as clients_api
from app.schemas.client import MediaBuyingConfigUpdateRequest, MediaBuyingLeadDailyValueUpsertRequest
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service


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

    def tearDown(self):
        clients_api.media_buying_store = self.original_store
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
            payload=MediaBuyingConfigUpdateRequest(template_type="lead", custom_label_1="Leads calificate", custom_label_5="Refund"),
            user=self.user,
        )

        self.assertEqual(updated["custom_label_1"], "Leads calificate")
        self.assertEqual(updated["custom_label_5"], "Refund")

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


if __name__ == "__main__":
    unittest.main()
