import unittest

from app.api import clients as clients_api
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, query, params=None):
        return None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _Cursor(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ClientRegistryRecoveredColumnsHotfixTests(unittest.TestCase):
    def setUp(self):
        self.original_is_test_mode = client_registry_service._is_test_mode
        self.original_connect_or_raise = client_registry_service._connect_or_raise
        self.original_get_last_import = client_registry_service.get_last_import_at

        client_registry_service._is_test_mode = lambda: False

    def tearDown(self):
        client_registry_service._is_test_mode = self.original_is_test_mode
        client_registry_service._connect_or_raise = self.original_connect_or_raise
        client_registry_service.get_last_import_at = self.original_get_last_import

    def test_list_platform_accounts_with_recovered_columns_present(self):
        row = (
            "3986597205",
            "Anime Dating",
            11,
            "Client A",
            "Europe/Bucharest",
            "RON",
            "active",
            None,
            None,
            None,
            None,
            None,
            "done",
            "historical_backfill",
            "2026-03-05T10:00:00+00:00",
            "2026-03-05T10:10:00+00:00",
            None,
            False,
            None,
            None,
            None,
            None,
            "2026-01-01",
            "2026-01-10",
            "2026-03-05T10:10:00+00:00",
        )
        client_registry_service._connect_or_raise = lambda: _Conn([row])

        items = client_registry_service.list_platform_accounts(platform="google_ads")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sync_start_date"], "2026-01-01")
        self.assertEqual(items[0]["backfill_completed_through"], "2026-01-10")
        self.assertEqual(items[0]["last_success_at"], "2026-03-05T10:10:00+00:00")

    def test_full_recovery_extends_backfill_completed_through_to_source_end_even_when_explicit_is_smaller(self):
        row = (
            "3986597205",
            "Anime Dating",
            11,
            "Client A",
            "Europe/Bucharest",
            "RON",
            "active",
            "2024-01-09",
            "2024-10-21",
            None,
            "2024-10-21T10:00:00+00:00",
            "old failed chunk",
            "done",
            "historical_backfill",
            "2026-03-05T10:00:00+00:00",
            "2026-03-05T10:10:00+00:00",
            None,
            False,
            None,
            None,
            None,
            "2026-03-05T10:10:00+00:00",
            "2024-01-09",
            "2026-03-03",
            "2026-03-05T10:10:00+00:00",
        )
        client_registry_service._connect_or_raise = lambda: _Conn([row])

        items = client_registry_service.list_platform_accounts(platform="google_ads")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sync_start_date"], "2024-01-09")
        self.assertEqual(items[0]["backfill_completed_through"], "2026-03-03")
        self.assertEqual(items[0]["last_success_at"], "2026-03-05T10:10:00+00:00")
        self.assertIsNone(items[0]["last_error"])

    def test_partial_recovery_does_not_artificially_extend_backfill_completed_through(self):
        row = (
            "3986597205",
            "Anime Dating",
            11,
            "Client A",
            "Europe/Bucharest",
            "RON",
            "inactive",
            "2024-01-09",
            "2024-10-21",
            None,
            "2024-10-21T10:00:00+00:00",
            "still failing",
            "error",
            "historical_backfill",
            "2026-03-05T10:00:00+00:00",
            "2026-03-05T10:10:00+00:00",
            "still failing",
            False,
            None,
            None,
            None,
            "2024-10-21T10:00:00+00:00",
            None,
            None,
            None,
        )
        client_registry_service._connect_or_raise = lambda: _Conn([row])

        items = client_registry_service.list_platform_accounts(platform="google_ads")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["backfill_completed_through"], "2024-10-21")
        self.assertEqual(items[0]["last_error"], "still failing")

    def test_list_platform_accounts_without_recovered_columns_does_not_raise(self):
        row_without_recovered = (
            "3986597205",
            "Anime Dating",
            11,
            "Client A",
            "Europe/Bucharest",
            "RON",
            "disabled",
            None,
            None,
            None,
            None,
            None,
            "error",
            "historical_backfill",
            "2026-03-05T10:00:00+00:00",
            "2026-03-05T10:10:00+00:00",
            "chunk failed",
            True,
            "2026-01-02",
            "2026-01-08",
            None,
            "2026-03-04T10:10:00+00:00",
        )
        client_registry_service._connect_or_raise = lambda: _Conn([row_without_recovered])

        items = client_registry_service.list_platform_accounts(platform="google_ads")

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["sync_start_date"], "2026-01-02")
        self.assertEqual(items[0]["backfill_completed_through"], "2026-01-08")
        self.assertEqual(items[0]["last_error"], "chunk failed")

    def test_clients_google_endpoint_no_500_with_short_rows(self):
        row_without_recovered = (
            "3986597205",
            "Anime Dating",
            11,
            "Client A",
            "Europe/Bucharest",
            "RON",
            "active",
            None,
            None,
            None,
            None,
            None,
            "queued",
            "historical_backfill",
            "2026-03-05T10:00:00+00:00",
            None,
            None,
            True,
            None,
            None,
            None,
            None,
        )
        client_registry_service._connect_or_raise = lambda: _Conn([row_without_recovered])
        client_registry_service.get_last_import_at = lambda *, platform: "2026-03-05T11:00:00+00:00"

        payload = clients_api.list_google_accounts(user=AuthUser(email="owner@example.com", role="agency_admin"))

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["account_id"], "3986597205")


if __name__ == "__main__":
    unittest.main()
