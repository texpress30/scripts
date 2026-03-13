from datetime import date

from app.services import dashboard as dashboard_module
from app.services.dashboard import unified_dashboard_service


class _FakeCursor:
    def __init__(self, mappings, recon_rows, dashboard_rows):
        self._mappings = mappings
        self._recon_rows = recon_rows
        self._dashboard_rows = dashboard_rows
        self._last_sql = ""

    def execute(self, sql, params=None):
        self._last_sql = str(sql)

    def fetchall(self):
        sql = self._last_sql
        if "FROM agency_account_client_mappings" in sql and "ORDER BY platform, account_id" in sql:
            return self._mappings
        if "COALESCE(apr.extra_metrics, '{}'::jsonb)" in sql:
            return self._dashboard_rows
        return self._recon_rows

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


def test_dashboard_and_reconciliation_share_reporting_currency_decision_metadata():
    decision_payload = {
        "reporting_currency": "EUR",
        "reporting_currency_source": "agency_client_currency",
        "mixed_attached_account_currencies": True,
        "attached_account_currency_summary": [
            {"currency": "EUR", "account_count": 1},
            {"currency": "RON", "account_count": 1},
        ],
    }

    mappings = [("google_ads", "ga_1", 11, "EUR", date(2026, 1, 1))]
    dashboard_rows = [
        ("google_ads", date(2026, 3, 1), "EUR", 10.0, 100, 10, 1, 20.0, {"google_ads": {}}),
        ("meta_ads", date(2026, 3, 1), "RON", 5.0, 50, 5, 1, 7.0, {"meta_ads": {}}),
    ]
    recon_rows = [
        ("google_ads", "ga_1", date(2026, 3, 1), 10.0, 100, 10, 1.0, 20.0, "account_daily", "account_daily", "EUR", "EUR", "EUR", "EUR", "mapping_account_currency", True),
    ]

    fake_cursor = _FakeCursor(mappings, recon_rows, dashboard_rows)
    fake_conn = _FakeConn(fake_cursor)

    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_reporting = dashboard_module.client_registry_service.get_client_reporting_currency_decision
    original_connect = unified_dashboard_service._connect
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    original_init_schema = dashboard_module.performance_reports_store.initialize_schema
    original_google = dashboard_module.google_ads_service.get_metrics
    original_meta = dashboard_module.meta_ads_service.get_metrics
    original_tiktok = dashboard_module.tiktok_ads_service.get_metrics
    original_pinterest = dashboard_module.pinterest_ads_service.get_metrics
    original_snapchat = dashboard_module.snapchat_ads_service.get_metrics
    try:
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: dict(decision_payload)
        unified_dashboard_service._connect = lambda: fake_conn
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"EUR": 5.0, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
        dashboard_module.performance_reports_store.initialize_schema = lambda: None

        unified_dashboard_service._is_test_mode = lambda: False
        dashboard_payload = unified_dashboard_service.get_client_dashboard(
            client_id=11,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        reconciliation_payload = unified_dashboard_service.get_client_dashboard_reconciliation(
            client_id=11,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        dashboard_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        unified_dashboard_service._connect = original_connect
        unified_dashboard_service._get_fx_rate_to_ron = original_rate
        dashboard_module.performance_reports_store.initialize_schema = original_init_schema
        dashboard_module.google_ads_service.get_metrics = original_google
        dashboard_module.meta_ads_service.get_metrics = original_meta
        dashboard_module.tiktok_ads_service.get_metrics = original_tiktok
        dashboard_module.pinterest_ads_service.get_metrics = original_pinterest
        dashboard_module.snapchat_ads_service.get_metrics = original_snapchat

    assert dashboard_payload["reporting_currency"] == "EUR"
    assert dashboard_payload["reporting_currency_source"] == "agency_client_currency"
    assert dashboard_payload["mixed_attached_account_currencies"] is True

    assert reconciliation_payload["reporting_currency"] == "EUR"
    assert reconciliation_payload["reporting_currency_source"] == "agency_client_currency"
    assert reconciliation_payload["mixed_attached_account_currencies"] is True
