import os
import unittest

from app.services.client_registry import client_registry_service


class ClientRegistryAccountCurrencyResolutionTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"

        self.original_is_test_mode = client_registry_service._is_test_mode
        client_registry_service._is_test_mode = lambda: True

        client_registry_service._clients = []
        client_registry_service._next_id = 1
        client_registry_service._memory_platform_accounts = {}
        client_registry_service._memory_last_import_at = {}
        client_registry_service._memory_account_client_mappings = {}
        client_registry_service._memory_account_profiles = {}

    def tearDown(self):
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def _create_client(self, *, currency: str = "USD") -> int:
        payload = client_registry_service.create_client(name="Client A", owner_email="owner@example.com")
        client_id = int(payload["id"])
        for idx, client in enumerate(client_registry_service._clients):
            if client.id == client_id:
                client_registry_service._clients[idx] = client.__class__(
                    id=client.id,
                    name=client.name,
                    owner_email=client.owner_email,
                    source=client.source,
                    client_type=client.client_type,
                    account_manager=client.account_manager,
                    currency=currency,
                    client_logo_url=client.client_logo_url,
                    media_storage_bytes=client.media_storage_bytes,
                )
                break
        return client_id

    def test_attach_seeds_mapping_currency_from_platform_currency_code_when_available(self):
        client_registry_service.upsert_platform_accounts(
            platform="meta_ads",
            accounts=[{"id": "act_1", "name": "Meta One"}],
        )
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_1",
            currency_code="EUR",
        )
        client_id = self._create_client(currency="USD")

        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_1")
        rows = client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=client_id)

        self.assertEqual(rows[0]["effective_account_currency"], "EUR")
        self.assertEqual(rows[0]["account_currency_source"], "mapping_account_currency")
        self.assertEqual(rows[0]["mapping_account_currency"], "EUR")

    def test_attach_does_not_overwrite_existing_explicit_mapping_currency(self):
        client_registry_service.upsert_platform_accounts(
            platform="meta_ads",
            accounts=[{"id": "act_1", "name": "Meta One"}],
        )
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_1",
            currency_code="EUR",
        )
        client_id = self._create_client(currency="USD")

        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_1")
        client_registry_service._memory_account_profiles["meta_ads"]["act_1"][client_id]["account_currency"] = "GBP"
        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_1")

        rows = client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=client_id)
        self.assertEqual(rows[0]["mapping_account_currency"], "GBP")
        self.assertEqual(rows[0]["effective_account_currency"], "GBP")
        self.assertEqual(rows[0]["account_currency_source"], "mapping_account_currency")

    def test_effective_account_currency_follows_mapping_then_platform_then_client(self):
        client_registry_service.upsert_platform_accounts(
            platform="meta_ads",
            accounts=[
                {"id": "act_map", "name": "Has Mapping"},
                {"id": "act_platform", "name": "Has Platform"},
                {"id": "act_client", "name": "Client Fallback"},
            ],
        )
        client_registry_service.update_platform_account_operational_metadata(platform="meta_ads", account_id="act_map", currency_code="EUR")
        client_registry_service.update_platform_account_operational_metadata(platform="meta_ads", account_id="act_platform", currency_code="RON")
        client_id = self._create_client(currency="USD")

        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_map")
        client_registry_service._memory_account_profiles["meta_ads"]["act_map"][client_id]["account_currency"] = "GBP"

        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_platform")
        client_registry_service._memory_account_profiles["meta_ads"]["act_platform"][client_id]["account_currency"] = ""

        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_client")
        client_registry_service._memory_account_profiles["meta_ads"]["act_client"][client_id]["account_currency"] = ""

        rows = {row["id"]: row for row in client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=client_id)}

        self.assertEqual(rows["act_map"]["effective_account_currency"], "GBP")
        self.assertEqual(rows["act_map"]["account_currency_source"], "mapping_account_currency")

        self.assertEqual(rows["act_platform"]["effective_account_currency"], "RON")
        self.assertEqual(rows["act_platform"]["account_currency_source"], "platform_account_currency")

        self.assertEqual(rows["act_client"]["effective_account_currency"], "USD")
        self.assertEqual(rows["act_client"]["account_currency_source"], "client_currency")



    def test_display_currency_uses_agency_client_currency_even_when_single_attached_currency_differs(self):
        client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=[{"id": "ga_1", "name": "Google One"}])
        client_registry_service.update_platform_account_operational_metadata(platform="google_ads", account_id="ga_1", currency_code="EUR")
        client_id = self._create_client(currency="USD")
        client_registry_service.attach_platform_account_to_client(platform="google_ads", client_id=client_id, account_id="ga_1")

        decision = client_registry_service.get_client_reporting_currency_decision(client_id=client_id)

        self.assertEqual(decision["reporting_currency"], "USD")
        self.assertEqual(decision["client_display_currency"], "USD")
        self.assertEqual(decision["reporting_currency_source"], "agency_client_currency")
        self.assertEqual(decision["display_currency_source"], "agency_client_currency")
        self.assertFalse(decision["mixed_attached_account_currencies"])

    def test_display_currency_uses_agency_client_currency_with_mixed_attached_currencies(self):
        client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=[{"id": "ga_1", "name": "Google One"}])
        client_registry_service.upsert_platform_accounts(platform="meta_ads", accounts=[{"id": "act_1", "name": "Meta One"}])
        client_registry_service.update_platform_account_operational_metadata(platform="google_ads", account_id="ga_1", currency_code="EUR")
        client_registry_service.update_platform_account_operational_metadata(platform="meta_ads", account_id="act_1", currency_code="RON")
        client_id = self._create_client(currency="USD")
        client_registry_service.attach_platform_account_to_client(platform="google_ads", client_id=client_id, account_id="ga_1")
        client_registry_service.attach_platform_account_to_client(platform="meta_ads", client_id=client_id, account_id="act_1")
        client_registry_service._memory_account_profiles["google_ads"]["ga_1"][client_id]["account_currency"] = ""
        client_registry_service._memory_account_profiles["meta_ads"]["act_1"][client_id]["account_currency"] = ""

        decision = client_registry_service.get_client_reporting_currency_decision(client_id=client_id)

        self.assertEqual(decision["reporting_currency"], "USD")
        self.assertEqual(decision["reporting_currency_source"], "agency_client_currency")
        self.assertTrue(decision["mixed_attached_account_currencies"])

    def test_display_currency_uses_agency_client_currency_with_no_attached_accounts(self):
        client_id = self._create_client(currency="GBP")

        decision = client_registry_service.get_client_reporting_currency_decision(client_id=client_id)

        self.assertEqual(decision["reporting_currency"], "GBP")
        self.assertEqual(decision["reporting_currency_source"], "agency_client_currency")
        self.assertFalse(decision["mixed_attached_account_currencies"])

    def test_display_currency_safe_fallback_when_client_currency_invalid(self):
        client_id = self._create_client(currency="12")

        decision = client_registry_service.get_client_reporting_currency_decision(client_id=client_id)

        self.assertEqual(decision["reporting_currency"], "USD")
        self.assertEqual(decision["client_display_currency"], "USD")
        self.assertEqual(decision["reporting_currency_source"], "safe_fallback")
        self.assertEqual(decision["display_currency_source"], "safe_fallback")
        self.assertFalse(decision["mixed_attached_account_currencies"])

class ClientRegistryBackfillSqlTests(unittest.TestCase):
    def test_backfill_updates_only_blank_or_null_mapping_currency(self):
        statements = []

        class _Cursor:
            def execute(self, sql, params=None):
                statements.append(str(sql))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _Conn:
            def cursor(self):
                return _Cursor()

        client_registry_service._backfill_blank_mapping_account_currency(conn=_Conn())

        sql = "\n".join(statements)
        assert "UPDATE agency_account_client_mappings m" in sql
        assert "m.account_currency IS NULL OR TRIM(m.account_currency) = ''" in sql
        assert "apa.currency_code IS NOT NULL" in sql


if __name__ == "__main__":
    unittest.main()
