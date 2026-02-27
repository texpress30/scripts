import os
import unittest

try:
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.audit import audit_log_service
except Exception:  # environment dependency may be absent in CI sandbox
    TestClient = None
    app = None
    audit_log_service = None


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
        audit_log_service._events.clear()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def _auth_header(self, role: str = "agency_admin") -> dict[str, str]:
        resp = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "admin123", "role": role},
        )
        self.assertEqual(resp.status_code, 200)
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_login_endpoint_accepts_post(self):
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "admin123", "role": "agency_admin"},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_endpoint_rejects_get_with_405(self):
        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 405)

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
        ai_resp = self.client.get(f"/ai/recommendations/{client_id}", headers=headers)
        self.assertEqual(ai_resp.status_code, 200)
        rec_id = int(ai_resp.json()["items"][0]["id"])
        self.assertEqual(
            self.client.post(
                f"/ai/recommendations/{client_id}/{rec_id}/review",
                headers=headers,
                json={"action": "approve", "snooze_days": 3},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(f"/ai/recommendations/{client_id}/impact-report", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/insights/weekly/{client_id}/generate", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(f"/exports/bigquery/{client_id}", headers=headers).status_code, 200)

        audit_events = self.client.get("/audit", headers=headers)
        self.assertEqual(audit_events.status_code, 200)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("auth.login.succeeded", actions)
        self.assertIn("clients.create", actions)
        self.assertIn("google_ads.sync", actions)
        self.assertIn("meta_ads.sync", actions)
        self.assertIn("rules.evaluate", actions)
        self.assertIn("ai.weekly_insight.generate", actions)
        self.assertIn("export.bigquery.run", actions)

    def test_creative_library_to_publish_flow(self):
        headers = self._auth_header()

        create_asset = self.client.post(
            "/creative/library/assets",
            json={
                "client_id": 1,
                "name": "UGC Video",
                "format": "video",
                "dimensions": "1080x1920",
                "objective_fit": "awareness",
                "platform_fit": ["meta", "tiktok"],
                "language": "ro",
                "brand_tags": ["ugc", "q2"],
                "legal_status": "pending",
                "approval_status": "draft",
            },
            headers=headers,
        )
        self.assertEqual(create_asset.status_code, 200)
        asset_id = int(create_asset.json()["id"])

        ai_generate = self.client.post(
            f"/creative/ai-generation/assets/{asset_id}/variants",
            json={"count": 2},
            headers=headers,
        )
        self.assertEqual(ai_generate.status_code, 200)

        approve = self.client.post(
            f"/creative/approvals/assets/{asset_id}",
            json={"legal_status": "approved", "approval_status": "approved"},
            headers=headers,
        )
        self.assertEqual(approve.status_code, 200)

        publish = self.client.post(
            f"/creative/publish/assets/{asset_id}/to-channel",
            json={"channel": "tiktok"},
            headers=headers,
        )
        self.assertEqual(publish.status_code, 200)



    def test_company_settings_get_and_update(self):
        headers = self._auth_header()

        initial = self.client.get('/company/settings', headers=headers)
        self.assertEqual(initial.status_code, 200)

        update = self.client.patch(
            '/company/settings',
            headers=headers,
            json={
                'company_name': 'OMAROSA Agency',
                'company_email': 'office@omarosa.ro',
                'company_phone_prefix': '+40',
                'company_phone': '0712345678',
                'company_website': 'https://omarosa.ro',
                'business_category': 'Marketing',
                'business_niche': 'Performance',
                'platform_primary_use': 'Administrare campanii',
                'address_line1': 'Strada Principală 1',
                'city': 'București',
                'postal_code': '010101',
                'region': 'București',
                'country': 'România',
                'timezone': 'Europe/Bucharest',
                'logo_url': 'https://example.com/logo.png',
            },
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()['company_name'], 'OMAROSA Agency')

        loaded = self.client.get('/company/settings', headers=headers)
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()['company_email'], 'office@omarosa.ro')

    def test_team_members_list_and_create_flow(self):
        headers = self._auth_header()

        empty_list = self.client.get('/team/members', headers=headers)
        self.assertEqual(empty_list.status_code, 200)
        self.assertIn('items', empty_list.json())

        create_member = self.client.post(
            '/team/members',
            headers=headers,
            json={
                'first_name': 'Ana',
                'last_name': 'Popescu',
                'email': 'ana.popescu@example.com',
                'phone': '0712345678',
                'extension': '101',
                'user_type': 'agency',
                'user_role': 'member',
                'location': 'București',
                'subaccount': 'Toate',
            },
        )
        self.assertEqual(create_member.status_code, 200)
        self.assertEqual(create_member.json()['item']['email'], 'ana.popescu@example.com')

        list_after_create = self.client.get('/team/members?search=ana.popescu', headers=headers)
        self.assertEqual(list_after_create.status_code, 200)
        self.assertEqual(list_after_create.json()['total'], 1)
        self.assertEqual(list_after_create.json()['items'][0]['first_name'], 'Ana')


    def test_storage_media_usage_endpoint(self):
        headers = self._auth_header()

        self.client.post('/clients', json={'name': 'Storage Client A'}, headers=headers)
        self.client.post('/clients', json={'name': 'Storage Client B'}, headers=headers)

        resp = self.client.get('/storage/media-usage?page=1&page_size=10', headers=headers)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn('items', body)
        self.assertIn('total', body)


    def test_admin_can_impersonate_user(self):
        headers = self._auth_header(role="agency_admin")
        response = self.client.post(
            "/auth/impersonate",
            headers=headers,
            json={"email": "viewer@example.com", "role": "client_viewer"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())


    def test_agency_dashboard_summary_range(self):
        headers = self._auth_header(role="agency_admin")
        response = self.client.get("/dashboard/agency/summary?start_date=2024-01-01&end_date=2030-01-01", headers=headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("totals", body)
        self.assertIn("top_clients", body)
        self.assertIn("date_range", body)

    def test_scope_enforcement_for_client_viewer(self):
        headers = self._auth_header(role="client_viewer")

        clients_list = self.client.get("/clients", headers=headers)
        self.assertEqual(clients_list.status_code, 403)

        write_rule = self.client.post(
            "/rules/1",
            json={
                "name": "Blocked",
                "rule_type": "stop_loss",
                "threshold": 10.0,
                "action_value": 0.0,
                "status": "active",
            },
            headers=headers,
        )
        self.assertEqual(write_rule.status_code, 403)



    def test_tiktok_contract_is_feature_flagged_off_by_default(self):
        headers = self._auth_header()

        status_response = self.client.get("/integrations/tiktok-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "disabled")

        sync_response = self.client.post("/integrations/tiktok-ads/1/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 400)

    def test_tiktok_status_and_sync_contract_when_feature_enabled(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        headers = self._auth_header()

        create_client = self.client.post("/clients", json={"name": "TikTok Pilot"}, headers=headers)
        self.assertEqual(create_client.status_code, 200)
        client_id = int(create_client.json()["id"])

        status_response = self.client.get("/integrations/tiktok-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "connected")

        sync_response = self.client.post(f"/integrations/tiktok-ads/{client_id}/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.json()["status"], "success")
        self.assertGreaterEqual(int(sync_response.json().get("attempts", 1)), 1)

        dashboard_response = self.client.get(f"/dashboard/{client_id}", headers=headers)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertGreater(float(dashboard_response.json()["platforms"]["tiktok_ads"]["spend"]), 0.0)

        audit_events = self.client.get("/audit", headers=headers)
        self.assertEqual(audit_events.status_code, 200)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("tiktok_ads.sync.start", actions)
        self.assertIn("tiktok_ads.sync.success", actions)

    def test_tiktok_scope_enforcement_for_client_viewer(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        headers = self._auth_header(role="client_viewer")

        self.assertEqual(self.client.get("/integrations/tiktok-ads/status", headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/integrations/tiktok-ads/1/sync", headers=headers).status_code, 403)


    def test_tiktok_sync_fail_audit_when_retries_exhausted(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["TIKTOK_SYNC_RETRY_ATTEMPTS"] = "2"
        os.environ["TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES"] = "5"
        headers = self._auth_header()

        response = self.client.post("/integrations/tiktok-ads/1/sync", headers=headers)
        self.assertEqual(response.status_code, 400)

        audit_events = self.client.get("/audit", headers=headers)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("tiktok_ads.sync.start", actions)
        self.assertIn("tiktok_ads.sync.fail", actions)


    def test_attach_google_account_to_client(self):
        headers = self._auth_header()
        created = self.client.post("/clients", json={"name": "Client Attach"}, headers=headers)
        self.assertEqual(created.status_code, 200)
        client_id = int(created.json()["id"])

        response = self.client.post(
            f"/clients/{client_id}/attach-google-account",
            json={"customer_id": "7563058696"},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("google_customer_id"), "7563058696")

    def test_google_accounts_endpoint_contract(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://scripts-chi-nine.vercel.app/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        headers = self._auth_header()

        from app.services.google_ads import google_ads_service
        original = google_ads_service.list_accessible_customer_accounts
        try:
            google_ads_service.list_accessible_customer_accounts = lambda: [
                {"id": "3908678909", "name": "Account 3908678909"},
                {"id": "1234567890", "name": "Account 1234567890"},
            ]
            response = self.client.get("/integrations/google-ads/accounts", headers=headers)
        finally:
            google_ads_service.list_accessible_customer_accounts = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(response.json()["items"][0]["id"], "3908678909")
        self.assertIn("name", response.json()["items"][0])

        alias = self.client.get("/integrations/google/accounts", headers=headers)
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.json()["count"], 2)

    def test_pinterest_contract_is_feature_flagged_off_by_default(self):
        headers = self._auth_header()

        status_response = self.client.get("/integrations/pinterest-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "disabled")

        sync_response = self.client.post("/integrations/pinterest-ads/1/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 400)

    def test_pinterest_status_and_sync_contract_when_feature_enabled(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        headers = self._auth_header()

        create_client = self.client.post("/clients", json={"name": "Pinterest Pilot"}, headers=headers)
        self.assertEqual(create_client.status_code, 200)
        client_id = int(create_client.json()["id"])

        status_response = self.client.get("/integrations/pinterest-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "connected")

        sync_response = self.client.post(f"/integrations/pinterest-ads/{client_id}/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.json()["status"], "success")
        self.assertGreaterEqual(int(sync_response.json().get("attempts", 1)), 1)

        dashboard_response = self.client.get(f"/dashboard/{client_id}", headers=headers)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertGreater(float(dashboard_response.json()["platforms"]["pinterest_ads"]["spend"]), 0.0)

        audit_events = self.client.get("/audit", headers=headers)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("pinterest_ads.sync.start", actions)
        self.assertIn("pinterest_ads.sync.success", actions)

    def test_pinterest_sync_fail_audit_when_retries_exhausted(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        os.environ["PINTEREST_SYNC_RETRY_ATTEMPTS"] = "2"
        os.environ["PINTEREST_SYNC_FORCE_TRANSIENT_FAILURES"] = "5"
        headers = self._auth_header()

        response = self.client.post("/integrations/pinterest-ads/1/sync", headers=headers)
        self.assertEqual(response.status_code, 400)

        audit_events = self.client.get("/audit", headers=headers)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("pinterest_ads.sync.start", actions)
        self.assertIn("pinterest_ads.sync.fail", actions)

    def test_pinterest_scope_enforcement_for_client_viewer(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        headers = self._auth_header(role="client_viewer")

        self.assertEqual(self.client.get("/integrations/pinterest-ads/status", headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/integrations/pinterest-ads/1/sync", headers=headers).status_code, 403)

    def test_snapchat_contract_is_feature_flagged_off_by_default(self):
        headers = self._auth_header()

        status_response = self.client.get("/integrations/snapchat-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "disabled")

        sync_response = self.client.post("/integrations/snapchat-ads/1/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 400)

    def test_snapchat_status_and_sync_contract_when_feature_enabled(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"
        headers = self._auth_header()

        create_client = self.client.post("/clients", json={"name": "Snapchat Pilot"}, headers=headers)
        self.assertEqual(create_client.status_code, 200)
        client_id = int(create_client.json()["id"])

        status_response = self.client.get("/integrations/snapchat-ads/status", headers=headers)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "connected")

        sync_response = self.client.post(f"/integrations/snapchat-ads/{client_id}/sync", headers=headers)
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(sync_response.json()["status"], "success")
        self.assertGreaterEqual(int(sync_response.json().get("attempts", 1)), 1)

        dashboard_response = self.client.get(f"/dashboard/{client_id}", headers=headers)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertGreater(float(dashboard_response.json()["platforms"]["snapchat_ads"]["spend"]), 0.0)

        audit_events = self.client.get("/audit", headers=headers)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("snapchat_ads.sync.start", actions)
        self.assertIn("snapchat_ads.sync.success", actions)

    def test_snapchat_sync_fail_audit_when_retries_exhausted(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"
        os.environ["SNAPCHAT_SYNC_RETRY_ATTEMPTS"] = "2"
        os.environ["SNAPCHAT_SYNC_FORCE_TRANSIENT_FAILURES"] = "5"
        headers = self._auth_header()

        response = self.client.post("/integrations/snapchat-ads/1/sync", headers=headers)
        self.assertEqual(response.status_code, 400)

        audit_events = self.client.get("/audit", headers=headers)
        actions = {item["action"] for item in audit_events.json()["items"]}
        self.assertIn("snapchat_ads.sync.start", actions)
        self.assertIn("snapchat_ads.sync.fail", actions)

    def test_snapchat_scope_enforcement_for_client_viewer(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"
        headers = self._auth_header(role="client_viewer")

        self.assertEqual(self.client.get("/integrations/snapchat-ads/status", headers=headers).status_code, 403)
        self.assertEqual(self.client.post("/integrations/snapchat-ads/1/sync", headers=headers).status_code, 403)



if __name__ == "__main__":
    unittest.main()
