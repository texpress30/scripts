import unittest
from types import SimpleNamespace

from app.api import team as team_api
from app.services.auth import AuthUser
from app.services.email_templates import RenderedEmailTemplate
from app.services.mailgun_service import MailgunIntegrationError


class TeamInviteApiTests(unittest.TestCase):
    def test_invite_membership_not_found_returns_404(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: None
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.invite_team_member(membership_id=123, user=user)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            team_api.team_members_service.get_membership_with_user = original_get

    def test_invite_forbidden_for_subaccount_user_outside_scope(self):
        user = AuthUser(email="u@example.com", role="subaccount_admin", subaccount_id=7)
        original_get = team_api.team_members_service.get_membership_with_user
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 22,
                "user_id": 14,
                "scope_type": "subaccount",
                "subaccount_id": 9,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.invite_team_member(membership_id=22, user=user)
            self.assertEqual(ctx.exception.status_code, 403)
        finally:
            team_api.team_members_service.get_membership_with_user = original_get

    def test_invite_mailgun_unavailable_returns_503(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        original_assert = team_api.mailgun_service.assert_available
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 31,
                "user_id": 19,
                "scope_type": "agency",
                "subaccount_id": None,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            team_api.mailgun_service.assert_available = lambda: (_ for _ in ()).throw(
                MailgunIntegrationError("Mailgun nu este configurat", status_code=503)
            )
            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.invite_team_member(membership_id=31, user=user)
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            team_api.team_members_service.get_membership_with_user = original_get
            team_api.mailgun_service.assert_available = original_assert

    def test_invite_missing_frontend_base_url_returns_503(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        original_assert = team_api.mailgun_service.assert_available
        original_settings = team_api.load_settings
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 51,
                "user_id": 29,
                "scope_type": "agency",
                "subaccount_id": None,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            team_api.mailgun_service.assert_available = lambda: None
            team_api.load_settings = lambda: SimpleNamespace(frontend_base_url="", auth_reset_token_ttl_minutes=60)

            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.invite_team_member(membership_id=51, user=user)
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            team_api.team_members_service.get_membership_with_user = original_get
            team_api.mailgun_service.assert_available = original_assert
            team_api.load_settings = original_settings

    def test_invite_success_uses_default_template_rendered_content(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        original_assert = team_api.mailgun_service.assert_available
        original_settings = team_api.load_settings
        original_create = team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user
        original_send = team_api.mailgun_service.send_email
        original_render = team_api.email_templates_service.render_effective_template
        captured: dict[str, object] = {}
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 41,
                "user_id": 21,
                "scope_type": "agency",
                "subaccount_id": None,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            team_api.mailgun_service.assert_available = lambda: None
            team_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = lambda **kwargs: ("invite-raw-token", None)
            team_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="team_invite_user",
                subject="Invitație",
                text_body=f"Text {kwargs['variables']['invite_link']}",
                html_body=f"<p>{kwargs['variables']['invite_link']}</p>",
                enabled=True,
                available_variables=("invite_link", "expires_minutes", "user_email"),
            )

            def _fake_send_email(**kwargs):
                captured.update(kwargs)
                return {"ok": True}

            team_api.mailgun_service.send_email = _fake_send_email

            response = team_api.invite_team_member(membership_id=41, user=user)
            self.assertIn("trimisă", response.message)
            self.assertEqual(captured["to_email"], "member@example.com")
            self.assertIn("invite-raw-token", str(captured["text"]))
            self.assertIn("invite-raw-token", str(captured["html"]))
        finally:
            team_api.team_members_service.get_membership_with_user = original_get
            team_api.mailgun_service.assert_available = original_assert
            team_api.load_settings = original_settings
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = original_create
            team_api.mailgun_service.send_email = original_send
            team_api.email_templates_service.render_effective_template = original_render

    def test_invite_override_template_is_used(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        original_assert = team_api.mailgun_service.assert_available
        original_settings = team_api.load_settings
        original_create = team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user
        original_send = team_api.mailgun_service.send_email
        original_render = team_api.email_templates_service.render_effective_template
        captured: dict[str, object] = {}
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 41,
                "user_id": 21,
                "scope_type": "agency",
                "subaccount_id": None,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            team_api.mailgun_service.assert_available = lambda: None
            team_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = lambda **kwargs: ("invite-raw-token", None)
            team_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="team_invite_user",
                subject="Override invite",
                text_body="Override text",
                html_body="<p>Override html</p>",
                enabled=True,
                available_variables=("invite_link", "expires_minutes", "user_email"),
            )
            team_api.mailgun_service.send_email = lambda **kwargs: captured.update(kwargs) or {"ok": True}

            team_api.invite_team_member(membership_id=41, user=user)
            self.assertEqual(captured["subject"], "Override invite")
            self.assertEqual(captured["text"], "Override text")
            self.assertEqual(captured["html"], "<p>Override html</p>")
        finally:
            team_api.team_members_service.get_membership_with_user = original_get
            team_api.mailgun_service.assert_available = original_assert
            team_api.load_settings = original_settings
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = original_create
            team_api.mailgun_service.send_email = original_send
            team_api.email_templates_service.render_effective_template = original_render

    def test_invite_template_disabled_returns_503(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_get = team_api.team_members_service.get_membership_with_user
        original_assert = team_api.mailgun_service.assert_available
        original_settings = team_api.load_settings
        original_create = team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user
        original_send = team_api.mailgun_service.send_email
        original_render = team_api.email_templates_service.render_effective_template
        try:
            team_api.team_members_service.get_membership_with_user = lambda **kwargs: {
                "membership_id": 41,
                "user_id": 21,
                "scope_type": "agency",
                "subaccount_id": None,
                "status": "active",
                "email": "member@example.com",
                "is_active": True,
            }
            team_api.mailgun_service.assert_available = lambda: None
            team_api.load_settings = lambda: SimpleNamespace(frontend_base_url="https://app.example.com", auth_reset_token_ttl_minutes=60)
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = lambda **kwargs: ("invite-raw-token", None)
            team_api.email_templates_service.render_effective_template = lambda **kwargs: RenderedEmailTemplate(
                key="team_invite_user",
                subject="sub",
                text_body="txt",
                html_body="",
                enabled=False,
                available_variables=("invite_link", "expires_minutes", "user_email"),
            )
            team_api.mailgun_service.send_email = lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not send"))

            with self.assertRaises(team_api.HTTPException) as ctx:
                team_api.invite_team_member(membership_id=41, user=user)
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            team_api.team_members_service.get_membership_with_user = original_get
            team_api.mailgun_service.assert_available = original_assert
            team_api.load_settings = original_settings
            team_api.auth_email_tokens_service.create_user_invite_token_for_existing_user = original_create
            team_api.mailgun_service.send_email = original_send
            team_api.email_templates_service.render_effective_template = original_render


if __name__ == "__main__":
    unittest.main()
