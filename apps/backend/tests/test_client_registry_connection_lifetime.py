import unittest

from app.services.client_registry import ClientRegistryService
from app.services import client_registry as client_registry_module


class _FakeCursor:
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


class _FakeConn:
    def __init__(self, rows):
        self.closed = False
        self._rows = rows

    def cursor(self):
        if self.closed:
            raise RuntimeError("cursor requested on closed connection")
        return _FakeCursor(self._rows)

    def __enter__(self):
        self.closed = False
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class ClientRegistryConnectionLifetimeTests(unittest.TestCase):
    def test_list_platform_accounts_calls_watermarks_with_open_connection(self):
        row = (
            "3986597205",  # account_id
            "Test Account",  # account_name
            11,  # client_id
            "Test Client",  # client name
            "UTC",  # account_timezone
            "USD",  # currency_code
            "active",  # status
            None,  # sync_start_date
            None,  # backfill_completed_through
            None,  # rolling_synced_through
            None,  # last_success_at
            None,  # last_error
            None,  # latest.status
            None,  # latest.job_type
            None,  # latest.started_at
            None,  # latest.finished_at
            None,  # latest.error
            False,  # has_active_sync
            None,  # hist.min_start_date
            None,  # hist.max_end_date
            None,  # roll.max_end_date
            None,  # success.last_success_at
            None,  # recovered_hist.min_start_date
            None,  # recovered_hist.max_end_date
            None,  # recovered_hist.last_success_at
        )
        fake_conn = _FakeConn(rows=[row])
        service = ClientRegistryService()
        service._is_test_mode = lambda: False
        service._connect_or_raise = lambda: fake_conn

        original_watermarks = client_registry_module.list_platform_account_watermarks

        def _watermarks_stub(conn, *, platform, account_ids, grains):
            self.assertFalse(conn.closed)
            self.assertEqual(platform, "google_ads")
            self.assertEqual(account_ids, ["3986597205"])
            self.assertEqual(grains, ["campaign_daily", "ad_group_daily", "ad_daily"])
            return {}

        client_registry_module.list_platform_account_watermarks = _watermarks_stub
        try:
            result = service.list_platform_accounts(platform="google_ads")
        finally:
            client_registry_module.list_platform_account_watermarks = original_watermarks

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["account_id"], "3986597205")
        self.assertEqual(
            set((result[0].get("entity_watermarks") or {}).keys()),
            {"campaign_daily", "ad_group_daily", "ad_daily"},
        )


if __name__ == "__main__":
    unittest.main()
