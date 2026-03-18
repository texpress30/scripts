import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.api import email_templates as email_templates_api
from app.services.auth import AuthUser
from app.services.email_templates import EffectiveEmailTemplate, EmailTemplatesService


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
