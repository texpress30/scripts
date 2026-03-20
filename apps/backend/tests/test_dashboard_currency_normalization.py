from datetime import date

from app.services.dashboard import unified_dashboard_service
from app.services import dashboard as dashboard_service_module


def test_aggregate_client_rows_normalizes_money_to_target_currency_and_keeps_non_monetary_metrics():
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    try:
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 5.0, "RON": 1.0, "EUR": 4.0}.get(kwargs.get("currency_code"), 1.0)
        rows = [
            ("google_ads", date(2026, 3, 1), "USD", 100.0, 1000, 100, 10, 50.0, {"src": "usd"}),
            ("meta_ads", date(2026, 3, 1), "RON", 200.0, 2000, 200, 20, 80.0, {"src": "ron"}),
        ]
        platform_totals = unified_dashboard_service._aggregate_client_rows(rows=rows, target_currency="USD")
    finally:
        unified_dashboard_service._get_fx_rate_to_ron = original_rate

    google = platform_totals["google_ads"]
    meta = platform_totals["meta_ads"]

    assert round(float(google["spend"]), 2) == 100.0
    assert round(float(meta["spend"]), 2) == 40.0
    assert round(float(google["conversion_value"]), 2) == 50.0
    assert round(float(meta["conversion_value"]), 2) == 16.0

    assert int(google["impressions"]) == 1000
    assert int(meta["impressions"]) == 2000
    assert int(google["clicks"]) == 100
    assert int(meta["clicks"]) == 200
    assert int(google["conversions"]) == 10
    assert int(meta["conversions"]) == 20


def test_agency_dashboard_test_mode_top_clients_are_sorted_and_displayed_in_ron():
    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_list_clients = dashboard_service_module.client_registry_service.list_clients
    original_get_client_dashboard = unified_dashboard_service.get_client_dashboard
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    try:
        unified_dashboard_service._is_test_mode = lambda: True
        dashboard_service_module.client_registry_service.list_clients = lambda: [
            {"id": 1, "name": "FBM"},
            {"id": 2, "name": "RO Client"},
        ]

        def _client_dashboard(cid: int, **kwargs):
            if int(cid) == 1:
                return {"currency": "USD", "totals": {"spend": 100.0, "impressions": 1000, "clicks": 100, "conversions": 10, "revenue": 200.0}}
            return {"currency": "RON", "totals": {"spend": 300.0, "impressions": 1000, "clicks": 100, "conversions": 10, "revenue": 450.0}}

        unified_dashboard_service.get_client_dashboard = _client_dashboard
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 5.0, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)

        payload = unified_dashboard_service.get_agency_dashboard(start_date=date(2026, 3, 1), end_date=date(2026, 3, 7))
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        dashboard_service_module.client_registry_service.list_clients = original_list_clients
        unified_dashboard_service.get_client_dashboard = original_get_client_dashboard
        unified_dashboard_service._get_fx_rate_to_ron = original_rate

    assert payload["currency"] == "RON"
    assert payload["totals"]["spend"] == 800.0
    assert payload["totals"]["revenue"] == 1450.0
    assert payload["top_clients"][0]["name"] == "FBM"
    assert payload["top_clients"][0]["currency"] == "RON"
    assert payload["top_clients"][0]["spend"] == 500.0
    assert payload["top_clients"][1]["spend"] == 300.0


def test_normalize_money_uses_fallback_fx_rate_when_provider_missing():
    original_get = dashboard_service_module.requests.get
    original_fallback = unified_dashboard_service._fallback_fx_rate_to_ron
    original_cache = dict(unified_dashboard_service._fx_cache)
    try:
        unified_dashboard_service._fx_cache = {}

        def _boom(*args, **kwargs):
            raise RuntimeError("offline")

        dashboard_service_module.requests.get = _boom
        unified_dashboard_service._fallback_fx_rate_to_ron = lambda **kwargs: 4.2

        amount_ron = unified_dashboard_service._normalize_money(amount=10.0, from_currency="USD", to_currency="RON", rate_date=date(2026, 3, 7))
    finally:
        dashboard_service_module.requests.get = original_get
        unified_dashboard_service._fallback_fx_rate_to_ron = original_fallback
        unified_dashboard_service._fx_cache = original_cache

    assert round(amount_ron, 2) == 42.0


def test_meta_ron_to_ron_is_not_double_converted_observed_case_3587_60():
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    try:
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 4.359, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
        rows = [
            ("meta_ads", date(2026, 3, 1), "RON", 3587.60, 1000, 100, 10, 0.0, {"meta_ads": {"account_currency": "RON"}}),
        ]
        platform_totals = unified_dashboard_service._aggregate_client_rows(rows=rows, target_currency="RON")
    finally:
        unified_dashboard_service._get_fx_rate_to_ron = original_rate

    meta = platform_totals["meta_ads"]
    assert round(float(meta["spend"]), 2) == 3587.60


def test_client_dashboard_query_uses_account_daily_membership_and_currency_precedence():
    client_query = unified_dashboard_service._client_reports_query()

    assert "FROM ad_performance_reports apr" in client_query
    assert "JOIN agency_account_client_mappings mapped" in client_query
    assert "mapped.client_id = %s" in client_query
    assert "mapped.created_at::date <= apr.report_date" not in client_query
    assert "'account_daily'" in client_query
    assert "COALESCE(apr.client_id, mapped.client_id)" not in client_query
    assert "apr.extra_metrics -> 'meta_ads' ->> 'account_currency'" in client_query
    assert "apr.extra_metrics -> 'tiktok_ads' ->> 'account_currency'" in client_query
    assert "apr.extra_metrics -> 'google_ads' ->> 'account_currency'" in client_query
    assert "apa.currency_code" in client_query
    assert "client.currency" in client_query
    assert client_query.index("mapped.account_currency") < client_query.index("apa.currency_code")


def test_tiktok_ron_to_ron_is_not_double_converted_observed_case_805_85():
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    try:
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 4.359, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
        rows = [
            ("tiktok_ads", date(2026, 2, 1), "RON", 805.85, 1000, 100, 10, 0.0, {"tiktok_ads": {"account_currency": "RON"}}),
            ("tiktok_ads", date(2026, 3, 11), "RON", 50.40, 100, 10, 1, 0.0, {"tiktok_ads": {"account_currency": "RON"}}),
        ]
        platform_totals = unified_dashboard_service._aggregate_client_rows(rows=rows, target_currency="RON")
    finally:
        unified_dashboard_service._get_fx_rate_to_ron = original_rate

    tiktok = platform_totals["tiktok_ads"]
    assert round(float(tiktok["spend"]), 2) == 856.25



def test_dashboard_spend_matches_media_buying_for_same_client_and_interval():
    from app.services.media_buying_store import MediaBuyingStore

    rows = [
        ("google_ads", date(2026, 3, 11), "RON", 100.0, 1000, 100, 10, 0.0, {}),
        ("meta_ads", date(2026, 3, 11), "RON", 200.0, 2000, 200, 20, 0.0, {}),
        ("tiktok_ads", date(2026, 3, 11), "RON", 50.40, 1500, 150, 15, 0.0, {}),
    ]
    dashboard_platform_totals = unified_dashboard_service._aggregate_client_rows(rows=rows, target_currency="RON")

    store = MediaBuyingStore()
    store._ensure_schema = lambda: None
    store.get_config = lambda **kwargs: {"client_id": 97, "template_type": "lead", "display_currency": "RON"}
    store._resolve_client_template_type = lambda **kwargs: "lead"
    store.list_lead_daily_manual_values = lambda **kwargs: []
    store._list_automated_daily_costs = lambda **kwargs: [
        {"date": date(2026, 3, 11), "platform": "google_ads", "account_currency": "RON", "spend": 100.0},
        {"date": date(2026, 3, 11), "platform": "meta_ads", "account_currency": "RON", "spend": 200.0},
        {"date": date(2026, 3, 11), "platform": "tiktok_ads", "account_currency": "RON", "spend": 50.40},
    ]
    store._normalize_money_to_display_currency = lambda **kwargs: kwargs["amount"]

    media_buying_payload = store.get_lead_table(client_id=97, date_from=date(2026, 3, 11), date_to=date(2026, 3, 11))
    day = media_buying_payload["days"][0]

    assert round(float(day["cost_google"]), 2) == round(float(dashboard_platform_totals["google_ads"]["spend"]), 2)
    assert round(float(day["cost_meta"]), 2) == round(float(dashboard_platform_totals["meta_ads"]["spend"]), 2)
    assert round(float(day["cost_tiktok"]), 2) == round(float(dashboard_platform_totals["tiktok_ads"]["spend"]), 2)


def test_build_spend_by_day_fills_selected_range_and_normalizes_currency():
    original_rate = unified_dashboard_service._get_fx_rate_to_ron
    try:
        unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 5.0, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
        rows = [
            ("google_ads", date(2026, 3, 1), "USD", 10.0, 100, 10, 1, 5.0, {}),
            ("meta_ads", date(2026, 3, 1), "RON", 10.0, 100, 10, 1, 5.0, {}),
            ("tiktok_ads", date(2026, 3, 3), "RON", 12.0, 100, 10, 1, 5.0, {}),
        ]
        spend_by_day = unified_dashboard_service._build_spend_by_day(
            rows=rows,
            target_currency="RON",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 3),
        )
    finally:
        unified_dashboard_service._get_fx_rate_to_ron = original_rate

    assert spend_by_day == [
        {
            "date": "2026-03-01",
            "spend": 60.0,
            "platform_spend": {"google_ads": 50.0, "meta_ads": 10.0, "tiktok_ads": 0.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
        {
            "date": "2026-03-02",
            "spend": 0.0,
            "platform_spend": {"google_ads": 0.0, "meta_ads": 0.0, "tiktok_ads": 0.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
        {
            "date": "2026-03-03",
            "spend": 12.0,
            "platform_spend": {"google_ads": 0.0, "meta_ads": 0.0, "tiktok_ads": 12.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
    ]


def test_get_client_dashboard_returns_spend_by_day_without_breaking_existing_payload():
    decision_payload = {
        "reporting_currency": "RON",
        "reporting_currency_source": "agency_client_currency",
        "mixed_attached_account_currencies": False,
        "attached_account_currency_summary": [{"currency": "RON", "account_count": 1}],
    }
    rows = [
        ("google_ads", date(2026, 3, 1), "RON", 10.0, 100, 10, 1, 20.0, {"google_ads": {"grain": "account_daily"}}),
        ("meta_ads", date(2026, 3, 2), "RON", 25.0, 200, 20, 2, 35.0, {"meta_ads": {"grain": "account_daily"}}),
    ]

    class _FakeCursor:
        def __init__(self):
            self._last_sql = ""

        def execute(self, sql, params=None):
            self._last_sql = str(sql)

        def fetchall(self):
            if "COALESCE(apr.extra_metrics, '{}'::jsonb)" in self._last_sql:
                return rows
            return []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeConn:
        def __init__(self):
            self._cursor = _FakeCursor()

        def cursor(self):
            return self._cursor

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_connect = unified_dashboard_service._connect
    original_reporting = dashboard_service_module.client_registry_service.get_client_reporting_currency_decision
    original_init_schema = dashboard_service_module.performance_reports_store.initialize_schema
    original_sync_summary = unified_dashboard_service._build_dashboard_platform_sync_summary
    try:
        unified_dashboard_service._is_test_mode = lambda: False
        unified_dashboard_service._connect = lambda: _FakeConn()
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: dict(decision_payload)
        dashboard_service_module.performance_reports_store.initialize_schema = lambda: None
        unified_dashboard_service._build_dashboard_platform_sync_summary = lambda **kwargs: {}

        payload = unified_dashboard_service.get_client_dashboard(
            client_id=44,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 3),
        )
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        unified_dashboard_service._connect = original_connect
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        dashboard_service_module.performance_reports_store.initialize_schema = original_init_schema
        unified_dashboard_service._build_dashboard_platform_sync_summary = original_sync_summary

    assert payload["client_id"] == 44
    assert payload["totals"]["spend"] == 35.0
    assert "platforms" in payload
    assert payload["spend_by_day"] == [
        {
            "date": "2026-03-01",
            "spend": 10.0,
            "platform_spend": {"google_ads": 10.0, "meta_ads": 0.0, "tiktok_ads": 0.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
        {
            "date": "2026-03-02",
            "spend": 25.0,
            "platform_spend": {"google_ads": 0.0, "meta_ads": 25.0, "tiktok_ads": 0.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
        {
            "date": "2026-03-03",
            "spend": 0.0,
            "platform_spend": {"google_ads": 0.0, "meta_ads": 0.0, "tiktok_ads": 0.0, "pinterest_ads": 0.0, "snapchat_ads": 0.0},
        },
    ]


def test_get_client_google_ads_account_performance_uses_real_rows_and_currency():
    rows = [
        ("1001", "Google Main RO", "active", date(2026, 3, 1), "RON", 100.0, 220.0, 1000, 120),
        ("1001", "Google Main RO", "active", date(2026, 3, 2), "RON", 50.0, 80.0, 800, 90),
        ("1002", "Google Prospecting", "paused", date(2026, 3, 1), "RON", 20.0, 10.0, 300, 20),
    ]

    class _FakeCursor:
        def execute(self, sql, params=None):
            self._last_sql = str(sql)

        def fetchall(self):
            return rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    original_connect = unified_dashboard_service._connect
    original_reporting = dashboard_service_module.client_registry_service.get_client_reporting_currency_decision
    original_init_schema = dashboard_service_module.performance_reports_store.initialize_schema
    try:
        unified_dashboard_service._connect = lambda: _FakeConn()
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: {
            "reporting_currency": "RON",
            "reporting_currency_source": "agency_client_currency",
            "mixed_attached_account_currencies": False,
            "attached_account_currency_summary": [{"currency": "RON", "account_count": 2}],
        }
        dashboard_service_module.performance_reports_store.initialize_schema = lambda: None
        payload = unified_dashboard_service.get_client_google_ads_account_performance(
            client_id=96,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        dashboard_service_module.performance_reports_store.initialize_schema = original_init_schema

    assert payload["currency"] == "RON"
    assert payload["items"][0]["account_id"] == "1001"
    assert payload["items"][0]["cost"] == 150.0
    assert payload["items"][0]["rev_inf"] == 300.0
    assert payload["items"][0]["roas_inf"] == 2.0
    assert payload["items"][0]["new_visits"] is None
    assert payload["items"][0]["visits"] is None


def test_get_client_platform_account_performance_supports_meta_ads():
    rows = [
        ("meta-1001", "Meta Prospecting", "active", date(2026, 3, 10), "RON", 40.0, 120.0, 500, 45),
    ]

    class _FakeCursor:
        def execute(self, sql, params=None):
            self.last_sql = str(sql)

        def fetchall(self):
            return rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    original_connect = unified_dashboard_service._connect
    original_reporting = dashboard_service_module.client_registry_service.get_client_reporting_currency_decision
    original_init_schema = dashboard_service_module.performance_reports_store.initialize_schema
    try:
        unified_dashboard_service._connect = lambda: _FakeConn()
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: {
            "reporting_currency": "RON",
            "reporting_currency_source": "agency_client_currency",
            "mixed_attached_account_currencies": False,
            "attached_account_currency_summary": [{"currency": "RON", "account_count": 1}],
        }
        dashboard_service_module.performance_reports_store.initialize_schema = lambda: None
        payload = unified_dashboard_service.get_client_platform_account_performance(
            client_id=96,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
            platform="meta_ads",
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        dashboard_service_module.performance_reports_store.initialize_schema = original_init_schema

    assert payload["currency"] == "RON"
    assert payload["items"][0]["account_id"] == "meta-1001"
    assert payload["items"][0]["cost"] == 40.0
    assert payload["items"][0]["rev_inf"] == 120.0


def test_get_client_platform_account_campaign_performance_filters_by_account_and_range():
    rows = [
        ("meta-1001", "Meta Main", "cmp-1", "Campaign 1", "active", date(2026, 3, 10), "RON", 40.0, 120.0, 500, 45),
        ("meta-1001", "Meta Main", "cmp-1", "Campaign 1", "active", date(2026, 3, 11), "RON", 10.0, 30.0, 100, 10),
        ("meta-1001", "Meta Main", "cmp-2", "Campaign 2", "paused", date(2026, 3, 10), "RON", 20.0, 15.0, 200, 15),
    ]

    class _FakeCursor:
        def execute(self, sql, params=None):
            self.sql = str(sql)
            self.params = params

        def fetchall(self):
            return rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    original_connect = unified_dashboard_service._connect
    original_reporting = dashboard_service_module.client_registry_service.get_client_reporting_currency_decision
    original_init_schema = dashboard_service_module.performance_reports_store.initialize_schema
    try:
        unified_dashboard_service._connect = lambda: _FakeConn()
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: {
            "reporting_currency": "RON",
            "reporting_currency_source": "agency_client_currency",
            "mixed_attached_account_currencies": False,
            "attached_account_currency_summary": [{"currency": "RON", "account_count": 1}],
        }
        dashboard_service_module.performance_reports_store.initialize_schema = lambda: None
        payload = unified_dashboard_service.get_client_platform_account_campaign_performance(
            client_id=96,
            platform="meta_ads",
            account_id="meta-1001",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        dashboard_service_module.performance_reports_store.initialize_schema = original_init_schema

    assert payload["account_id"] == "meta-1001"
    assert payload["account_name"] == "Meta Main"
    assert payload["items"][0]["campaign_id"] == "cmp-1"
    assert payload["items"][0]["cost"] == 50.0
    assert payload["items"][0]["rev_inf"] == 150.0
    assert payload["items"][1]["campaign_id"] == "cmp-2"


def test_get_client_platform_account_campaign_performance_meta_normalizes_act_prefix():
    rows = [
        ("123456", "Meta Named Account", "cmp-77", "Prospecting", "paused", date(2026, 3, 10), "RON", 5.0, 20.0, 100, 10),
    ]

    class _FakeCursor:
        def execute(self, sql, params=None):
            self.sql = str(sql)
            self.params = params

        def fetchall(self):
            return rows

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeConn:
        def cursor(self):
            return _FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    original_connect = unified_dashboard_service._connect
    original_reporting = dashboard_service_module.client_registry_service.get_client_reporting_currency_decision
    original_init_schema = dashboard_service_module.performance_reports_store.initialize_schema
    try:
        unified_dashboard_service._connect = lambda: _FakeConn()
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = lambda **kwargs: {
            "reporting_currency": "RON",
            "reporting_currency_source": "agency_client_currency",
            "mixed_attached_account_currencies": False,
            "attached_account_currency_summary": [{"currency": "RON", "account_count": 1}],
        }
        dashboard_service_module.performance_reports_store.initialize_schema = lambda: None
        payload = unified_dashboard_service.get_client_platform_account_campaign_performance(
            client_id=96,
            platform="meta_ads",
            account_id="act_123456",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_service_module.client_registry_service.get_client_reporting_currency_decision = original_reporting
        dashboard_service_module.performance_reports_store.initialize_schema = original_init_schema

    assert payload["account_name"] == "Meta Named Account"
    assert payload["items"][0]["campaign_name"] == "Prospecting"
    assert payload["items"][0]["status"] == "paused"
