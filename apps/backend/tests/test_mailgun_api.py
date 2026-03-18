import unittest

from app.api import mailgun as mailgun_api
from app.services.auth import AuthUser


class MailgunApiTests(unittest.TestCase):
    def test_status_without_config(self):
        user = AuthUser(email="viewer@example.com", role="agency_viewer")
        original_status = mailgun_api.mailgun_service.status
        try:
            mailgun_api.mailgun_service.status = lambda: {
                "configured": False,
                "enabled": False,
                "config_source": "none",
                "domain": "",
                "base_url": "",
                "from_email": "",
                "from_name": "",
                "reply_to": "",
                "api_key_masked": "",
            }
            payload = mailgun_api.mailgun_status(user=user)
            self.assertFalse(payload["configured"])
        finally:
            mailgun_api.mailgun_service.status = original_status

    def test_config_forbidden_for_agency_member(self):
        user = AuthUser(email="member@example.com", role="agency_member")
        payload = mailgun_api.MailgunConfigRequest(
            api_key="key",
            domain="mg.example.com",
            base_url="https://api.mailgun.net",
            from_email="noreply@example.com",
            from_name="Agency",
            reply_to="",
            enabled=True,
        )
        with self.assertRaises(mailgun_api.HTTPException) as ctx:
            mailgun_api.save_mailgun_config(payload=payload, user=user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_test_forbidden_for_agency_member(self):
        user = AuthUser(email="member@example.com", role="agency_member")
        payload = mailgun_api.MailgunTestRequest(to_email="to@example.com")
        with self.assertRaises(mailgun_api.HTTPException) as ctx:
            mailgun_api.send_mailgun_test(payload=payload, user=user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_config_success_masks_api_key(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_upsert = mailgun_api.mailgun_service.upsert_config
        try:
            mailgun_api.mailgun_service.upsert_config = lambda **kwargs: {
                "configured": True,
                "enabled": True,
                "config_source": "db",
                "domain": "mg.example.com",
                "base_url": "https://api.mailgun.net",
                "from_email": "noreply@example.com",
                "from_name": "Agency",
                "reply_to": "",
                "api_key_masked": "key***ret",
            }
            payload = mailgun_api.MailgunConfigRequest(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency",
                reply_to="",
                enabled=True,
            )
            resp = mailgun_api.save_mailgun_config(payload=payload, user=user)
            self.assertTrue(resp["configured"])
            self.assertEqual(resp["api_key_masked"], "key***ret")
            self.assertNotIn("api_key", resp)
        finally:
            mailgun_api.mailgun_service.upsert_config = original_upsert

    def test_import_from_env_forbidden_for_agency_member(self):
        user = AuthUser(email="member@example.com", role="agency_member")
        with self.assertRaises(mailgun_api.HTTPException) as ctx:
            mailgun_api.import_mailgun_config_from_env(user=user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_import_from_env_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_import = mailgun_api.mailgun_service.import_from_env
        try:
            mailgun_api.mailgun_service.import_from_env = lambda: {
                "imported": True,
                "message": "Configurația Mailgun a fost importată din env în DB.",
                "configured": True,
                "enabled": True,
                "config_source": "db",
                "domain": "mg.example.com",
                "base_url": "https://api.mailgun.net",
                "from_email": "noreply@example.com",
                "from_name": "Agency",
                "reply_to": "",
                "api_key_masked": "key***ret",
            }
            payload = mailgun_api.import_mailgun_config_from_env(user=user)
            self.assertTrue(payload["imported"])
            self.assertEqual(payload["config_source"], "db")
            self.assertNotIn("api_key", payload)
        finally:
            mailgun_api.mailgun_service.import_from_env = original_import

    def test_test_send_errors(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_send = mailgun_api.mailgun_service.send_test_email
        try:
            mailgun_api.mailgun_service.send_test_email = lambda **kwargs: (_ for _ in ()).throw(
                mailgun_api.MailgunIntegrationError("Mailgun nu este configurat", status_code=404)
            )
            with self.assertRaises(mailgun_api.HTTPException) as ctx_missing:
                mailgun_api.send_mailgun_test(payload=mailgun_api.MailgunTestRequest(to_email="to@example.com"), user=user)
            self.assertEqual(ctx_missing.exception.status_code, 404)

            mailgun_api.mailgun_service.send_test_email = lambda **kwargs: (_ for _ in ()).throw(
                mailgun_api.MailgunIntegrationError("Integrarea Mailgun este dezactivată", status_code=400)
            )
            with self.assertRaises(mailgun_api.HTTPException) as ctx_disabled:
                mailgun_api.send_mailgun_test(payload=mailgun_api.MailgunTestRequest(to_email="to@example.com"), user=user)
            self.assertEqual(ctx_disabled.exception.status_code, 400)
        finally:
            mailgun_api.mailgun_service.send_test_email = original_send

    def test_test_send_success(self):
        user = AuthUser(email="admin@example.com", role="agency_admin")
        original_send = mailgun_api.mailgun_service.send_test_email
        try:
            mailgun_api.mailgun_service.send_test_email = lambda **kwargs: {
                "ok": True,
                "message": "Queued. Thank you.",
                "id": "<abc@example>",
                "to_email": "to@example.com",
                "subject": "Mailgun test email",
                "sent_at": "2026-03-17T00:00:00+00:00",
            }
            resp = mailgun_api.send_mailgun_test(payload=mailgun_api.MailgunTestRequest(to_email="to@example.com"), user=user)
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["to_email"], "to@example.com")
        finally:
            mailgun_api.mailgun_service.send_test_email = original_send


if __name__ == "__main__":
    unittest.main()
