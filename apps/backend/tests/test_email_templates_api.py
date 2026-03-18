import unittest

from app.api import email_templates as email_templates_api
from app.services.auth import AuthUser


class EmailTemplatesApiTests(unittest.TestCase):
    def test_list_includes_minimum_templates(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        resp = email_templates_api.list_agency_email_templates(user=user)

        keys = {item.key for item in resp.items}
        self.assertIn("auth_forgot_password", keys)
        self.assertIn("team_invite_user", keys)

    def test_detail_auth_forgot_password(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        resp = email_templates_api.get_agency_email_template_detail(template_key="auth_forgot_password", user=user)

        self.assertEqual(resp.key, "auth_forgot_password")
        self.assertEqual(resp.scope, "agency")
        self.assertIn("reset_link", resp.available_variables)

    def test_detail_team_invite_user(self):
        user = AuthUser(email="owner@example.com", role="agency_owner")
        resp = email_templates_api.get_agency_email_template_detail(template_key="team_invite_user", user=user)

        self.assertEqual(resp.key, "team_invite_user")
        self.assertEqual(resp.scope, "agency")
        self.assertIn("invite_link", resp.available_variables)

    def test_invalid_template_key_returns_404(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with self.assertRaises(email_templates_api.HTTPException) as ctx:
            email_templates_api.get_agency_email_template_detail(template_key="does_not_exist", user=user)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_rbac_blocks_non_admin_role(self):
        user = AuthUser(email="member@example.com", role="agency_member")
        with self.assertRaises(email_templates_api.HTTPException) as ctx:
            email_templates_api.list_agency_email_templates(user=user)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
