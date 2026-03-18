import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.api import email_templates as email_templates_api
from app.services.auth import AuthUser
from app.services.email_templates import EmailTemplatePreviewResult, EmailTemplateTestSendResult, EffectiveEmailTemplate, EmailTemplatesService
from app.services import mailgun_service as mailgun_module
from app.services.mailgun_service import MailgunIntegrationError


class _FakeCursor:
    def __init__(self, statements: list[str]):
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params=None):  # noqa: ANN001
        self._statements.append(" ".join(query.split()))


class _FakeConnection:
    def __init__(self, statements: list[str]):
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._statements)

    def commit(self):
        return None


class EmailTemplatesApiTests(unittest.TestCase):
    def test_schema_initialize_idempotent(self):
        service = EmailTemplatesService()
        statements: list[str] = []
        service._connect = lambda: _FakeConnection(statements)  # type: ignore[attr-defined]

        service.initialize_schema()
        service.initialize_schema()

        create_table_count = sum(1 for statement in statements if "CREATE TABLE IF NOT EXISTS agency_email_templates" in statement)
        unique_constraint_seen = any("UNIQUE (template_key, scope_key)" in statement for statement in statements)
        self.assertEqual(create_table_count, 2)
        self.assertTrue(unique_constraint_seen)

    def test_list_without_override_marks_default_state(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "list_effective_templates") as mock_list:
            mock_list.return_value = [
                EffectiveEmailTemplate(
                    key="auth_forgot_password",
                    label="Auth · Forgot Password",
                    description="desc",
                    subject="Default subject",
                    text_body="Default text",
                    html_body="<p>Default</p>",
                    available_variables=("reset_link",),
                    scope="agency",
                    enabled=True,
                    is_overridden=False,
                    updated_at=None,
                )
            ]
            resp = email_templates_api.list_agency_email_templates(user=user)

        self.assertEqual(resp.items[0].key, "auth_forgot_password")
        self.assertFalse(resp.items[0].is_overridden)
        self.assertTrue(resp.items[0].enabled)

    def test_detail_without_override_uses_catalog_default(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "get_effective_template") as mock_get:
            mock_get.return_value = EffectiveEmailTemplate(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                subject="Resetează parola",
                text_body="Default text",
                html_body="<p>Default</p>",
                available_variables=("reset_link",),
                scope="agency",
                enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            resp = email_templates_api.get_agency_email_template_detail(template_key="auth_forgot_password", user=user)

        self.assertEqual(resp.key, "auth_forgot_password")
        self.assertFalse(resp.is_overridden)
        self.assertEqual(resp.subject, "Resetează parola")

    def test_save_override_success_and_detail_after_override(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        updated_at = datetime.now(timezone.utc)

        with patch.object(email_templates_api.email_templates_service, "save_override") as mock_save:
            mock_save.return_value = EffectiveEmailTemplate(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                subject="Subiect custom",
                text_body="Text custom",
                html_body="<p>Custom</p>",
                available_variables=("reset_link",),
                scope="agency",
                enabled=False,
                is_overridden=True,
                updated_at=updated_at,
            )
            resp = email_templates_api.upsert_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplateUpsertRequest(
                    subject="Subiect custom",
                    text_body="Text custom",
                    html_body="<p>Custom</p>",
                    enabled=False,
                ),
                user=user,
            )

        self.assertEqual(resp.subject, "Subiect custom")
        self.assertTrue(resp.is_overridden)
        self.assertFalse(resp.enabled)
        self.assertIsNotNone(resp.updated_at)

    def test_reset_override_returns_default_payload(self):
        user = AuthUser(email="owner@example.com", role="agency_owner")
        with patch.object(email_templates_api.email_templates_service, "reset_override") as mock_reset:
            mock_reset.return_value = EffectiveEmailTemplate(
                key="team_invite_user",
                label="Team · Invite User",
                description="desc",
                subject="Invitație în platformă",
                text_body="Default invite text",
                html_body="<p>Default invite html</p>",
                available_variables=("invite_link",),
                scope="agency",
                enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            resp = email_templates_api.reset_agency_email_template(template_key="team_invite_user", user=user)

        self.assertEqual(resp.key, "team_invite_user")
        self.assertFalse(resp.is_overridden)
        self.assertTrue(resp.enabled)

    def test_invalid_template_key_returns_404(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")

        with patch.object(email_templates_api.email_templates_service, "get_effective_template", return_value=None):
            with self.assertRaises(email_templates_api.HTTPException) as get_ctx:
                email_templates_api.get_agency_email_template_detail(template_key="does_not_exist", user=user)
            self.assertEqual(get_ctx.exception.status_code, 404)

        with patch.object(email_templates_api.email_templates_service, "save_override", return_value=None):
            with self.assertRaises(email_templates_api.HTTPException) as put_ctx:
                email_templates_api.upsert_agency_email_template(
                    template_key="does_not_exist",
                    payload=email_templates_api.AgencyEmailTemplateUpsertRequest(subject="a", text_body="b"),
                    user=user,
                )
            self.assertEqual(put_ctx.exception.status_code, 404)

        with patch.object(email_templates_api.email_templates_service, "reset_override", return_value=None):
            with self.assertRaises(email_templates_api.HTTPException) as reset_ctx:
                email_templates_api.reset_agency_email_template(template_key="does_not_exist", user=user)
            self.assertEqual(reset_ctx.exception.status_code, 404)

        with patch.object(email_templates_api.email_templates_service, "render_template_preview", return_value=None):
            with self.assertRaises(email_templates_api.HTTPException) as preview_ctx:
                email_templates_api.preview_agency_email_template(
                    template_key="does_not_exist",
                    payload=email_templates_api.AgencyEmailTemplatePreviewRequest(),
                    user=user,
                )
            self.assertEqual(preview_ctx.exception.status_code, 404)

        with patch.object(email_templates_api.email_templates_service, "send_template_test_email", return_value=None):
            with self.assertRaises(email_templates_api.HTTPException) as test_send_ctx:
                email_templates_api.test_send_agency_email_template(
                    template_key="does_not_exist",
                    payload=email_templates_api.AgencyEmailTemplateTestSendRequest(to_email="qa@example.com"),
                    user=user,
                )
            self.assertEqual(test_send_ctx.exception.status_code, 404)

    def test_save_validation_subject_and_text_required(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "save_override", side_effect=ValueError("subject este obligatoriu")):
            with self.assertRaises(email_templates_api.HTTPException) as ctx_subject:
                email_templates_api.upsert_agency_email_template(
                    template_key="auth_forgot_password",
                    payload=email_templates_api.AgencyEmailTemplateUpsertRequest(subject="", text_body="abc"),
                    user=user,
                )
            self.assertEqual(ctx_subject.exception.status_code, 400)

        with patch.object(email_templates_api.email_templates_service, "save_override", side_effect=ValueError("text_body este obligatoriu")):
            with self.assertRaises(email_templates_api.HTTPException) as ctx_text:
                email_templates_api.upsert_agency_email_template(
                    template_key="auth_forgot_password",
                    payload=email_templates_api.AgencyEmailTemplateUpsertRequest(subject="abc", text_body="   "),
                    user=user,
                )
            self.assertEqual(ctx_text.exception.status_code, 400)



    def test_render_effective_template_replaces_variables_deterministically(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template") as mock_effective:
            mock_effective.return_value = EffectiveEmailTemplate(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                subject="Reset {{user_email}}",
                text_body="Folosește {{reset_link}} în {{expires_minutes}} minute",
                html_body="<a href='{{reset_link}}'>Reset</a>",
                available_variables=("reset_link", "expires_minutes", "user_email"),
                scope="agency",
                enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            rendered = service.render_effective_template(
                template_key="auth_forgot_password",
                variables={
                    "reset_link": "https://app/reset?t=1",
                    "expires_minutes": "60",
                    "user_email": "u@example.com",
                },
            )

        self.assertIsNotNone(rendered)
        self.assertEqual(rendered.subject, "Reset u@example.com")
        self.assertIn("https://app/reset?t=1", rendered.text_body)
        self.assertIn("60", rendered.text_body)

    def test_render_effective_template_returns_none_for_missing_key(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template", return_value=None):
            rendered = service.render_effective_template(template_key="missing", variables={"a": "b"})
        self.assertIsNone(rendered)

    def test_preview_default_auth_forgot_password_uses_canonical_samples(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template") as mock_effective:
            mock_effective.return_value = EffectiveEmailTemplate(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                subject="Resetare pentru {{user_email}}",
                text_body="Folosește {{reset_link}} în {{expires_minutes}} minute",
                html_body="<a href='{{reset_link}}'>Reset</a>",
                available_variables=("reset_link", "expires_minutes", "user_email"),
                scope="agency",
                enabled=False,
                is_overridden=False,
                updated_at=None,
            )
            preview = service.render_template_preview(template_key="auth_forgot_password")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(preview.key, "auth_forgot_password")
        self.assertIn("preview.user@example.com", preview.rendered_subject)
        self.assertIn("https://app.example.com/reset-password", preview.rendered_text_body)
        self.assertIn("60", preview.rendered_text_body)

    def test_preview_default_team_invite_user_uses_canonical_samples(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template") as mock_effective:
            mock_effective.return_value = EffectiveEmailTemplate(
                key="team_invite_user",
                label="Team · Invite User",
                description="desc",
                subject="Invitație pentru {{user_email}}",
                text_body="Activează contul: {{invite_link}}",
                html_body="<a href='{{invite_link}}'>Activează</a>",
                available_variables=("invite_link", "expires_minutes", "user_email"),
                scope="agency",
                enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            preview = service.render_template_preview(template_key="team_invite_user")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertIn("https://app.example.com/activate-invite", preview.rendered_text_body)
        self.assertEqual(preview.sample_variables["user_email"], "preview.user@example.com")

    def test_preview_uses_saved_override_when_no_draft_values_sent(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template") as mock_effective:
            mock_effective.return_value = EffectiveEmailTemplate(
                key="team_invite_user",
                label="Team · Invite User",
                description="desc",
                subject="Subiect override {{user_email}}",
                text_body="Body override {{invite_link}}",
                html_body="<p>Override {{invite_link}}</p>",
                available_variables=("invite_link", "expires_minutes", "user_email"),
                scope="agency",
                enabled=False,
                is_overridden=True,
                updated_at=None,
            )
            preview = service.render_template_preview(template_key="team_invite_user")

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertTrue(preview.is_overridden)
        self.assertIn("Subiect override", preview.rendered_subject)
        self.assertIn("activate-invite", preview.rendered_text_body)

    def test_preview_uses_draft_values_when_sent_in_request(self):
        service = EmailTemplatesService()
        with patch.object(service, "get_effective_template") as mock_effective:
            mock_effective.return_value = EffectiveEmailTemplate(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                subject="Persisted {{user_email}}",
                text_body="Persisted text {{reset_link}}",
                html_body="<p>Persisted html</p>",
                available_variables=("reset_link", "expires_minutes", "user_email"),
                scope="agency",
                enabled=True,
                is_overridden=True,
                updated_at=None,
            )
            preview = service.render_template_preview(
                template_key="auth_forgot_password",
                subject="Draft {{user_email}}",
                text_body="Draft {{reset_link}}",
                html_body="<strong>Draft {{expires_minutes}}</strong>",
            )

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertIn("Draft preview.user@example.com", preview.rendered_subject)
        self.assertIn("reset-password", preview.rendered_text_body)
        self.assertIn("60", preview.rendered_html_body)

    def test_service_test_send_default_auth_forgot_password(self):
        service = EmailTemplatesService()
        with (
            patch.object(
                service,
                "render_template_preview",
                return_value=EmailTemplatePreviewResult(
                    key="auth_forgot_password",
                    rendered_subject="Subject auth",
                    rendered_text_body="Text auth",
                    rendered_html_body="<p>Html auth</p>",
                    sample_variables={"reset_link": "https://example"},
                    is_overridden=False,
                ),
            ),
            patch("app.services.mailgun_service.mailgun_service.send_email") as mock_send,
        ):
            mock_send.return_value = {"ok": True, "to_email": "qa@example.com", "message": "Queued"}
            result = service.send_template_test_email(template_key="auth_forgot_password", to_email="qa@example.com")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.key, "auth_forgot_password")
        self.assertTrue(result.sent)

    def test_service_test_send_default_team_invite_user(self):
        service = EmailTemplatesService()
        with (
            patch.object(
                service,
                "render_template_preview",
                return_value=EmailTemplatePreviewResult(
                    key="team_invite_user",
                    rendered_subject="Subject invite",
                    rendered_text_body="Text invite",
                    rendered_html_body="<p>Html invite</p>",
                    sample_variables={"invite_link": "https://example"},
                    is_overridden=False,
                ),
            ),
            patch("app.services.mailgun_service.mailgun_service.send_email") as mock_send,
        ):
            mock_send.return_value = {"ok": True, "to_email": "qa@example.com", "message": "Queued"}
            result = service.send_template_test_email(template_key="team_invite_user", to_email="qa@example.com")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.key, "team_invite_user")

    def test_service_test_send_with_override_and_disabled_template_allowed(self):
        service = EmailTemplatesService()
        with (
            patch.object(
                service,
                "render_template_preview",
                return_value=EmailTemplatePreviewResult(
                    key="auth_forgot_password",
                    rendered_subject="Override subject",
                    rendered_text_body="Override text",
                    rendered_html_body="<p>Override html</p>",
                    sample_variables={"reset_link": "https://example"},
                    is_overridden=True,
                ),
            ),
            patch("app.services.mailgun_service.mailgun_service.send_email") as mock_send,
        ):
            mock_send.return_value = {"ok": True, "to_email": "qa@example.com", "message": "Queued"}
            result = service.send_template_test_email(template_key="auth_forgot_password", to_email="qa@example.com")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.sent)
        self.assertIn("Override", result.rendered_subject)

    def test_service_test_send_uses_draft_values(self):
        service = EmailTemplatesService()
        with (
            patch.object(service, "render_template_preview") as mock_preview,
            patch("app.services.mailgun_service.mailgun_service.send_email") as mock_send,
        ):
            mock_preview.return_value = EmailTemplatePreviewResult(
                key="auth_forgot_password",
                rendered_subject="Draft subject",
                rendered_text_body="Draft text",
                rendered_html_body="<p>Draft html</p>",
                sample_variables={},
                is_overridden=False,
            )
            mock_send.return_value = {"ok": True, "to_email": "qa@example.com", "message": "Queued"}
            result = service.send_template_test_email(
                template_key="auth_forgot_password",
                to_email="qa@example.com",
                subject="Draft {{user_email}}",
                text_body="Draft {{reset_link}}",
                html_body="<p>Draft html {{expires_minutes}}</p>",
            )

        self.assertIsNotNone(result)
        mock_preview.assert_called_once_with(
            template_key="auth_forgot_password",
            subject="Draft {{user_email}}",
            text_body="Draft {{reset_link}}",
            html_body="<p>Draft html {{expires_minutes}}</p>",
        )

    def test_service_test_send_works_with_env_mailgun_fallback(self):
        service = EmailTemplatesService()
        fake_store = type(
            "_FakeStore",
            (),
            {
                "get_secret": staticmethod(lambda **kwargs: None),
                "upsert_secret": staticmethod(lambda **kwargs: None),
            },
        )()

        original_store = mailgun_module.integration_secrets_store
        original_settings = mailgun_module.load_settings
        original_post = mailgun_module.requests.post
        try:
            mailgun_module.integration_secrets_store = fake_store
            mailgun_module.load_settings = lambda: type(
                "_S",
                (),
                {
                    "mailgun_api_key": "key-from-env",
                    "mailgun_domain": "mg.env.example.com",
                    "mailgun_base_url": "https://api.mailgun.net",
                    "mailgun_from_email": "env@example.com",
                    "mailgun_from_name": "Env Sender",
                    "mailgun_reply_to": "",
                    "mailgun_enabled": True,
                },
            )()

            def _fake_post(url, auth, data, timeout):
                class _Resp:
                    ok = True
                    status_code = 200

                    @staticmethod
                    def json():
                        return {"id": "abc123", "message": "Queued"}

                    text = ""

                return _Resp()

            mailgun_module.requests.post = _fake_post

            with patch.object(
                service,
                "render_template_preview",
                return_value=EmailTemplatePreviewResult(
                    key="auth_forgot_password",
                    rendered_subject="Subject auth",
                    rendered_text_body="Text auth",
                    rendered_html_body="<p>Html auth</p>",
                    sample_variables={"reset_link": "https://example"},
                    is_overridden=False,
                ),
            ):
                result = service.send_template_test_email(template_key="auth_forgot_password", to_email="qa@example.com")
            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.sent)
        finally:
            mailgun_module.integration_secrets_store = original_store
            mailgun_module.load_settings = original_settings
            mailgun_module.requests.post = original_post

    def test_service_save_override_enforces_required_subject_and_text(self):
        service = EmailTemplatesService()
        with patch.object(service, "_fetch_override_row", return_value=None):
            with self.assertRaisesRegex(ValueError, "subject este obligatoriu"):
                service._normalize_override_input(
                    subject="   ",
                    text_body="text",
                    html_body=None,
                    enabled=None,
                    template_key="auth_forgot_password",
                )
            with self.assertRaisesRegex(ValueError, "text_body este obligatoriu"):
                service._normalize_override_input(
                    subject="Subiect",
                    text_body="   ",
                    html_body=None,
                    enabled=None,
                    template_key="auth_forgot_password",
                )

    def test_service_save_override_defaults_enabled_true(self):
        service = EmailTemplatesService()
        with (
            patch.object(service, "_fetch_override_row", side_effect=[None, {
                "template_key": "auth_forgot_password",
                "scope_key": "agency_default",
                "subject_override": "Subiect nou",
                "text_body_override": "Text nou",
                "html_body_override": "",
                "enabled": True,
                "updated_at": datetime.now(timezone.utc),
            }]),
            patch.object(service, "_upsert_override_row", return_value=None),
        ):
            saved = service.save_override(
                template_key="auth_forgot_password",
                subject="Subiect nou",
                text_body="Text nou",
                html_body=None,
                enabled=None,
            )

        self.assertIsNotNone(saved)
        self.assertTrue(saved.enabled)
        self.assertTrue(saved.is_overridden)

    def test_rbac_blocks_non_admin_on_read_and_write(self):
        user = AuthUser(email="member@example.com", role="agency_member")
        with self.assertRaises(email_templates_api.HTTPException) as list_ctx:
            email_templates_api.list_agency_email_templates(user=user)
        self.assertEqual(list_ctx.exception.status_code, 403)

        with self.assertRaises(email_templates_api.HTTPException) as put_ctx:
            email_templates_api.upsert_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplateUpsertRequest(subject="abc", text_body="def"),
                user=user,
            )
        self.assertEqual(put_ctx.exception.status_code, 403)

        with self.assertRaises(email_templates_api.HTTPException) as preview_ctx:
            email_templates_api.preview_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplatePreviewRequest(),
                user=user,
            )
        self.assertEqual(preview_ctx.exception.status_code, 403)

        with self.assertRaises(email_templates_api.HTTPException) as test_send_ctx:
            email_templates_api.test_send_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplateTestSendRequest(to_email="qa@example.com"),
                user=user,
            )
        self.assertEqual(test_send_ctx.exception.status_code, 403)

    def test_preview_endpoint_uses_service_and_returns_rendered_payload(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "render_template_preview") as mock_preview:
            mock_preview.return_value = EmailTemplatePreviewResult(
                key="auth_forgot_password",
                rendered_subject="Rendered subject",
                rendered_text_body="Rendered text",
                rendered_html_body="<p>Rendered html</p>",
                sample_variables={"reset_link": "https://example/reset"},
                is_overridden=True,
            )
            resp = email_templates_api.preview_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplatePreviewRequest(subject="Draft"),
                user=user,
            )

        self.assertEqual(resp.key, "auth_forgot_password")
        self.assertEqual(resp.rendered_subject, "Rendered subject")
        self.assertEqual(resp.sample_variables["reset_link"], "https://example/reset")
        mock_preview.assert_called_once()

    def test_test_send_endpoint_uses_service_and_returns_payload(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "send_template_test_email") as mock_send:
            mock_send.return_value = EmailTemplateTestSendResult(
                key="auth_forgot_password",
                to_email="qa@example.com",
                sent=True,
                rendered_subject="Rendered subject",
                message="Queued",
            )
            resp = email_templates_api.test_send_agency_email_template(
                template_key="auth_forgot_password",
                payload=email_templates_api.AgencyEmailTemplateTestSendRequest(
                    to_email="qa@example.com",
                    subject="Draft",
                ),
                user=user,
            )

        self.assertEqual(resp.key, "auth_forgot_password")
        self.assertTrue(resp.sent)
        self.assertEqual(resp.to_email, "qa@example.com")
        mock_send.assert_called_once()

    def test_test_send_endpoint_invalid_to_email_returns_400(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "send_template_test_email", side_effect=ValueError("to_email invalid")):
            with self.assertRaises(email_templates_api.HTTPException) as ctx:
                email_templates_api.test_send_agency_email_template(
                    template_key="auth_forgot_password",
                    payload=email_templates_api.AgencyEmailTemplateTestSendRequest(to_email="invalid"),
                    user=user,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_test_send_endpoint_mailgun_unavailable_returns_503(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(
            email_templates_api.email_templates_service,
            "send_template_test_email",
            side_effect=MailgunIntegrationError("Mailgun nu este configurat", status_code=503),
        ):
            with self.assertRaises(email_templates_api.HTTPException) as ctx:
                email_templates_api.test_send_agency_email_template(
                    template_key="auth_forgot_password",
                    payload=email_templates_api.AgencyEmailTemplateTestSendRequest(to_email="qa@example.com"),
                    user=user,
                )
            self.assertEqual(ctx.exception.status_code, 503)

    def test_existing_read_endpoints_still_work_with_new_fields(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "list_effective_templates") as mock_list:
            mock_list.return_value = [
                EffectiveEmailTemplate(
                    key="team_invite_user",
                    label="Team · Invite User",
                    description="desc",
                    subject="Invitație",
                    text_body="Body",
                    html_body="<p>Body</p>",
                    available_variables=("invite_link",),
                    scope="agency",
                    enabled=True,
                    is_overridden=True,
                    updated_at=datetime.now(timezone.utc),
                )
            ]
            resp = email_templates_api.list_agency_email_templates(user=user)

        self.assertEqual(len(resp.items), 1)
        self.assertEqual(resp.items[0].key, "team_invite_user")
        self.assertTrue(resp.items[0].is_overridden)


if __name__ == "__main__":
    unittest.main()
