from datetime import date

from app.services import dashboard as dashboard_module
from app.services.dashboard import unified_dashboard_service


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._last_rows: list[tuple] = []

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).lower().split())
        if normalized.startswith("select"):
            rows = []
            for row in self._conn.rows:
                if row.get("platform") != "tiktok_ads":
                    continue
                if str(row.get("grain") or "account_daily") != "account_daily":
                    continue
                rows.append(
                    (
                        int(row["id"]),
                        str(row.get("customer_id") or ""),
                        row.get("report_date"),
                        float(row.get("spend") or 0.0),
                        int(row.get("impressions") or 0),
                        int(row.get("clicks") or 0),
                        float(row.get("conversions") or 0.0),
                        float(row.get("conversion_value") or 0.0),
                        row.get("client_id"),
                        row.get("extra_metrics") or {},
                    )
                )
            rows.sort(key=lambda item: (item[2].isoformat(), item[1], item[0]))
            self._last_rows = rows
            return None

        if normalized.startswith("update ad_performance_reports"):
            canonical_id, row_id = params
            for row in self._conn.rows:
                if int(row.get("id") or 0) == int(row_id):
                    row["customer_id"] = str(canonical_id)
            return None

        if normalized.startswith("delete from ad_performance_reports"):
            delete_ids = set(int(item) for item in (params[0] or []))
            self._conn.rows = [row for row in self._conn.rows if int(row.get("id") or 0) not in delete_ids]
            return None

        # SAVEPOINT/ROLLBACK/RELEASE no-op in fake cursor.
        return None

    def fetchall(self):
        return list(self._last_rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self, rows):
        self.rows = list(rows)
        self.committed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _run_repair(*, rows, attached_accounts, dry_run=True, account_id=None):
    fake_conn = _FakeConn(rows)
    original_connect = unified_dashboard_service._connect
    original_init_schema = dashboard_module.performance_reports_store.initialize_schema
    original_list_attached = dashboard_module.client_registry_service.list_client_platform_accounts
    try:
        unified_dashboard_service._connect = lambda: fake_conn
        dashboard_module.performance_reports_store.initialize_schema = lambda: None
        dashboard_module.client_registry_service.list_client_platform_accounts = lambda **kwargs: list(attached_accounts)
        payload = unified_dashboard_service.repair_client_tiktok_account_daily(
            client_id=99,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 3),
            account_id=account_id,
            dry_run=dry_run,
        )
        return payload, fake_conn
    finally:
        unified_dashboard_service._connect = original_connect
        dashboard_module.performance_reports_store.initialize_schema = original_init_schema
        dashboard_module.client_registry_service.list_client_platform_accounts = original_list_attached


def test_tiktok_account_daily_repair_dry_run_detects_candidates_without_mutation():
    rows = [
        {"id": 1, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "alias_1", "report_date": date(2026, 3, 1), "spend": 10.0, "impressions": 100, "clicks": 10, "conversions": 1.0, "conversion_value": 20.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
    ]
    payload, conn = _run_repair(rows=rows, attached_accounts=[{"id": "tt_1", "name": "TikTok 1"}], dry_run=True)

    assert payload["dry_run"] is True
    assert payload["safe_repair_candidate_units"] == 1
    assert payload["applied_units"] == 0
    assert conn.rows[0]["customer_id"] == "alias_1"


def test_tiktok_account_daily_repair_apply_exact_duplicate_keeps_one_survivor():
    rows = [
        {"id": 1, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "tt_1", "report_date": date(2026, 3, 1), "spend": 10.0, "impressions": 100, "clicks": 10, "conversions": 1.0, "conversion_value": 20.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
        {"id": 2, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "alias_1", "report_date": date(2026, 3, 1), "spend": 10.0, "impressions": 100, "clicks": 10, "conversions": 1.0, "conversion_value": 20.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
    ]
    payload, conn = _run_repair(rows=rows, attached_accounts=[{"id": "tt_1", "name": "TikTok 1"}], dry_run=False)

    assert payload["applied_units"] == 1
    assert payload["deleted_rows"] == 1
    survivors = [row for row in conn.rows if row["platform"] == "tiktok_ads"]
    assert len(survivors) == 1
    assert survivors[0]["customer_id"] == "tt_1"


def test_tiktok_account_daily_repair_apply_rewrites_safe_noncanonical_singleton():
    rows = [
        {"id": 3, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "alias_1", "report_date": date(2026, 3, 2), "spend": 11.0, "impressions": 110, "clicks": 11, "conversions": 2.0, "conversion_value": 21.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
    ]
    payload, conn = _run_repair(rows=rows, attached_accounts=[{"id": "tt_1", "name": "TikTok 1"}], dry_run=False)

    assert payload["rewritten_rows"] == 1
    assert conn.rows[0]["customer_id"] == "tt_1"


def test_tiktok_account_daily_repair_skips_conflicting_metrics_as_ambiguous():
    rows = [
        {"id": 4, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "tt_1", "report_date": date(2026, 3, 3), "spend": 15.0, "impressions": 150, "clicks": 15, "conversions": 2.0, "conversion_value": 30.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
        {"id": 5, "platform": "tiktok_ads", "grain": "account_daily", "customer_id": "alias_1", "report_date": date(2026, 3, 3), "spend": 99.0, "impressions": 999, "clicks": 99, "conversions": 9.0, "conversion_value": 90.0, "client_id": 99, "extra_metrics": {"tiktok_ads": {"provider_identity_candidates": ["tt_1"]}}},
    ]
    payload, conn = _run_repair(rows=rows, attached_accounts=[{"id": "tt_1", "name": "TikTok 1"}], dry_run=False)

    assert payload["applied_units"] == 0
    assert payload["skipped_units"] >= 1
    reasons = {item["reason"] for item in payload["unresolved_units"]}
    assert "conflicting_metrics" in reasons
    assert len(conn.rows) == 2


def test_tiktok_account_daily_repair_non_tiktok_rows_remain_unchanged():
    rows = [
        {"id": 10, "platform": "meta_ads", "grain": "account_daily", "customer_id": "act_1", "report_date": date(2026, 3, 1), "spend": 50.0, "impressions": 500, "clicks": 50, "conversions": 5.0, "conversion_value": 100.0, "client_id": 99, "extra_metrics": {"meta_ads": {"grain": "account_daily"}}},
    ]
    payload, conn = _run_repair(rows=rows, attached_accounts=[{"id": "tt_1", "name": "TikTok 1"}], dry_run=False)

    assert payload["total_units_scanned"] == 0
    assert len(conn.rows) == 1
    assert conn.rows[0]["platform"] == "meta_ads"
