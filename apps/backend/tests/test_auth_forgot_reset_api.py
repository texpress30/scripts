import unittest
from types import SimpleNamespace

from app.api import auth as auth_api
from app.schemas.auth import ForgotPasswordRequest, ResetPasswordConfirmRequest
from app.services.auth_email_tokens import AuthEmailTokenError, PasswordResetTokenRecord
from app.services.email_notifications import RuntimeEmailNotification
from app.services.email_templates import RenderedEmailTemplate
from app.services.mailgun_service import MailgunIntegrationError


class AuthForgotResetApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_resolve_notification = auth_api.email_notifications_service.resolve_runtime_notification
        auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
            key="auth_forgot_password",
            template_key="auth_forgot_password",
            enabled=True,
            default_enabled=True,
            is_overridden=False,
            updated_at=None,
        )

    def tearDown(self) -> None:
        auth_api.email_notifications_service.resolve_runtime_notification = self._original_resolve_notification

    def test_forgot_password_existing_user_sends_email_and_generic_response(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_create = auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user
        original_send = auth_api.mailgun_service.send_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        captured: dict[str, object] = {}

        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = lambda **kwargs: ("raw-token-1", None)
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="auth_forgot_password",
                subject="Subiect reset",
                text_body=f"Text reset {kwargs['variables']['reset_link']}",
                html_body=f"<p>{kwargs['variables']['reset_link']}</p>",
                enabled=True,
                available_variables=("reset_link", "expires_minutes", "user_email"),
            )

            def _fake_send_email(**kwargs):
                captured.update(kwargs)
                return {"ok": True}

            auth_api.mailgun_service.send_email = _fake_send_email

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="U@example.com "))
            self.assertIn("Dacă există un cont", resp.message)
            self.assertEqual(captured["to_email"], "u@example.com")
            self.assertIn("raw-token-1", str(captured["text"]))
            self.assertIn("https://app.example.com/reset-password?token=raw-token-1", str(captured["html"]))
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = original_create
            auth_api.mailgun_service.send_email = original_send
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_returns_generic_without_token_or_send(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_create = auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user
        original_send = auth_api.mailgun_service.send_email
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("token should not be created when notification is disabled")
            )
            auth_api.mailgun_service.send_email = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("should not send when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = original_create
            auth_api.mailgun_service.send_email = original_send
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_notification_disabled_has_priority_over_template_disabled(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.email_notifications_service.resolve_runtime_notification = lambda **kwargs: RuntimeEmailNotification(
                key="auth_forgot_password",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: (_ for _ in ()).throw(
                AssertionError("template should not be resolved when notification is disabled")
            )
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_unknown_email_returns_generic_without_email_send(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_send = auth_api.mailgun_service.send_email
        original_settings = auth_api.load_settings

        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.find_active_user_by_email = lambda email: None
            auth_api.mailgun_service.send_email = lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not send"))
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            resp = auth_api.forgot_password(ForgotPasswordRequest(email="missing@example.com"))
            self.assertIn("Dacă există un cont", resp.message)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.mailgun_service.send_email = original_send
            auth_api.load_settings = original_settings

    def test_forgot_password_template_override_is_used(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_create = auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user
        original_send = auth_api.mailgun_service.send_email
        original_render = auth_api.email_templates_service.render_effective_template
        original_settings = auth_api.load_settings
        captured: dict[str, object] = {}

        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = lambda **kwargs: ("raw-token-1", None)
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=45)
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="auth_forgot_password",
                subject="Override subject",
                text_body="Override text",
                html_body="<p>Override html</p>",
                enabled=True,
                available_variables=("reset_link", "expires_minutes", "user_email"),
            )
            auth_api.mailgun_service.send_email = lambda **kwargs: captured.update(kwargs) or {"ok": True}

            auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(captured["subject"], "Override subject")
            self.assertEqual(captured["text"], "Override text")
            self.assertEqual(captured["html"], "<p>Override html</p>")
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = original_create
            auth_api.mailgun_service.send_email = original_send
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.load_settings = original_settings

    def test_forgot_password_template_disabled_returns_503(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_create = auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user
        original_render = auth_api.email_templates_service.render_effective_template
        original_send = auth_api.mailgun_service.send_email
        original_settings = auth_api.load_settings

        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = lambda **kwargs: ("raw-token-1", None)
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)
            auth_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="auth_forgot_password",
                subject="sub",
                text_body="txt",
                html_body="",
                enabled=False,
                available_variables=("reset_link", "expires_minutes", "user_email"),
            )
            auth_api.mailgun_service.send_email = lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not send"))

            with self.assertRaises(auth_api.HTTPException) as ctx:
                auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = original_create
            auth_api.email_templates_service.render_effective_template = original_render
            auth_api.mailgun_service.send_email = original_send
            auth_api.load_settings = original_settings

    def test_forgot_password_mailgun_unavailable_or_disabled_returns_clear_error(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            auth_api.mailgun_service.assert_available = lambda: (_ for _ in ()).throw(
                MailgunIntegrationError("Mailgun nu este configurat", status_code=503)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_unconfigured:
                auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(ctx_unconfigured.exception.status_code, 503)

            auth_api.mailgun_service.assert_available = lambda: (_ for _ in ()).throw(
                MailgunIntegrationError("Integrarea Mailgun este dezactivată", status_code=503)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_disabled:
                auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(ctx_disabled.exception.status_code, 503)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.load_settings = original_settings

    def test_forgot_password_token_generation_failure_returns_clear_error(self):
        original_rate = auth_api.rate_limiter_service.check
        original_assert = auth_api.mailgun_service.assert_available
        original_find = auth_api.find_active_user_by_email
        original_create = auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user
        original_send = auth_api.mailgun_service.send_email
        original_settings = auth_api.load_settings

        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.mailgun_service.assert_available = lambda: None
            auth_api.find_active_user_by_email = lambda email: {"id": 9, "email": "u@example.com", "is_active": True}
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token generation failed", reason="persist_failed", status_code=500)
            )
            auth_api.mailgun_service.send_email = lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not send"))
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)

            with self.assertRaises(auth_api.HTTPException) as ctx:
                auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(ctx.exception.status_code, 503)
            self.assertIn("nu este disponibil", str(ctx.exception.detail))
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.mailgun_service.assert_available = original_assert
            auth_api.find_active_user_by_email = original_find
            auth_api.auth_email_tokens_service.create_password_reset_token_for_existing_user = original_create
            auth_api.mailgun_service.send_email = original_send
            auth_api.load_settings = original_settings

    def test_forgot_password_missing_frontend_base_url_returns_clear_error(self):
        original_rate = auth_api.rate_limiter_service.check
        original_settings = auth_api.load_settings
        try:
            auth_api.rate_limiter_service.check = lambda *args, **kwargs: None
            auth_api.load_settings = lambda: SimpleNamespace(frontend_base_url="", auth_reset_token_ttl_minutes=60)

            with self.assertRaises(auth_api.HTTPException) as ctx:
                auth_api.forgot_password(ForgotPasswordRequest(email="u@example.com"))
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            auth_api.rate_limiter_service.check = original_rate
            auth_api.load_settings = original_settings

    def test_reset_confirm_success_updates_password_and_consumes_token(self):
        original_validate = auth_api.auth_email_tokens_service.validate_reset_or_invite_token
        original_consume = auth_api.auth_email_tokens_service.consume_reset_or_invite_token
        original_set = auth_api.set_user_password
        original_invalidate = auth_api.auth_email_tokens_service.invalidate_active_tokens
        calls: dict[str, object] = {}

        try:
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = lambda **kwargs: PasswordResetTokenRecord(
                id=11,
                user_id=7,
                email="u@example.com",
                token_type="password_reset",
                expires_at=SimpleNamespace(),
                consumed_at=None,
                metadata_json="{}",
            )
            auth_api.auth_email_tokens_service.consume_reset_or_invite_token = lambda **kwargs: PasswordResetTokenRecord(
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
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = original_validate
            auth_api.auth_email_tokens_service.consume_reset_or_invite_token = original_consume
            auth_api.set_user_password = original_set
            auth_api.auth_email_tokens_service.invalidate_active_tokens = original_invalidate

    def test_reset_confirm_invalid_expired_consumed_tokens(self):
        original_validate = auth_api.auth_email_tokens_service.validate_reset_or_invite_token
        try:
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token invalid", reason="invalid_token", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_invalid:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="bad", new_password="new-pass-123"))
            self.assertEqual(ctx_invalid.exception.status_code, 400)

            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token expirat", reason="token_expired", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_exp:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="expired", new_password="new-pass-123"))
            self.assertEqual(ctx_exp.exception.status_code, 400)

            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = lambda **kwargs: (_ for _ in ()).throw(
                AuthEmailTokenError("Token deja folosit", reason="token_consumed", status_code=400)
            )
            with self.assertRaises(auth_api.HTTPException) as ctx_cons:
                auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="used", new_password="new-pass-123"))
            self.assertEqual(ctx_cons.exception.status_code, 400)
        finally:
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = original_validate

    def test_reset_confirm_invalid_new_password(self):
        with self.assertRaises(auth_api.HTTPException) as ctx:
            auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="t", new_password="short"))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_reset_confirm_accepts_invite_user_token(self):
        original_validate = auth_api.auth_email_tokens_service.validate_reset_or_invite_token
        original_consume = auth_api.auth_email_tokens_service.consume_reset_or_invite_token
        original_set = auth_api.set_user_password
        original_invalidate = auth_api.auth_email_tokens_service.invalidate_active_tokens

        try:
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = lambda **kwargs: PasswordResetTokenRecord(
                id=21,
                user_id=12,
                email="invitee@example.com",
                token_type="invite_user",
                expires_at=SimpleNamespace(),
                consumed_at=None,
                metadata_json="{}",
            )
            auth_api.auth_email_tokens_service.consume_reset_or_invite_token = lambda **kwargs: PasswordResetTokenRecord(
                id=21,
                user_id=12,
                email="invitee@example.com",
                token_type="invite_user",
                expires_at=SimpleNamespace(),
                consumed_at=SimpleNamespace(),
                metadata_json="{}",
            )
            auth_api.set_user_password = lambda **kwargs: None
            auth_api.auth_email_tokens_service.invalidate_active_tokens = lambda **kwargs: None

            response = auth_api.reset_password_confirm(ResetPasswordConfirmRequest(token="invite-token", new_password="invite-pass-123"))
            self.assertIn("resetată", response.message)
        finally:
            auth_api.auth_email_tokens_service.validate_reset_or_invite_token = original_validate
            auth_api.auth_email_tokens_service.consume_reset_or_invite_token = original_consume
            auth_api.set_user_password = original_set
            auth_api.auth_email_tokens_service.invalidate_active_tokens = original_invalidate


if __name__ == "__main__":
    unittest.main()
