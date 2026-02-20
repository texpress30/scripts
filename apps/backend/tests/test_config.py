import os
import unittest

from app.core.config import load_settings


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_app_auth_secret_is_required(self):
        os.environ.clear()

        with self.assertRaisesRegex(RuntimeError, "APP_AUTH_SECRET"):
            load_settings()


    def test_integration_keys_are_optional_for_boot(self):
        os.environ.clear()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"

        settings = load_settings()

        self.assertEqual(settings.openai_api_key, "")
        self.assertEqual(settings.google_ads_token, "")
        self.assertEqual(settings.meta_access_token, "")
        self.assertEqual(settings.bigquery_project_id, "")
        self.assertFalse(settings.ff_tiktok_integration)
        self.assertEqual(settings.tiktok_sync_retry_attempts, 2)
        self.assertEqual(settings.tiktok_sync_backoff_ms, 75)


    def test_tiktok_feature_flag_can_be_enabled_from_env(self):
        os.environ.clear()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["FF_TIKTOK_INTEGRATION"] = "true"

        settings = load_settings()

        self.assertTrue(settings.ff_tiktok_integration)

    def test_tiktok_sync_db_path_is_configurable(self):
        os.environ.clear()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["TIKTOK_SYNC_DB_PATH"] = "/tmp/custom-tiktok.db"
        os.environ["TIKTOK_SYNC_RETRY_ATTEMPTS"] = "4"
        os.environ["TIKTOK_SYNC_BACKOFF_MS"] = "125"

        settings = load_settings()

        self.assertEqual(settings.tiktok_sync_db_path, "/tmp/custom-tiktok.db")
        self.assertEqual(settings.tiktok_sync_retry_attempts, 4)
        self.assertEqual(settings.tiktok_sync_backoff_ms, 125)

    def test_invalid_cors_regex_falls_back_to_default(self):
        os.environ.clear()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["APP_CORS_ORIGIN_REGEX"] = "["

        settings = load_settings()

        self.assertEqual(settings.cors_origin_regex, r"https://.*\.vercel\.app")

    def test_empty_cors_regex_can_disable_pattern(self):
        os.environ.clear()
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["APP_CORS_ORIGIN_REGEX"] = ""

        settings = load_settings()

        self.assertIsNone(settings.cors_origin_regex)

    def test_settings_are_loaded_from_environment(self):
        os.environ["APP_ENV"] = "test"
        os.environ["APP_HOST"] = "127.0.0.1"
        os.environ["APP_PORT"] = "9000"
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["APP_LOGIN_EMAIL"] = "owner@test.com"
        os.environ["APP_LOGIN_PASSWORD"] = "secret-pass"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["GOOGLE_ADS_TOKEN"] = "test-google-token"
        os.environ["META_ACCESS_TOKEN"] = "test-meta-token"
        os.environ["BIGQUERY_PROJECT_ID"] = "test-project"
        os.environ["DATABASE_URL"] = "postgresql://example"
        os.environ["REDIS_URL"] = "redis://example"
        os.environ["APP_CORS_ORIGINS"] = "https://frontend.example.com,https://admin.example.com"
        os.environ["APP_CORS_ORIGIN_REGEX"] = r"https://.*\\.example\\.com"
        os.environ["TIKTOK_SYNC_DB_PATH"] = "/tmp/test-mcc-tiktok.db"
        os.environ["TIKTOK_SYNC_RETRY_ATTEMPTS"] = "3"
        os.environ["TIKTOK_SYNC_BACKOFF_MS"] = "50"

        settings = load_settings()

        self.assertEqual(settings.app_env, "test")
        self.assertEqual(settings.app_host, "127.0.0.1")
        self.assertEqual(settings.app_port, 9000)
        self.assertEqual(settings.app_auth_secret, "test-auth-secret")
        self.assertEqual(settings.app_login_email, "owner@test.com")
        self.assertEqual(settings.app_login_password, "secret-pass")
        self.assertEqual(settings.openai_api_key, "test-openai-key")
        self.assertEqual(settings.google_ads_token, "test-google-token")
        self.assertEqual(settings.meta_access_token, "test-meta-token")
        self.assertEqual(settings.bigquery_project_id, "test-project")
        self.assertEqual(settings.cors_origins, ("https://frontend.example.com", "https://admin.example.com"))
        self.assertEqual(settings.cors_origin_regex, r"https://.*\\.example\\.com")
        self.assertEqual(settings.tiktok_sync_db_path, "/tmp/test-mcc-tiktok.db")
        self.assertEqual(settings.tiktok_sync_retry_attempts, 3)
        self.assertEqual(settings.tiktok_sync_backoff_ms, 50)


if __name__ == "__main__":
    unittest.main()
