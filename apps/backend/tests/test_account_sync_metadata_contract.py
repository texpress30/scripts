import unittest

from app.services.client_registry import _normalize_account_sync_metadata_payload


class AccountSyncMetadataContractTests(unittest.TestCase):
    def test_normalize_account_sync_metadata_payload_shapes_expected_contract(self):
        payload = _normalize_account_sync_metadata_payload(
            platform="google_ads",
            account_id="398-659-7205",
            display_name="Demo Account",
            attached_client_id=21,
            attached_client_name="Client A",
            timezone_value="Europe/Bucharest",
            currency_value="RON",
            sync_start_date="2024-01-09",
            backfill_completed_through="2024-05-01",
            rolling_synced_through="2024-05-10",
            last_success_at="2024-05-11T10:00:00+00:00",
            last_error="Quota exceeded",
            last_run_status="error",
            last_run_type="rolling_refresh",
            last_run_started_at="2024-05-11T09:55:00+00:00",
            last_run_finished_at="2024-05-11T10:00:00+00:00",
            has_active_sync=True,
        )

        self.assertEqual(payload["platform"], "google_ads")
        self.assertEqual(payload["account_id"], "398-659-7205")
        self.assertEqual(payload["display_name"], "Demo Account")
        self.assertEqual(payload["id"], "398-659-7205")
        self.assertEqual(payload["name"], "Demo Account")
        self.assertEqual(payload["attached_client_id"], 21)
        self.assertEqual(payload["attached_client_name"], "Client A")
        self.assertEqual(payload["timezone"], "Europe/Bucharest")
        self.assertEqual(payload["currency"], "RON")
        self.assertEqual(payload["sync_start_date"], "2024-01-09")
        self.assertEqual(payload["backfill_completed_through"], "2024-05-01")
        self.assertEqual(payload["rolling_synced_through"], "2024-05-10")
        self.assertEqual(payload["last_success_at"], "2024-05-11T10:00:00+00:00")
        self.assertEqual(payload["last_error"], "Quota exceeded")
        self.assertEqual(payload["last_run_status"], "error")
        self.assertEqual(payload["last_run_type"], "rolling_refresh")
        self.assertEqual(payload["last_run_started_at"], "2024-05-11T09:55:00+00:00")
        self.assertEqual(payload["last_run_finished_at"], "2024-05-11T10:00:00+00:00")
        self.assertTrue(payload["has_active_sync"])

    def test_normalize_account_sync_metadata_payload_handles_missing_values(self):
        payload = _normalize_account_sync_metadata_payload(
            platform="google_ads",
            account_id="123",
            display_name="123",
            attached_client_id=None,
            attached_client_name=None,
            timezone_value=None,
            currency_value=None,
            sync_start_date=None,
            backfill_completed_through=None,
            rolling_synced_through=None,
            last_success_at=None,
            last_error=None,
            last_run_status=None,
            last_run_type=None,
            last_run_started_at=None,
            last_run_finished_at=None,
            has_active_sync=False,
        )

        self.assertIsNone(payload["attached_client_id"])
        self.assertIsNone(payload["sync_start_date"])
        self.assertIsNone(payload["last_run_status"])
        self.assertFalse(payload["has_active_sync"])


if __name__ == "__main__":
    unittest.main()
