import os
import unittest

from app.api import clients as clients_api
from app.schemas.client import SubaccountBusinessProfilePayload
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.subaccount_business_profile_store import subaccount_business_profile_store
from app.services.storage_media_access import StorageMediaAccessError


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
        self.original_enforce_subaccount = clients_api.enforce_subaccount_action
        clients_api.enforce_subaccount_action = lambda **kwargs: None
        self.original_storage_access = clients_api.storage_media_access_service.build_access_url
        clients_api.storage_media_access_service.build_access_url = lambda **kwargs: {"url": "https://preview.example/logo.png"}

        self.user = AuthUser(email="owner@example.com", role="admin")
        created = client_registry_service.create_client(name="Client Empty", owner_email="owner@example.com")
        self.client_id = int(created["id"])
        self.display_id = int(created["display_id"])

    def tearDown(self):
        clients_api.enforce_action_scope = self.original_enforce_scope
        clients_api.enforce_subaccount_action = self.original_enforce_subaccount
        clients_api.storage_media_access_service.build_access_url = self.original_storage_access
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_profile_returns_only_empty_business_profile_payload_without_display_fallback(self):
        payload = clients_api.get_subaccount_business_profile_by_subaccount_id(subaccount_id=self.client_id, user=self.user)
        assert payload.client_id == self.client_id
        assert payload.display_id == self.display_id
        assert payload.client_name == "Client Empty"
        assert payload.general == {}
        assert payload.business == {}
        assert payload.address == {}
        assert payload.representative == {}
        assert payload.logo_url == ""
        assert payload.logo_media_id is None

    def test_upsert_and_get_profile_roundtrip(self):
        updated = clients_api.upsert_subaccount_business_profile_by_subaccount_id(
            subaccount_id=self.client_id,
            payload=SubaccountBusinessProfilePayload(
                general={"friendlyName": "ROC Auto", "email": "biz@roc.example"},
                business={"businessType": "srl"},
                address={"city": "Onești", "country": "RO"},
                representative={"firstName": "Ana", "lastName": "Popescu"},
                logo_url="data:image/png;base64,AAAA",
                logo_media_id="m_logo_1",
            ),
            user=self.user,
        )

        assert updated.general.get("friendlyName") == "ROC Auto"
        assert updated.address.get("city") == "Onești"
        assert updated.logo_media_id == "m_logo_1"
        assert updated.logo_url == "https://preview.example/logo.png"

        reloaded = clients_api.get_subaccount_business_profile(display_id=self.display_id, user=self.user)
        assert reloaded.client_id == self.client_id
        assert reloaded.general.get("friendlyName") == "ROC Auto"
        assert reloaded.address.get("city") == "Onești"
        assert reloaded.logo_media_id == "m_logo_1"
        assert reloaded.logo_url == "https://preview.example/logo.png"

    def test_profile_with_legacy_logo_url_remains_compatible_without_logo_media_id(self):
        updated = clients_api.upsert_subaccount_business_profile_by_subaccount_id(
            subaccount_id=self.client_id,
            payload=SubaccountBusinessProfilePayload(
                general={"friendlyName": "Legacy"},
                business={},
                address={},
                representative={},
                logo_url="https://legacy.example/logo.png",
                logo_media_id=None,
            ),
            user=self.user,
        )

        assert updated.logo_media_id is None
        assert updated.logo_url == "https://legacy.example/logo.png"

    def test_logo_preview_fallback_does_not_break_endpoint_when_storage_access_fails(self):
        clients_api.storage_media_access_service.build_access_url = lambda **kwargs: (_ for _ in ()).throw(
            StorageMediaAccessError("Media record not found", status_code=404)
        )
        updated = clients_api.upsert_subaccount_business_profile_by_subaccount_id(
            subaccount_id=self.client_id,
            payload=SubaccountBusinessProfilePayload(
                general={"friendlyName": "Fallback"},
                business={},
                address={},
                representative={},
                logo_url="https://legacy.example/fallback.png",
                logo_media_id="m_missing",
            ),
            user=self.user,
        )

        assert updated.logo_media_id == "m_missing"
        assert updated.logo_url == "https://legacy.example/fallback.png"
