import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from app.main import app
except Exception:
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi/testclient dependency not available")
class ClientsPlatformSummarySyncEnabledTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def _auth_headers(self):
        return {"Authorization": "Bearer test-secret"}

    def test_summary_reports_tiktok_sync_enabled_true_when_config_enabled(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"TIKTOK_SYNC_ENABLED": "1", "FF_TIKTOK_INTEGRATION": "0"}, clear=False):
            response = self.client.get("/clients/accounts/summary", headers=headers)

        self.assertEqual(response.status_code, 200)
        items = response.json().get("items") or []
        tiktok = next((item for item in items if item.get("platform") == "tiktok_ads"), None)
        self.assertIsNotNone(tiktok)
        self.assertTrue(bool(tiktok.get("sync_enabled")))

    def test_platform_accounts_payload_exposes_sync_enabled_false_for_tiktok(self):
        headers = self._auth_headers()
        with patch.dict(os.environ, {"TIKTOK_SYNC_ENABLED": "0", "FF_TIKTOK_INTEGRATION": "1"}, clear=False):
            response = self.client.get("/clients/accounts/tiktok_ads", headers=headers)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("sync_enabled", payload)
        self.assertFalse(bool(payload.get("sync_enabled")))
