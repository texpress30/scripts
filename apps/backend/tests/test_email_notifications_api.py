import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.api import email_notifications as email_notifications_api
from app.api import email_templates as email_templates_api
from app.services.auth import AuthUser
from app.services.email_notifications import EffectiveEmailNotification, EmailNotificationsService
from app.services.email_templates import EffectiveEmailTemplate


class _FakeCursor:
    def __init__(self, statements: list[str]):
        self._statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params=None):  # noqa: ANN001
        self._statements.append(" ".join(query.split()))

    def fetchall(self):
        return []

    def fetchone(self):
        return None


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


class EmailNotificationsApiTests(unittest.TestCase):
    def test_schema_initialize_idempotent(self):
        service = EmailNotificationsService()
        statements: list[str] = []
        service._connect = lambda: _FakeConnection(statements)  # type: ignore[attr-defined]

        service.initialize_schema()
        service.initialize_schema()

        create_table_count = sum(1 for statement in statements if "CREATE TABLE IF NOT EXISTS agency_email_notifications" in statement)
        unique_constraint_seen = any("UNIQUE (notification_key, scope_key)" in statement for statement in statements)
        self.assertEqual(create_table_count, 2)
        self.assertTrue(unique_constraint_seen)

    def test_catalog_contains_required_notifications(self):
        service = EmailNotificationsService()
        keys = {item.key for item in service.list_notifications()}
        self.assertIn("auth_forgot_password", keys)
        self.assertIn("team_invite_user", keys)

    def test_get_notification_catalog_detail_for_each_required_key(self):
        service = EmailNotificationsService()
        forgot = service.get_notification("auth_forgot_password")
        invite = service.get_notification("team_invite_user")
        self.assertIsNotNone(forgot)
        self.assertIsNotNone(invite)
        assert forgot is not None
        assert invite is not None
        self.assertEqual(forgot.template_key, "auth_forgot_password")
        self.assertEqual(invite.template_key, "team_invite_user")
        self.assertIn("fără parolă", str(invite.description).lower())
        self.assertIn("cu parolă", str(invite.description).lower())

    def test_effective_notification_defaults_when_no_override(self):
        service = EmailNotificationsService()
        with patch.object(service, "_fetch_override_row", return_value=None):
            item = service.get_effective_notification("auth_forgot_password")
        self.assertIsNotNone(item)
        assert item is not None
        self.assertTrue(item.enabled)
        self.assertFalse(item.is_overridden)

    def test_effective_notification_uses_override_when_present(self):
        service = EmailNotificationsService()
        with patch.object(
            service,
            "_fetch_override_row",
            return_value={
                "notification_key": "team_invite_user",
                "scope_key": "agency_default",
                "enabled_override": False,
                "updated_at": datetime.now(timezone.utc),
            },
        ):
            item = service.get_effective_notification("team_invite_user")
        self.assertIsNotNone(item)
        assert item is not None
        self.assertFalse(item.enabled)
        self.assertTrue(item.is_overridden)

    def test_resolve_runtime_notification_returns_compact_effective_payload(self):
        service = EmailNotificationsService()
        with patch.object(
            service,
            "get_effective_notification",
            return_value=EffectiveEmailNotification(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                channel="email",
                scope="agency",
                template_key="auth_forgot_password",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=datetime.now(timezone.utc),
            ),
        ):
            runtime = service.resolve_runtime_notification(notification_key="auth_forgot_password")
        self.assertIsNotNone(runtime)
        assert runtime is not None
        self.assertEqual(runtime.key, "auth_forgot_password")
        self.assertEqual(runtime.template_key, "auth_forgot_password")
        self.assertFalse(runtime.enabled)
        self.assertTrue(runtime.is_overridden)

    def test_list_endpoint_returns_effective_items(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_notifications_api.email_notifications_service, "list_effective_notifications") as mock_list:
            mock_list.return_value = [
                EffectiveEmailNotification(
                    key="auth_forgot_password",
                    label="Auth · Forgot Password",
                    description="desc",
                    channel="email",
                    scope="agency",
                    template_key="auth_forgot_password",
                    enabled=True,
                    default_enabled=True,
                    is_overridden=False,
                    updated_at=None,
                ),
                EffectiveEmailNotification(
                    key="team_invite_user",
                    label="Team · Invite User",
                    description="desc",
                    channel="email",
                    scope="agency",
                    template_key="team_invite_user",
                    enabled=False,
                    default_enabled=True,
                    is_overridden=True,
                    updated_at=datetime.now(timezone.utc),
                ),
            ]
            resp = email_notifications_api.list_agency_email_notifications(user=user)

        self.assertEqual(len(resp.items), 2)
        self.assertEqual(resp.items[0].key, "auth_forgot_password")
        self.assertEqual(resp.items[1].key, "team_invite_user")

    def test_detail_endpoint_returns_notification(self):
        user = AuthUser(email="owner@example.com", role="agency_owner")
        with patch.object(email_notifications_api.email_notifications_service, "get_effective_notification") as mock_get:
            mock_get.return_value = EffectiveEmailNotification(
                key="auth_forgot_password",
                label="Auth · Forgot Password",
                description="desc",
                channel="email",
                scope="agency",
                template_key="auth_forgot_password",
                enabled=True,
                default_enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            resp = email_notifications_api.get_agency_email_notification_detail(notification_key="auth_forgot_password", user=user)
        self.assertEqual(resp.key, "auth_forgot_password")

    def test_save_override_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_notifications_api.email_notifications_service, "save_override") as mock_save:
            mock_save.return_value = EffectiveEmailNotification(
                key="team_invite_user",
                label="Team · Invite User",
                description="desc",
                channel="email",
                scope="agency",
                template_key="team_invite_user",
                enabled=False,
                default_enabled=True,
                is_overridden=True,
                updated_at=datetime.now(timezone.utc),
            )
            resp = email_notifications_api.upsert_agency_email_notification(
                notification_key="team_invite_user",
                payload=email_notifications_api.AgencyEmailNotificationUpsertRequest(enabled=False),
                user=user,
            )
        self.assertFalse(resp.enabled)
        self.assertTrue(resp.is_overridden)

    def test_reset_override_returns_default_state(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_notifications_api.email_notifications_service, "reset_override") as mock_reset:
            mock_reset.return_value = EffectiveEmailNotification(
                key="team_invite_user",
                label="Team · Invite User",
                description="desc",
                channel="email",
                scope="agency",
                template_key="team_invite_user",
                enabled=True,
                default_enabled=True,
                is_overridden=False,
                updated_at=None,
            )
            resp = email_notifications_api.reset_agency_email_notification(notification_key="team_invite_user", user=user)
        self.assertTrue(resp.enabled)
        self.assertFalse(resp.is_overridden)

    def test_invalid_notification_key_returns_404(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")

        with patch.object(email_notifications_api.email_notifications_service, "get_effective_notification", return_value=None):
            with self.assertRaises(email_notifications_api.HTTPException) as detail_ctx:
                email_notifications_api.get_agency_email_notification_detail(notification_key="missing", user=user)
            self.assertEqual(detail_ctx.exception.status_code, 404)

        with patch.object(email_notifications_api.email_notifications_service, "save_override", return_value=None):
            with self.assertRaises(email_notifications_api.HTTPException) as save_ctx:
                email_notifications_api.upsert_agency_email_notification(
                    notification_key="missing",
                    payload=email_notifications_api.AgencyEmailNotificationUpsertRequest(enabled=True),
                    user=user,
                )
            self.assertEqual(save_ctx.exception.status_code, 404)

        with patch.object(email_notifications_api.email_notifications_service, "reset_override", return_value=None):
            with self.assertRaises(email_notifications_api.HTTPException) as reset_ctx:
                email_notifications_api.reset_agency_email_notification(notification_key="missing", user=user)
            self.assertEqual(reset_ctx.exception.status_code, 404)

    def test_save_requires_enabled_and_returns_400(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_notifications_api.email_notifications_service, "save_override", side_effect=ValueError("enabled este obligatoriu")):
            with self.assertRaises(email_notifications_api.HTTPException) as ctx:
                email_notifications_api.upsert_agency_email_notification(
                    notification_key="auth_forgot_password",
                    payload=email_notifications_api.AgencyEmailNotificationUpsertRequest(enabled=None),
                    user=user,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    def test_rbac_read_write_forbidden_for_agency_member(self):
        member = AuthUser(email="member@example.com", role="agency_member")
        with self.assertRaises(email_notifications_api.HTTPException) as list_ctx:
            email_notifications_api.list_agency_email_notifications(user=member)
        self.assertEqual(list_ctx.exception.status_code, 403)

        with self.assertRaises(email_notifications_api.HTTPException) as put_ctx:
            email_notifications_api.upsert_agency_email_notification(
                notification_key="auth_forgot_password",
                payload=email_notifications_api.AgencyEmailNotificationUpsertRequest(enabled=True),
                user=member,
            )
        self.assertEqual(put_ctx.exception.status_code, 403)

    def test_email_templates_endpoint_remains_compatible(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        with patch.object(email_templates_api.email_templates_service, "list_effective_templates") as mock_list:
            mock_list.return_value = [
                EffectiveEmailTemplate(
                    key="auth_forgot_password",
                    label="Auth · Forgot Password",
                    description="desc",
                    subject="Subject",
                    text_body="Text",
                    html_body="<p>Html</p>",
                    available_variables=("reset_link",),
                    scope="agency",
                    enabled=True,
                    is_overridden=False,
                    updated_at=None,
                )
            ]
            response = email_templates_api.list_agency_email_templates(user=user)
        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].key, "auth_forgot_password")


if __name__ == "__main__":
    unittest.main()
