import unittest

from app.services.error_observability import safe_body_snippet, sanitize_payload, sanitize_text


class ErrorObservabilityTests(unittest.TestCase):
    def test_sanitize_text_masks_bearer_and_long_token(self):
        value = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
        sanitized = sanitize_text(value)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", sanitized)
        self.assertIn("Bearer ***", sanitized)

    def test_sanitize_payload_masks_sensitive_keys(self):
        payload = {"access_token": "tok_secret_12345678901234567890", "nested": {"client_secret": "secret-value"}}
        sanitized = sanitize_payload(payload)
        self.assertEqual(sanitized["access_token"], "***")
        self.assertEqual(sanitized["nested"]["client_secret"], "***")

    def test_safe_body_snippet_masks_json_tokens(self):
        snippet = safe_body_snippet('{"error": {"message": "bad"}, "refresh_token": "tok_refresh_12345678901234567890"}')
        self.assertIn('"refresh_token": "***"', snippet)
        self.assertNotIn("tok_refresh_12345678901234567890", snippet)


if __name__ == "__main__":
    unittest.main()
