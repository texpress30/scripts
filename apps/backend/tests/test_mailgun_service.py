import unittest
from types import SimpleNamespace

from app.services import mailgun_service as mailgun_module


class _FakeSecretsStore:
    def __init__(self):
        self.data: dict[tuple[str, str, str], str] = {}

    def upsert_secret(self, *, provider: str, secret_key: str, value: str, scope: str = "agency_default") -> None:
        self.data[(provider, secret_key, scope)] = str(value)

    def get_secret(self, *, provider: str, secret_key: str, scope: str = "agency_default"):
        value = self.data.get((provider, secret_key, scope))
        if value is None:
            return None
        return SimpleNamespace(value=value)


class _FakeResponse:
    def __init__(self, ok: bool, status_code: int, payload: dict[str, object] | None = None, text: str = ""):
        self.ok = ok
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class MailgunServiceTests(unittest.TestCase):
    def test_status_without_config(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        try:
            mailgun_module.integration_secrets_store = fake_store
            status_payload = service.status()
            self.assertFalse(status_payload["configured"])
            self.assertEqual(status_payload["api_key_masked"], "")
        finally:
            mailgun_module.integration_secrets_store = original_store

    def test_upsert_config_validation(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        try:
            mailgun_module.integration_secrets_store = fake_store
            with self.assertRaises(ValueError):
                service.upsert_config(
                    api_key="",
                    domain="mg.example.com",
                    base_url="https://api.mailgun.net",
                    from_email="noreply@example.com",
                    from_name="Agency",
                    reply_to="",
                    enabled=True,
                )
            with self.assertRaises(ValueError):
                service.upsert_config(
                    api_key="key-123",
                    domain="mg.example.com",
                    base_url="not-url",
                    from_email="noreply@example.com",
                    from_name="Agency",
                    reply_to="",
                    enabled=True,
                )
        finally:
            mailgun_module.integration_secrets_store = original_store

    def test_status_with_config_masks_api_key(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        try:
            mailgun_module.integration_secrets_store = fake_store
            payload = service.upsert_config(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency Name",
                reply_to="help@example.com",
                enabled=True,
            )
            self.assertTrue(payload["configured"])
            self.assertNotIn("key-super-secret", str(payload))
            self.assertEqual(payload["api_key_masked"], "key***ret")
        finally:
            mailgun_module.integration_secrets_store = original_store

    def test_send_test_without_config(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        try:
            mailgun_module.integration_secrets_store = fake_store
            with self.assertRaises(mailgun_module.MailgunIntegrationError) as ctx:
                service.send_test_email(to_email="to@example.com", subject="", text="")
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            mailgun_module.integration_secrets_store = original_store

    def test_send_test_with_disabled_integration(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        try:
            mailgun_module.integration_secrets_store = fake_store
            service.upsert_config(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency Name",
                reply_to="",
                enabled=False,
            )
            with self.assertRaises(mailgun_module.MailgunIntegrationError) as ctx:
                service.send_test_email(to_email="to@example.com", subject="", text="")
            self.assertEqual(ctx.exception.status_code, 503)
        finally:
            mailgun_module.integration_secrets_store = original_store


    def test_send_email_backward_compatible_without_html(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        original_post = mailgun_module.requests.post
        captured: dict[str, object] = {}

        try:
            mailgun_module.integration_secrets_store = fake_store
            service.upsert_config(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency Name",
                reply_to="",
                enabled=True,
            )

            def _fake_post(url, auth, data, timeout):
                captured["data"] = dict(data)
                return _FakeResponse(ok=True, status_code=200, payload={"id": "abc123", "message": "Queued"})

            mailgun_module.requests.post = _fake_post
            payload = service.send_email(to_email="test@example.com", subject="Subiect", text="Text simplu")
            self.assertTrue(payload["ok"])
            self.assertNotIn("html", captured["data"])
        finally:
            mailgun_module.integration_secrets_store = original_store
            mailgun_module.requests.post = original_post

    def test_send_email_includes_html_when_provided(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        original_post = mailgun_module.requests.post
        captured: dict[str, object] = {}

        try:
            mailgun_module.integration_secrets_store = fake_store
            service.upsert_config(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency Name",
                reply_to="",
                enabled=True,
            )

            def _fake_post(url, auth, data, timeout):
                captured["data"] = dict(data)
                return _FakeResponse(ok=True, status_code=200, payload={"id": "abc123", "message": "Queued"})

            mailgun_module.requests.post = _fake_post
            payload = service.send_email(
                to_email="test@example.com",
                subject="Subiect",
                text="Text simplu",
                html="<p>HTML</p>",
            )
            self.assertTrue(payload["ok"])
            self.assertEqual(captured["data"]["html"], "<p>HTML</p>")
        finally:
            mailgun_module.integration_secrets_store = original_store
            mailgun_module.requests.post = original_post

    def test_send_test_success_with_mocked_http(self):
        service = mailgun_module.MailgunService()
        fake_store = _FakeSecretsStore()
        original_store = mailgun_module.integration_secrets_store
        original_post = mailgun_module.requests.post
        captured: dict[str, object] = {}

        try:
            mailgun_module.integration_secrets_store = fake_store
            service.upsert_config(
                api_key="key-super-secret",
                domain="mg.example.com",
                base_url="https://api.mailgun.net",
                from_email="noreply@example.com",
                from_name="Agency Name",
                reply_to="reply@example.com",
                enabled=True,
            )

            def _fake_post(url, auth, data, timeout):
                captured["url"] = url
                captured["auth"] = auth
                captured["data"] = dict(data)
                captured["timeout"] = timeout
                return _FakeResponse(ok=True, status_code=200, payload={"id": "abc123", "message": "Queued"})

            mailgun_module.requests.post = _fake_post
            payload = service.send_test_email(to_email="test@example.com", subject="Subiect", text="Text")
            self.assertTrue(payload["ok"])
            self.assertEqual(captured["url"], "https://api.mailgun.net/v3/mg.example.com/messages")
            self.assertEqual(captured["auth"], ("api", "key-super-secret"))
            self.assertEqual(captured["data"]["to"], "test@example.com")
            self.assertEqual(captured["data"]["h:Reply-To"], "reply@example.com")
            self.assertEqual(captured["timeout"], 10)
        finally:
            mailgun_module.integration_secrets_store = original_store
            mailgun_module.requests.post = original_post


if __name__ == "__main__":
    unittest.main()
