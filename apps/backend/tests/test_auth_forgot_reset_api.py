import unittest
from types import SimpleNamespace

from app.api import auth as auth_api
from app.schemas.auth import ResetPasswordConfirmRequest
from app.services.auth_email_tokens import AuthEmailTokenError, PasswordResetTokenRecord


class AuthResetConfirmApiTests(unittest.TestCase):
    def test_reset_confirm_success_updates_password_and_consumes_token(self):
        original_validate = auth_api.auth_email_tokens_service.validate_password_reset_token
        original_consume = auth_api.auth_email_tokens_service.consume_password_reset_token
        original_set = auth_api.set_user_password
        original_invalidate = auth_api.auth_email_tokens_service.invalidate_active_tokens
        calls: dict[str, object] = {}

        try:
            auth_api.auth_email_tokens_service.validate_password_reset_token = lambda **kwargs: PasswordResetTokenRecord(
                id=11,
                user_id=7,
                email="u@example.com",
                token_type="password_reset",
                expires_at=SimpleNamespace(),
                consumed_at=None,
                metadata_json="{}",
            )
            auth_api.auth_email_tokens_service.consume_password_reset_token = lambda **kwargs: PasswordResetTokenRecord(
                id=11,
                user_id=7,
                email="u@example.com",
                token_type="password_reset",
                expires_at=SimpleNamespace(),
                consumed_at=SimpleNamespace(),
                metadata_json="{}",
            )

            def _fake_set_user_password(**kwargs):
                calls["set"] = kwargs

            def _fake_invalidate(**kwargs):
                calls["invalidate"] = kwargs

            auth_api.set_user_password = _fake_set_user_password
            auth_api.auth_email_tokens_service.invalidate_active_tokens = _fake_invalidate

            resp = auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="raw", new_password="new-pass-123"))
            self.assertIn("resetată", resp.message)
            self.assertEqual(calls["set"]["user_id"], 7)
            self.assertEqual(calls["set"]["new_password"], "new-pass-123")
            self.assertEqual(calls["invalidate"]["exclude_token_id"], 11)
        finally:
            auth_api.auth_email_tokens_service.validate_password_reset_token = original_validate
            auth_api.auth_email_tokens_service.consume_password_reset_token = original_consume
            auth_api.set_user_password = original_set
            auth_api.auth_email_tokens_service.invalidate_active_tokens = original_invalidate

    def test_reset_confirm_invalid_expired_consumed_tokens(self):
        original_validate = auth_api.auth_email_tokens_service.validate_password_reset_token
        try:
            auth_api.auth_email_tokens_service.validate_password_reset_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token invalid", reason="invalid_token", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_invalid:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="bad", new_password="new-pass-123"))
            self.assertEqual(ctx_invalid.exception.status_code, 400)

            auth_api.auth_email_tokens_service.validate_password_reset_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token expirat", reason="token_expired", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_exp:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="expired", new_password="new-pass-123"))
            self.assertEqual(ctx_exp.exception.status_code, 400)

            auth_api.auth_email_tokens_service.validate_password_reset_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token deja folosit", reason="token_consumed", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_cons:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="used", new_password="new-pass-123"))
            self.assertEqual(ctx_cons.exception.status_code, 400)
        finally:
            auth_api.auth_email_tokens_service.validate_password_reset_token = original_validate

    def test_reset_confirm_invalid_new_password(self):
        with self.assertRaises(auth_api.HTTPException) as ctx:
            auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="t", new_password="short"))
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
