from datetime import date

from app.services import dashboard as dashboard_module
from app.services.dashboard import unified_dashboard_service


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        return None

    def fetchall(self):
        return list(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _run_audit(
    *,
    platform: str,
    rows,
    attached_accounts,
    mapping_rows,
    sync_runs_by_account,
    start: date = date(2026, 3, 1),
    end: date = date(2026, 3, 3),
    include_daily_breakdown: bool = False,
):
    original_connect = unified_dashboard_service._connect
    original_init_schema = dashboard_module.performance_reports_store.initialize_schema
    original_list_client_platform_accounts = dashboard_module.client_registry_service.list_client_platform_accounts
    original_list_platform_accounts_for_mapping = dashboard_module.client_registry_service.list_platform_accounts_for_mapping
    original_list_runs = dashboard_module.sync_runs_store.list_sync_runs_for_account
    original_chunk_counts = dashboard_module.sync_run_chunks_store.get_sync_run_chunk_status_counts
    try:
        unified_dashboard_service._connect = lambda: _FakeConn(rows)
        dashboard_module.performance_reports_store.initialize_schema = lambda: None
        dashboard_module.client_registry_service.list_client_platform_accounts = lambda **kwargs: list(attached_accounts)
        dashboard_module.client_registry_service.list_platform_accounts_for_mapping = lambda **kwargs: list(mapping_rows)
        dashboard_module.sync_runs_store.list_sync_runs_for_account = lambda **kwargs: list(sync_runs_by_account.get(str(kwargs.get("account_id") or ""), []))
        dashboard_module.sync_run_chunks_store.get_sync_run_chunk_status_counts = lambda job_id: {"queued": 0, "running": 0, "done": 1, "error": 0}

        return unified_dashboard_service.get_client_platform_sync_audit(
            client_id=99,
            platform=platform,
            start_date=start,
            end_date=end,
            include_daily_breakdown=include_daily_breakdown,
        )
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_module.performance_reports_store.initialize_schema = original_init_schema
        dashboard_module.client_registry_service.list_client_platform_accounts = original_list_client_platform_accounts
        dashboard_module.client_registry_service.list_platform_accounts_for_mapping = original_list_platform_accounts_for_mapping
        dashboard_module.sync_runs_store.list_sync_runs_for_account = original_list_runs
        dashboard_module.sync_run_chunks_store.get_sync_run_chunk_status_counts = original_chunk_counts


def test_tiktok_duplicate_like_account_daily_rows_flagged():
    rows = [
        (1, "tt_1", date(2026, 3, 1), 10.0, 100, 10, 1.0, 20.0, 99, "account_daily", "EUR", {"tiktok_ads": {}}),
        (2, "tt_1", date(2026, 3, 1), 10.0, 100, 10, 1.0, 20.0, 99, "account_daily", "EUR", {"tiktok_ads": {}}),
    ]
    payload = _run_audit(
        platform="tiktok_ads",
        rows=rows,
        attached_accounts=[{"id": "tt_1", "name": "TikTok A", "effective_account_currency": "EUR", "account_currency_source": "mapping_account_currency"}],
        mapping_rows=[{"account_id": "tt_1", "client_id": 99, "last_error": None, "last_success_at": "2026-03-03T10:00:00+00:00"}],
        sync_runs_by_account={"tt_1": []},
    )

    assert payload["anomaly_flags"]["duplicate_like_rows_on_natural_key"] is True
    assert payload["anomaly_flags"]["multiple_account_daily_rows_same_account_same_day"] is True


def test_tiktok_rows_before_supported_floor_are_flagged():
    rows = [
        (3, "tt_1", date(2024, 8, 31), 3.0, 30, 3, 0.0, 0.0, 99, "account_daily", "EUR", {"tiktok_ads": {}}),
    ]
    payload = _run_audit(
        platform="tiktok_ads",
        rows=rows,
        attached_accounts=[{"id": "tt_1", "name": "TikTok A", "effective_account_currency": "EUR", "account_currency_source": "mapping_account_currency"}],
        mapping_rows=[{"account_id": "tt_1", "client_id": 99, "last_error": None}],
        sync_runs_by_account={"tt_1": []},
        start=date(2024, 8, 30),
        end=date(2024, 9, 2),
    )

    assert payload["anomaly_flags"]["persisted_dates_before_platform_supported_start"] is True
    assert len(payload["anomaly_details"]["persisted_dates_before_platform_supported_start"]) == 1


def test_meta_missing_account_daily_with_sync_error_exposes_partial_coverage():
    rows = [
        (4, "act_1", date(2026, 3, 1), 5.0, 50, 5, 0.0, 0.0, 99, "campaign_daily", "RON", {"meta_ads": {"grain": "campaign_daily"}}),
    ]
    sync_runs = {
        "act_1": [
            {
                "job_id": "run-1",
                "platform": "meta_ads",
                "account_id": "act_1",
                "client_id": 99,
                "job_type": "historical_backfill",
                "status": "error",
                "grain": "account_daily",
                "date_start": "2026-03-01",
                "date_end": "2026-03-03",
                "chunks_total": 3,
                "chunks_done": 1,
                "rows_written": 10,
                "error": "chunk failure",
                "metadata": {"last_error_details": {"message": "provider timeout", "access_token": "secret"}},
                "created_at": "2026-03-03T09:00:00+00:00",
                "updated_at": "2026-03-03T09:30:00+00:00",
                "started_at": "2026-03-03T09:00:00+00:00",
                "finished_at": "2026-03-03T09:30:00+00:00",
            }
        ]
    }
    payload = _run_audit(
        platform="meta_ads",
        rows=rows,
        attached_accounts=[{"id": "act_1", "name": "Meta A", "effective_account_currency": "RON", "account_currency_source": "mapping_account_currency"}],
        mapping_rows=[{"account_id": "act_1", "client_id": 99, "last_error": "chunk failure", "last_success_at": None}],
        sync_runs_by_account=sync_runs,
    )

    assert payload["anomaly_flags"]["lower_grain_rows_present_without_account_daily"] is True
    assert payload["anomaly_flags"]["account_daily_missing_for_days_inside_range"] is True
    recent_runs = payload["sync_run_summary"]["recent_runs"]
    assert recent_runs[0]["last_error_summary"] == "chunk failure"
    assert recent_runs[0]["last_error_details"]["access_token"] == "[redacted]"


def test_id_mismatch_rows_without_attached_mapping_are_flagged():
    rows = [
        (5, "tt_1", date(2026, 3, 1), 5.0, 50, 5, 0.0, 0.0, 99, "account_daily", "EUR", {"tiktok_ads": {}}),
        (6, "tt_alias", date(2026, 3, 1), 7.0, 70, 7, 0.0, 0.0, 99, "account_daily", "EUR", {"tiktok_ads": {}}),
    ]
    payload = _run_audit(
        platform="tiktok_ads",
        rows=rows,
        attached_accounts=[{"id": "tt_1", "name": "TikTok A", "effective_account_currency": "EUR", "account_currency_source": "mapping_account_currency"}],
        mapping_rows=[{"account_id": "tt_1", "client_id": 99, "last_error": None}],
        sync_runs_by_account={"tt_1": []},
    )

    assert payload["anomaly_flags"]["rows_present_but_no_attached_mapping"] is True
    assert payload["anomaly_flags"]["mixed_customer_ids_for_same_attached_account"] is True


def test_multi_account_platform_audit_works_and_exposes_account_daily_totals():
    rows = [
        (7, "act_1", date(2026, 3, 1), 4.0, 40, 4, 0.0, 0.0, 99, "account_daily", "RON", {"meta_ads": {}}),
        (8, "act_2", date(2026, 3, 1), 6.0, 60, 6, 0.0, 0.0, 99, "account_daily", "RON", {"meta_ads": {}}),
        (9, "act_2", date(2026, 3, 1), 2.0, 20, 2, 0.0, 0.0, 99, "campaign_daily", "RON", {"meta_ads": {"grain": "campaign_daily"}}),
    ]
    payload = _run_audit(
        platform="meta_ads",
        rows=rows,
        attached_accounts=[
            {"id": "act_1", "name": "Meta A", "effective_account_currency": "RON", "account_currency_source": "mapping_account_currency"},
            {"id": "act_2", "name": "Meta B", "effective_account_currency": "RON", "account_currency_source": "mapping_account_currency"},
        ],
        mapping_rows=[
            {"account_id": "act_1", "client_id": 99, "last_error": None},
            {"account_id": "act_2", "client_id": 99, "last_error": None},
        ],
        sync_runs_by_account={"act_1": [], "act_2": []},
        include_daily_breakdown=True,
    )

    assert len(payload["attached_accounts"]) == 2
    assert len(payload["account_daily_totals"]) == 2
    assert payload["anomaly_flags"]["possible_overcount_if_summing_multiple_grains"] is True
    assert len(payload["lower_grain_totals"]["daily_breakdown"]) == 1


def test_meta_attached_account_payload_includes_latest_run_coverage_status_fields():
    rows = [
        (10, "act_1", date(2026, 3, 1), 5.0, 50, 5, 0.0, 0.0, 99, "account_daily", "RON", {"meta_ads": {"grain": "account_daily"}}),
    ]
    sync_runs = {
        "act_1": [
            {
                "job_id": "run-meta-coverage",
                "platform": "meta_ads",
                "account_id": "act_1",
                "client_id": 99,
                "job_type": "historical_backfill",
                "status": "error",
                "grain": "account_daily",
                "date_start": "2026-03-01",
                "date_end": "2026-03-10",
                "chunks_total": 2,
                "chunks_done": 1,
                "rows_written": 12,
                "error": "chunk failed",
                "metadata": {
                    "coverage_status": "partial_request_coverage",
                    "sync_health_status": "partial_request_coverage",
                    "requested_start_date": "2026-03-01",
                    "requested_end_date": "2026-03-10",
                    "total_chunk_count": 2,
                    "successful_chunk_count": 1,
                    "failed_chunk_count": 1,
                    "retry_attempted": True,
                    "retry_recovered_chunk_count": 0,
                    "rows_written_count": 12,
                    "first_persisted_date": "2026-03-01",
                    "last_persisted_date": "2026-03-09",
                    "last_error": "chunk failed",
                    "last_error_summary": "chunk failed",
                    "last_error_details": {"message": "provider timeout", "access_token": "secret"},
                },
                "created_at": "2026-03-10T12:00:00+00:00",
                "updated_at": "2026-03-10T12:01:00+00:00",
                "started_at": "2026-03-10T11:00:00+00:00",
                "finished_at": "2026-03-10T12:01:00+00:00",
            }
        ]
    }
    payload = _run_audit(
        platform="meta_ads",
        rows=rows,
        attached_accounts=[{"id": "act_1", "name": "Meta A", "effective_account_currency": "RON", "account_currency_source": "mapping_account_currency"}],
        mapping_rows=[{"account_id": "act_1", "client_id": 99, "last_error": None}],
        sync_runs_by_account=sync_runs,
    )

    attached = payload["attached_accounts"][0]
    recent = payload["sync_run_summary"]["recent_runs"][0]
    assert attached["coverage_status"] == "partial_request_coverage"
    assert recent["coverage_status"] == "partial_request_coverage"
    assert attached["failed_chunk_count"] == 1
    assert recent["failed_chunk_count"] == 1
    assert recent["last_error_details"]["access_token"] == "[redacted]"
