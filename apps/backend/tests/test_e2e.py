import os
import unittest

try:
    from fastapi.testclient import TestClient
    from app.main import app
except ModuleNotFoundError:  # environment dependency may be absent in CI sandbox
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None or app is None, "fastapi/testclient dependency not available in this environment")
class E2EFlowTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        os.environ["OPENAI_API_KEY"] = "your_openai_api_key"
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        os.environ["BIGQUERY_PROJECT_ID"] = "test-project"
        self.client = TestClient(app)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def _auth_header(self) -> dict[str, str]:
        resp = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "role": "agency_admin"},
        )
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_onboarding_to_export_flow(self):
        headers = self._auth_header()

        create_client = self.client.post("/clients", json={"name": "Pilot Client"}, headers=headers)
        self.assertEqual(create_client.status_code, 200)
        client_id = int(create_client.json()["id"])

        self.assertEqual(self.client.post(f"/integrations/google-ads/{client_id}/sync", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/integrations/meta-ads/{client_id}/sync", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f"/dashboard/{client_id}", headers=headers).status_code, 200)

        create_rule = self.client.post(
            f"/rules/{client_id}",
            json={
                "name": "Stop-Loss",
                "rule_type": "stop_loss",
                "threshold": 50.0,
                "action_value": 0.0,
                "status": "active",
            },
            headers=headers,
        )
        self.assertEqual(create_rule.status_code, 200)

        self.assertEqual(self.client.post(f"/rules/{client_id}/evaluate", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f"/ai/recommendations/{client_id}", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/insights/weekly/{client_id}/generate", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/exports/bigquery/{client_id}", headers=headers).status_code, 200)


if __name__ == "__main__":
    unittest.main()
