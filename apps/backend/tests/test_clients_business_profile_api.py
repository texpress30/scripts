import os
import unittest

from app.api import clients as clients_api
from app.schemas.client import SubaccountBusinessProfilePayload
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.subaccount_business_profile_store import subaccount_business_profile_store


class ClientsBusinessProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"

        self.original_is_test_mode = client_registry_service._is_test_mode
        client_registry_service._is_test_mode = lambda: True
        client_registry_service._clients = []
        client_registry_service._next_id = 1

        subaccount_business_profile_store._memory_profiles = {}

        self.original_enforce_scope = clients_api.enforce_action_scope
        clients_api.enforce_action_scope = lambda **kwargs: None

        self.user = AuthUser(email="owner@example.com", role="admin")
        created = client_registry_service.create_client(name="Client Empty", owner_email="owner@example.com")
        self.display_id = int(created["display_id"])

    def tearDown(self):
        clients_api.enforce_action_scope = self.original_enforce_scope
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_profile_returns_only_empty_business_profile_payload_without_display_fallback(self):
        payload = clients_api.get_subaccount_business_profile(display_id=self.display_id, user=self.user)
        assert payload.display_id == self.display_id
        assert payload.general == {}
        assert payload.business == {}
        assert payload.address == {}
        assert payload.representative == {}
        assert payload.logo_url == ""

    def test_upsert_and_get_profile_roundtrip(self):
        updated = clients_api.upsert_subaccount_business_profile(
            display_id=self.display_id,
            payload=SubaccountBusinessProfilePayload(
                general={"friendlyName": "ROC Auto", "email": "biz@roc.example"},
                business={"businessType": "srl"},
                address={"city": "Onești", "country": "RO"},
                representative={"firstName": "Ana", "lastName": "Popescu"},
                logo_url="data:image/png;base64,AAAA",
            ),
            user=self.user,
        )

        assert updated.general.get("friendlyName") == "ROC Auto"
        assert updated.address.get("city") == "Onești"
        assert updated.logo_url.startswith("data:image")

        reloaded = clients_api.get_subaccount_business_profile(display_id=self.display_id, user=self.user)
        assert reloaded.general.get("friendlyName") == "ROC Auto"
        assert reloaded.address.get("city") == "Onești"
        assert reloaded.logo_url.startswith("data:image")

