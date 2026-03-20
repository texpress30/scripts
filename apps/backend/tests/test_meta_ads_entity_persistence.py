from __future__ import annotations

from datetime import date

from app.services import meta_ads as meta_ads_module
from app.services.meta_ads import meta_ads_service


class _FakeConn:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self) -> None:
        self.committed = True


def test_write_campaign_daily_rows_non_test_mode_upserts_and_commits(monkeypatch):
    captured: dict[str, object] = {}
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)

    def fake_upsert(conn, rows):
        captured["conn"] = conn
        captured["rows"] = rows
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_campaign_performance_reports", fake_upsert)

    rows = [{"platform": "meta_ads", "account_id": "act_123", "campaign_id": "cmp-1", "report_date": date(2026, 3, 20)}]
    written = meta_ads_service._write_campaign_daily_rows(rows=rows)

    assert written == 1
    assert captured["conn"] is fake_conn
    assert captured["rows"] == rows
    assert fake_conn.committed is True


def test_write_ad_group_daily_rows_non_test_mode_upserts_and_commits(monkeypatch):
    captured: dict[str, object] = {}
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)

    def fake_upsert(conn, rows):
        captured["conn"] = conn
        captured["rows"] = rows
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_ad_group_performance_reports", fake_upsert)

    rows = [{"platform": "meta_ads", "account_id": "act_123", "ad_group_id": "ag-1", "report_date": date(2026, 3, 20)}]
    written = meta_ads_service._write_ad_group_daily_rows(rows=rows)

    assert written == 1
    assert captured["conn"] is fake_conn
    assert captured["rows"] == rows
    assert fake_conn.committed is True


def test_write_ad_daily_rows_non_test_mode_upserts_and_commits(monkeypatch):
    captured: dict[str, object] = {}
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)

    def fake_upsert(conn, rows):
        captured["conn"] = conn
        captured["rows"] = rows
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_ad_unit_performance_reports", fake_upsert)

    rows = [{"platform": "meta_ads", "account_id": "act_123", "ad_id": "ad-1", "report_date": date(2026, 3, 20)}]
    written = meta_ads_service._write_ad_daily_rows(rows=rows)

    assert written == 1
    assert captured["conn"] is fake_conn
    assert captured["rows"] == rows
    assert fake_conn.committed is True


def test_meta_campaign_daily_sync_persists_rows_and_metadata_with_normalized_account(monkeypatch):
    captured_rows: list[dict[str, object]] = []
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(meta_ads_service, "_resolve_active_access_token_with_source", lambda: ("token", "database", None, None))
    monkeypatch.setattr(meta_ads_service, "graph_api_version", lambda: "v24.0")
    monkeypatch.setattr(meta_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["act_123456"])
    monkeypatch.setattr(meta_ads_service, "_probe_account_access", lambda **kwargs: {"account_path": "act_123456", "graph_version": "v24.0"})
    monkeypatch.setattr(meta_ads_service, "_resolve_attached_account_currency", lambda **kwargs: "RON")
    monkeypatch.setattr(
        meta_ads_service,
        "_fetch_campaign_daily_insights",
        lambda **kwargs: [
            {
                "date_start": "2026-03-20",
                "campaign_id": "cmp-1",
                "campaign_name": "Prospecting",
                "campaign_status": "PAUSED",
                "spend": "12.5",
                "impressions": "100",
                "clicks": "10",
                "actions": [{"action_type": "lead", "value": "2"}],
                "action_values": [{"value": "30.0"}],
            }
        ],
    )

    def fake_upsert_campaign(conn, rows):
        captured_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_campaign_performance_reports", fake_upsert_campaign)

    snapshot = meta_ads_service.sync_client(
        client_id=96,
        grain="campaign_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
        account_id="123456",
        update_snapshot=False,
    )

    assert snapshot["rows_written"] == 1
    assert snapshot["accounts"][0]["rows_written"] == 1
    assert captured_rows[0]["account_id"] == "act_123456"
    assert captured_rows[0]["campaign_id"] == "cmp-1"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["campaign_name"] == "Prospecting"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["campaign_status"] == "PAUSED"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["grain"] == "campaign_daily"


def test_meta_ad_group_daily_sync_persists_adset_metadata_and_rows_written(monkeypatch):
    captured_rows: list[dict[str, object]] = []
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(meta_ads_service, "_resolve_active_access_token_with_source", lambda: ("token", "database", None, None))
    monkeypatch.setattr(meta_ads_service, "graph_api_version", lambda: "v24.0")
    monkeypatch.setattr(meta_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["act_222"])
    monkeypatch.setattr(meta_ads_service, "_probe_account_access", lambda **kwargs: {"account_path": "act_222", "graph_version": "v24.0"})
    monkeypatch.setattr(meta_ads_service, "_resolve_attached_account_currency", lambda **kwargs: "USD")
    monkeypatch.setattr(
        meta_ads_service,
        "_fetch_ad_group_daily_insights",
        lambda **kwargs: [
            {
                "date_start": "2026-03-20",
                "campaign_id": "cmp-2",
                "campaign_name": "Retargeting",
                "adset_id": "adset-9",
                "adset_name": "Adset Nine",
                "adset_status": "ACTIVE",
                "spend": "20",
                "impressions": "200",
                "clicks": "22",
                "actions": [{"action_type": "lead", "value": "1"}],
                "action_values": [{"value": "12"}],
            }
        ],
    )

    def fake_upsert_ad_group(conn, rows):
        captured_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_ad_group_performance_reports", fake_upsert_ad_group)

    snapshot = meta_ads_service.sync_client(
        client_id=96,
        grain="ad_group_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
        update_snapshot=False,
    )

    assert snapshot["rows_written"] == 1
    assert captured_rows[0]["ad_group_id"] == "adset-9"
    assert captured_rows[0]["campaign_id"] == "cmp-2"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["adset_name"] == "Adset Nine"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["campaign_name"] == "Retargeting"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["grain"] == "ad_group_daily"


def test_meta_ad_daily_sync_persists_ad_metadata_and_rows_written(monkeypatch):
    captured_rows: list[dict[str, object]] = []
    fake_conn = _FakeConn()

    monkeypatch.setattr(meta_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(meta_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(meta_ads_service, "_resolve_active_access_token_with_source", lambda: ("token", "database", None, None))
    monkeypatch.setattr(meta_ads_service, "graph_api_version", lambda: "v24.0")
    monkeypatch.setattr(meta_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["act_777"])
    monkeypatch.setattr(meta_ads_service, "_probe_account_access", lambda **kwargs: {"account_path": "act_777", "graph_version": "v24.0"})
    monkeypatch.setattr(meta_ads_service, "_resolve_attached_account_currency", lambda **kwargs: "EUR")
    monkeypatch.setattr(
        meta_ads_service,
        "_fetch_ad_daily_insights",
        lambda **kwargs: [
            {
                "date_start": "2026-03-20",
                "campaign_id": "cmp-7",
                "campaign_name": "Scale",
                "adset_id": "ag-7",
                "adset_name": "Set 7",
                "ad_id": "ad-7",
                "ad_name": "Ad Seven",
                "ad_status": "ACTIVE",
                "spend": "5",
                "impressions": "50",
                "clicks": "5",
                "actions": [{"action_type": "lead", "value": "3"}],
                "action_values": [{"value": "44"}],
            }
        ],
    )

    def fake_upsert_ad(conn, rows):
        captured_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(meta_ads_module, "upsert_ad_unit_performance_reports", fake_upsert_ad)

    snapshot = meta_ads_service.sync_client(
        client_id=96,
        grain="ad_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
        update_snapshot=False,
    )

    assert snapshot["rows_written"] == 1
    assert captured_rows[0]["ad_id"] == "ad-7"
    assert captured_rows[0]["ad_group_id"] == "ag-7"
    assert captured_rows[0]["campaign_id"] == "cmp-7"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["ad_name"] == "Ad Seven"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["adset_name"] == "Set 7"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["campaign_name"] == "Scale"
    assert captured_rows[0]["extra_metrics"]["meta_ads"]["grain"] == "ad_daily"
