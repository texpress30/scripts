import os
import unittest

from app.services.auth import AuthError, create_access_token, decode_access_token, validate_login_credentials
from app.services.ai_assistant import ai_assistant_service
from app.services.insights import insights_service
from app.services.dashboard import unified_dashboard_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service
from app.services.tiktok_store import tiktok_snapshot_store
from app.services.tiktok_observability import tiktok_sync_metrics
from app.services.creative_workflow import creative_workflow_service
from app.services.notifications import notification_service
from app.services.recommendations import recommendations_service
from app.services.rbac import AuthorizationError, require_action, require_permission
from app.services.rules_engine import rules_engine_service
from app.services.audit import audit_log_service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        os.environ["APP_LOGIN_EMAIL"] = "admin@example.com"
        os.environ["APP_LOGIN_PASSWORD"] = "admin123"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["GOOGLE_ADS_TOKEN"] = "test-google-token"
        os.environ["META_ACCESS_TOKEN"] = "test-meta-token"
        os.environ["BIGQUERY_PROJECT_ID"] = "test-project"
        os.environ["TIKTOK_SYNC_DB_PATH"] = "/tmp/test-mcc-tiktok-services.sqlite3"

    def tearDown(self):
        google_ads_service._snapshots.clear()
        meta_ads_service._snapshots.clear()
        tiktok_snapshot_store.clear()
        tiktok_sync_metrics.reset()
        rules_engine_service._rules.clear()
        rules_engine_service._next_id = 1
        notification_service._events.clear()
        insights_service._items.clear()
        creative_workflow_service.reset()
        audit_log_service._events.clear()
        os.environ.clear()
        os.environ.update(self.original_env)

    # Sprint 1 coverage
    def test_token_encode_decode_roundtrip(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        user = decode_access_token(token)
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(user.role, "agency_admin")


    def test_login_credentials_validation(self):
        self.assertTrue(validate_login_credentials("admin@example.com", "admin123"))
        self.assertFalse(validate_login_credentials("admin@example.com", "wrong"))

    def test_invalid_token_signature_is_rejected(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        tampered = token + "broken"
        with self.assertRaises(AuthError):
            decode_access_token(tampered)

    def test_rbac_permission_validation(self):
        require_permission("agency_admin", "clients:create")
        with self.assertRaises(AuthorizationError):
            require_permission("client_viewer", "clients:create")

    def test_rbac_action_scope_validation(self):
        require_action("agency_admin", action="clients:list", scope="agency")
        with self.assertRaises(AuthorizationError):
            require_action("agency_admin", action="clients:list", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("client_viewer", action="rules:create", scope="subaccount")

    # Sprint 2 coverage (Google)
    def test_google_ads_status_pending_when_placeholder(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "pending")

    def test_google_ads_status_connected_when_token_is_real(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "real-token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "connected")

    def test_google_ads_sync_fails_with_placeholder_token(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        with self.assertRaises(GoogleAdsIntegrationError):
            google_ads_service.sync_client(client_id=1)


    def test_tiktok_ads_sync_fails_when_feature_flag_disabled(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "0"
        with self.assertRaises(TikTokAdsIntegrationError):
            tiktok_ads_service.sync_client(client_id=2)

    def test_tiktok_ads_sync_persists_snapshot(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        snapshot = tiktok_ads_service.sync_client(client_id=9)
        metrics = tiktok_ads_service.get_metrics(client_id=9)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(metrics["platform"], "tiktok_ads")
        self.assertTrue(metrics["is_synced"])
        self.assertGreater(float(metrics["spend"]), 0.0)


    def test_tiktok_ads_retry_succeeds_after_transient_failures(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["TIKTOK_SYNC_RETRY_ATTEMPTS"] = "3"
        os.environ["TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES"] = "2"

        snapshot = tiktok_ads_service.sync_client(client_id=10)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["attempts"], 3)

    # Sprint 3 coverage (Meta + unified dashboard)
    def test_meta_ads_status_pending_when_placeholder(self):
        os.environ["META_ACCESS_TOKEN"] = "your_meta_access_token"
        status = meta_ads_service.integration_status()
        self.assertEqual(status["status"], "pending")

    def test_meta_ads_sync_fails_with_placeholder_token(self):
        os.environ["META_ACCESS_TOKEN"] = "your_meta_access_token"
        with self.assertRaises(MetaAdsIntegrationError):
            meta_ads_service.sync_client(client_id=2)

    def test_unified_dashboard_consolidates_google_meta_and_tiktok(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        google_snapshot = google_ads_service.sync_client(client_id=3)
        meta_snapshot = meta_ads_service.sync_client(client_id=3)
        tiktok_snapshot = tiktok_ads_service.sync_client(client_id=3)

        dashboard = unified_dashboard_service.get_client_dashboard(client_id=3)

        expected_spend = float(google_snapshot["spend"]) + float(meta_snapshot["spend"]) + float(tiktok_snapshot["spend"])
        expected_conversions = int(google_snapshot["conversions"]) + int(meta_snapshot["conversions"]) + int(tiktok_snapshot["conversions"])

        self.assertTrue(dashboard["is_synced"])
        self.assertEqual(dashboard["totals"]["spend"], round(expected_spend, 2))
        self.assertEqual(dashboard["totals"]["conversions"], expected_conversions)

    # Sprint 4 coverage (rules + notifications + system_bot audit)
    def test_rules_engine_stop_loss_triggers_and_notifies(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=5)
        meta_ads_service.sync_client(client_id=5)

        rule = rules_engine_service.create_rule(
            client_id=5,
            name="Stop-Loss High Spend",
            rule_type="stop_loss",
            threshold=50.0,
            action_value=0.0,
            status="active",
        )
        self.assertEqual(rule["rule_type"], "stop_loss")

        actions = rules_engine_service.evaluate_client_rules(client_id=5)
        self.assertGreaterEqual(len(actions), 1)

        event = notification_service.send_email_mock(
            to_email="owner@example.com",
            subject="Rule triggered",
            message=str(actions[0]),
        )
        self.assertEqual(event["channel"], "email_mock")

    def test_rules_engine_auto_scale_triggers(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=4)
        meta_ads_service.sync_client(client_id=4)

        rules_engine_service.create_rule(
            client_id=4,
            name="Scale Winners",
            rule_type="auto_scale",
            threshold=2.0,
            action_value=20.0,
            status="active",
        )

        actions = rules_engine_service.evaluate_client_rules(client_id=4)
        self.assertGreaterEqual(len(actions), 1)
        self.assertEqual(actions[0]["rule_type"], "auto_scale")


    def test_structured_recommendation_lifecycle_and_impact_report(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=8)
        meta_ads_service.sync_client(client_id=8)

        generated = recommendations_service.generate_recommendations(client_id=8)
        self.assertEqual(len(generated), 1)
        self.assertIn("problema", generated[0]["payload"])

        recommendation_id = int(generated[0]["id"])
        updated = recommendations_service.review_recommendation(
            client_id=8, recommendation_id=recommendation_id, action="approve", actor="tester@example.com"
        )
        self.assertEqual(updated["status"], "applied")

        actions = recommendations_service.list_actions(client_id=8)
        self.assertGreaterEqual(len(actions), 2)

        report = recommendations_service.get_impact_report(client_id=8)
        windows = [item["window_days"] for item in report["windows"]]
        self.assertEqual(windows, [3, 7, 14])

    # Sprint 5 coverage (AI assistant + insights + guardrails)
    def test_ai_recommendation_fallback_when_insufficient_data(self):
        rec = ai_assistant_service.generate_recommendation(client_id=999)
        self.assertEqual(rec["recommendation"], "Nu am destule date")

    def test_weekly_insight_generation_and_storage(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=6)
        meta_ads_service.sync_client(client_id=6)

        insight = insights_service.generate_weekly_insight(client_id=6)
        self.assertEqual(insight["client_id"], 6)
        self.assertIn("Spend", insight["summary"])

        latest = insights_service.get_latest(client_id=6)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["client_id"], 6)

    # Sprint 7 coverage (creative library + ai generation + approvals + publish)
    def test_creative_asset_metadata_variants_scores_and_links(self):
        asset = creative_workflow_service.create_asset(
            client_id=11,
            name="Video Awareness RO",
            format="video",
            dimensions="1080x1920",
            objective_fit="awareness",
            platform_fit=["meta", "tiktok"],
            language="ro",
            brand_tags=["summer", "promo"],
            legal_status="pending",
            approval_status="draft",
        )

        creative_workflow_service.generate_variants(asset_id=int(asset["id"]), count=2)
        creative_workflow_service.set_performance_scores(
            asset_id=int(asset["id"]),
            scores={"google": 71.2, "meta": 88.1, "tiktok": 91.4},
        )
        creative_workflow_service.link_to_campaign(asset_id=int(asset["id"]), campaign_id=201, ad_set_id=301)
        full_asset = creative_workflow_service.get_asset(int(asset["id"]))

        self.assertEqual(full_asset["metadata"]["format"], "video")
        self.assertEqual(len(full_asset["creative_variants"]), 2)
        self.assertEqual(full_asset["performance_scores"]["tiktok"], 91.4)
        self.assertEqual(full_asset["campaign_links"][0]["campaign_id"], 201)

    def test_publish_to_channel_uses_platform_adapter(self):
        asset = creative_workflow_service.create_asset(
            client_id=22,
            name="Static Conversion",
            format="image",
            dimensions="1200x628",
            objective_fit="conversion",
            platform_fit=["google", "meta"],
            language="ro",
            brand_tags=["always_on"],
            legal_status="approved",
            approval_status="approved",
        )
        variant = creative_workflow_service.add_variant(
            asset_id=int(asset["id"]),
            headline="Cumpara acum",
            body="Oferta limitata",
            cta="Comanda",
            media="image_v1",
        )

        published = creative_workflow_service.publish_to_channel(
            asset_id=int(asset["id"]),
            channel="meta",
            variant_id=int(variant["id"]),
        )

        self.assertEqual(published["native_object_type"], "ad_creative")
        self.assertTrue(str(published["native_id"]).startswith("meta_ad_creative_"))



if __name__ == "__main__":
    unittest.main()
