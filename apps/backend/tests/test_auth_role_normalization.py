import unittest

from app.api import auth as auth_api
from app.schemas.auth import LoginRequest


class AuthRoleNormalizationTests(unittest.TestCase):
    def test_login_accepts_legacy_role_alias_account_manager(self):
        original_rate = auth_api.rate_limiter_service.check
        original_validate = auth_api.validate_login_credentials
        original_token = auth_api.create_access_token
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.validate_login_credentials = lambda email, password: True
            auth_api.create_access_token = lambda email, role: f"token:{email}:{role}"

            resp = auth_api.login(LoginRequest(email="user@example.com", password="ok", role="account_manager"))
            self.assertIn("subaccount_user", resp.access_token)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.validate_login_credentials = original_validate
            auth_api.create_access_token = original_token

    def test_login_rejects_unknown_role(self):
        original_rate = auth_api.rate_limiter_service.check
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            with self.assertRaises(auth_api.HTTPException) as ctx:
                auth_api.login(LoginRequest(email="user@example.com", password="ok", role="bogus"))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            auth_api.rate_limiter_service.check = original_rate


if __name__ == "__main__":
    unittest.main()
