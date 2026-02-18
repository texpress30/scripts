import os
import unittest

from app.core.config import load_settings


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_required_env_variables_are_enforced(self):
        required = [
            "APP_AUTH_SECRET",
            "OPENAI_API_KEY",
            "GOOGLE_ADS_TOKEN",
            "META_ACCESS_TOKEN",
            "BIGQUERY_PROJECT_ID",
        ]

        base_env = {
            "APP_AUTH_SECRET": "test-auth-secret",
            "OPENAI_API_KEY": "test-openai-key",
            "GOOGLE_ADS_TOKEN": "test-google-token",
            "META_ACCESS_TOKEN": "test-meta-token",
            "BIGQUERY_PROJECT_ID": "test-project",
        }

        for missing in required:
            os.environ.clear()
            for key, value in base_env.items():
                if key != missing:
                    os.environ[key] = value

            with self.assertRaisesRegex(RuntimeError, missing):
                load_settings()

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


if __name__ == "__main__":
    unittest.main()
