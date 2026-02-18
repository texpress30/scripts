import os
import unittest

from app.services.auth import AuthError, create_access_token, decode_access_token
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
        os.environ.clear()
        os.environ.update(self.original_env)

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


if __name__ == "__main__":
    unittest.main()
