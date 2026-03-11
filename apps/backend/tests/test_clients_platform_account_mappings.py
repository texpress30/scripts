import os
import unittest

from fastapi import HTTPException

from app.api import clients as clients_api
from app.schemas.client import AttachGoogleAccountRequest, AttachPlatformAccountRequest, DetachPlatformAccountRequest
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service


class ClientsPlatformAccountMappingsApiTests(unittest.TestCase):
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

        client_registry_service.upsert_platform_accounts(platform="meta_ads", accounts=[{"id": "act_101", "name": "Meta One"}])
        client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=[{"id": "1234567890", "name": "Google One"}])
        client_registry_service.upsert_platform_accounts(platform="tiktok_ads", accounts=[{"id": "tt_101", "name": "TikTok One"}])

        self.user = AuthUser(email="owner@example.com", role="admin")
        self.original_enforce = clients_api.enforce_action_scope
        clients_api.enforce_action_scope = lambda **kwargs: None

    def tearDown(self):
        clients_api.enforce_action_scope = self.original_enforce
        client_registry_service._is_test_mode = self.original_is_test_mode
        os.environ.clear()
        os.environ.update(self.original_env)

    def _create_client(self, name: str) -> int:
        payload = client_registry_service.create_client(name=name, owner_email="owner@example.com")
        return int(payload["id"])

    def test_attach_meta_account_and_list_client_accounts(self):
        client_id = self._create_client("Client A")

        attached = clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )
        self.assertEqual(attached["status"], "ok")

        listed = clients_api.list_client_accounts(client_id=client_id, platform=None, user=self.user)
        self.assertEqual(listed["count"], 1)
        row = listed["items"][0]
        self.assertEqual(row["platform"], "meta_ads")
        self.assertEqual(row["account_id"], "act_101")
        self.assertEqual(row["account_name"], "Meta One")
        self.assertTrue(row["is_attached"])

    def test_attach_idempotent_for_same_client(self):
        client_id = self._create_client("Client A")

        first = clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )
        second = clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )
        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")

        listed = clients_api.list_client_accounts(client_id=client_id, platform="meta_ads", user=self.user)
        self.assertEqual(listed["count"], 1)

    def test_attach_conflict_when_account_attached_to_different_client(self):
        first_client = self._create_client("Client A")
        second_client = self._create_client("Client B")

        clients_api.attach_platform_account(
            client_id=first_client,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )

        with self.assertRaises(HTTPException) as ctx:
            clients_api.attach_platform_account(
                client_id=second_client,
                payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
                user=self.user,
            )

        self.assertEqual(ctx.exception.status_code, 409)
        detail = ctx.exception.detail
        self.assertEqual(detail["platform"], "meta_ads")
        self.assertEqual(detail["account_id"], "act_101")
        self.assertEqual(detail["client_id"], first_client)

    def test_detach_meta_account(self):
        client_id = self._create_client("Client A")

        clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )

        detached = clients_api.detach_platform_account(
            client_id=client_id,
            payload=DetachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )
        self.assertEqual(detached["status"], "ok")

        listed = clients_api.list_client_accounts(client_id=client_id, platform="meta_ads", user=self.user)
        self.assertEqual(listed["count"], 0)

    def test_list_platform_accounts_includes_attachment_state(self):
        client_id = self._create_client("Client A")

        clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )

        listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        self.assertEqual(listed["platform"], "meta_ads")
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["items"][0]["account_id"], "act_101")
        self.assertEqual(listed["items"][0]["client_id"], client_id)
        self.assertEqual(listed["items"][0]["client_name"], "Client A")
        self.assertTrue(listed["items"][0]["is_attached"])

    def test_meta_platform_accounts_expose_sync_coverage_metadata_fields(self):
        client_id = self._create_client("Client A")
        clients_api.attach_platform_account(
            client_id=client_id,
            payload=AttachPlatformAccountRequest(platform="meta_ads", account_id="act_101"),
            user=self.user,
        )

        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_101",
            sync_start_date="2026-01-01",
            backfill_completed_through="2026-02-10",
            last_success_at="2026-02-10T10:00:00+00:00",
            last_error=None,
        )

        listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        row = listed["items"][0]
        self.assertEqual(row["sync_start_date"], "2026-01-01")
        self.assertEqual(row["backfill_completed_through"], "2026-02-10")
        self.assertEqual(row["last_success_at"], "2026-02-10T10:00:00+00:00")

    def test_operational_backfill_metadata_keeps_max_value_in_test_mode(self):
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_101",
            backfill_completed_through="2026-02-10",
            last_success_at="2026-02-10T10:00:00+00:00",
        )
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_101",
            backfill_completed_through="2026-02-03",
            last_success_at="2026-02-03T10:00:00+00:00",
        )

        listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        row = listed["items"][0]
        self.assertEqual(row["backfill_completed_through"], "2026-02-10")
        self.assertEqual(row["last_success_at"], "2026-02-10T10:00:00+00:00")


    def test_meta_multigrain_updates_keep_coherent_max_coverage_out_of_order(self):
        updates = [
            ("2026-02-12", "2026-02-12T10:00:00+00:00"),
            ("2026-02-08", "2026-02-08T10:00:00+00:00"),
            ("2026-02-14", "2026-02-14T10:00:00+00:00"),
            ("2026-02-11", "2026-02-11T10:00:00+00:00"),
        ]
        for backfill_end, success_at in updates:
            client_registry_service.update_platform_account_operational_metadata(
                platform="meta_ads",
                account_id="act_101",
                backfill_completed_through=backfill_end,
                last_success_at=success_at,
            )

        listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        row = listed["items"][0]
        self.assertEqual(row["backfill_completed_through"], "2026-02-14")
        self.assertEqual(row["last_success_at"], "2026-02-14T10:00:00+00:00")

    def test_meta_retry_success_clears_error_and_keeps_best_coverage(self):
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_101",
            backfill_completed_through="2026-02-09",
            last_success_at="2026-02-09T09:00:00+00:00",
            last_error="initial failure",
        )
        client_registry_service.update_platform_account_operational_metadata(
            platform="meta_ads",
            account_id="act_101",
            backfill_completed_through="2026-02-14",
            last_success_at="2026-02-14T10:00:00+00:00",
            last_error=None,
        )

        listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        row = listed["items"][0]
        self.assertEqual(row["backfill_completed_through"], "2026-02-14")
        self.assertEqual(row["last_success_at"], "2026-02-14T10:00:00+00:00")
        self.assertIsNone(row["last_error"])



    def test_tiktok_enabled_suppresses_stale_feature_flag_recent_error(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        client_registry_service.update_platform_account_operational_metadata(
            platform="tiktok_ads",
            account_id="tt_101",
            last_error="TikTok integration is disabled by feature flag.",
        )

        listed = clients_api.list_platform_accounts(platform="tiktok_ads", user=self.user)
        self.assertTrue(bool(listed.get("sync_enabled")))
        self.assertEqual(listed["count"], 1)
        self.assertIsNone(listed["items"][0]["last_error"])

    def test_tiktok_disabled_keeps_feature_flag_recent_error_visible(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "0"
        client_registry_service.update_platform_account_operational_metadata(
            platform="tiktok_ads",
            account_id="tt_101",
            last_error="TikTok integration is disabled by feature flag.",
        )

        listed = clients_api.list_platform_accounts(platform="tiktok_ads", user=self.user)
        self.assertFalse(bool(listed.get("sync_enabled")))
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["items"][0]["last_error"], "TikTok integration is disabled by feature flag.")

    def test_tiktok_success_status_suppresses_stale_recent_error_in_payload(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        original_list_mapping = clients_api.client_registry_service.list_platform_accounts_for_mapping
        try:
            clients_api.client_registry_service.list_platform_accounts_for_mapping = lambda **kwargs: [
                {
                    "platform": "tiktok_ads",
                    "id": "tt_101",
                    "account_id": "tt_101",
                    "name": "TikTok Account",
                    "last_error": "TikTok API timeout from old run",
                    "last_run_status": "done",
                    "last_success_at": "2026-03-10T10:00:00+00:00",
                    "has_active_sync": False,
                }
            ]
            listed = clients_api.list_platform_accounts(platform="tiktok_ads", user=self.user)
        finally:
            clients_api.client_registry_service.list_platform_accounts_for_mapping = original_list_mapping

        self.assertEqual(listed["count"], 1)
        self.assertIsNone(listed["items"][0]["last_error"])

    def test_meta_success_status_suppresses_stale_recent_error_in_payload(self):
        original_list_mapping = clients_api.client_registry_service.list_platform_accounts_for_mapping
        try:
            clients_api.client_registry_service.list_platform_accounts_for_mapping = lambda **kwargs: [
                {
                    "platform": "meta_ads",
                    "id": "act_101",
                    "account_id": "act_101",
                    "name": "Meta Account",
                    "last_error": "meta stale error",
                    "last_run_status": "done",
                    "last_success_at": "2026-03-10T11:00:00+00:00",
                    "has_active_sync": False,
                    "backfill_completed_through": "2026-03-09",
                    "rolling_synced_through": "2026-03-10",
                }
            ]
            listed = clients_api.list_platform_accounts(platform="meta_ads", user=self.user)
        finally:
            clients_api.client_registry_service.list_platform_accounts_for_mapping = original_list_mapping

        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["items"][0]["backfill_completed_through"], "2026-03-09")
        self.assertEqual(listed["items"][0]["rolling_synced_through"], "2026-03-10")
        self.assertEqual(listed["items"][0]["last_success_at"], "2026-03-10T11:00:00+00:00")
        self.assertIsNone(listed["items"][0]["last_error"])

    def test_google_legacy_endpoints_still_function(self):
        client_id = self._create_client("Client A")

        attached = clients_api.attach_google_account(
            client_id=client_id,
            payload=AttachGoogleAccountRequest(customer_id="1234567890"),
            user=self.user,
        )
        self.assertEqual(attached["google_customer_id"], "1234567890")

        google_list = clients_api.list_google_accounts(user=self.user)
        self.assertEqual(google_list["count"], 1)

        client_google_accounts = clients_api.list_client_accounts(client_id=client_id, platform="google_ads", user=self.user)
        self.assertEqual(client_google_accounts["count"], 1)
        self.assertEqual(client_google_accounts["items"][0]["account_id"], "1234567890")


if __name__ == "__main__":
    unittest.main()
