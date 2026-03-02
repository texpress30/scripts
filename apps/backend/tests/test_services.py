import os
from datetime import date, datetime
import unittest
from decimal import Decimal

from fastapi import BackgroundTasks

from app.services.auth import AuthError, AuthUser, create_access_token, decode_access_token, validate_login_credentials
from app.api import google_ads as google_ads_api
from app.api import meta_ads as meta_ads_api
from app.api import tiktok_ads as tiktok_ads_api
from app.api import pinterest_ads as pinterest_ads_api
from app.api import snapchat_ads as snapchat_ads_api
from app.services.ai_assistant import ai_assistant_service
from app.services.insights import insights_service
from app.services.dashboard import unified_dashboard_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service
from app.services.meta_ads import MetaAdsIntegrationError, meta_ads_service
from app.services.google_store import google_snapshot_store
from app.services.meta_store import meta_snapshot_store
from app.services.pinterest_ads import PinterestAdsIntegrationError, pinterest_ads_service
from app.services.pinterest_store import pinterest_snapshot_store
from app.services.pinterest_observability import pinterest_sync_metrics
from app.services.snapchat_ads import SnapchatAdsIntegrationError, snapchat_ads_service
from app.services.snapchat_store import snapchat_snapshot_store
from app.services.snapchat_observability import snapchat_sync_metrics
from app.services.tiktok_ads import TikTokAdsIntegrationError, tiktok_ads_service
from app.services.tiktok_store import tiktok_snapshot_store
from app.services.tiktok_observability import tiktok_sync_metrics
from app.services.creative_workflow import creative_workflow_service
from app.services.notifications import notification_service
from app.services.recommendations import recommendations_service
from app.services.rbac import AuthorizationError, require_action, require_permission
from app.services.rules_engine import rules_engine_service
from app.services.audit import audit_log_service
from app.services.client_registry import client_registry_service
from app.services.performance_reports import performance_reports_store
from app.services.report_metric_catalog import DERIVED_METRICS_IMPLEMENTED, MANUAL_BUSINESS_METRICS_EXCLUDED
from app.services.report_metric_formulas import build_derived_metrics
from app.services.sync_runs_store import sync_runs_store
from app.services.sync_state_store import sync_state_store
from app.services.sync_run_chunks_store import sync_run_chunks_store
from app.services.client_business_inputs_store import client_business_inputs_store
from app.services.client_business_inputs_import_service import (
    import_client_business_inputs,
    normalize_client_business_input_row,
    validate_client_business_input_row,
)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()
        os.environ["APP_ENV"] = "test"
        os.environ["APP_AUTH_SECRET"] = "test-secret"
        os.environ["APP_LOGIN_EMAIL"] = "admin@example.com"
        os.environ["APP_LOGIN_PASSWORD"] = "admin123"
        os.environ["OPENAI_API_KEY"] = "test-openai-key"
        os.environ["GOOGLE_ADS_TOKEN"] = "test-google-token"
        os.environ["META_ACCESS_TOKEN"] = "test-meta-token"
        os.environ["BIGQUERY_PROJECT_ID"] = "test-project"
        google_ads_service._runtime_refresh_token = None

    def tearDown(self):
        google_snapshot_store.clear()
        meta_snapshot_store.clear()
        tiktok_snapshot_store.clear()
        pinterest_snapshot_store.clear()
        snapchat_snapshot_store.clear()
        tiktok_sync_metrics.reset()
        pinterest_sync_metrics.reset()
        snapchat_sync_metrics.reset()
        rules_engine_service._rules.clear()
        rules_engine_service._next_id = 1
        notification_service._events.clear()
        insights_service._items.clear()
        creative_workflow_service.reset()
        audit_log_service._events.clear()
        client_registry_service.clear()
        google_ads_service._runtime_refresh_token = None
        os.environ.clear()
        os.environ.update(self.original_env)

    # Sprint 1 coverage
    def test_token_encode_decode_roundtrip(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        user = decode_access_token(token)
        self.assertEqual(user.email, "owner@example.com")
        self.assertEqual(user.role, "agency_admin")


    def test_login_credentials_validation(self):
        self.assertTrue(validate_login_credentials("admin@example.com", "admin123"))
        self.assertFalse(validate_login_credentials("admin@example.com", "wrong"))

    def test_invalid_token_signature_is_rejected(self):
        token = create_access_token(email="owner@example.com", role="agency_admin")
        tampered = token + "broken"
        with self.assertRaises(AuthError):
            decode_access_token(tampered)

    def test_rbac_permission_validation(self):
        require_permission("agency_admin", "clients:create")
        with self.assertRaises(AuthorizationError):
            require_permission("client_viewer", "clients:create")

    def test_rbac_dashboard_view_allowed_for_agency_scope(self):
        require_action("agency_admin", action="dashboard:view", scope="agency")

    def test_rbac_action_scope_validation(self):
        require_action("agency_admin", action="clients:list", scope="agency")
        with self.assertRaises(AuthorizationError):
            require_action("agency_admin", action="clients:list", scope="subaccount")
        with self.assertRaises(AuthorizationError):
            require_action("client_viewer", action="rules:create", scope="subaccount")


    def test_client_registry_updates_account_currency_per_mapping(self):
        created = client_registry_service.create_client(name="Currency Client", owner_email="owner@example.com")
        client_registry_service.upsert_platform_accounts(
            platform="google_ads",
            accounts=[{"id": "1234567890", "name": "Currency Account"}],
        )
        client_registry_service.attach_platform_account_to_client(
            platform="google_ads",
            client_id=int(created["id"]),
            account_id="1234567890",
        )

        updated = client_registry_service.update_client_profile_by_display_id(
            display_id=int(created["display_id"]),
            platform="google_ads",
            account_id="1234567890",
            currency="ron",
        )

        self.assertIsNotNone(updated)
        assert updated is not None
        google_platform = next(item for item in updated["platforms"] if item["platform"] == "google_ads")
        self.assertEqual(google_platform["accounts"][0]["currency"], "RON")


    def test_client_registry_preferred_currency_uses_account_mapping_currency(self):
        created = client_registry_service.create_client(name="Currency Pref Client", owner_email="owner@example.com")
        client_registry_service.upsert_platform_accounts(
            platform="google_ads",
            accounts=[{"id": "7777777777", "name": "Google Currency Ref"}],
        )
        client_registry_service.attach_platform_account_to_client(
            platform="google_ads",
            client_id=int(created["id"]),
            account_id="7777777777",
        )
        client_registry_service.update_client_profile_by_display_id(
            display_id=int(created["display_id"]),
            platform="google_ads",
            account_id="7777777777",
            currency="eur",
        )

        preferred_currency = client_registry_service.get_preferred_currency_for_client(client_id=int(created["id"]))
        self.assertEqual(preferred_currency, "EUR")

    def test_client_registry_update_platform_account_operational_metadata_updates_existing_row(self):
        client_registry_service._operational_metadata_schema_initialized = False
        state: dict[tuple[str, str], dict[str, object]] = {
            ("google_ads", "1234567890"): {
                "platform": "google_ads",
                "account_id": "1234567890",
                "status": "queued",
                "currency_code": "USD",
                "account_timezone": "UTC",
                "sync_start_date": None,
                "last_synced_at": None,
            }
        }

        class _FakeCursor:
            _row: tuple[object, ...] | None
            rowcount: int

            def __init__(self):
                self._row = None
                self.rowcount = 0

            def execute(self, query, params=None):
                sql = str(query)
                self.rowcount = 0

                if "SELECT to_regclass('public.agency_platform_accounts')" in sql:
                    self._row = ("agency_platform_accounts",)
                    return

                if "FROM information_schema.columns" in sql and "agency_platform_accounts" in sql:
                    self._row = (5,)
                    return

                if "UPDATE agency_platform_accounts" in sql and "WHERE platform = %s AND account_id = %s" in sql:
                    platform = str(params[-2])
                    account_id = str(params[-1])
                    record = state.get((platform, account_id))
                    if record is None:
                        self.rowcount = 0
                        return

                    assignments = str(sql).split("SET", 1)[1].split("WHERE", 1)[0]
                    column_names = [part.strip().split("=", 1)[0].strip() for part in assignments.split(",") if "=" in part]
                    values = list(params[:-2])
                    for column_name, value in zip(column_names, values):
                        record[column_name] = value
                    self.rowcount = 1
                    return

                if "SELECT platform, account_id, status, currency_code, account_timezone, sync_start_date, last_synced_at" in sql:
                    platform = str(params[0])
                    account_id = str(params[1])
                    record = state.get((platform, account_id))
                    if record is None:
                        self._row = None
                    else:
                        self._row = (
                            record["platform"],
                            record["account_id"],
                            record["status"],
                            record["currency_code"],
                            record["account_timezone"],
                            record["sync_start_date"],
                            record["last_synced_at"],
                        )
                    return

                raise AssertionError(f"Unexpected SQL: {sql}")

            def fetchone(self):
                return self._row

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original_is_test_mode = client_registry_service._is_test_mode
        original_connect = client_registry_service._connect_or_raise
        try:
            client_registry_service._is_test_mode = lambda: False
            client_registry_service._connect_or_raise = lambda: _FakeConn()

            updated_full = client_registry_service.update_platform_account_operational_metadata(
                platform="google_ads",
                account_id="1234567890",
                status="running",
                currency_code="RON",
                account_timezone="Europe/Bucharest",
                sync_start_date=date(2026, 1, 1),
                last_synced_at=datetime.fromisoformat("2026-03-01T00:00:01+00:00"),
            )
            updated_subset = client_registry_service.update_platform_account_operational_metadata(
                platform="google_ads",
                account_id="1234567890",
                status="done",
            )
            missing = client_registry_service.update_platform_account_operational_metadata(
                platform="google_ads",
                account_id="does-not-exist",
                status="done",
            )
        finally:
            client_registry_service._is_test_mode = original_is_test_mode
            client_registry_service._connect_or_raise = original_connect
            client_registry_service._operational_metadata_schema_initialized = False

        self.assertIsNotNone(updated_full)
        assert updated_full is not None
        self.assertEqual(updated_full.get("status"), "running")
        self.assertEqual(updated_full.get("currency_code"), "RON")
        self.assertEqual(updated_full.get("account_timezone"), "Europe/Bucharest")
        self.assertEqual(updated_full.get("sync_start_date"), "2026-01-01")
        self.assertEqual(updated_full.get("last_synced_at"), "2026-03-01 00:00:01+00:00")

        self.assertIsNotNone(updated_subset)
        assert updated_subset is not None
        self.assertEqual(updated_subset.get("status"), "done")
        self.assertEqual(updated_subset.get("currency_code"), "RON")
        self.assertEqual(updated_subset.get("account_timezone"), "Europe/Bucharest")
        self.assertEqual(updated_subset.get("sync_start_date"), "2026-01-01")
        self.assertEqual(updated_subset.get("last_synced_at"), "2026-03-01 00:00:01+00:00")

        self.assertIsNone(missing)

    def test_client_registry_operational_metadata_schema_missing_raises_clear_error(self):
        client_registry_service._operational_metadata_schema_initialized = False

        class _FakeCursor:
            def execute(self, query, params=None):
                return None

            def fetchone(self):
                return (None,)

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

        original_is_test_mode = client_registry_service._is_test_mode
        original_connect = client_registry_service._connect_or_raise
        try:
            client_registry_service._is_test_mode = lambda: False
            client_registry_service._connect_or_raise = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                client_registry_service.update_platform_account_operational_metadata(
                    platform="google_ads",
                    account_id="1234567890",
                    status="running",
                )
        finally:
            client_registry_service._is_test_mode = original_is_test_mode
            client_registry_service._connect_or_raise = original_connect
            client_registry_service._operational_metadata_schema_initialized = False

        self.assertIn(
            "Database schema for agency_platform_accounts operational metadata is not ready; run DB migrations",
            str(ctx.exception),
        )

    # Sprint 2 coverage (Google)
    def test_google_ads_status_pending_when_placeholder(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "pending")

    def test_google_ads_status_connected_when_token_is_real(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "real-token"
        status = google_ads_service.integration_status()
        self.assertEqual(status["status"], "connected")

    def test_google_ads_sync_fails_with_placeholder_token(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "your_google_ads_token"
        with self.assertRaises(GoogleAdsIntegrationError):
            google_ads_service.sync_client(client_id=1)



    def test_google_ads_sync_uses_production_daily_metrics_when_mode_enabled(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "1234567890"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_CUSTOMER_IDS_CSV"] = "1111111111,2222222222"

        original_fetch = google_ads_service._fetch_production_daily_metrics
        original_persist = google_ads_service._persist_performance_report
        persisted_report_dates: list[str] = []
        try:
            google_ads_service._fetch_production_daily_metrics = lambda customer_id, days=30: {
                "rows": [
                    {"report_date": "2026-02-27", "spend": 100.0, "impressions": 1000, "clicks": 100, "conversions": 0, "revenue": 0.0},
                    {"report_date": "2026-02-28", "spend": 200.5, "impressions": 11000, "clicks": 430, "conversions": 0, "revenue": 0.0},
                ]
            }

            def fake_persist(*, snapshot, client_id):
                persisted_report_dates.append(str(snapshot.get("report_date") or ""))
                return 1

            google_ads_service._persist_performance_report = fake_persist
            snapshot = google_ads_service.sync_client(client_id=2)
        finally:
            google_ads_service._fetch_production_daily_metrics = original_fetch
            google_ads_service._persist_performance_report = original_persist

        self.assertEqual(snapshot["google_customer_id"], "2222222222")
        self.assertEqual(snapshot["spend"], 300.5)
        self.assertEqual(snapshot["impressions"], 12000)
        self.assertEqual(snapshot["clicks"], 530)
        self.assertEqual(snapshot["conversions"], 0)
        self.assertEqual(snapshot["revenue"], 0.0)
        self.assertEqual(sorted(persisted_report_dates), ["2026-02-27", "2026-02-28"])


    def test_google_ads_sync_aggregates_all_mapped_accounts_for_client(self):
        original_ids = google_ads_service.get_recommended_customer_ids_for_client
        original_persist = google_ads_service._persist_performance_report
        persisted: list[str] = []
        try:
            google_ads_service.get_recommended_customer_ids_for_client = lambda client_id: ["1111111111", "2222222222"]

            def fake_persist(*, snapshot, client_id):
                persisted.append(str(snapshot.get("google_customer_id") or ""))
                return 1

            google_ads_service._persist_performance_report = fake_persist
            snapshot = google_ads_service.sync_client(client_id=2)
        finally:
            google_ads_service.get_recommended_customer_ids_for_client = original_ids
            google_ads_service._persist_performance_report = original_persist

        self.assertEqual(snapshot["synced_customers_count"], 2)
        self.assertEqual(snapshot["spend"], round((100 + 2 * 17) * 2, 2))
        self.assertEqual(snapshot["google_customer_id"], "1111111111")
        self.assertEqual(sorted(persisted), ["1111111111", "2222222222"])

    def test_google_ads_sync_wraps_unexpected_errors_with_customer_context(self):
        original_ids = google_ads_service.get_recommended_customer_ids_for_client
        original_persist = google_ads_service._persist_performance_report
        try:
            google_ads_service.get_recommended_customer_ids_for_client = lambda client_id: ["1111111111"]

            def fake_persist(*, snapshot, client_id):
                raise RuntimeError("db write failed")

            google_ads_service._persist_performance_report = fake_persist
            with self.assertRaises(GoogleAdsIntegrationError) as ctx:
                google_ads_service.sync_client(client_id=2)
        finally:
            google_ads_service.get_recommended_customer_ids_for_client = original_ids
            google_ads_service._persist_performance_report = original_persist

        self.assertIn("Google Ads sync failed for customer", str(ctx.exception))
        self.assertIn("db write failed", str(ctx.exception))

    def test_google_ads_fetch_daily_metrics_uses_between_clause_for_explicit_range(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "1234567890"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"

        original_access_token = google_ads_service._access_token_from_refresh
        original_required_manager = google_ads_service._required_manager_customer_id
        original_fetch_rows = google_ads_service._fetch_gaql_daily_rows
        captured_queries: list[str] = []
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"
            google_ads_service._required_manager_customer_id = lambda: "1234567890"

            def fake_fetch_rows(*, customer_id, query, login_customer_id, access_token):
                captured_queries.append(query)
                return {"rows": [], "gaql_rows_fetched": 0}

            google_ads_service._fetch_gaql_daily_rows = fake_fetch_rows
            payload = google_ads_service._fetch_production_daily_metrics(
                customer_id="1111111111",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                days=31,
            )
        finally:
            google_ads_service._access_token_from_refresh = original_access_token
            google_ads_service._required_manager_customer_id = original_required_manager
            google_ads_service._fetch_gaql_daily_rows = original_fetch_rows

        self.assertEqual(len(captured_queries), 2)
        self.assertIn("segments.date BETWEEN '2026-01-01' AND '2026-01-31'", captured_queries[0])
        self.assertIn("segments.date BETWEEN '2026-01-01' AND '2026-01-31'", captured_queries[1])
        self.assertIn("2026-01-01..2026-01-31", str(payload.get("zero_data_message") or ""))

    def test_google_ads_list_accessible_customers_uses_manager_search_stream(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "3908678909"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        original_token = google_ads_service._access_token_from_refresh
        original_http = google_ads_service._http_json
        original_preflight = google_ads_service._list_accessible_customers_via_http
        calls: list[tuple[str, str]] = []
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"

            captured_headers: dict[str, str] = {}

            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                calls.append((method, url))
                if isinstance(headers, dict):
                    captured_headers.update({str(k): str(v) for k, v in headers.items()})
                return [{"results": [{"customerClient": {"id": "1111111111"}}, {"customerClient": {"id": "2222222222"}}]}]

            google_ads_service._list_accessible_customers_via_http = lambda **kwargs: ["3908678909", "1111111111"]
            google_ads_service._http_json = fake_http_json
            result = google_ads_service.list_accessible_customers()
        finally:
            google_ads_service._access_token_from_refresh = original_token
            google_ads_service._http_json = original_http
            google_ads_service._list_accessible_customers_via_http = original_preflight

        self.assertEqual(result, ["3908678909", "1111111111", "2222222222"])
        self.assertEqual(calls[0][0], "POST")
        self.assertIn("/v23/customers/3908678909/googleAds:searchStream", calls[0][1])
        self.assertEqual(captured_headers.get("login-customer-id"), "3908678909")
        self.assertEqual(captured_headers.get("developer-token"), "dev-token-123456")

    def test_google_ads_discovery_falls_back_to_search_when_searchstream_404(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "3908678909"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        original_token = google_ads_service._access_token_from_refresh
        original_http = google_ads_service._http_json
        original_preflight = google_ads_service._list_accessible_customers_via_http
        calls: list[str] = []
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"
            google_ads_service._list_accessible_customers_via_http = lambda **kwargs: ["3908678909", "4444444444"]

            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                calls.append(url)
                if "googleAds:searchStream" in url:
                    raise GoogleAdsIntegrationError("Google Ads HTTP request failed: method=POST url=%s status=404 reason=Not Found response=..." % url)
                return {"results": [{"customerClient": {"id": "4444444444"}}]}

            google_ads_service._http_json = fake_http_json
            result = google_ads_service.list_accessible_customers()
        finally:
            google_ads_service._access_token_from_refresh = original_token
            google_ads_service._http_json = original_http
            google_ads_service._list_accessible_customers_via_http = original_preflight

        self.assertTrue(any("googleAds:searchStream" in call for call in calls))
        self.assertTrue(any("googleAds:search" in call for call in calls))
        self.assertEqual(result, ["3908678909", "4444444444"])

    def test_google_ads_list_accessible_customers_uses_single_configured_version(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "3908678909"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        original_token = google_ads_service._access_token_from_refresh
        original_http = google_ads_service._http_json
        original_preflight = google_ads_service._list_accessible_customers_via_http
        calls: list[str] = []
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"
            google_ads_service._list_accessible_customers_via_http = lambda **kwargs: ["3908678909", "3333333333"]

            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                calls.append(url)
                return [{"results": [{"customerClient": {"id": "3333333333"}}]}]

            google_ads_service._http_json = fake_http_json
            result = google_ads_service.list_accessible_customers()
        finally:
            google_ads_service._access_token_from_refresh = original_token
            google_ads_service._http_json = original_http
            google_ads_service._list_accessible_customers_via_http = original_preflight

        self.assertTrue(all("/v23/" in call for call in calls))
        self.assertEqual(result, ["3908678909", "3333333333"])

    def test_google_ads_list_accessible_customers_fails_when_service_accessible_empty(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "3908678909"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        original_token = google_ads_service._access_token_from_refresh
        original_preflight = google_ads_service._list_accessible_customers_via_http
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"
            google_ads_service._list_accessible_customers_via_http = lambda **kwargs: []
            with self.assertRaises(GoogleAdsIntegrationError):
                google_ads_service.list_accessible_customers()
        finally:
            google_ads_service._access_token_from_refresh = original_token
            google_ads_service._list_accessible_customers_via_http = original_preflight

    def test_google_ads_api_version_normalizes_numeric_input(self):
        os.environ["GOOGLE_ADS_API_VERSION"] = "23"
        self.assertEqual(google_ads_service._google_api_version(), "v23")

    def test_google_ads_list_accessible_customers_http_preflight_uses_get_and_required_headers(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"

        original_http = google_ads_service._http_json
        captured: dict[str, object] = {}
        try:
            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                captured["method"] = method
                captured["url"] = url
                captured["payload"] = payload
                captured["headers"] = headers or {}
                return {"resourceNames": ["customers/3986597205"]}

            google_ads_service._http_json = fake_http_json
            result = google_ads_service._list_accessible_customers_via_http(access_token="ya29.token")
        finally:
            google_ads_service._http_json = original_http

        self.assertEqual(captured.get("method"), "GET")
        self.assertEqual(captured.get("url"), "https://googleads.googleapis.com/v23/customers:listAccessibleCustomers")
        self.assertIsNone(captured.get("payload"))
        headers = captured.get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer ya29.token")
        self.assertEqual(headers.get("developer-token"), "dev-token-123456")
        self.assertFalse("login-customer-id" in headers)
        self.assertEqual(result, ["3986597205"])

    def test_google_ads_sdk_client_requires_refresh_token(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = ""

        original_runtime = google_ads_service._runtime_refresh_token
        google_ads_service._runtime_refresh_token = None
        try:
            with self.assertRaises(GoogleAdsIntegrationError):
                google_ads_service._google_ads_client()
        finally:
            google_ads_service._runtime_refresh_token = original_runtime

    def test_google_ads_exchange_discovers_accounts_after_token_exchange(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"

        state = "test-oauth-state"
        google_ads_service._oauth_state_cache.add(state)

        original_http = google_ads_service._http_json
        original_list = google_ads_service.list_accessible_customers
        captured: dict[str, object] = {}
        try:
            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                return {"refresh_token": "refresh-from-exchange"}

            def fake_list_accessible_customers():
                captured["called"] = True
                return ["3986597205", "3578697670"]

            google_ads_service._http_json = fake_http_json
            google_ads_service.list_accessible_customers = fake_list_accessible_customers

            response = google_ads_service.exchange_oauth_code(code="auth-code", state=state)
        finally:
            google_ads_service._http_json = original_http
            google_ads_service.list_accessible_customers = original_list

        self.assertTrue(bool(captured.get("called")))
        self.assertEqual(response["accessible_customers"], ["3986597205", "3578697670"])

    def test_google_ads_sdk_client_config_uses_refresh_and_developer_token(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        module = __import__("app.services.google_ads", fromlist=["GoogleAdsClient"])
        original_client = module.GoogleAdsClient

        captured: dict[str, object] = {}

        class FakeGoogleAdsClient:
            @staticmethod
            def load_from_dict(config, version=None):
                captured["config"] = config
                captured["version"] = version
                return object()

        try:
            module.GoogleAdsClient = FakeGoogleAdsClient
            google_ads_service._google_ads_client()
        finally:
            module.GoogleAdsClient = original_client

        self.assertEqual(str(captured["version"]), "v23")
        config = captured["config"]
        self.assertEqual(config["developer_token"], "dev-token-123456")
        self.assertEqual(config["oauth2_refresh_token"], "refresh-token")

    def test_google_ads_fetch_production_metrics_uses_manager_login_customer_id(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = "client-id"
        os.environ["GOOGLE_ADS_CLIENT_SECRET"] = "client-secret"
        os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"] = "dev-token-123456"
        os.environ["GOOGLE_ADS_REDIRECT_URI"] = "https://app.example.com/agency/integrations/google/callback"
        os.environ["GOOGLE_ADS_REFRESH_TOKEN"] = "refresh-token"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "398-659-7205"
        os.environ["GOOGLE_ADS_API_VERSION"] = "v23"

        original_token = google_ads_service._access_token_from_refresh
        original_http = google_ads_service._http_json
        captured_headers: dict[str, str] = {}
        try:
            google_ads_service._access_token_from_refresh = lambda: "ya29.token"

            def fake_http_json(*, method: str, url: str, payload=None, headers=None):
                if isinstance(headers, dict):
                    captured_headers.update({str(k): str(v) for k, v in headers.items()})
                return [{"results": [{"metrics": {"costMicros": 1000000, "impressions": 10, "clicks": 1, "conversions": 1, "conversionsValue": 5}}]}]

            google_ads_service._http_json = fake_http_json
            result = google_ads_service._fetch_production_metrics(customer_id="357-869-7670")
        finally:
            google_ads_service._access_token_from_refresh = original_token
            google_ads_service._http_json = original_http

        self.assertEqual(captured_headers.get("login-customer-id"), "3986597205")
        self.assertEqual(captured_headers.get("developer-token"), "dev-token-123456")
        self.assertEqual(result["google_customer_id"], "3578697670")

    def test_google_ads_diagnostics_flags_invalid_manager_id(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "123-45"
        diagnostics = google_ads_service.production_diagnostics()
        self.assertFalse(bool(diagnostics["manager_customer_id_valid"]))
        self.assertTrue(any("MANAGER" in msg for msg in diagnostics["warnings"]))

    def test_google_ads_diagnostics_warns_when_manager_id_contains_dashes(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_MANAGER_CUSTOMER_ID"] = "123-456-7890"
        diagnostics = google_ads_service.production_diagnostics()
        self.assertTrue(bool(diagnostics["manager_customer_id_valid"]))
        self.assertTrue(bool(diagnostics["manager_customer_id_has_dashes"]))
        self.assertTrue(any("without dashes" in msg for msg in diagnostics["warnings"]))

    def test_google_ads_oauth_url_requires_production_credentials(self):
        os.environ["GOOGLE_ADS_MODE"] = "production"
        os.environ["GOOGLE_ADS_CLIENT_ID"] = ""
        with self.assertRaises(GoogleAdsIntegrationError):
            google_ads_service.build_oauth_authorize_url()

    def test_tiktok_ads_sync_fails_when_feature_flag_disabled(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "0"
        with self.assertRaises(TikTokAdsIntegrationError):
            tiktok_ads_service.sync_client(client_id=2)

    def test_tiktok_ads_sync_persists_snapshot(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"

        snapshot = tiktok_ads_service.sync_client(client_id=9)
        metrics = tiktok_ads_service.get_metrics(client_id=9)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(metrics["platform"], "tiktok_ads")
        self.assertTrue(metrics["is_synced"])
        self.assertGreater(float(metrics["spend"]), 0.0)


    def test_tiktok_ads_retry_succeeds_after_transient_failures(self):
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["TIKTOK_SYNC_RETRY_ATTEMPTS"] = "3"
        os.environ["TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES"] = "2"

        snapshot = tiktok_ads_service.sync_client(client_id=10)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["attempts"], 3)



    def test_pinterest_ads_sync_fails_when_feature_flag_disabled(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "0"
        with self.assertRaises(PinterestAdsIntegrationError):
            pinterest_ads_service.sync_client(client_id=2)

    def test_pinterest_ads_sync_persists_snapshot_when_feature_flag_enabled(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        snapshot = pinterest_ads_service.sync_client(client_id=2)
        metrics = pinterest_ads_service.get_metrics(client_id=2)
        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["platform"], "pinterest_ads")
        self.assertEqual(snapshot["attempts"], 1)
        self.assertTrue(metrics["is_synced"])

    def test_pinterest_ads_retry_succeeds_after_transient_failures(self):
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        os.environ["PINTEREST_SYNC_RETRY_ATTEMPTS"] = "3"
        os.environ["PINTEREST_SYNC_FORCE_TRANSIENT_FAILURES"] = "2"

        snapshot = pinterest_ads_service.sync_client(client_id=3)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["attempts"], 3)

    def test_snapchat_ads_sync_fails_when_feature_flag_disabled(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "0"
        with self.assertRaises(SnapchatAdsIntegrationError):
            snapchat_ads_service.sync_client(client_id=2)

    def test_snapchat_ads_sync_persists_snapshot_when_feature_flag_enabled(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"
        snapshot = snapchat_ads_service.sync_client(client_id=2)
        metrics = snapchat_ads_service.get_metrics(client_id=2)
        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["platform"], "snapchat_ads")
        self.assertEqual(snapshot["attempts"], 1)
        self.assertTrue(metrics["is_synced"])

    def test_snapchat_ads_retry_succeeds_after_transient_failures(self):
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"
        os.environ["SNAPCHAT_SYNC_RETRY_ATTEMPTS"] = "3"
        os.environ["SNAPCHAT_SYNC_FORCE_TRANSIENT_FAILURES"] = "2"

        snapshot = snapchat_ads_service.sync_client(client_id=3)

        self.assertEqual(snapshot["status"], "success")
        self.assertEqual(snapshot["attempts"], 3)


    def test_dashboard_numeric_coercion_supports_decimal(self):
        self.assertEqual(unified_dashboard_service._normalize_platform_metrics(
            "google_ads",
            {
                "spend": Decimal("988.45"),
                "impressions": Decimal("4363"),
                "clicks": Decimal("376"),
                "conversions": Decimal("0"),
                "revenue": Decimal("0"),
            },
            client_id=95,
        )["spend"], 988.45)

        metrics = unified_dashboard_service._normalize_platform_metrics(
            "google_ads",
            {
                "spend": Decimal("988.45"),
                "impressions": Decimal("4363"),
                "clicks": Decimal("376"),
                "conversions": Decimal("0"),
                "revenue": Decimal("0"),
            },
            client_id=95,
        )

        self.assertEqual(metrics["impressions"], 4363)
        self.assertEqual(metrics["clicks"], 376)



    def test_google_fetch_gaql_daily_rows_maps_conversions_and_conversion_value(self):
        original_http_json = google_ads_service._http_json
        try:
            google_ads_service._http_json = lambda **kwargs: [
                {
                    "results": [
                        {
                            "segments": {"date": "2026-03-01"},
                            "metrics": {
                                "costMicros": 1500000,
                                "impressions": 100,
                                "clicks": 10,
                                "conversions": 2.5,
                                "conversionsValue": 33.75,
                            },
                        },
                        {
                            "segments": {"date": "2026-03-01"},
                            "metrics": {
                                "costMicros": 500000,
                                "impressions": 40,
                                "clicks": 3,
                                "conversions": 1.0,
                                "conversionsValue": 11.25,
                            },
                        },
                    ]
                }
            ]
            payload = google_ads_service._fetch_gaql_daily_rows(
                customer_id="1234567890",
                query="SELECT ...",
                login_customer_id="1234567890",
                access_token="token",
            )
        finally:
            google_ads_service._http_json = original_http_json

        rows = payload["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(float(rows[0]["conversions"]), 3.5)
        self.assertEqual(float(rows[0]["revenue"]), 45.0)
        self.assertEqual(int(rows[0]["extra_metrics"]["google_ads"]["cost_micros"]), 2000000)


    def test_report_formula_common_metrics_return_expected_values(self):
        derived = build_derived_metrics(
            platform="google_ads",
            spend=100.0,
            impressions=10000,
            clicks=250,
            conversions=10,
            conversion_value=400.0,
            extra_metrics={
                "google_ads": {
                    "search_spend": 60.0,
                    "search_clicks": 150,
                    "search_impressions": 6000,
                    "pmax_spend": 40.0,
                    "pmax_clicks": 100,
                    "pmax_impressions": 4000,
                }
            },
        )
        self.assertEqual(derived["ctr"], 0.025)
        self.assertEqual(derived["cpc"], 0.4)
        self.assertEqual(derived["cpm"], 10.0)
        self.assertEqual(derived["cpa"], 10.0)
        self.assertEqual(derived["roas"], 4.0)
        self.assertEqual(derived["cost_vs_revenue"], 0.25)
        self.assertEqual(derived["cpc_search"], 0.4)
        self.assertEqual(derived["cpc_pmax"], 0.4)
        self.assertEqual(derived["cpm_search"], 10.0)
        self.assertEqual(derived["cpm_pmax"], 10.0)

    def test_report_formula_meta_tiktok_and_zero_denominator_return_none(self):
        meta_derived = build_derived_metrics(
            platform="meta_ads",
            spend=120.0,
            impressions=0,
            clicks=0,
            conversions=0,
            conversion_value=0,
            extra_metrics={
                "meta_ads": {
                    "landing_page_views": 30,
                    "outbound_clicks": 60,
                    "purchases": 3,
                    "purchase_value": 450.0,
                }
            },
        )
        self.assertEqual(meta_derived["lp_view_rate"], 0.5)
        self.assertEqual(meta_derived["cp_landing_page_view"], 4.0)
        self.assertEqual(meta_derived["aov"], 150.0)

        tiktok_derived = build_derived_metrics(
            platform="tiktok_ads",
            spend=90.0,
            impressions=0,
            clicks=0,
            conversions=0,
            conversion_value=0,
            extra_metrics={
                "tiktok_ads": {
                    "landing_page_views": 0,
                    "destination_clicks": 0,
                }
            },
        )
        self.assertIsNone(tiktok_derived["lp_view_rate"])
        self.assertIsNone(tiktok_derived["cp_landing_page_view"])
        self.assertIsNone(tiktok_derived["aov"])

    def test_report_metric_catalog_keeps_manual_business_metrics_out(self):
        self.assertIn("ctr", DERIVED_METRICS_IMPLEMENTED)
        self.assertIn("cp_landing_page_view", DERIVED_METRICS_IMPLEMENTED)
        self.assertIn("applicants", MANUAL_BUSINESS_METRICS_EXCLUDED)
        self.assertIn("gross_profit", MANUAL_BUSINESS_METRICS_EXCLUDED)

    def test_platform_metrics_include_extra_and_derived_metrics_additively(self):
        metrics = unified_dashboard_service._normalize_platform_metrics(
            "meta_ads",
            {
                "client_id": 44,
                "spend": 100.0,
                "impressions": 1000,
                "clicks": 50,
                "conversions": 5,
                "conversion_value": 250.0,
                "extra_metrics": {
                    "meta_ads": {
                        "landing_page_views": 25,
                        "outbound_clicks": 50,
                        "purchases": 2,
                        "purchase_value": 300.0,
                    }
                },
            },
            44,
        )

        self.assertEqual(metrics["conversions"], 5.0)
        self.assertEqual(metrics["conversion_value"], 250.0)
        self.assertEqual(metrics["extra_metrics"]["meta_ads"]["landing_page_views"], 25)
        self.assertIn("derived_metrics", metrics)
        self.assertEqual(metrics["derived_metrics"]["lp_view_rate"], 0.5)
        self.assertEqual(metrics["derived_metrics"]["cp_landing_page_view"], 4.0)

    def test_performance_reports_dedup_query_targets_daily_duplicate_keys(self):
        query = performance_reports_store._deduplicate_reports_query()

        self.assertIn("PARTITION BY report_date, platform, customer_id", query)
        self.assertIn("DELETE FROM ad_performance_reports", query)
        self.assertIn("ranked.rn > 1", query)

    def test_performance_reports_upsert_uses_canonical_key_and_updates_client_id_payload(self):
        performance_reports_store._memory_rows.clear()

        performance_reports_store.write_daily_report(
            report_date=date(2026, 2, 28),
            platform="google_ads",
            customer_id="1111111111",
            client_id=10,
            spend=100.0,
            impressions=1000,
            clicks=100,
            conversions=10.0,
            conversion_value=50.0,
        )

        performance_reports_store.write_daily_report(
            report_date=date(2026, 2, 28),
            platform="google_ads",
            customer_id="1111111111",
            client_id=20,
            spend=200.0,
            impressions=2000,
            clicks=200,
            conversions=20.0,
            conversion_value=150.0,
        )

        self.assertEqual(len(performance_reports_store._memory_rows), 1)
        row = performance_reports_store._memory_rows[0]
        self.assertEqual(row["client_id"], 20)
        self.assertEqual(float(row["spend"]), 200.0)
        self.assertEqual(int(row["impressions"]), 2000)
        self.assertEqual(row["extra_metrics"], {})


    def test_performance_reports_upsert_overwrites_extra_metrics_on_conflict(self):
        performance_reports_store._memory_rows.clear()

        performance_reports_store.write_daily_report(
            report_date=date(2026, 3, 1),
            platform="meta_ads",
            customer_id="client-44",
            client_id=44,
            spend=120.0,
            impressions=1500,
            clicks=90,
            conversions=11.0,
            conversion_value=260.0,
            extra_metrics={"meta_ads": {"inline_link_clicks": 90}},
        )

        performance_reports_store.write_daily_report(
            report_date=date(2026, 3, 1),
            platform="meta_ads",
            customer_id="client-44",
            client_id=44,
            spend=180.0,
            impressions=2000,
            clicks=120,
            conversions=14.0,
            conversion_value=330.0,
            extra_metrics={"meta_ads": {"inline_link_clicks": 120, "purchase_roas_value": 330.0}},
        )

        self.assertEqual(len(performance_reports_store._memory_rows), 1)
        row = performance_reports_store._memory_rows[0]
        self.assertEqual(row["extra_metrics"], {"meta_ads": {"inline_link_clicks": 120, "purchase_roas_value": 330.0}})

    def test_performance_reports_schema_validation_is_read_only_and_errors_when_missing(self):
        os.environ["APP_ENV"] = "development"
        performance_reports_store._schema_initialized = False

        queries: list[str] = []

        class _FakeCursor:
            def execute(self, query, params=None):
                queries.append(str(query).strip())

            def fetchone(self):
                return (None,)

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

        original_connect = performance_reports_store._connect
        try:
            performance_reports_store._connect = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                performance_reports_store.initialize_schema()
        finally:
            performance_reports_store._connect = original_connect
            performance_reports_store._schema_initialized = False
            os.environ["APP_ENV"] = "test"

        self.assertIn("Database schema for ad_performance_reports is not ready; run DB migrations", str(ctx.exception))
        self.assertEqual(len(queries), 1)
        self.assertIn("SELECT to_regclass('public.ad_performance_reports')", queries[0])

    def test_sync_runs_store_schema_missing_raises_clear_error(self):
        sync_runs_store._schema_initialized = False

        class _FakeCursor:
            def execute(self, query, params=None):
                return None

            def fetchone(self):
                return (None,)

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

        original_connect = sync_runs_store._connect
        try:
            sync_runs_store._connect = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                sync_runs_store.get_sync_run("missing")
        finally:
            sync_runs_store._connect = original_connect
            sync_runs_store._schema_initialized = False

        self.assertIn("Database schema for sync_runs is not ready; run DB migrations", str(ctx.exception))

    def test_google_ads_sync_now_async_mirrors_sync_run_create_and_planned_chunks(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()

        original_enforce = google_ads_api.enforce_action_scope
        original_list = google_ads_api.client_registry_service.list_google_mapped_accounts
        original_create = google_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_mirror_create = google_ads_api.sync_runs_store.create_sync_run
        original_chunk_create = google_ads_api.sync_run_chunks_store.create_sync_run_chunk
        captured: dict[str, object] = {"chunk_payloads": []}

        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.client_registry_service.list_google_mapped_accounts = lambda: [{"client_id": 96, "customer_id": "1234567890"}]
            google_ads_api.backfill_job_store.create = lambda payload: "job-xyz"

            def fake_add_task(func, *args, **kwargs):
                captured["task"] = {"func": getattr(func, "__name__", str(func)), "args": args, "kwargs": kwargs}

            background_tasks.add_task = fake_add_task

            def fake_create_sync_run(**kwargs):
                captured["sync_run_payload"] = kwargs
                return {"job_id": kwargs.get("job_id")}

            def fake_create_sync_chunk(**kwargs):
                payloads = captured.get("chunk_payloads")
                assert isinstance(payloads, list)
                payloads.append(kwargs)
                return {"job_id": kwargs.get("job_id"), "chunk_index": kwargs.get("chunk_index")}

            google_ads_api.sync_runs_store.create_sync_run = fake_create_sync_run
            google_ads_api.sync_run_chunks_store.create_sync_run_chunk = fake_create_sync_chunk

            response = google_ads_api.sync_google_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=96,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                days=30,
                async_mode=True,
                chunk_days=14,
            )
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.client_registry_service.list_google_mapped_accounts = original_list
            google_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            google_ads_api.sync_runs_store.create_sync_run = original_mirror_create
            google_ads_api.sync_run_chunks_store.create_sync_run_chunk = original_chunk_create

        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["job_id"], "job-xyz")
        self.assertEqual(response["chunk_days"], 14)
        self.assertEqual(captured["task"]["func"], "_run_google_backfill_job")

        sync_run_payload = captured.get("sync_run_payload") or {}
        self.assertEqual(sync_run_payload.get("job_id"), "job-xyz")
        self.assertEqual(sync_run_payload.get("platform"), "google_ads")
        self.assertEqual(sync_run_payload.get("status"), "queued")
        self.assertEqual(sync_run_payload.get("client_id"), 96)
        self.assertIsNone(sync_run_payload.get("account_id"))
        self.assertEqual(str(sync_run_payload.get("date_start")), "2026-01-01")
        self.assertEqual(str(sync_run_payload.get("date_end")), "2026-01-31")
        self.assertEqual(sync_run_payload.get("chunk_days"), 14)
        self.assertEqual((sync_run_payload.get("metadata") or {}).get("job_type"), "backfill")

        chunk_payloads = captured.get("chunk_payloads") or []
        self.assertEqual(len(chunk_payloads), 3)
        self.assertEqual([int(item.get("chunk_index", -1)) for item in chunk_payloads], [0, 1, 2])
        self.assertEqual([str(item.get("date_start")) for item in chunk_payloads], ["2026-01-01", "2026-01-15", "2026-01-29"])
        self.assertEqual([str(item.get("date_end")) for item in chunk_payloads], ["2026-01-14", "2026-01-28", "2026-01-31"])
        self.assertTrue(all(str(item.get("status")) == "queued" for item in chunk_payloads))

    def test_google_ads_sync_now_async_continues_when_sync_run_chunk_mirror_fails(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()

        original_enforce = google_ads_api.enforce_action_scope
        original_list = google_ads_api.client_registry_service.list_google_mapped_accounts
        original_create = google_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_mirror_create = google_ads_api.sync_runs_store.create_sync_run
        original_chunk_create = google_ads_api.sync_run_chunks_store.create_sync_run_chunk

        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.client_registry_service.list_google_mapped_accounts = lambda: [{"client_id": 96, "customer_id": "1234567890"}]
            google_ads_api.backfill_job_store.create = lambda payload: "job-fallback"
            background_tasks.add_task = lambda *args, **kwargs: None
            google_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: {"job_id": kwargs.get("job_id")}

            def failing_create_sync_chunk(**kwargs):
                raise RuntimeError("sync_run_chunks unavailable")

            google_ads_api.sync_run_chunks_store.create_sync_run_chunk = failing_create_sync_chunk

            response = google_ads_api.sync_google_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=96,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                days=30,
                async_mode=True,
                chunk_days=7,
            )
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.client_registry_service.list_google_mapped_accounts = original_list
            google_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            google_ads_api.sync_runs_store.create_sync_run = original_mirror_create
            google_ads_api.sync_run_chunks_store.create_sync_run_chunk = original_chunk_create

        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["job_id"], "job-fallback")

    def test_google_sync_now_job_status_memory_hit_enriches_with_chunks(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        db_calls: list[str] = []

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        original_chunk_list = google_ads_api.sync_run_chunks_store.list_sync_run_chunks
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: {"status": "running", "platform": "google_ads", "source": "memory"}

            def db_get(job_id: str):
                db_calls.append(job_id)
                return {"job_id": job_id}

            google_ads_api.sync_runs_store.get_sync_run = db_get
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = lambda job_id: [
                {
                    "chunk_index": 0,
                    "status": "queued",
                    "date_start": "2026-01-01",
                    "date_end": "2026-01-07",
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "metadata": {"chunk_days": 7},
                },
                {
                    "chunk_index": 1,
                    "status": "done",
                    "date_start": "2026-01-08",
                    "date_end": "2026-01-14",
                    "started_at": "2026-03-01T00:00:01+00:00",
                    "finished_at": "2026-03-01T00:00:05+00:00",
                    "error": None,
                    "metadata": {},
                },
            ]

            response = google_ads_api.sync_now_job_status("job-memory", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = original_chunk_list

        self.assertEqual(response.get("status"), "running")
        self.assertEqual(response.get("source"), "memory")
        self.assertEqual(db_calls, [])
        self.assertEqual((response.get("chunk_summary") or {}).get("total"), 2)
        self.assertEqual((response.get("chunk_summary") or {}).get("queued"), 1)
        self.assertEqual((response.get("chunk_summary") or {}).get("done"), 1)
        self.assertEqual(len(response.get("chunks") or []), 2)

    def test_google_sync_now_job_status_memory_hit_chunks_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        original_chunk_list = google_ads_api.sync_run_chunks_store.list_sync_run_chunks
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: {"status": "running", "platform": "google_ads", "source": "memory"}
            google_ads_api.sync_runs_store.get_sync_run = lambda job_id: {"job_id": job_id}

            def failing_chunk_list(job_id: str):
                raise RuntimeError("chunk db unavailable")

            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = failing_chunk_list
            response = google_ads_api.sync_now_job_status("job-memory", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = original_chunk_list

        self.assertEqual(response.get("status"), "running")
        self.assertEqual(response.get("source"), "memory")
        self.assertNotIn("chunk_summary", response)
        self.assertNotIn("chunks", response)

    def test_google_sync_now_job_status_falls_back_to_sync_runs_store_and_enriches_chunks(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        original_chunk_list = google_ads_api.sync_run_chunks_store.list_sync_run_chunks
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: None
            google_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "google_ads",
                "status": "done",
                "client_id": 96,
                "account_id": None,
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "chunk_days": 7,
                "created_at": "2026-03-01T00:00:01+00:00",
                "updated_at": "2026-03-01T00:00:10+00:00",
                "started_at": "2026-03-01T00:00:03+00:00",
                "finished_at": "2026-03-01T00:00:09+00:00",
                "error": None,
                "metadata": {"mapped_accounts_count": 3},
            }
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = lambda job_id: [
                {
                    "chunk_index": 0,
                    "status": "done",
                    "date_start": "2026-01-01",
                    "date_end": "2026-01-07",
                    "started_at": "2026-03-01T00:00:01+00:00",
                    "finished_at": "2026-03-01T00:00:05+00:00",
                    "error": None,
                    "metadata": {"rows": 7},
                }
            ]

            response = google_ads_api.sync_now_job_status("job-db", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = original_chunk_list

        self.assertEqual(response.get("job_id"), "job-db")
        self.assertEqual(response.get("status"), "done")
        self.assertEqual(response.get("created_at"), "2026-03-01T00:00:01+00:00")
        self.assertEqual(response.get("started_at"), "2026-03-01T00:00:03+00:00")
        self.assertEqual(response.get("finished_at"), "2026-03-01T00:00:09+00:00")
        self.assertIsNone(response.get("error"))
        self.assertEqual((response.get("metadata") or {}).get("mapped_accounts_count"), 3)
        self.assertEqual((response.get("chunk_summary") or {}).get("total"), 1)
        self.assertEqual((response.get("chunk_summary") or {}).get("done"), 1)
        self.assertEqual(len(response.get("chunks") or []), 1)

    def test_google_sync_now_job_status_fallback_db_hit_chunks_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        original_chunk_list = google_ads_api.sync_run_chunks_store.list_sync_run_chunks
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: None
            google_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "google_ads",
                "status": "running",
                "client_id": 96,
                "account_id": None,
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "chunk_days": 7,
                "created_at": "2026-03-01T00:00:01+00:00",
                "updated_at": "2026-03-01T00:00:10+00:00",
                "started_at": "2026-03-01T00:00:03+00:00",
                "finished_at": None,
                "error": None,
                "metadata": {},
            }

            def failing_chunk_list(job_id: str):
                raise RuntimeError("chunk read failure")

            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = failing_chunk_list
            response = google_ads_api.sync_now_job_status("job-db-chunk-error", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get
            google_ads_api.sync_run_chunks_store.list_sync_run_chunks = original_chunk_list

        self.assertEqual(response.get("job_id"), "job-db-chunk-error")
        self.assertEqual(response.get("status"), "running")
        self.assertNotIn("chunk_summary", response)
        self.assertNotIn("chunks", response)

    def test_google_sync_now_job_status_not_found_when_missing_in_memory_and_db(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: None
            google_ads_api.sync_runs_store.get_sync_run = lambda job_id: None

            with self.assertRaises(google_ads_api.HTTPException) as ctx:
                google_ads_api.sync_now_job_status("job-missing", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(str(ctx.exception.detail), "job not found")

    def test_meta_ads_sync_now_async_mirrors_sync_run_create(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = meta_ads_api.enforce_action_scope
        original_create = meta_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_mirror_create = meta_ads_api.sync_runs_store.create_sync_run
        original_list_meta_accounts = meta_ads_api.client_registry_service.list_client_platform_accounts

        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            meta_ads_api.backfill_job_store.create = lambda payload: "meta-job-1"
            meta_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "act_1200"}]
            background_tasks.add_task = lambda func, *args, **kwargs: captured.update({"task": getattr(func, "__name__", "")})
            meta_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"job_id": kwargs.get("job_id")}

            response = meta_ads_api.sync_meta_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=96,
                async_mode=True,
            )
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            meta_ads_api.sync_runs_store.create_sync_run = original_mirror_create
            meta_ads_api.client_registry_service.list_client_platform_accounts = original_list_meta_accounts

        self.assertEqual(response.get("status"), "queued")
        self.assertEqual(response.get("job_id"), "meta-job-1")
        payload = captured.get("sync_run_payload") or {}
        self.assertEqual(payload.get("job_id"), "meta-job-1")
        self.assertEqual(payload.get("platform"), "meta_ads")
        self.assertEqual(payload.get("status"), "queued")
        self.assertEqual(payload.get("client_id"), 96)
        self.assertEqual(payload.get("account_id"), "act_1200")

    def test_meta_backfill_runner_updates_sync_runs_running_done_and_error(self):
        status_calls: list[dict[str, object]] = []
        sync_state_calls: list[dict[str, object]] = []
        sync_run_status_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []
        op_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []

        original_set_running = meta_ads_api.backfill_job_store.set_running
        original_set_done = meta_ads_api.backfill_job_store.set_done
        original_set_error = meta_ads_api.backfill_job_store.set_error
        original_sync_client = meta_ads_api.meta_ads_service.sync_client
        original_update_status = meta_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = meta_ads_api.sync_state_store.upsert_sync_state
        original_list_meta_accounts = meta_ads_api.client_registry_service.list_client_platform_accounts
        original_operational_update = meta_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            meta_ads_api.backfill_job_store.set_running = lambda job_id: None
            meta_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            meta_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            meta_ads_api.meta_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            meta_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            meta_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"account_id": kwargs.get("account_id")}
            meta_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: ([{"id": "act_700", "currency": "eur"}] if int(kwargs.get("client_id") or 0) == 7 else [{"id": "act_800"}])
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or kwargs

            meta_ads_api._run_meta_sync_job("meta-job-ok", client_id=7)

            def boom_sync(*args, **kwargs):
                raise RuntimeError("meta down")

            meta_ads_api.meta_ads_service.sync_client = boom_sync
            meta_ads_api._run_meta_sync_job("meta-job-fail", client_id=8)
        finally:
            meta_ads_api.backfill_job_store.set_running = original_set_running
            meta_ads_api.backfill_job_store.set_done = original_set_done
            meta_ads_api.backfill_job_store.set_error = original_set_error
            meta_ads_api.meta_ads_service.sync_client = original_sync_client
            meta_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            meta_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            meta_ads_api.client_registry_service.list_client_platform_accounts = original_list_meta_accounts
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertTrue(any(call.get("job_id") == "meta-job-ok" and call.get("status") == "running" for call in status_calls))
        self.assertTrue(any(call.get("job_id") == "meta-job-ok" and call.get("status") == "done" for call in status_calls))
        self.assertTrue(any(call.get("job_id") == "meta-job-fail" and call.get("status") == "running" for call in status_calls))
        self.assertTrue(any(call.get("job_id") == "meta-job-fail" and call.get("status") == "error" for call in status_calls))

        running_call = next((call for call in sync_state_calls if call.get("last_job_id") == "meta-job-ok" and call.get("last_status") == "running"), None)
        self.assertIsNotNone(running_call)
        self.assertEqual((running_call or {}).get("platform"), "meta_ads")
        self.assertEqual((running_call or {}).get("account_id"), "act_700")
        self.assertEqual((running_call or {}).get("grain"), "account_daily")
        self.assertEqual((running_call or {}).get("error"), None)

        done_call = next((call for call in sync_state_calls if call.get("last_job_id") == "meta-job-ok" and call.get("last_status") == "done"), None)
        self.assertIsNotNone(done_call)
        self.assertIsNotNone((done_call or {}).get("last_successful_at"))
        self.assertIsNotNone((done_call or {}).get("last_successful_date"))
        self.assertEqual((done_call or {}).get("error"), None)

        error_call = next((call for call in sync_state_calls if call.get("last_job_id") == "meta-job-fail" and call.get("last_status") == "error"), None)
        self.assertIsNotNone(error_call)
        self.assertEqual((error_call or {}).get("account_id"), "act_800")
        self.assertTrue("meta down" in str((error_call or {}).get("error") or ""))

        start_op_call = next((call for call in operational_calls if call.get("account_id") == "act_700" and call.get("sync_start_date") is not None and call.get("last_synced_at") is None), None)
        self.assertIsNotNone(start_op_call)
        self.assertEqual((start_op_call or {}).get("platform"), "meta_ads")
        self.assertEqual((start_op_call or {}).get("currency_code"), "EUR")

        success_op_call = next((call for call in operational_calls if call.get("account_id") == "act_700" and call.get("last_synced_at") is not None), None)
        self.assertIsNotNone(success_op_call)

    def test_meta_sync_now_job_status_memory_first_and_db_fallback(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = meta_ads_api.enforce_action_scope
        original_memory_get = meta_ads_api.backfill_job_store.get
        original_db_get = meta_ads_api.sync_runs_store.get_sync_run
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            meta_ads_api.backfill_job_store.get = lambda job_id: {"status": "running", "source": "memory"}
            meta_ads_api.sync_runs_store.get_sync_run = lambda job_id: {"job_id": job_id, "status": "done"}
            memory_response = meta_ads_api.sync_now_job_status("meta-memory", user=user)

            meta_ads_api.backfill_job_store.get = lambda job_id: None
            meta_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "meta_ads",
                "status": "done",
                "client_id": 10,
                "account_id": None,
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "chunk_days": 1,
                "created_at": "2026-03-01T00:00:01+00:00",
                "updated_at": "2026-03-01T00:00:10+00:00",
                "started_at": "2026-03-01T00:00:03+00:00",
                "finished_at": "2026-03-01T00:00:09+00:00",
                "error": None,
                "metadata": {},
            }
            db_response = meta_ads_api.sync_now_job_status("meta-db", user=user)

            meta_ads_api.sync_runs_store.get_sync_run = lambda job_id: None
            with self.assertRaises(meta_ads_api.HTTPException) as ctx:
                meta_ads_api.sync_now_job_status("meta-missing", user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.backfill_job_store.get = original_memory_get
            meta_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(memory_response.get("source"), "memory")
        self.assertEqual(db_response.get("job_id"), "meta-db")
        self.assertEqual(db_response.get("status"), "done")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_meta_sync_now_job_status_db_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = meta_ads_api.enforce_action_scope
        original_memory_get = meta_ads_api.backfill_job_store.get
        original_db_get = meta_ads_api.sync_runs_store.get_sync_run
        try:
            meta_ads_api.enforce_action_scope = lambda **kwargs: None
            meta_ads_api.backfill_job_store.get = lambda job_id: None
            meta_ads_api.sync_runs_store.get_sync_run = lambda job_id: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            with self.assertRaises(meta_ads_api.HTTPException) as ctx:
                meta_ads_api.sync_now_job_status("meta-db-error", user=user)
        finally:
            meta_ads_api.enforce_action_scope = original_enforce
            meta_ads_api.backfill_job_store.get = original_memory_get
            meta_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)

    def test_meta_sync_state_upsert_failures_are_non_blocking(self):
        status_calls: list[dict[str, object]] = []

        original_set_running = meta_ads_api.backfill_job_store.set_running
        original_set_done = meta_ads_api.backfill_job_store.set_done
        original_set_error = meta_ads_api.backfill_job_store.set_error
        original_sync_client = meta_ads_api.meta_ads_service.sync_client
        original_update_status = meta_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = meta_ads_api.sync_state_store.upsert_sync_state
        original_list_meta_accounts = meta_ads_api.client_registry_service.list_client_platform_accounts
        original_operational_update = meta_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            meta_ads_api.backfill_job_store.set_running = lambda job_id: None
            meta_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            meta_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            meta_ads_api.meta_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            meta_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            meta_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sync_state unavailable"))
            meta_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "act_9900"}]
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("operational metadata unavailable"))

            meta_ads_api._run_meta_sync_job("meta-job-state-fail", client_id=99)
        finally:
            meta_ads_api.backfill_job_store.set_running = original_set_running
            meta_ads_api.backfill_job_store.set_done = original_set_done
            meta_ads_api.backfill_job_store.set_error = original_set_error
            meta_ads_api.meta_ads_service.sync_client = original_sync_client
            meta_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            meta_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            meta_ads_api.client_registry_service.list_client_platform_accounts = original_list_meta_accounts
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertTrue(any(call.get("job_id") == "meta-job-state-fail" and call.get("status") == "running" for call in status_calls))
        self.assertTrue(any(call.get("job_id") == "meta-job-state-fail" and call.get("status") == "done" for call in status_calls))

    def test_meta_sync_state_skips_when_real_account_id_is_missing(self):
        status_calls: list[dict[str, object]] = []
        sync_state_calls: list[dict[str, object]] = []
        op_calls: list[dict[str, object]] = []

        original_set_running = meta_ads_api.backfill_job_store.set_running
        original_set_done = meta_ads_api.backfill_job_store.set_done
        original_set_error = meta_ads_api.backfill_job_store.set_error
        original_sync_client = meta_ads_api.meta_ads_service.sync_client
        original_update_status = meta_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = meta_ads_api.sync_state_store.upsert_sync_state
        original_list_meta_accounts = meta_ads_api.client_registry_service.list_client_platform_accounts
        original_operational_update = meta_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            meta_ads_api.backfill_job_store.set_running = lambda job_id: None
            meta_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            meta_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            meta_ads_api.meta_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            meta_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            meta_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"account_id": kwargs.get("account_id")}
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: op_calls.append(kwargs) or kwargs
            meta_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: []

            meta_ads_api._run_meta_sync_job("meta-job-no-account", client_id=111)
        finally:
            meta_ads_api.backfill_job_store.set_running = original_set_running
            meta_ads_api.backfill_job_store.set_done = original_set_done
            meta_ads_api.backfill_job_store.set_error = original_set_error
            meta_ads_api.meta_ads_service.sync_client = original_sync_client
            meta_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            meta_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            meta_ads_api.client_registry_service.list_client_platform_accounts = original_list_meta_accounts
            meta_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertEqual(sync_state_calls, [])
        self.assertEqual(op_calls, [])
        self.assertEqual(op_calls, [])
        self.assertTrue(any(call.get("job_id") == "meta-job-no-account" and call.get("status") == "running" for call in status_calls))
        done_call = next((call for call in status_calls if call.get("job_id") == "meta-job-no-account" and call.get("status") == "done"), None)
        self.assertIsNotNone(done_call)
        self.assertNotIn("account_id", (done_call or {}).get("metadata") or {})

    def test_tiktok_ads_sync_now_async_mirrors_sync_run_create(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_create = tiktok_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_mirror_create = tiktok_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = tiktok_ads_api.client_registry_service.list_client_platform_accounts
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None
            tiktok_ads_api.backfill_job_store.create = lambda payload: "tt-job-1"
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "tt-acc-1"}]
            background_tasks.add_task = lambda func, *args, **kwargs: captured.update({"task": getattr(func, "__name__", "")})
            tiktok_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"job_id": kwargs.get("job_id")}

            response = tiktok_ads_api.sync_tiktok_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=77,
                async_mode=True,
            )
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            tiktok_ads_api.sync_runs_store.create_sync_run = original_mirror_create
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        self.assertEqual(response.get("job_id"), "tt-job-1")
        payload = captured.get("sync_run_payload") or {}
        self.assertEqual(payload.get("platform"), "tiktok_ads")
        self.assertEqual(payload.get("status"), "queued")
        self.assertEqual(payload.get("client_id"), 77)
        self.assertEqual(payload.get("account_id"), "tt-acc-1")

    def test_tiktok_backfill_runner_updates_sync_runs_sync_state_and_operational_metadata(self):
        status_calls: list[dict[str, object]] = []
        sync_state_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []

        original_set_running = tiktok_ads_api.backfill_job_store.set_running
        original_set_done = tiktok_ads_api.backfill_job_store.set_done
        original_set_error = tiktok_ads_api.backfill_job_store.set_error
        original_sync_client = tiktok_ads_api.tiktok_ads_service.sync_client
        original_update_status = tiktok_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = tiktok_ads_api.sync_state_store.upsert_sync_state
        original_list_accounts = tiktok_ads_api.client_registry_service.list_client_platform_accounts
        original_operational_update = tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            tiktok_ads_api.backfill_job_store.set_running = lambda job_id: None
            tiktok_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            tiktok_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            tiktok_ads_api.tiktok_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            tiktok_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            tiktok_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"account_id": kwargs.get("account_id")}
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: ([{"id": "tt-acc-ok", "currency": "eur"}] if int(kwargs.get("client_id") or 0) == 11 else [{"id": "tt-acc-fail"}])
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or kwargs

            tiktok_ads_api._run_tiktok_sync_job("tt-job-ok", client_id=11, account_id="tt-acc-ok")

            def boom_sync(*args, **kwargs):
                raise RuntimeError("tiktok down")

            tiktok_ads_api.tiktok_ads_service.sync_client = boom_sync
            tiktok_ads_api._run_tiktok_sync_job("tt-job-fail", client_id=12, account_id="tt-acc-fail")
        finally:
            tiktok_ads_api.backfill_job_store.set_running = original_set_running
            tiktok_ads_api.backfill_job_store.set_done = original_set_done
            tiktok_ads_api.backfill_job_store.set_error = original_set_error
            tiktok_ads_api.tiktok_ads_service.sync_client = original_sync_client
            tiktok_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            tiktok_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertTrue(any(call.get("job_id") == "tt-job-ok" and call.get("status") == "running" for call in status_calls))
        done_call = next((call for call in status_calls if call.get("job_id") == "tt-job-ok" and call.get("status") == "done"), None)
        self.assertIsNotNone(done_call)
        self.assertEqual(((done_call or {}).get("metadata") or {}).get("account_id"), "tt-acc-ok")
        self.assertTrue(any(call.get("job_id") == "tt-job-fail" and call.get("status") == "error" for call in status_calls))

        running_call = next((call for call in sync_state_calls if call.get("last_job_id") == "tt-job-ok" and call.get("last_status") == "running"), None)
        self.assertIsNotNone(running_call)
        self.assertEqual((running_call or {}).get("platform"), "tiktok_ads")
        self.assertEqual((running_call or {}).get("account_id"), "tt-acc-ok")
        self.assertEqual((running_call or {}).get("grain"), "account_daily")

        done_state_call = next((call for call in sync_state_calls if call.get("last_job_id") == "tt-job-ok" and call.get("last_status") == "done"), None)
        self.assertIsNotNone(done_state_call)
        self.assertIsNotNone((done_state_call or {}).get("last_successful_at"))
        self.assertIsNotNone((done_state_call or {}).get("last_successful_date"))
        self.assertEqual((done_state_call or {}).get("error"), None)

        error_state_call = next((call for call in sync_state_calls if call.get("last_job_id") == "tt-job-fail" and call.get("last_status") == "error"), None)
        self.assertIsNotNone(error_state_call)
        self.assertEqual((error_state_call or {}).get("account_id"), "tt-acc-fail")
        self.assertTrue("tiktok down" in str((error_state_call or {}).get("error") or ""))

        start_op_call = next((call for call in operational_calls if call.get("account_id") == "tt-acc-ok" and call.get("sync_start_date") is not None and call.get("last_synced_at") is None), None)
        self.assertIsNotNone(start_op_call)
        self.assertEqual((start_op_call or {}).get("platform"), "tiktok_ads")
        self.assertEqual((start_op_call or {}).get("currency_code"), "EUR")

        success_op_call = next((call for call in operational_calls if call.get("account_id") == "tt-acc-ok" and call.get("last_synced_at") is not None), None)
        self.assertIsNotNone(success_op_call)

    def test_tiktok_sync_now_job_status_memory_first_and_db_fallback(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_memory_get = tiktok_ads_api.backfill_job_store.get
        original_db_get = tiktok_ads_api.sync_runs_store.get_sync_run
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None
            tiktok_ads_api.backfill_job_store.get = lambda job_id: {"status": "running", "source": "memory"}
            tiktok_ads_api.sync_runs_store.get_sync_run = lambda job_id: {"job_id": job_id, "status": "done"}
            memory_response = tiktok_ads_api.sync_now_job_status("tt-memory", user=user)

            tiktok_ads_api.backfill_job_store.get = lambda job_id: None
            tiktok_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "tiktok_ads",
                "status": "done",
                "client_id": 77,
                "account_id": "tt-acc-77",
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "chunk_days": 1,
                "created_at": "2026-03-01T00:00:01+00:00",
                "updated_at": "2026-03-01T00:00:10+00:00",
                "started_at": "2026-03-01T00:00:03+00:00",
                "finished_at": "2026-03-01T00:00:09+00:00",
                "error": None,
                "metadata": {},
            }
            db_response = tiktok_ads_api.sync_now_job_status("tt-db", user=user)

            tiktok_ads_api.sync_runs_store.get_sync_run = lambda job_id: None
            with self.assertRaises(tiktok_ads_api.HTTPException) as ctx:
                tiktok_ads_api.sync_now_job_status("tt-missing", user=user)
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.backfill_job_store.get = original_memory_get
            tiktok_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(memory_response.get("source"), "memory")
        self.assertEqual(db_response.get("job_id"), "tt-db")
        self.assertEqual(db_response.get("account_id"), "tt-acc-77")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_tiktok_sync_now_job_status_db_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_memory_get = tiktok_ads_api.backfill_job_store.get
        original_db_get = tiktok_ads_api.sync_runs_store.get_sync_run
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None
            tiktok_ads_api.backfill_job_store.get = lambda job_id: None
            tiktok_ads_api.sync_runs_store.get_sync_run = lambda job_id: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            with self.assertRaises(tiktok_ads_api.HTTPException) as ctx:
                tiktok_ads_api.sync_now_job_status("tt-db-error", user=user)
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.backfill_job_store.get = original_memory_get
            tiktok_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)

    def test_tiktok_sync_state_upsert_failures_are_non_blocking(self):
        status_calls: list[dict[str, object]] = []

        original_set_running = tiktok_ads_api.backfill_job_store.set_running
        original_set_done = tiktok_ads_api.backfill_job_store.set_done
        original_set_error = tiktok_ads_api.backfill_job_store.set_error
        original_sync_client = tiktok_ads_api.tiktok_ads_service.sync_client
        original_update_status = tiktok_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = tiktok_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            tiktok_ads_api.backfill_job_store.set_running = lambda job_id: None
            tiktok_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            tiktok_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            tiktok_ads_api.tiktok_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            tiktok_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            tiktok_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sync_state unavailable"))
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("operational metadata unavailable"))

            tiktok_ads_api._run_tiktok_sync_job("tt-job-state-fail", client_id=33, account_id="tt-acc-33")
        finally:
            tiktok_ads_api.backfill_job_store.set_running = original_set_running
            tiktok_ads_api.backfill_job_store.set_done = original_set_done
            tiktok_ads_api.backfill_job_store.set_error = original_set_error
            tiktok_ads_api.tiktok_ads_service.sync_client = original_sync_client
            tiktok_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            tiktok_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertTrue(any(call.get("job_id") == "tt-job-state-fail" and call.get("status") == "running" for call in status_calls))
        self.assertTrue(any(call.get("job_id") == "tt-job-state-fail" and call.get("status") == "done" for call in status_calls))

    def test_tiktok_sync_state_skips_when_account_id_missing(self):
        status_calls: list[dict[str, object]] = []
        sync_state_calls: list[dict[str, object]] = []
        op_calls: list[dict[str, object]] = []

        original_set_running = tiktok_ads_api.backfill_job_store.set_running
        original_set_done = tiktok_ads_api.backfill_job_store.set_done
        original_set_error = tiktok_ads_api.backfill_job_store.set_error
        original_sync_client = tiktok_ads_api.tiktok_ads_service.sync_client
        original_update_status = tiktok_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = tiktok_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            tiktok_ads_api.backfill_job_store.set_running = lambda job_id: None
            tiktok_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            tiktok_ads_api.backfill_job_store.set_error = lambda job_id, error: None
            tiktok_ads_api.tiktok_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            tiktok_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: status_calls.append(kwargs) or {"job_id": kwargs.get("job_id")}
            tiktok_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"account_id": kwargs.get("account_id")}
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: op_calls.append(kwargs) or kwargs

            tiktok_ads_api._run_tiktok_sync_job("tt-job-no-account", client_id=44, account_id=None)
        finally:
            tiktok_ads_api.backfill_job_store.set_running = original_set_running
            tiktok_ads_api.backfill_job_store.set_done = original_set_done
            tiktok_ads_api.backfill_job_store.set_error = original_set_error
            tiktok_ads_api.tiktok_ads_service.sync_client = original_sync_client
            tiktok_ads_api.sync_runs_store.update_sync_run_status = original_update_status
            tiktok_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            tiktok_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertEqual(sync_state_calls, [])
        self.assertEqual(op_calls, [])
        self.assertTrue(any(call.get("job_id") == "tt-job-no-account" and call.get("status") == "running" for call in status_calls))
        done_call = next((call for call in status_calls if call.get("job_id") == "tt-job-no-account" and call.get("status") == "done"), None)
        self.assertIsNotNone(done_call)
        self.assertNotIn("account_id", (done_call or {}).get("metadata") or {})

    def test_tiktok_sync_now_async_does_not_use_client_id_as_account_id_when_ambiguous(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = tiktok_ads_api.enforce_action_scope
        original_create = tiktok_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_mirror_create = tiktok_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = tiktok_ads_api.client_registry_service.list_client_platform_accounts
        try:
            tiktok_ads_api.enforce_action_scope = lambda **kwargs: None
            tiktok_ads_api.backfill_job_store.create = lambda payload: "tt-job-amb"
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "tt-1"}, {"id": "tt-2"}]
            background_tasks.add_task = lambda func, *args, **kwargs: captured.update({"task": getattr(func, "__name__", "")})
            tiktok_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"job_id": kwargs.get("job_id")}

            response = tiktok_ads_api.sync_tiktok_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=88,
                async_mode=True,
            )
        finally:
            tiktok_ads_api.enforce_action_scope = original_enforce
            tiktok_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            tiktok_ads_api.sync_runs_store.create_sync_run = original_mirror_create
            tiktok_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        payload = captured.get("sync_run_payload") or {}
        self.assertIsNone(payload.get("account_id"))
        self.assertNotEqual(payload.get("account_id"), "88")

    def test_cross_platform_sync_constants_are_canonical(self):
        self.assertEqual(getattr(google_ads_api, "PLATFORM_GOOGLE_ADS", None), "google_ads")
        self.assertEqual(getattr(meta_ads_api, "PLATFORM_META_ADS", None), "meta_ads")
        self.assertEqual(getattr(tiktok_ads_api, "PLATFORM_TIKTOK_ADS", None), "tiktok_ads")
        self.assertEqual(getattr(google_ads_api, "SYNC_GRAIN_ACCOUNT_DAILY", None), "account_daily")
        self.assertEqual(getattr(meta_ads_api, "SYNC_GRAIN_ACCOUNT_DAILY", None), "account_daily")
        self.assertEqual(getattr(tiktok_ads_api, "SYNC_GRAIN_ACCOUNT_DAILY", None), "account_daily")
        self.assertEqual(getattr(google_ads_api, "SYNC_STATUS_QUEUED", None), "queued")
        self.assertEqual(getattr(meta_ads_api, "SYNC_STATUS_RUNNING", None), "running")
        self.assertEqual(getattr(tiktok_ads_api, "SYNC_STATUS_DONE", None), "done")
        self.assertEqual(getattr(tiktok_ads_api, "SYNC_STATUS_ERROR", None), "error")

    def test_meta_and_tiktok_do_not_wire_sync_run_chunks(self):
        self.assertFalse(hasattr(meta_ads_api, "sync_run_chunks_store"))
        self.assertFalse(hasattr(tiktok_ads_api, "sync_run_chunks_store"))

    def test_pinterest_ads_sync_now_returns_queued_job_payload(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = pinterest_ads_api.enforce_action_scope
        original_create = pinterest_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_sync_runs_create = pinterest_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.enforce_action_scope = lambda **kwargs: None
            pinterest_ads_api.backfill_job_store.create = lambda payload: "pin-job-1"
            background_tasks.add_task = lambda func, *args, **kwargs: captured.update(
                {
                    "task": getattr(func, "__name__", ""),
                    "task_args": args,
                    "task_kwargs": kwargs,
                }
            )
            pinterest_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-acc-66"}]

            response = pinterest_ads_api.sync_pinterest_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=66,
            )
        finally:
            pinterest_ads_api.enforce_action_scope = original_enforce
            pinterest_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            pinterest_ads_api.sync_runs_store.create_sync_run = original_sync_runs_create
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        self.assertEqual(response.get("job_id"), "pin-job-1")
        self.assertEqual(response.get("client_id"), 66)
        self.assertEqual(response.get("platform"), "pinterest_ads")
        self.assertEqual(captured.get("task"), "_run_pinterest_sync_job")

        payload = captured.get("sync_run_payload") if isinstance(captured.get("sync_run_payload"), dict) else {}
        self.assertEqual(payload.get("job_id"), "pin-job-1")
        self.assertEqual(payload.get("status"), "queued")
        self.assertEqual(payload.get("platform"), "pinterest_ads")
        self.assertEqual(payload.get("client_id"), 66)
        self.assertEqual(payload.get("account_id"), "pin-acc-66")
        self.assertEqual(payload.get("chunk_days"), 1)
        self.assertEqual(str(payload.get("date_start")), str(payload.get("date_end")))

    def test_pinterest_sync_now_create_uses_account_id_none_when_ambiguous(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = pinterest_ads_api.enforce_action_scope
        original_create = pinterest_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_sync_runs_create = pinterest_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.enforce_action_scope = lambda **kwargs: None
            pinterest_ads_api.backfill_job_store.create = lambda payload: "pin-job-amb"
            background_tasks.add_task = lambda func, *args, **kwargs: None
            pinterest_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-1"}, {"id": "pin-2"}]

            response = pinterest_ads_api.sync_pinterest_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=99,
            )
        finally:
            pinterest_ads_api.enforce_action_scope = original_enforce
            pinterest_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            pinterest_ads_api.sync_runs_store.create_sync_run = original_sync_runs_create
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        payload = captured.get("sync_run_payload") if isinstance(captured.get("sync_run_payload"), dict) else {}
        self.assertIsNone(payload.get("account_id"))
        self.assertNotEqual(payload.get("account_id"), "99")

    def test_pinterest_backfill_runner_updates_memory_job_success_and_error(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []
        sync_state_calls: list[dict[str, object]] = []
        sync_run_status_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []

        original_set_running = pinterest_ads_api.backfill_job_store.set_running
        original_set_done = pinterest_ads_api.backfill_job_store.set_done
        original_set_error = pinterest_ads_api.backfill_job_store.set_error
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_sync_state_upsert = pinterest_ads_api.sync_state_store.upsert_sync_state
        original_sync_runs_update = pinterest_ads_api.sync_runs_store.update_sync_run_status
        original_operational_update = pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            pinterest_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            pinterest_ads_api.backfill_job_store.set_error = lambda job_id, error: captured_calls.append(("error", {"job_id": job_id, "error": error}))
            pinterest_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"ok": True}
            pinterest_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: sync_run_status_calls.append(kwargs) or {"ok": True}
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-acc-21", "status": "active", "currency_code": "usd", "account_timezone": "UTC"}] if int(kwargs.get("client_id") or 0) == 21 else [{"id": "pin-acc-22", "status": "active", "currency_code": "eur", "account_timezone": "Europe/Berlin"}]

            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            pinterest_ads_api._run_pinterest_sync_job("pin-job-ok", client_id=21)

            def failing_sync(*args, **kwargs):
                raise RuntimeError("x" * 400)

            pinterest_ads_api.pinterest_ads_service.sync_client = failing_sync
            pinterest_ads_api._run_pinterest_sync_job("pin-job-fail", client_id=22)
        finally:
            pinterest_ads_api.backfill_job_store.set_running = original_set_running
            pinterest_ads_api.backfill_job_store.set_done = original_set_done
            pinterest_ads_api.backfill_job_store.set_error = original_set_error
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            pinterest_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        running_calls = [payload for event, payload in captured_calls if event == "running"]
        done_calls = [payload for event, payload in captured_calls if event == "done"]
        error_calls = [payload for event, payload in captured_calls if event == "error"]

        self.assertTrue(any(call.get("job_id") == "pin-job-ok" for call in running_calls))
        self.assertTrue(any(call.get("job_id") == "pin-job-fail" for call in running_calls))
        self.assertEqual(done_calls[0].get("job_id"), "pin-job-ok")
        done_result = done_calls[0].get("result") if isinstance(done_calls[0].get("result"), dict) else {}
        self.assertEqual(done_result.get("status"), "done")
        self.assertEqual(done_result.get("platform"), "pinterest_ads")
        self.assertEqual(done_result.get("client_id"), 21)
        self.assertEqual(done_result.get("result"), {"status": "ok", "client_id": 21})
        self.assertEqual(error_calls[0].get("job_id"), "pin-job-fail")
        self.assertEqual(len(str(error_calls[0].get("error") or "")), 300)

        running_state_ok = next((call for call in sync_state_calls if call.get("last_job_id") == "pin-job-ok" and call.get("last_status") == "running"), None)
        done_state_ok = next((call for call in sync_state_calls if call.get("last_job_id") == "pin-job-ok" and call.get("last_status") == "done"), None)
        running_state_fail = next((call for call in sync_state_calls if call.get("last_job_id") == "pin-job-fail" and call.get("last_status") == "running"), None)
        error_state_fail = next((call for call in sync_state_calls if call.get("last_job_id") == "pin-job-fail" and call.get("last_status") == "error"), None)
        self.assertIsNotNone(running_state_ok)
        self.assertIsNotNone(done_state_ok)
        self.assertIsNotNone(running_state_fail)
        self.assertIsNotNone(error_state_fail)
        self.assertEqual((running_state_ok or {}).get("account_id"), "pin-acc-21")
        self.assertEqual((done_state_ok or {}).get("account_id"), "pin-acc-21")
        self.assertEqual((error_state_fail or {}).get("account_id"), "pin-acc-22")
        self.assertEqual((running_state_ok or {}).get("grain"), "account_daily")
        self.assertIsNone((done_state_ok or {}).get("error"))
        self.assertIsNotNone((done_state_ok or {}).get("last_successful_at"))
        self.assertIsNotNone((done_state_ok or {}).get("last_successful_date"))
        self.assertTrue(str((done_state_ok or {}).get("last_successful_date")).count("-") == 2)
        self.assertTrue(len(str((error_state_fail or {}).get("error") or "")) == 300)

        self.assertTrue(any(call.get("job_id") == "pin-job-ok" and call.get("status") == "running" for call in sync_run_status_calls))
        self.assertTrue(any(call.get("job_id") == "pin-job-ok" and call.get("status") == "done" and call.get("mark_finished") is True for call in sync_run_status_calls))
        self.assertTrue(any(call.get("job_id") == "pin-job-fail" and call.get("status") == "error" and call.get("mark_finished") is True for call in sync_run_status_calls))

        start_operational = next((call for call in operational_calls if call.get("account_id") == "pin-acc-21" and call.get("last_synced_at") is None), None)
        success_operational = next((call for call in operational_calls if call.get("account_id") == "pin-acc-21" and call.get("last_synced_at") is not None), None)
        self.assertIsNotNone(start_operational)
        self.assertIsNotNone(success_operational)
        self.assertEqual((start_operational or {}).get("platform"), "pinterest_ads")
        self.assertEqual((start_operational or {}).get("status"), "active")
        self.assertEqual((start_operational or {}).get("currency_code"), "USD")
        self.assertEqual((start_operational or {}).get("account_timezone"), "UTC")
        self.assertIsNotNone((start_operational or {}).get("sync_start_date"))

    def test_pinterest_sync_state_upsert_failure_is_non_blocking(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []

        original_set_running = pinterest_ads_api.backfill_job_store.set_running
        original_set_done = pinterest_ads_api.backfill_job_store.set_done
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_sync_state_upsert = pinterest_ads_api.sync_state_store.upsert_sync_state
        original_sync_runs_update = pinterest_ads_api.sync_runs_store.update_sync_run_status
        original_operational_update = pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            pinterest_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            pinterest_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            pinterest_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-acc-7"}]

            pinterest_ads_api._run_pinterest_sync_job("pin-job-state-fail", client_id=7)
        finally:
            pinterest_ads_api.backfill_job_store.set_running = original_set_running
            pinterest_ads_api.backfill_job_store.set_done = original_set_done
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            pinterest_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertTrue(any(event == "running" and payload.get("job_id") == "pin-job-state-fail" for event, payload in captured_calls))
        self.assertTrue(any(event == "done" and payload.get("job_id") == "pin-job-state-fail" for event, payload in captured_calls))

    def test_pinterest_sync_state_skips_upsert_when_account_id_is_ambiguous(self):
        original_set_running = pinterest_ads_api.backfill_job_store.set_running
        original_set_done = pinterest_ads_api.backfill_job_store.set_done
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_sync_state_upsert = pinterest_ads_api.sync_state_store.upsert_sync_state
        original_sync_runs_update = pinterest_ads_api.sync_runs_store.update_sync_run_status
        original_operational_update = pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.backfill_job_store.set_running = lambda job_id: None
            pinterest_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}

            sync_state_calls: list[dict[str, object]] = []
            pinterest_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"ok": True}
            pinterest_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-a"}, {"id": "pin-b"}]

            pinterest_ads_api._run_pinterest_sync_job("pin-job-amb", client_id=99)
        finally:
            pinterest_ads_api.backfill_job_store.set_running = original_set_running
            pinterest_ads_api.backfill_job_store.set_done = original_set_done
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            pinterest_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(sync_state_calls, [])

    def test_pinterest_operational_metadata_update_failure_is_non_blocking(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []

        original_set_running = pinterest_ads_api.backfill_job_store.set_running
        original_set_done = pinterest_ads_api.backfill_job_store.set_done
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_sync_state_upsert = pinterest_ads_api.sync_state_store.upsert_sync_state
        original_sync_runs_update = pinterest_ads_api.sync_runs_store.update_sync_run_status
        original_operational_update = pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            pinterest_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            pinterest_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}
            pinterest_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("operational metadata unavailable"))
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-acc-7", "status": "active", "currency_code": "usd", "account_timezone": "UTC"}]

            pinterest_ads_api._run_pinterest_sync_job("pin-job-op-fail", client_id=7)
        finally:
            pinterest_ads_api.backfill_job_store.set_running = original_set_running
            pinterest_ads_api.backfill_job_store.set_done = original_set_done
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            pinterest_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertTrue(any(event == "running" and payload.get("job_id") == "pin-job-op-fail" for event, payload in captured_calls))
        self.assertTrue(any(event == "done" and payload.get("job_id") == "pin-job-op-fail" for event, payload in captured_calls))

    def test_pinterest_operational_metadata_skips_when_account_id_is_ambiguous(self):
        original_set_running = pinterest_ads_api.backfill_job_store.set_running
        original_set_done = pinterest_ads_api.backfill_job_store.set_done
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_sync_state_upsert = pinterest_ads_api.sync_state_store.upsert_sync_state
        original_sync_runs_update = pinterest_ads_api.sync_runs_store.update_sync_run_status
        original_operational_update = pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = pinterest_ads_api.client_registry_service.list_client_platform_accounts
        try:
            pinterest_ads_api.backfill_job_store.set_running = lambda job_id: None
            pinterest_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            pinterest_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}
            pinterest_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}

            operational_calls: list[dict[str, object]] = []
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or {"ok": True}
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "pin-a"}, {"id": "pin-b"}]

            pinterest_ads_api._run_pinterest_sync_job("pin-job-amb-op", client_id=99)
        finally:
            pinterest_ads_api.backfill_job_store.set_running = original_set_running
            pinterest_ads_api.backfill_job_store.set_done = original_set_done
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            pinterest_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            pinterest_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            pinterest_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(operational_calls, [])

    def test_pinterest_sync_now_job_status_memory_first_and_db_fallback(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = pinterest_ads_api.enforce_action_scope
        original_memory_get = pinterest_ads_api.backfill_job_store.get
        original_db_get = pinterest_ads_api.sync_runs_store.get_sync_run
        try:
            pinterest_ads_api.enforce_action_scope = lambda **kwargs: None
            pinterest_ads_api.backfill_job_store.get = lambda job_id: {"job_id": job_id, "status": "running", "source": "memory"} if job_id == "pin-memory" else None

            memory_response = pinterest_ads_api.sync_now_job_status("pin-memory", user=user)

            pinterest_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "pinterest_ads",
                "status": "done",
                "client_id": 66,
                "account_id": "pin-acc-66",
                "date_start": "2026-03-01",
                "date_end": "2026-03-01",
                "chunk_days": 1,
                "error": None,
                "metadata": {"source": "db"},
            }
            db_response = pinterest_ads_api.sync_now_job_status("pin-db", user=user)

            pinterest_ads_api.sync_runs_store.get_sync_run = lambda job_id: None
            with self.assertRaises(pinterest_ads_api.HTTPException) as ctx:
                pinterest_ads_api.sync_now_job_status("pin-missing", user=user)
        finally:
            pinterest_ads_api.enforce_action_scope = original_enforce
            pinterest_ads_api.backfill_job_store.get = original_memory_get
            pinterest_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(memory_response.get("source"), "memory")
        self.assertEqual(db_response.get("job_id"), "pin-db")
        self.assertEqual(db_response.get("status"), "done")
        self.assertEqual(db_response.get("account_id"), "pin-acc-66")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_pinterest_sync_now_job_status_db_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = pinterest_ads_api.enforce_action_scope
        original_memory_get = pinterest_ads_api.backfill_job_store.get
        original_db_get = pinterest_ads_api.sync_runs_store.get_sync_run
        try:
            pinterest_ads_api.enforce_action_scope = lambda **kwargs: None
            pinterest_ads_api.backfill_job_store.get = lambda job_id: None
            pinterest_ads_api.sync_runs_store.get_sync_run = lambda job_id: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            with self.assertRaises(pinterest_ads_api.HTTPException) as ctx:
                pinterest_ads_api.sync_now_job_status("pin-db-error", user=user)
        finally:
            pinterest_ads_api.enforce_action_scope = original_enforce
            pinterest_ads_api.backfill_job_store.get = original_memory_get
            pinterest_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)

    def test_snapchat_ads_sync_now_returns_queued_job_payload(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = snapchat_ads_api.enforce_action_scope
        original_create = snapchat_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_sync_runs_create = snapchat_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.enforce_action_scope = lambda **kwargs: None
            snapchat_ads_api.backfill_job_store.create = lambda payload: "sc-job-1"
            background_tasks.add_task = lambda func, *args, **kwargs: captured.update({"task": getattr(func, "__name__", "")})
            snapchat_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"ok": True}
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-acc-77"}]

            response = snapchat_ads_api.sync_snapchat_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=77,
            )
        finally:
            snapchat_ads_api.enforce_action_scope = original_enforce
            snapchat_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            snapchat_ads_api.sync_runs_store.create_sync_run = original_sync_runs_create
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        self.assertEqual(response.get("job_id"), "sc-job-1")
        self.assertEqual(response.get("client_id"), 77)
        self.assertEqual(response.get("platform"), "snapchat_ads")
        self.assertEqual(captured.get("task"), "_run_snapchat_sync_job")

        payload = captured.get("sync_run_payload") if isinstance(captured.get("sync_run_payload"), dict) else {}
        self.assertEqual(payload.get("job_id"), "sc-job-1")
        self.assertEqual(payload.get("status"), "queued")
        self.assertEqual(payload.get("platform"), "snapchat_ads")
        self.assertEqual(payload.get("client_id"), 77)
        self.assertEqual(payload.get("account_id"), "sc-acc-77")
        self.assertEqual(payload.get("chunk_days"), 1)
        self.assertEqual(str(payload.get("date_start")), str(payload.get("date_end")))

    def test_snapchat_sync_now_create_uses_account_id_none_when_ambiguous(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")
        background_tasks = BackgroundTasks()
        captured: dict[str, object] = {}

        original_enforce = snapchat_ads_api.enforce_action_scope
        original_create = snapchat_ads_api.backfill_job_store.create
        original_add_task = background_tasks.add_task
        original_sync_runs_create = snapchat_ads_api.sync_runs_store.create_sync_run
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.enforce_action_scope = lambda **kwargs: None
            snapchat_ads_api.backfill_job_store.create = lambda payload: "sc-job-amb"
            background_tasks.add_task = lambda func, *args, **kwargs: None
            snapchat_ads_api.sync_runs_store.create_sync_run = lambda **kwargs: captured.update({"sync_run_payload": kwargs}) or {"ok": True}
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-1"}, {"id": "sc-2"}]

            response = snapchat_ads_api.sync_snapchat_ads_now(
                background_tasks=background_tasks,
                user=user,
                client_id=99,
            )
        finally:
            snapchat_ads_api.enforce_action_scope = original_enforce
            snapchat_ads_api.backfill_job_store.create = original_create
            background_tasks.add_task = original_add_task
            snapchat_ads_api.sync_runs_store.create_sync_run = original_sync_runs_create
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(response.get("status"), "queued")
        payload = captured.get("sync_run_payload") if isinstance(captured.get("sync_run_payload"), dict) else {}
        self.assertIsNone(payload.get("account_id"))
        self.assertNotEqual(payload.get("account_id"), "99")

    def test_snapchat_backfill_runner_updates_memory_sync_runs_and_sync_state(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []
        sync_run_status_calls: list[dict[str, object]] = []
        sync_state_calls: list[dict[str, object]] = []
        operational_calls: list[dict[str, object]] = []

        original_set_running = snapchat_ads_api.backfill_job_store.set_running
        original_set_done = snapchat_ads_api.backfill_job_store.set_done
        original_set_error = snapchat_ads_api.backfill_job_store.set_error
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_sync_runs_update = snapchat_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = snapchat_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            snapchat_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            snapchat_ads_api.backfill_job_store.set_error = lambda job_id, error: captured_calls.append(("error", {"job_id": job_id, "error": error}))
            snapchat_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: sync_run_status_calls.append(kwargs) or {"ok": True}
            snapchat_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"ok": True}
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or {"ok": True}
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-acc-31", "status": "active", "currency_code": "usd", "account_timezone": "UTC"}] if int(kwargs.get("client_id") or 0) == 31 else [{"id": "sc-acc-32", "status": "active", "currency_code": "eur", "account_timezone": "Europe/Berlin"}]

            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            snapchat_ads_api._run_snapchat_sync_job("sc-job-ok", client_id=31)

            def failing_sync(*args, **kwargs):
                raise RuntimeError("x" * 400)

            snapchat_ads_api.snapchat_ads_service.sync_client = failing_sync
            snapchat_ads_api._run_snapchat_sync_job("sc-job-fail", client_id=32)
        finally:
            snapchat_ads_api.backfill_job_store.set_running = original_set_running
            snapchat_ads_api.backfill_job_store.set_done = original_set_done
            snapchat_ads_api.backfill_job_store.set_error = original_set_error
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            snapchat_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        running_calls = [payload for event, payload in captured_calls if event == "running"]
        done_calls = [payload for event, payload in captured_calls if event == "done"]
        error_calls = [payload for event, payload in captured_calls if event == "error"]

        self.assertTrue(any(call.get("job_id") == "sc-job-ok" for call in running_calls))
        self.assertTrue(any(call.get("job_id") == "sc-job-fail" for call in running_calls))
        done_result = done_calls[0].get("result") if isinstance(done_calls[0].get("result"), dict) else {}
        self.assertEqual(done_result.get("status"), "done")
        self.assertEqual(done_result.get("platform"), "snapchat_ads")
        self.assertEqual(done_result.get("client_id"), 31)
        self.assertEqual(done_result.get("result"), {"status": "ok", "client_id": 31})
        self.assertEqual(len(str(error_calls[0].get("error") or "")), 300)

        self.assertTrue(any(call.get("job_id") == "sc-job-ok" and call.get("status") == "running" for call in sync_run_status_calls))
        self.assertTrue(any(call.get("job_id") == "sc-job-ok" and call.get("status") == "done" and call.get("mark_finished") is True for call in sync_run_status_calls))
        self.assertTrue(any(call.get("job_id") == "sc-job-fail" and call.get("status") == "error" and call.get("mark_finished") is True for call in sync_run_status_calls))

        running_state_ok = next((call for call in sync_state_calls if call.get("last_job_id") == "sc-job-ok" and call.get("last_status") == "running"), None)
        done_state_ok = next((call for call in sync_state_calls if call.get("last_job_id") == "sc-job-ok" and call.get("last_status") == "done"), None)
        error_state_fail = next((call for call in sync_state_calls if call.get("last_job_id") == "sc-job-fail" and call.get("last_status") == "error"), None)
        self.assertIsNotNone(running_state_ok)
        self.assertIsNotNone(done_state_ok)
        self.assertIsNotNone(error_state_fail)
        self.assertEqual((running_state_ok or {}).get("account_id"), "sc-acc-31")
        self.assertEqual((done_state_ok or {}).get("account_id"), "sc-acc-31")
        self.assertEqual((error_state_fail or {}).get("account_id"), "sc-acc-32")
        self.assertEqual((running_state_ok or {}).get("grain"), "account_daily")
        self.assertIsNotNone((done_state_ok or {}).get("last_successful_at"))
        self.assertIsNotNone((done_state_ok or {}).get("last_successful_date"))
        self.assertTrue(str((done_state_ok or {}).get("last_successful_date")).count("-") == 2)
        self.assertEqual(len(str((error_state_fail or {}).get("error") or "")), 300)

        start_operational = next((call for call in operational_calls if call.get("account_id") == "sc-acc-31" and call.get("last_synced_at") is None), None)
        success_operational = next((call for call in operational_calls if call.get("account_id") == "sc-acc-31" and call.get("last_synced_at") is not None), None)
        self.assertIsNotNone(start_operational)
        self.assertIsNotNone(success_operational)
        self.assertEqual((start_operational or {}).get("platform"), "snapchat_ads")
        self.assertEqual((start_operational or {}).get("status"), "active")
        self.assertEqual((start_operational or {}).get("currency_code"), "USD")
        self.assertEqual((start_operational or {}).get("account_timezone"), "UTC")
        self.assertIsNotNone((start_operational or {}).get("sync_start_date"))

    def test_snapchat_sync_state_upsert_failure_is_non_blocking(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []

        original_set_running = snapchat_ads_api.backfill_job_store.set_running
        original_set_done = snapchat_ads_api.backfill_job_store.set_done
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_sync_runs_update = snapchat_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = snapchat_ads_api.sync_state_store.upsert_sync_state
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            snapchat_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            snapchat_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            snapchat_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-acc-7"}]

            snapchat_ads_api._run_snapchat_sync_job("sc-job-state-fail", client_id=7)
        finally:
            snapchat_ads_api.backfill_job_store.set_running = original_set_running
            snapchat_ads_api.backfill_job_store.set_done = original_set_done
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            snapchat_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertTrue(any(event == "running" and payload.get("job_id") == "sc-job-state-fail" for event, payload in captured_calls))
        self.assertTrue(any(event == "done" and payload.get("job_id") == "sc-job-state-fail" for event, payload in captured_calls))

    def test_snapchat_sync_state_skips_upsert_when_account_id_is_ambiguous(self):
        original_set_running = snapchat_ads_api.backfill_job_store.set_running
        original_set_done = snapchat_ads_api.backfill_job_store.set_done
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_sync_runs_update = snapchat_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = snapchat_ads_api.sync_state_store.upsert_sync_state
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.backfill_job_store.set_running = lambda job_id: None
            snapchat_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            snapchat_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            sync_state_calls: list[dict[str, object]] = []
            snapchat_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {"ok": True}
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-a"}, {"id": "sc-b"}]

            snapchat_ads_api._run_snapchat_sync_job("sc-job-amb", client_id=99)
        finally:
            snapchat_ads_api.backfill_job_store.set_running = original_set_running
            snapchat_ads_api.backfill_job_store.set_done = original_set_done
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            snapchat_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(sync_state_calls, [])

    def test_snapchat_operational_metadata_update_failure_is_non_blocking(self):
        captured_calls: list[tuple[str, dict[str, object]]] = []

        original_set_running = snapchat_ads_api.backfill_job_store.set_running
        original_set_done = snapchat_ads_api.backfill_job_store.set_done
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_sync_runs_update = snapchat_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = snapchat_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.backfill_job_store.set_running = lambda job_id: captured_calls.append(("running", {"job_id": job_id}))
            snapchat_ads_api.backfill_job_store.set_done = lambda job_id, result: captured_calls.append(("done", {"job_id": job_id, "result": result}))
            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            snapchat_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            snapchat_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("operational metadata unavailable"))
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-acc-7", "status": "active", "currency_code": "usd", "account_timezone": "UTC"}]

            snapchat_ads_api._run_snapchat_sync_job("sc-job-op-fail", client_id=7)
        finally:
            snapchat_ads_api.backfill_job_store.set_running = original_set_running
            snapchat_ads_api.backfill_job_store.set_done = original_set_done
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            snapchat_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertTrue(any(event == "running" and payload.get("job_id") == "sc-job-op-fail" for event, payload in captured_calls))
        self.assertTrue(any(event == "done" and payload.get("job_id") == "sc-job-op-fail" for event, payload in captured_calls))

    def test_snapchat_operational_metadata_skips_when_account_id_is_ambiguous(self):
        original_set_running = snapchat_ads_api.backfill_job_store.set_running
        original_set_done = snapchat_ads_api.backfill_job_store.set_done
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_sync_runs_update = snapchat_ads_api.sync_runs_store.update_sync_run_status
        original_sync_state_upsert = snapchat_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata
        original_list_accounts = snapchat_ads_api.client_registry_service.list_client_platform_accounts
        try:
            snapchat_ads_api.backfill_job_store.set_running = lambda job_id: None
            snapchat_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id}
            snapchat_ads_api.sync_runs_store.update_sync_run_status = lambda **kwargs: {"ok": True}
            snapchat_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}

            operational_calls: list[dict[str, object]] = []
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: operational_calls.append(kwargs) or {"ok": True}
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = lambda **kwargs: [{"id": "sc-a"}, {"id": "sc-b"}]

            snapchat_ads_api._run_snapchat_sync_job("sc-job-amb-op", client_id=99)
        finally:
            snapchat_ads_api.backfill_job_store.set_running = original_set_running
            snapchat_ads_api.backfill_job_store.set_done = original_set_done
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.sync_runs_store.update_sync_run_status = original_sync_runs_update
            snapchat_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            snapchat_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update
            snapchat_ads_api.client_registry_service.list_client_platform_accounts = original_list_accounts

        self.assertEqual(operational_calls, [])

    def test_snapchat_sync_now_job_status_memory_first_and_db_fallback(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = snapchat_ads_api.enforce_action_scope
        original_memory_get = snapchat_ads_api.backfill_job_store.get
        original_db_get = snapchat_ads_api.sync_runs_store.get_sync_run
        try:
            snapchat_ads_api.enforce_action_scope = lambda **kwargs: None
            snapchat_ads_api.backfill_job_store.get = lambda job_id: {"job_id": job_id, "status": "running", "source": "memory"} if job_id == "sc-memory" else None

            memory_response = snapchat_ads_api.sync_now_job_status("sc-memory", user=user)

            snapchat_ads_api.sync_runs_store.get_sync_run = lambda job_id: {
                "job_id": job_id,
                "platform": "snapchat_ads",
                "status": "done",
                "client_id": 66,
                "account_id": "sc-acc-66",
                "date_start": "2026-03-01",
                "date_end": "2026-03-01",
                "chunk_days": 1,
                "error": None,
                "metadata": {"source": "db"},
            }
            db_response = snapchat_ads_api.sync_now_job_status("sc-db", user=user)

            snapchat_ads_api.sync_runs_store.get_sync_run = lambda job_id: None
            with self.assertRaises(snapchat_ads_api.HTTPException) as ctx:
                snapchat_ads_api.sync_now_job_status("sc-missing", user=user)
        finally:
            snapchat_ads_api.enforce_action_scope = original_enforce
            snapchat_ads_api.backfill_job_store.get = original_memory_get
            snapchat_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(memory_response.get("source"), "memory")
        self.assertEqual(db_response.get("job_id"), "sc-db")
        self.assertEqual(db_response.get("status"), "done")
        self.assertEqual(db_response.get("account_id"), "sc-acc-66")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_snapchat_sync_now_job_status_db_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = snapchat_ads_api.enforce_action_scope
        original_memory_get = snapchat_ads_api.backfill_job_store.get
        original_db_get = snapchat_ads_api.sync_runs_store.get_sync_run
        try:
            snapchat_ads_api.enforce_action_scope = lambda **kwargs: None
            snapchat_ads_api.backfill_job_store.get = lambda job_id: None
            snapchat_ads_api.sync_runs_store.get_sync_run = lambda job_id: (_ for _ in ()).throw(RuntimeError("db unavailable"))
            with self.assertRaises(snapchat_ads_api.HTTPException) as ctx:
                snapchat_ads_api.sync_now_job_status("sc-db-error", user=user)
        finally:
            snapchat_ads_api.enforce_action_scope = original_enforce
            snapchat_ads_api.backfill_job_store.get = original_memory_get
            snapchat_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)

    def test_snapchat_legacy_sync_endpoint_still_calls_service(self):
        user = AuthUser(email="owner@example.com", role="agency_owner")

        original_enforce = snapchat_ads_api.enforce_action_scope
        original_rate_check = snapchat_ads_api.rate_limiter_service.check
        original_sync_client = snapchat_ads_api.snapchat_ads_service.sync_client
        original_audit_log = snapchat_ads_api.audit_log_service.log
        original_metrics_increment = snapchat_ads_api.snapchat_sync_metrics.increment
        original_metrics_snapshot = snapchat_ads_api.snapchat_sync_metrics.snapshot
        try:
            snapchat_ads_api.enforce_action_scope = lambda **kwargs: None
            snapchat_ads_api.rate_limiter_service.check = lambda *args, **kwargs: None
            snapchat_ads_api.snapchat_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id, "attempts": 1}
            snapchat_ads_api.audit_log_service.log = lambda **kwargs: None
            snapchat_ads_api.snapchat_sync_metrics.increment = lambda *args, **kwargs: None
            snapchat_ads_api.snapchat_sync_metrics.snapshot = lambda: {"sync_succeeded": 1}

            response = snapchat_ads_api.sync_snapchat_ads(client_id=56, user=user)
        finally:
            snapchat_ads_api.enforce_action_scope = original_enforce
            snapchat_ads_api.rate_limiter_service.check = original_rate_check
            snapchat_ads_api.snapchat_ads_service.sync_client = original_sync_client
            snapchat_ads_api.audit_log_service.log = original_audit_log
            snapchat_ads_api.snapchat_sync_metrics.increment = original_metrics_increment
            snapchat_ads_api.snapchat_sync_metrics.snapshot = original_metrics_snapshot

        self.assertEqual(response.get("status"), "ok")
        self.assertEqual(response.get("client_id"), 56)

    def test_pinterest_legacy_sync_endpoint_still_calls_service(self):
        user = AuthUser(email="owner@example.com", role="agency_owner")

        original_enforce = pinterest_ads_api.enforce_action_scope
        original_rate_check = pinterest_ads_api.rate_limiter_service.check
        original_sync_client = pinterest_ads_api.pinterest_ads_service.sync_client
        original_audit_log = pinterest_ads_api.audit_log_service.log
        original_metrics_increment = pinterest_ads_api.pinterest_sync_metrics.increment
        original_metrics_snapshot = pinterest_ads_api.pinterest_sync_metrics.snapshot
        try:
            pinterest_ads_api.enforce_action_scope = lambda **kwargs: None
            pinterest_ads_api.rate_limiter_service.check = lambda *args, **kwargs: None
            pinterest_ads_api.pinterest_ads_service.sync_client = lambda client_id: {"status": "ok", "client_id": client_id, "attempts": 1}
            pinterest_ads_api.audit_log_service.log = lambda **kwargs: None
            pinterest_ads_api.pinterest_sync_metrics.increment = lambda *args, **kwargs: None
            pinterest_ads_api.pinterest_sync_metrics.snapshot = lambda: {"sync_succeeded": 1}

            response = pinterest_ads_api.sync_pinterest_ads(client_id=55, user=user)
        finally:
            pinterest_ads_api.enforce_action_scope = original_enforce
            pinterest_ads_api.rate_limiter_service.check = original_rate_check
            pinterest_ads_api.pinterest_ads_service.sync_client = original_sync_client
            pinterest_ads_api.audit_log_service.log = original_audit_log
            pinterest_ads_api.pinterest_sync_metrics.increment = original_metrics_increment
            pinterest_ads_api.pinterest_sync_metrics.snapshot = original_metrics_snapshot

        self.assertEqual(response.get("status"), "ok")
        self.assertEqual(response.get("client_id"), 55)

    def test_google_sync_now_job_status_db_error_is_non_blocking(self):
        user = AuthUser(email="admin@example.com", role="agency_owner")

        original_enforce = google_ads_api.enforce_action_scope
        original_memory_get = google_ads_api.backfill_job_store.get
        original_db_get = google_ads_api.sync_runs_store.get_sync_run
        try:
            google_ads_api.enforce_action_scope = lambda **kwargs: None
            google_ads_api.backfill_job_store.get = lambda job_id: None

            def failing_db_get(job_id: str):
                raise RuntimeError("db unavailable")

            google_ads_api.sync_runs_store.get_sync_run = failing_db_get

            with self.assertRaises(google_ads_api.HTTPException) as ctx:
                google_ads_api.sync_now_job_status("job-db-error", user=user)
        finally:
            google_ads_api.enforce_action_scope = original_enforce
            google_ads_api.backfill_job_store.get = original_memory_get
            google_ads_api.sync_runs_store.get_sync_run = original_db_get

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(str(ctx.exception.detail), "job not found")

    def test_google_backfill_runner_updates_platform_account_operational_metadata_start_and_success(self):
        metadata_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        original_sync_state_upsert = google_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = google_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 3,
                "gaql_rows_fetched": 5,
                "db_rows_last_30_for_customer": 3,
                "reason_if_zero": None,
            }
            google_ads_api._mirror_sync_run_status = lambda **kwargs: None
            google_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}
            google_ads_api.client_registry_service.update_platform_account_operational_metadata = lambda **kwargs: metadata_calls.append(kwargs) or {
                "platform": kwargs.get("platform"),
                "account_id": kwargs.get("account_id"),
            }

            google_ads_api._run_google_backfill_job(
                "job-meta-ok",
                mapped_accounts=[
                    {
                        "client_id": 96,
                        "customer_id": "1234567890",
                        "status": "active",
                        "currency_code": "eur",
                        "account_timezone": "Europe/Bucharest",
                    }
                ],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status
            google_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            google_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertEqual(len(metadata_calls), 2)
        start_call = metadata_calls[0]
        success_call = metadata_calls[1]

        self.assertEqual(start_call.get("platform"), "google_ads")
        self.assertEqual(start_call.get("account_id"), "1234567890")
        self.assertEqual(start_call.get("status"), "active")
        self.assertEqual(start_call.get("currency_code"), "EUR")
        self.assertEqual(start_call.get("account_timezone"), "Europe/Bucharest")
        self.assertEqual(str(start_call.get("sync_start_date")), "2026-01-01")
        self.assertIsNone(start_call.get("last_synced_at"))

        self.assertEqual(success_call.get("platform"), "google_ads")
        self.assertEqual(success_call.get("account_id"), "1234567890")
        self.assertEqual(str(success_call.get("sync_start_date")), "2026-01-01")
        self.assertIsNotNone(success_call.get("last_synced_at"))

    def test_google_backfill_runner_operational_metadata_update_failure_is_non_blocking(self):
        done_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        original_sync_state_upsert = google_ads_api.sync_state_store.upsert_sync_state
        original_operational_update = google_ads_api.client_registry_service.update_platform_account_operational_metadata
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: done_calls.append(result)
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 1,
                "gaql_rows_fetched": 1,
                "db_rows_last_30_for_customer": 1,
                "reason_if_zero": None,
            }
            google_ads_api._mirror_sync_run_status = lambda **kwargs: None
            google_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: {"ok": True}

            def failing_operational_update(**kwargs):
                raise RuntimeError("operational metadata unavailable")

            google_ads_api.client_registry_service.update_platform_account_operational_metadata = failing_operational_update

            google_ads_api._run_google_backfill_job(
                "job-meta-fail",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status
            google_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert
            google_ads_api.client_registry_service.update_platform_account_operational_metadata = original_operational_update

        self.assertEqual(len(done_calls), 1)
        self.assertEqual(done_calls[0].get("status"), "ok")

    def test_google_backfill_runner_updates_sync_state_running_and_done_per_account(self):
        sync_state_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        original_sync_state_upsert = google_ads_api.sync_state_store.upsert_sync_state
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 3,
                "gaql_rows_fetched": 5,
                "db_rows_last_30_for_customer": 3,
                "reason_if_zero": None,
            }
            google_ads_api._mirror_sync_run_status = lambda **kwargs: None
            google_ads_api.sync_state_store.upsert_sync_state = lambda **kwargs: sync_state_calls.append(kwargs) or {
                "platform": kwargs.get("platform"),
                "account_id": kwargs.get("account_id"),
                "grain": kwargs.get("grain"),
            }

            google_ads_api._run_google_backfill_job(
                "job-state-ok",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status
            google_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert

        self.assertGreaterEqual(len(sync_state_calls), 2)
        first_call = sync_state_calls[0]
        last_call = sync_state_calls[-1]
        self.assertEqual(first_call.get("last_status"), "running")
        self.assertEqual(first_call.get("last_job_id"), "job-state-ok")
        self.assertEqual(first_call.get("account_id"), "1234567890")
        self.assertEqual(first_call.get("grain"), "account_daily")
        self.assertIsNone(first_call.get("error"))

        self.assertEqual(last_call.get("last_status"), "done")
        self.assertEqual(last_call.get("last_job_id"), "job-state-ok")
        self.assertEqual(str(last_call.get("last_successful_date")), "2026-01-31")
        self.assertIsNotNone(last_call.get("last_successful_at"))
        self.assertIsNone(last_call.get("error"))

    def test_google_backfill_runner_updates_sync_state_error_and_non_blocking_when_sync_state_fails(self):
        sync_state_calls: list[dict[str, object]] = []
        done_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        original_sync_state_upsert = google_ads_api.sync_state_store.upsert_sync_state
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: done_calls.append(result)

            def failing_sync_customer(**kwargs):
                raise RuntimeError("google down")

            google_ads_api.google_ads_service.sync_customer_for_client = failing_sync_customer
            google_ads_api._mirror_sync_run_status = lambda **kwargs: None

            def flaky_sync_state_upsert(**kwargs):
                sync_state_calls.append(kwargs)
                if str(kwargs.get("last_status")) == "running":
                    raise RuntimeError("sync_state unavailable")
                return {"platform": kwargs.get("platform")}

            google_ads_api.sync_state_store.upsert_sync_state = flaky_sync_state_upsert

            google_ads_api._run_google_backfill_job(
                "job-state-error",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status
            google_ads_api.sync_state_store.upsert_sync_state = original_sync_state_upsert

        self.assertGreaterEqual(len(sync_state_calls), 2)
        self.assertEqual(sync_state_calls[0].get("last_status"), "running")
        self.assertEqual(sync_state_calls[-1].get("last_status"), "error")
        self.assertIn("google down", str(sync_state_calls[-1].get("error") or ""))
        self.assertEqual(len(done_calls), 1)
        self.assertIn("errors_summary", done_calls[0])

    def test_google_backfill_runner_updates_sync_runs_running_and_done(self):
        status_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: None
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 3,
                "gaql_rows_fetched": 5,
                "db_rows_last_30_for_customer": 3,
                "reason_if_zero": None,
            }
            google_ads_api._mirror_sync_run_status = lambda **kwargs: status_calls.append(kwargs)

            google_ads_api._run_google_backfill_job(
                "job-1",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status

        self.assertGreaterEqual(len(status_calls), 2)
        self.assertEqual(status_calls[0].get("status"), "running")
        self.assertTrue(status_calls[0].get("mark_started"))
        self.assertEqual(status_calls[-1].get("status"), "done")
        self.assertTrue(status_calls[-1].get("mark_finished"))

    def test_google_backfill_runner_updates_sync_runs_error_when_runner_fails(self):
        status_calls: list[dict[str, object]] = []
        errors: list[str] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_error = google_ads_api.backfill_job_store.set_error
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_mirror_status = google_ads_api._mirror_sync_run_status
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_error = lambda job_id, error: errors.append(str(error))

            def boom_set_done(job_id, result):
                raise RuntimeError("explode")

            google_ads_api.backfill_job_store.set_done = boom_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 1,
                "gaql_rows_fetched": 1,
                "db_rows_last_30_for_customer": 1,
                "reason_if_zero": None,
            }
            google_ads_api._mirror_sync_run_status = lambda **kwargs: status_calls.append(kwargs)

            google_ads_api._run_google_backfill_job(
                "job-2",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_error = original_set_error
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api._mirror_sync_run_status = original_mirror_status

        self.assertGreaterEqual(len(status_calls), 2)
        self.assertEqual(status_calls[0].get("status"), "running")
        self.assertEqual(status_calls[-1].get("status"), "error")
        self.assertTrue(status_calls[-1].get("mark_finished"))
        self.assertIn("explode", str(status_calls[-1].get("error") or ""))
        self.assertTrue(any("explode" in item for item in errors))

    def test_google_backfill_runner_continues_when_sync_runs_status_mirror_fails(self):
        done_calls: list[dict[str, object]] = []

        original_set_running = google_ads_api.backfill_job_store.set_running
        original_set_done = google_ads_api.backfill_job_store.set_done
        original_sync_customer = google_ads_api.google_ads_service.sync_customer_for_client
        original_update_status = google_ads_api.sync_runs_store.update_sync_run_status
        try:
            google_ads_api.backfill_job_store.set_running = lambda job_id: None
            google_ads_api.backfill_job_store.set_done = lambda job_id, result: done_calls.append(result)
            google_ads_api.google_ads_service.sync_customer_for_client = lambda **kwargs: {
                "inserted_rows": 1,
                "gaql_rows_fetched": 1,
                "db_rows_last_30_for_customer": 1,
                "reason_if_zero": None,
            }

            def flaky_update(**kwargs):
                raise RuntimeError("mirror down")

            google_ads_api.sync_runs_store.update_sync_run_status = flaky_update

            google_ads_api._run_google_backfill_job(
                "job-3",
                mapped_accounts=[{"client_id": 96, "customer_id": "1234567890"}],
                resolved_start=date(2026, 1, 1),
                resolved_end=date(2026, 1, 31),
                days=31,
                chunk_days=7,
                requested_client_id=96,
            )
        finally:
            google_ads_api.backfill_job_store.set_running = original_set_running
            google_ads_api.backfill_job_store.set_done = original_set_done
            google_ads_api.google_ads_service.sync_customer_for_client = original_sync_customer
            google_ads_api.sync_runs_store.update_sync_run_status = original_update_status

        self.assertEqual(len(done_calls), 1)
        self.assertEqual(done_calls[0].get("status"), "ok")

    def test_sync_run_chunks_store_schema_missing_raises_clear_error(self):
        sync_run_chunks_store._schema_initialized = False

        class _FakeCursor:
            def execute(self, query, params=None):
                return None

            def fetchone(self):
                return (None,)

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

        original_connect = sync_run_chunks_store._connect
        try:
            sync_run_chunks_store._connect = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                sync_run_chunks_store.list_sync_run_chunks("missing")
        finally:
            sync_run_chunks_store._connect = original_connect
            sync_run_chunks_store._schema_initialized = False

        self.assertIn("Database schema for sync_run_chunks is not ready; run DB migrations", str(ctx.exception))

    def test_sync_run_chunks_store_create_list_update_lifecycle(self):
        sync_run_chunks_store._schema_initialized = False
        state: dict[tuple[str, int], dict[str, object]] = {}
        next_id = {"value": 0}
        tick = {"value": 0}

        def _now() -> str:
            tick["value"] += 1
            return f"2026-03-01T00:00:{tick['value']:02d}+00:00"

        class _FakeCursor:
            _row: tuple[object, ...] | None
            _rows: list[tuple[object, ...]]

            def __init__(self):
                self._row = None
                self._rows = []

            def execute(self, query, params=None):
                sql = str(query)

                if "SELECT to_regclass('public.sync_run_chunks')" in sql:
                    self._row = ("sync_run_chunks",)
                    return

                if "INSERT INTO sync_run_chunks" in sql:
                    job_id, chunk_index, status, date_start, date_end, metadata_json = params
                    key = (str(job_id), int(chunk_index))
                    next_id["value"] += 1
                    now_value = _now()
                    state[key] = {
                        "id": int(next_id["value"]),
                        "job_id": str(job_id),
                        "chunk_index": int(chunk_index),
                        "status": str(status),
                        "date_start": str(date_start),
                        "date_end": str(date_end),
                        "created_at": now_value,
                        "updated_at": now_value,
                        "started_at": None,
                        "finished_at": None,
                        "error": None,
                        "metadata": str(metadata_json),
                    }
                    return

                if "UPDATE sync_run_chunks" in sql:
                    status, mark_started, mark_finished, error, metadata_json, job_id, chunk_index = params
                    key = (str(job_id), int(chunk_index))
                    row = state.get(key)
                    if row is None:
                        return
                    row["status"] = str(status)
                    row["updated_at"] = _now()
                    if bool(mark_started) and row.get("started_at") is None:
                        row["started_at"] = row["updated_at"]
                    if bool(mark_finished):
                        row["finished_at"] = row["updated_at"]
                    if error is not None:
                        row["error"] = str(error)
                    if metadata_json is not None:
                        row["metadata"] = str(metadata_json)
                    return

                if "FROM sync_run_chunks" in sql and "ORDER BY chunk_index ASC" in sql:
                    job_id = str(params[0])
                    rows = [
                        (
                            row["id"],
                            row["job_id"],
                            row["chunk_index"],
                            row["status"],
                            row["date_start"],
                            row["date_end"],
                            row["created_at"],
                            row["updated_at"],
                            row["started_at"],
                            row["finished_at"],
                            row["error"],
                            row["metadata"],
                        )
                        for row in sorted(state.values(), key=lambda item: int(item["chunk_index"]))
                        if str(row["job_id"]) == job_id
                    ]
                    self._rows = rows
                    return

                raise AssertionError(f"Unexpected SQL: {sql}")

            def fetchone(self):
                return self._row

            def fetchall(self):
                return list(self._rows)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original_connect = sync_run_chunks_store._connect
        try:
            sync_run_chunks_store._connect = lambda: _FakeConn()

            created_2 = sync_run_chunks_store.create_sync_run_chunk(
                job_id="job-1",
                chunk_index=2,
                status="queued",
                date_start=date(2026, 1, 15),
                date_end=date(2026, 1, 21),
            )
            created_0 = sync_run_chunks_store.create_sync_run_chunk(
                job_id="job-1",
                chunk_index=0,
                status="queued",
                date_start=date(2026, 1, 1),
                date_end=date(2026, 1, 7),
                metadata={"range": "first"},
            )

            chunks_before = sync_run_chunks_store.list_sync_run_chunks("job-1")

            started = sync_run_chunks_store.update_sync_run_chunk_status(
                job_id="job-1",
                chunk_index=0,
                status="running",
                mark_started=True,
            )
            finished = sync_run_chunks_store.update_sync_run_chunk_status(
                job_id="job-1",
                chunk_index=0,
                status="done",
                mark_finished=True,
                error="chunk done",
                metadata={"rows": 10},
            )
            chunks_after = sync_run_chunks_store.list_sync_run_chunks("job-1")
        finally:
            sync_run_chunks_store._connect = original_connect
            sync_run_chunks_store._schema_initialized = False

        self.assertIsNotNone(created_2)
        self.assertIsNotNone(created_0)
        self.assertEqual(created_2["job_id"], "job-1")
        self.assertEqual(created_2["chunk_index"], 2)
        self.assertEqual(created_2["status"], "queued")
        self.assertEqual(created_2["metadata"], {})

        self.assertEqual([item["chunk_index"] for item in chunks_before], [0, 2])
        self.assertEqual(chunks_before[0]["metadata"].get("range"), "first")

        self.assertEqual(started["status"], "running")
        self.assertIsNotNone(started["started_at"])

        self.assertEqual(finished["status"], "done")
        self.assertIsNotNone(finished["finished_at"])
        self.assertEqual(finished["error"], "chunk done")
        self.assertEqual((finished.get("metadata") or {}).get("rows"), 10)
        self.assertNotEqual(started["updated_at"], finished["updated_at"])

        first_chunk = next(item for item in chunks_after if int(item["chunk_index"]) == 0)
        self.assertEqual(first_chunk["status"], "done")
        self.assertEqual(first_chunk["error"], "chunk done")



    def test_client_business_inputs_import_normalize_row_defaults_and_types(self):
        row = normalize_client_business_input_row(
            {
                "client_id": "21",
                "period_start": "2026-03-05",
                "period_end": "",
                "period_grain": " DAY ",
                "applicants": "10",
                "approved_applicants": "2.0",
                "actual_revenue": "1234.56",
                "target_revenue": "2000",
                "cogs": "300.5",
                "taxes": "100",
                "gross_profit": "834.06",
                "contribution_profit": "700.00",
                "notes": "",
                "source": "",
                "metadata": "",
            }
        )

        self.assertEqual(row["client_id"], 21)
        self.assertEqual(row["period_grain"], "day")
        self.assertEqual(row["period_start"], date(2026, 3, 5))
        self.assertEqual(row["period_end"], date(2026, 3, 5))
        self.assertEqual(row["applicants"], 10)
        self.assertEqual(row["approved_applicants"], 2)
        self.assertEqual(row["actual_revenue"], 1234.56)
        self.assertEqual(row["target_revenue"], 2000.0)
        self.assertEqual(row["cogs"], 300.5)
        self.assertEqual(row["taxes"], 100.0)
        self.assertEqual(row["gross_profit"], 834.06)
        self.assertEqual(row["contribution_profit"], 700.0)
        self.assertIsNone(row["notes"])
        self.assertEqual(row["source"], "manual")
        self.assertEqual(row["metadata"], {})

    def test_client_business_inputs_import_validate_accepts_day_and_week(self):
        day_row = normalize_client_business_input_row(
            {
                "client_id": 11,
                "period_start": "2026-03-07",
                "period_grain": "day",
            }
        )
        validate_client_business_input_row(day_row)

        week_row = normalize_client_business_input_row(
            {
                "client_id": 11,
                "period_start": "2026-03-03",
                "period_end": "2026-03-09",
                "period_grain": "week",
            }
        )
        validate_client_business_input_row(week_row)

    def test_client_business_inputs_import_validate_rejects_invalid_shapes(self):
        with self.assertRaises(ValueError):
            validate_client_business_input_row(
                normalize_client_business_input_row(
                    {
                        "client_id": 11,
                        "period_start": "2026-03-01",
                        "period_end": "2026-03-02",
                        "period_grain": "day",
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_client_business_input_row(
                normalize_client_business_input_row(
                    {
                        "client_id": 11,
                        "period_start": "2026-03-10",
                        "period_end": "2026-03-09",
                        "period_grain": "week",
                    }
                )
            )

        with self.assertRaises(ValueError):
            validate_client_business_input_row(
                normalize_client_business_input_row(
                    {
                        "client_id": 11,
                        "period_start": "2026-03-01",
                        "period_end": "2026-03-01",
                        "period_grain": "month",
                    }
                )
            )

    def test_client_business_inputs_import_bulk_continues_on_errors_and_upserts(self):
        saved: dict[tuple[int, date, date, str], dict[str, object]] = {}

        def _fake_upsert(**kwargs):
            key = (int(kwargs["client_id"]), kwargs["period_start"], kwargs["period_end"], str(kwargs["period_grain"]))
            current = dict(saved.get(key, {}))
            current.update(kwargs)
            current["id"] = current.get("id", len(saved) + 1)
            saved[key] = current
            return dict(current)

        original_upsert = client_business_inputs_store.upsert_client_business_input
        try:
            client_business_inputs_store.upsert_client_business_input = _fake_upsert
            result = import_client_business_inputs(
                [
                    {
                        "client_id": "31",
                        "period_start": "2026-03-01",
                        "period_grain": "day",
                        "applicants": "10",
                    },
                    {
                        "client_id": "31",
                        "period_start": "2026-03-01",
                        "period_grain": "day",
                        "applicants": "11",
                    },
                    {
                        "client_id": "31",
                        "period_start": "2026-03-10",
                        "period_end": "2026-03-09",
                        "period_grain": "week",
                    },
                ]
            )
        finally:
            client_business_inputs_store.upsert_client_business_input = original_upsert

        self.assertEqual(result["processed"], 3)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(int(result["errors"][0]["row_index"]), 2)
        self.assertEqual(len(saved), 1)

        key = (31, date(2026, 3, 1), date(2026, 3, 1), "day")
        self.assertEqual(saved[key]["applicants"], 11)

    def test_client_business_inputs_store_schema_missing_raises_clear_error(self):
        client_business_inputs_store._schema_initialized = False

        class _FakeCursor:
            def execute(self, query, params=None):
                return None

            def fetchone(self):
                return (None,)

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

        original_connect = client_business_inputs_store._connect
        try:
            client_business_inputs_store._connect = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                client_business_inputs_store.initialize_schema()
        finally:
            client_business_inputs_store._connect = original_connect
            client_business_inputs_store._schema_initialized = False

        self.assertIn("Database schema for client_business_inputs is not ready; run DB migrations", str(ctx.exception))

    def test_client_business_inputs_store_get_upsert_list_lifecycle(self):
        client_business_inputs_store._schema_initialized = False

        rows_by_key: dict[tuple[int, str, str, str], dict[str, object]] = {}
        next_id = 1
        tick = 0

        def _ts() -> str:
            nonlocal tick
            tick += 1
            return f"2026-03-01T00:00:{tick:02d}+00:00"

        def _row_tuple(row: dict[str, object]) -> tuple[object, ...]:
            return (
                row["id"],
                row["client_id"],
                row["period_start"],
                row["period_end"],
                row["period_grain"],
                row.get("applicants"),
                row.get("approved_applicants"),
                row.get("actual_revenue"),
                row.get("target_revenue"),
                row.get("cogs"),
                row.get("taxes"),
                row.get("gross_profit"),
                row.get("contribution_profit"),
                row.get("notes"),
                row.get("source"),
                row.get("metadata"),
                row.get("created_at"),
                row.get("updated_at"),
            )

        class _FakeCursor:
            def __init__(self):
                self._one = None
                self._all = []

            def execute(self, query, params=None):
                nonlocal next_id
                sql = " ".join(str(query).split()).lower()
                args = tuple(params or ())

                if "to_regclass('public.client_business_inputs')" in sql:
                    self._one = ("client_business_inputs",)
                    self._all = []
                    return

                if "from client_business_inputs" in sql and "where client_id = %s and period_start = %s and period_end = %s and period_grain = %s" in sql:
                    key = (int(args[0]), str(args[1]), str(args[2]), str(args[3]))
                    row = rows_by_key.get(key)
                    self._one = _row_tuple(row) if row is not None else None
                    self._all = []
                    return

                if "insert into client_business_inputs" in sql:
                    key = (int(args[0]), str(args[1]), str(args[2]), str(args[3]))
                    created = rows_by_key.get(key)
                    now_ts = _ts()
                    if created is None:
                        row = {
                            "id": next_id,
                            "client_id": int(args[0]),
                            "period_start": str(args[1]),
                            "period_end": str(args[2]),
                            "period_grain": str(args[3]),
                            "applicants": args[4],
                            "approved_applicants": args[5],
                            "actual_revenue": args[6],
                            "target_revenue": args[7],
                            "cogs": args[8],
                            "taxes": args[9],
                            "gross_profit": args[10],
                            "contribution_profit": args[11],
                            "notes": args[12],
                            "source": args[13],
                            "metadata": args[14],
                            "created_at": now_ts,
                            "updated_at": now_ts,
                        }
                        rows_by_key[key] = row
                        next_id += 1
                    else:
                        created.update(
                            {
                                "applicants": args[4],
                                "approved_applicants": args[5],
                                "actual_revenue": args[6],
                                "target_revenue": args[7],
                                "cogs": args[8],
                                "taxes": args[9],
                                "gross_profit": args[10],
                                "contribution_profit": args[11],
                                "notes": args[12],
                                "source": args[13],
                                "metadata": args[14],
                                "updated_at": now_ts,
                            }
                        )
                    self._one = None
                    self._all = []
                    return

                if "from client_business_inputs" in sql and "order by period_start asc, period_end asc" in sql:
                    client_id = int(args[0])
                    period_grain = str(args[1])
                    date_from = args[2] if len(args) >= 3 else None
                    date_to = args[3] if len(args) >= 4 else None

                    def _keep(row: dict[str, object]) -> bool:
                        if int(row["client_id"]) != client_id or str(row["period_grain"]) != period_grain:
                            return False
                        row_start = date.fromisoformat(str(row["period_start"]))
                        row_end = date.fromisoformat(str(row["period_end"]))
                        if date_from is not None and row_end < date_from:
                            return False
                        if date_to is not None and row_start > date_to:
                            return False
                        return True

                    selected = [_row_tuple(r) for r in rows_by_key.values() if _keep(r)]
                    selected.sort(key=lambda r: (str(r[2]), str(r[3])))
                    self._all = selected
                    self._one = None
                    return

                raise AssertionError(f"Unexpected SQL: {query}")

            def fetchone(self):
                return self._one

            def fetchall(self):
                return list(self._all)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original_connect = client_business_inputs_store._connect
        try:
            client_business_inputs_store._connect = lambda: _FakeConn()

            missing = client_business_inputs_store.get_client_business_input(
                11,
                date(2026, 3, 1),
                date(2026, 3, 1),
                "day",
            )
            self.assertIsNone(missing)

            created = client_business_inputs_store.upsert_client_business_input(
                client_id=11,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 1),
                period_grain="day",
                applicants=100,
                approved_applicants=10,
                actual_revenue=1200.5,
                target_revenue=2000.0,
                cogs=300.0,
                taxes=100.0,
                gross_profit=800.5,
                contribution_profit=700.0,
                notes="initial",
                source="manual",
                metadata={"origin": "sheet"},
            )
            self.assertIsNotNone(created)
            self.assertEqual(created["applicants"], 100)
            self.assertEqual(created["approved_applicants"], 10)
            self.assertEqual(created["actual_revenue"], 1200.5)
            self.assertEqual(created["target_revenue"], 2000.0)
            self.assertEqual(created["cogs"], 300.0)
            self.assertEqual(created["taxes"], 100.0)
            self.assertEqual(created["gross_profit"], 800.5)
            self.assertEqual(created["contribution_profit"], 700.0)
            self.assertEqual(created["notes"], "initial")
            self.assertEqual(created["source"], "manual")
            self.assertEqual(created["metadata"], {"origin": "sheet"})
            first_updated_at = str(created["updated_at"])

            updated = client_business_inputs_store.upsert_client_business_input(
                client_id=11,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 1),
                period_grain="day",
                applicants=120,
                approved_applicants=15,
                actual_revenue=None,
                target_revenue=2500.0,
                cogs=None,
                taxes=90.0,
                gross_profit=None,
                contribution_profit=760.0,
                notes=None,
                source=None,
                metadata=None,
            )
            self.assertIsNotNone(updated)
            self.assertEqual(updated["applicants"], 120)
            self.assertEqual(updated["approved_applicants"], 15)
            self.assertIsNone(updated["actual_revenue"])
            self.assertEqual(updated["target_revenue"], 2500.0)
            self.assertIsNone(updated["cogs"])
            self.assertEqual(updated["taxes"], 90.0)
            self.assertIsNone(updated["gross_profit"])
            self.assertEqual(updated["contribution_profit"], 760.0)
            self.assertIsNone(updated["notes"])
            self.assertEqual(updated["source"], "manual")
            self.assertEqual(updated["metadata"], {})
            self.assertNotEqual(first_updated_at, str(updated["updated_at"]))

            self.assertEqual(len(rows_by_key), 1)

            client_business_inputs_store.upsert_client_business_input(
                client_id=11,
                period_start=date(2026, 3, 3),
                period_end=date(2026, 3, 9),
                period_grain="week",
                applicants=330,
            )
            client_business_inputs_store.upsert_client_business_input(
                client_id=11,
                period_start=date(2026, 3, 10),
                period_end=date(2026, 3, 16),
                period_grain="week",
                applicants=440,
            )

            week_rows = client_business_inputs_store.list_client_business_inputs(
                client_id=11,
                period_grain="week",
            )
            self.assertEqual(len(week_rows), 2)
            self.assertEqual(week_rows[0]["period_start"], "2026-03-03")
            self.assertEqual(week_rows[1]["period_start"], "2026-03-10")

            week_filtered = client_business_inputs_store.list_client_business_inputs(
                client_id=11,
                period_grain="week",
                date_from=date(2026, 3, 8),
                date_to=date(2026, 3, 12),
            )
            self.assertEqual(len(week_filtered), 2)

            day_rows = client_business_inputs_store.list_client_business_inputs(
                client_id=11,
                period_grain="day",
                date_from=date(2026, 3, 1),
                date_to=date(2026, 3, 1),
            )
            self.assertEqual(len(day_rows), 1)
            self.assertEqual(day_rows[0]["period_grain"], "day")
        finally:
            client_business_inputs_store._connect = original_connect
            client_business_inputs_store._schema_initialized = False

    def test_sync_state_store_schema_missing_raises_clear_error(self):
        sync_state_store._schema_initialized = False

        class _FakeCursor:
            def execute(self, query, params=None):
                return None

            def fetchone(self):
                return (None,)

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

        original_connect = sync_state_store._connect
        try:
            sync_state_store._connect = lambda: _FakeConn()
            with self.assertRaises(RuntimeError) as ctx:
                sync_state_store.get_sync_state("google_ads", "123", "daily")
        finally:
            sync_state_store._connect = original_connect
            sync_state_store._schema_initialized = False

        self.assertIn("Database schema for sync_state is not ready; run DB migrations", str(ctx.exception))

    def test_sync_state_store_get_and_upsert_lifecycle(self):
        sync_state_store._schema_initialized = False
        state: dict[tuple[str, str, str], dict[str, object]] = {}
        tick = {"value": 0}

        def _now() -> str:
            tick["value"] += 1
            return f"2026-03-01T00:00:{tick['value']:02d}+00:00"

        class _FakeCursor:
            _row: tuple[object, ...] | None

            def __init__(self):
                self._row = None

            def execute(self, query, params=None):
                sql = str(query)

                if "SELECT to_regclass('public.sync_state')" in sql:
                    self._row = ("sync_state",)
                    return

                if "INSERT INTO sync_state" in sql and "ON CONFLICT (platform, account_id, grain)" in sql:
                    (
                        platform,
                        account_id,
                        grain,
                        last_status,
                        last_job_id,
                        last_attempted_at,
                        last_successful_at,
                        last_successful_date,
                        error,
                        metadata_json,
                    ) = params
                    key = (str(platform), str(account_id), str(grain))
                    existing = state.get(key)
                    if existing is None:
                        now_value = _now()
                        state[key] = {
                            "platform": str(platform),
                            "account_id": str(account_id),
                            "grain": str(grain),
                            "last_status": last_status,
                            "last_job_id": last_job_id,
                            "last_attempted_at": str(last_attempted_at) if last_attempted_at is not None else None,
                            "last_successful_at": str(last_successful_at) if last_successful_at is not None else None,
                            "last_successful_date": str(last_successful_date) if last_successful_date is not None else None,
                            "error": error,
                            "metadata": str(metadata_json),
                            "created_at": now_value,
                            "updated_at": now_value,
                        }
                    else:
                        existing["last_status"] = last_status
                        existing["last_job_id"] = last_job_id
                        existing["last_attempted_at"] = str(last_attempted_at) if last_attempted_at is not None else None
                        existing["last_successful_at"] = str(last_successful_at) if last_successful_at is not None else None
                        existing["last_successful_date"] = str(last_successful_date) if last_successful_date is not None else None
                        existing["error"] = error
                        existing["metadata"] = str(metadata_json)
                        existing["updated_at"] = _now()
                    return

                if "FROM sync_state" in sql and "WHERE platform = %s AND account_id = %s AND grain = %s" in sql:
                    key = (str(params[0]), str(params[1]), str(params[2]))
                    row = state.get(key)
                    if row is None:
                        self._row = None
                    else:
                        self._row = (
                            row["platform"],
                            row["account_id"],
                            row["grain"],
                            row["last_status"],
                            row["last_job_id"],
                            row["last_attempted_at"],
                            row["last_successful_at"],
                            row["last_successful_date"],
                            row["error"],
                            row["metadata"],
                            row["created_at"],
                            row["updated_at"],
                        )
                    return

                raise AssertionError(f"Unexpected SQL: {sql}")

            def fetchone(self):
                return self._row

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original_connect = sync_state_store._connect
        try:
            sync_state_store._connect = lambda: _FakeConn()

            missing = sync_state_store.get_sync_state("google_ads", "123", "daily")

            created = sync_state_store.upsert_sync_state(
                platform="google_ads",
                account_id="123",
                grain="daily",
                last_status="running",
                last_job_id="job-1",
                error="temporary failure",
                metadata={"chunk_days": 7},
            )
            updated = sync_state_store.upsert_sync_state(
                platform="google_ads",
                account_id="123",
                grain="daily",
                last_status="done",
                last_job_id="job-2",
                last_attempted_at=datetime.fromisoformat("2026-03-01T00:00:10+00:00"),
                last_successful_at=datetime.fromisoformat("2026-03-01T00:00:12+00:00"),
                last_successful_date=date(2026, 2, 28),
                error=None,
                metadata={"rows": 42},
            )
            fetched = sync_state_store.get_sync_state("google_ads", "123", "daily")
        finally:
            sync_state_store._connect = original_connect
            sync_state_store._schema_initialized = False

        self.assertIsNone(missing)

        self.assertIsNotNone(created)
        self.assertEqual(created.get("platform"), "google_ads")
        self.assertEqual(created.get("account_id"), "123")
        self.assertEqual(created.get("grain"), "daily")
        self.assertEqual(created.get("last_status"), "running")
        self.assertEqual(created.get("last_job_id"), "job-1")
        self.assertEqual(created.get("error"), "temporary failure")
        self.assertEqual((created.get("metadata") or {}).get("chunk_days"), 7)

        self.assertIsNotNone(updated)
        self.assertEqual(updated.get("last_status"), "done")
        self.assertEqual(updated.get("last_job_id"), "job-2")
        self.assertEqual(updated.get("last_successful_date"), "2026-02-28")
        self.assertEqual(updated.get("last_successful_at"), "2026-03-01 00:00:12+00:00")
        self.assertIsNone(updated.get("error"))
        self.assertEqual((updated.get("metadata") or {}).get("rows"), 42)
        self.assertNotEqual(created.get("updated_at"), updated.get("updated_at"))

        self.assertEqual(len(state), 1)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.get("last_status"), "done")
        self.assertIsNone(fetched.get("error"))

    def test_sync_runs_store_create_get_update_lifecycle(self):
        sync_runs_store._schema_initialized = False
        state: dict[str, dict[str, object]] = {}
        tick = {"value": 0}

        def _now() -> str:
            tick["value"] += 1
            return f"2026-03-01T00:00:{tick['value']:02d}+00:00"

        class _FakeCursor:
            _row: tuple[object, ...] | None

            def __init__(self):
                self._row = None

            def execute(self, query, params=None):
                sql = str(query)
                if "SELECT to_regclass('public.sync_runs')" in sql:
                    self._row = ("sync_runs",)
                    return

                if "INSERT INTO sync_runs" in sql:
                    job_id, platform, status, client_id, account_id, date_start, date_end, chunk_days, metadata_json = params
                    now_value = _now()
                    state[str(job_id)] = {
                        "job_id": str(job_id),
                        "platform": str(platform),
                        "status": str(status),
                        "client_id": client_id,
                        "account_id": account_id,
                        "date_start": str(date_start),
                        "date_end": str(date_end),
                        "chunk_days": int(chunk_days),
                        "created_at": now_value,
                        "updated_at": now_value,
                        "started_at": None,
                        "finished_at": None,
                        "error": None,
                        "metadata": str(metadata_json),
                    }
                    return

                if "UPDATE sync_runs" in sql:
                    status, mark_started, mark_finished, error, metadata_json, job_id = params
                    row = state.get(str(job_id))
                    if row is None:
                        return
                    row["status"] = str(status)
                    row["updated_at"] = _now()
                    if bool(mark_started) and row.get("started_at") is None:
                        row["started_at"] = _now()
                    if bool(mark_finished):
                        row["finished_at"] = _now()
                    if error is not None:
                        row["error"] = str(error)
                    if metadata_json is not None:
                        row["metadata"] = str(metadata_json)
                    return

                if "FROM sync_runs" in sql and "WHERE job_id = %s" in sql:
                    row = state.get(str(params[0]))
                    if row is None:
                        self._row = None
                    else:
                        self._row = (
                            row["job_id"],
                            row["platform"],
                            row["status"],
                            row["client_id"],
                            row["account_id"],
                            row["date_start"],
                            row["date_end"],
                            row["chunk_days"],
                            row["created_at"],
                            row["updated_at"],
                            row["started_at"],
                            row["finished_at"],
                            row["error"],
                            row["metadata"],
                        )
                    return

                raise AssertionError(f"Unexpected SQL: {sql}")

            def fetchone(self):
                return self._row

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class _FakeConn:
            def cursor(self):
                return _FakeCursor()

            def commit(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        original_connect = sync_runs_store._connect
        try:
            sync_runs_store._connect = lambda: _FakeConn()

            created = sync_runs_store.create_sync_run(
                job_id="job-1",
                platform="google_ads",
                status="queued",
                date_start=date(2026, 1, 1),
                date_end=date(2026, 1, 7),
                chunk_days=7,
                client_id=96,
                account_id="1234567890",
                metadata={"source": "test"},
            )
            self.assertIsNotNone(created)
            self.assertEqual(created["job_id"], "job-1")
            self.assertEqual(created["status"], "queued")
            self.assertEqual(created["metadata"], {"source": "test"})

            fetched = sync_runs_store.get_sync_run("job-1")
            self.assertEqual(fetched["job_id"], "job-1")
            self.assertEqual(fetched["platform"], "google_ads")

            updated_running = sync_runs_store.update_sync_run_status(
                job_id="job-1",
                status="running",
                mark_started=True,
            )
            self.assertEqual(updated_running["status"], "running")
            self.assertIsNotNone(updated_running["started_at"])
            updated_at_running = updated_running["updated_at"]

            updated_done = sync_runs_store.update_sync_run_status(
                job_id="job-1",
                status="error",
                mark_finished=True,
                error="boom",
                metadata={"step": "chunk-2"},
            )
            self.assertEqual(updated_done["status"], "error")
            self.assertEqual(updated_done["error"], "boom")
            self.assertEqual(updated_done["metadata"], {"step": "chunk-2"})
            self.assertIsNotNone(updated_done["finished_at"])
            self.assertNotEqual(updated_at_running, updated_done["updated_at"])
        finally:
            sync_runs_store._connect = original_connect
            sync_runs_store._schema_initialized = False

    def test_client_dashboard_query_filters_by_date_range(self):
        query = unified_dashboard_service._client_reports_query()

        self.assertIn("WHERE resolved_client_id = %s", query)
        self.assertIn("AND report_date BETWEEN %s AND %s", query)

    def test_agency_dashboard_rows_are_converted_to_ron_by_day_currency(self):
        original_rate = unified_dashboard_service._get_fx_rate_to_ron
        try:
            unified_dashboard_service._get_fx_rate_to_ron = lambda **kwargs: {"USD": 5.0, "EUR": 4.0, "RON": 1.0}.get(kwargs.get("currency_code"), 1.0)
            totals, spend_by_client_ron, spend_by_client_native, client_currency, row_count = unified_dashboard_service._aggregate_agency_rows(
                [
                    (date(2026, 2, 1), 10, "USD", 100.0, 1000, 100, 10, 50.0),
                    (date(2026, 2, 1), 10, "RON", 200.0, 2000, 200, 20, 100.0),
                    (date(2026, 2, 1), 11, "EUR", 50.0, 500, 50, 5, 25.0),
                ]
            )
        finally:
            unified_dashboard_service._get_fx_rate_to_ron = original_rate

        self.assertEqual(row_count, 3)
        self.assertEqual(round(float(totals["spend"]), 2), 900.0)
        self.assertEqual(round(float(totals["revenue"]), 2), 450.0)
        self.assertEqual(int(totals["impressions"]), 3500)
        self.assertEqual(int(totals["clicks"]), 350)
        self.assertEqual(int(totals["conversions"]), 35)
        self.assertEqual(round(spend_by_client_ron[10], 2), 700.0)
        self.assertEqual(round(spend_by_client_ron[11], 2), 200.0)
        self.assertEqual(round(spend_by_client_native[10], 2), 300.0)
        self.assertEqual(round(spend_by_client_native[11], 2), 50.0)
        self.assertEqual(client_currency[10], "USD")
        self.assertEqual(client_currency[11], "EUR")

    # Sprint 3 coverage (Meta + unified dashboard)
    def test_meta_ads_status_pending_when_placeholder(self):
        os.environ["META_ACCESS_TOKEN"] = "your_meta_access_token"
        status = meta_ads_service.integration_status()
        self.assertEqual(status["status"], "pending")

    def test_meta_ads_sync_fails_with_placeholder_token(self):
        os.environ["META_ACCESS_TOKEN"] = "your_meta_access_token"
        with self.assertRaises(MetaAdsIntegrationError):
            meta_ads_service.sync_client(client_id=2)

    def test_unified_dashboard_consolidates_all_platforms(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        os.environ["FF_TIKTOK_INTEGRATION"] = "1"
        os.environ["FF_PINTEREST_INTEGRATION"] = "1"
        os.environ["FF_SNAPCHAT_INTEGRATION"] = "1"

        google_snapshot = google_ads_service.sync_client(client_id=3)
        meta_snapshot = meta_ads_service.sync_client(client_id=3)
        tiktok_snapshot = tiktok_ads_service.sync_client(client_id=3)
        pinterest_snapshot = pinterest_ads_service.sync_client(client_id=3)
        snapchat_snapshot = snapchat_ads_service.sync_client(client_id=3)

        dashboard = unified_dashboard_service.get_client_dashboard(client_id=3)

        expected_spend = (
            float(google_snapshot["spend"])
            + float(meta_snapshot["spend"])
            + float(tiktok_snapshot["spend"])
            + float(pinterest_snapshot["spend"])
            + float(snapchat_snapshot["spend"])
        )
        expected_conversions = (
            int(google_snapshot["conversions"])
            + int(meta_snapshot["conversions"])
            + int(tiktok_snapshot["conversions"])
            + int(pinterest_snapshot["conversions"])
            + int(snapchat_snapshot["conversions"])
        )

        expected_revenue = (
            float(google_snapshot["revenue"])
            + float(meta_snapshot["revenue"])
            + float(tiktok_snapshot["revenue"])
            + float(pinterest_snapshot["revenue"])
            + float(snapchat_snapshot["revenue"])
        )

        self.assertTrue(dashboard["is_synced"])
        self.assertEqual(dashboard["totals"]["spend"], round(expected_spend, 2))
        self.assertEqual(dashboard["totals"]["conversions"], expected_conversions)
        self.assertEqual(dashboard["totals"]["revenue"], round(expected_revenue, 2))
        self.assertEqual(
            dashboard["totals"]["roas"],
            round(expected_revenue / expected_spend, 2),
        )

        for platform in ["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]:
            self.assertIn("roas", dashboard["platforms"][platform])
            self.assertIn("attempts", dashboard["platforms"][platform])
            self.assertIn("synced_at", dashboard["platforms"][platform])

    # Sprint 4 coverage (rules + notifications + system_bot audit)
    def test_rules_engine_stop_loss_triggers_and_notifies(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=5)
        meta_ads_service.sync_client(client_id=5)

        rule = rules_engine_service.create_rule(
            client_id=5,
            name="Stop-Loss High Spend",
            rule_type="stop_loss",
            threshold=50.0,
            action_value=0.0,
            status="active",
        )
        self.assertEqual(rule["rule_type"], "stop_loss")

        actions = rules_engine_service.evaluate_client_rules(client_id=5)
        self.assertGreaterEqual(len(actions), 1)

        event = notification_service.send_email_mock(
            to_email="owner@example.com",
            subject="Rule triggered",
            message=str(actions[0]),
        )
        self.assertEqual(event["channel"], "email_mock")

    def test_rules_engine_auto_scale_triggers(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=4)
        meta_ads_service.sync_client(client_id=4)

        rules_engine_service.create_rule(
            client_id=4,
            name="Scale Winners",
            rule_type="auto_scale",
            threshold=2.0,
            action_value=20.0,
            status="active",
        )

        actions = rules_engine_service.evaluate_client_rules(client_id=4)
        self.assertGreaterEqual(len(actions), 1)
        self.assertEqual(actions[0]["rule_type"], "auto_scale")


    def test_structured_recommendation_lifecycle_and_impact_report(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=8)
        meta_ads_service.sync_client(client_id=8)

        generated = recommendations_service.generate_recommendations(client_id=8)
        self.assertEqual(len(generated), 1)
        self.assertIn("problema", generated[0]["payload"])

        recommendation_id = int(generated[0]["id"])
        updated = recommendations_service.review_recommendation(
            client_id=8, recommendation_id=recommendation_id, action="approve", actor="tester@example.com"
        )
        self.assertEqual(updated["status"], "applied")

        actions = recommendations_service.list_actions(client_id=8)
        self.assertGreaterEqual(len(actions), 2)

        report = recommendations_service.get_impact_report(client_id=8)
        windows = [item["window_days"] for item in report["windows"]]
        self.assertEqual(windows, [3, 7, 14])

    # Sprint 5 coverage (AI assistant + insights + guardrails)
    def test_ai_recommendation_fallback_when_insufficient_data(self):
        rec = ai_assistant_service.generate_recommendation(client_id=999)
        self.assertEqual(rec["recommendation"], "Nu am destule date")

    def test_weekly_insight_generation_and_storage(self):
        os.environ["GOOGLE_ADS_TOKEN"] = "google-real-token"
        os.environ["META_ACCESS_TOKEN"] = "meta-real-token"
        google_ads_service.sync_client(client_id=6)
        meta_ads_service.sync_client(client_id=6)

        insight = insights_service.generate_weekly_insight(client_id=6)
        self.assertEqual(insight["client_id"], 6)
        self.assertIn("Spend", insight["summary"])

        latest = insights_service.get_latest(client_id=6)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["client_id"], 6)

    # Sprint 7 coverage (creative library + ai generation + approvals + publish)
    def test_creative_asset_metadata_variants_scores_and_links(self):
        asset = creative_workflow_service.create_asset(
            client_id=11,
            name="Video Awareness RO",
            format="video",
            dimensions="1080x1920",
            objective_fit="awareness",
            platform_fit=["meta", "tiktok"],
            language="ro",
            brand_tags=["summer", "promo"],
            legal_status="pending",
            approval_status="draft",
        )

        creative_workflow_service.generate_variants(asset_id=int(asset["id"]), count=2)
        creative_workflow_service.set_performance_scores(
            asset_id=int(asset["id"]),
            scores={"google": 71.2, "meta": 88.1, "tiktok": 91.4},
        )
        creative_workflow_service.link_to_campaign(asset_id=int(asset["id"]), campaign_id=201, ad_set_id=301)
        full_asset = creative_workflow_service.get_asset(int(asset["id"]))

        self.assertEqual(full_asset["metadata"]["format"], "video")
        self.assertEqual(len(full_asset["creative_variants"]), 2)
        self.assertEqual(full_asset["performance_scores"]["tiktok"], 91.4)
        self.assertEqual(full_asset["campaign_links"][0]["campaign_id"], 201)

    def test_publish_to_channel_uses_platform_adapter(self):
        asset = creative_workflow_service.create_asset(
            client_id=22,
            name="Static Conversion",
            format="image",
            dimensions="1200x628",
            objective_fit="conversion",
            platform_fit=["google", "meta"],
            language="ro",
            brand_tags=["always_on"],
            legal_status="approved",
            approval_status="approved",
        )
        variant = creative_workflow_service.add_variant(
            asset_id=int(asset["id"]),
            headline="Cumpara acum",
            body="Oferta limitata",
            cta="Comanda",
            media="image_v1",
        )

        published = creative_workflow_service.publish_to_channel(
            asset_id=int(asset["id"]),
            channel="meta",
            variant_id=int(variant["id"]),
        )

        self.assertEqual(published["native_object_type"], "ad_creative")
        self.assertTrue(str(published["native_id"]).startswith("meta_ad_creative_"))



if __name__ == "__main__":
    unittest.main()
