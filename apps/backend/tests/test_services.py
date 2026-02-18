import os
import unittest

from app.services.auth import AuthError, create_access_token, decode_access_token
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.rbac import AuthorizationError, require_permission


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["GOOGLE_ADS_TOKEN"] = "test-google-token"
        os.environ["META_ACCESS_TOKEN"] = "test-meta-token"
        os.environ["BIGQUERY_PROJECT_ID"] = "test-project"

    def tearDown(self):
        google_ads_service._snapshots.clear()
        os.environ.clear()
        os.environ.update(self.original_env)

    # Sprint 1 coverage
    def test_token_encode_decode_roundtrip(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        user = decode_access_token(token)

        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(user.role, "agency_admin")

    def test_invalid_token_signature_is_rejected(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        tampered = token + "broken"
        with self.assertRaises(AuthError):
            decode_access_token(tampered)

    def test_rbac_permission_validation(self):
        require_permission("agency_admin", "clients:create")
        with self.assertRaises(AuthorizationError):
            require_permission("client_viewer", "clients:create")

    # Sprint 2 coverage
    def test_google_ads_status_pending_when_placeholder(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "pending")

    def test_google_ads_status_connected_when_token_is_real(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "real-token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "connected")

    def test_google_ads_sync_and_dashboard_metrics(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "real-token"
        snapshot = google_ads_service.sync_client(client_id=3)
        self.assertEqual(snapshot["client_id"], 3)
        metrics = google_ads_service.get_dashboard_metrics(client_id=3)
        self.assertTrue(metrics["is_synced"])
        self.assertGreater(metrics["roas"], 0)

    def test_google_ads_sync_fails_with_placeholder_token(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        with self.assertRaises(GoogleAdsIntegrationError):
            google_ads_service.sync_client(client_id=1)


if __name__ == "__main__":
    unittest.main()
