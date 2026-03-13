from datetime import date

from app.services import dashboard as dashboard_module
from app.services.dashboard import unified_dashboard_service


class _FakeCursor:
    def __init__(self, mappings, rows):
        self._mappings = mappings
        self._rows = rows
        self._last_sql = ""

    def execute(self, sql, params=None):
        self._last_sql = sql

    def fetchall(self):
        if "FROM agency_account_client_mappings" in self._last_sql and "ORDER BY platform, account_id" in self._last_sql:
            return self._mappings
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_client_dashboard_reconciliation_reports_included_excluded_and_fallbacks():
    mappings = [
        ("google_ads", "123-456-7890", 77, "USD", date(2026, 1, 1)),
        ("meta_ads", "act_55", 77, None, date(2026, 1, 2)),
    ]
    rows = [
        ("google_ads", "123-456-7890", date(2026, 3, 1), 10.0, 100, 10, 1.0, 20.0, "account_daily", "account_daily", "USD", "USD", "USD", "USD", "report_extra_metrics", True),
        ("meta_ads", "act_missing", date(2026, 3, 1), 5.0, 50, 5, 0.0, 2.0, None, "account_daily", None, None, None, "RON", "fallback_ron", False),
        ("tiktok_ads", "tt_9", date(2026, 3, 1), 3.0, 30, 3, 0.0, 1.0, "campaign_daily", "campaign_daily", None, None, "EUR", "EUR", "mapping_account_currency", True),
        ("meta_ads", "act_55", date(2026, 3, 2), 7.0, 70, 7, 2.0, 9.0, None, "account_daily", None, None, None, "RON", "fallback_ron", True),
    ]

    fake_cursor = _FakeCursor(mappings, rows)
    fake_conn = _FakeConn(fake_cursor)

    original_connect = unified_dashboard_service._connect
    original_reporting_decision = dashboard_module.client_registry_service.get_client_reporting_currency_decision
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    original_init_schema = dashboard_module.performance_reports_store.initialize_schema
    try:
        unified_dashboard_service._connect = lambda: fake_conn
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: {
            "reporting_currency": "RON",
            "reporting_currency_source": "agency_client_currency",
            "mixed_attached_account_currencies": False,
            "attached_account_currency_summary": [{"currency": "RON", "account_count": 2}],
        }
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 4.0, "EUR": 5.0, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
        dashboard_module.performance_reports_store.initialize_schema = lambda: None

        payload = unified_dashboard_service.get_client_dashboard_reconciliation(
            client_id=77,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = original_reporting_decision
        unified_dashboard_service._get_fx_rate_to_ron = original_rate
        dashboard_module.performance_reports_store.initialize_schema = original_init_schema

    assert payload["client_id"] == 77
    assert payload["reporting_currency"] == "RON"
    assert payload["reporting_currency_source"] == "agency_client_currency"
    assert payload["mixed_attached_account_currencies"] is False
    assert payload["counts"] == {
        "total_rows_scanned": 4,
        "included_rows": 2,
        "excluded_rows": 2,
        "currency_fallback_rows": 2,
    }

    excluded = payload["excluded_rows"]
    assert len(excluded) == 2
    assert "missing_mapping" in excluded[0]["reasons"]
    assert "currency_resolution_fallback" in excluded[0]["reasons"]
    assert excluded[1]["reasons"] == ["grain_not_account_daily"]

    assert payload["summed_metrics"]["before_conversion"]["raw_db"]["spend"] == 25.0
    assert payload["summed_metrics"]["before_conversion"]["included_dashboard"]["spend"] == 17.0
    assert payload["summed_metrics"]["after_conversion"]["included_dashboard"]["spend"] == 47.0

    included_groups = payload["included_dashboard_totals_by_platform_account_currency"]
    google_group = next(item for item in included_groups if item["platform"] == "google_ads")
    assert google_group["totals_before_conversion"]["spend"] == 10.0
    assert google_group["totals_after_conversion"]["spend"] == 40.0
