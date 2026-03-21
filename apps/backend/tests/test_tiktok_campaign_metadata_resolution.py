from __future__ import annotations

from datetime import date

from app.services import tiktok_ads as tiktok_ads_module
from app.services.tiktok_ads import TikTokCampaignDailyMetric, tiktok_ads_service


class _FakeConn:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.committed = True


def test_resolve_and_persist_tiktok_campaign_metadata_by_campaign_id(monkeypatch):
    captured_rows: list[dict[str, object]] = []
    fake_conn = _FakeConn()

    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(tiktok_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(
        tiktok_ads_service,
        "_fetch_campaign_metadata_by_ids",
        lambda **kwargs: {
            "cmp-1": {
                "campaign_id": "cmp-1",
                "campaign_name": "TikTok Campaign One",
                "campaign_status": "ENABLE",
                "raw_payload": {"campaign_id": "cmp-1", "campaign_name": "TikTok Campaign One", "operation_status": "ENABLE"},
                "payload_hash": "hash-cmp-1",
            }
        },
    )

    def fake_upsert_platform_campaigns(conn, rows):
        captured_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(tiktok_ads_module, "upsert_platform_campaigns", fake_upsert_platform_campaigns)

    resolved = tiktok_ads_service._resolve_and_persist_campaign_metadata(
        account_id="tt-acc-1",
        access_token="token",
        campaign_ids=["cmp-1"],
        report_campaign_name_by_id={"cmp-1": ""},
    )

    assert resolved["cmp-1"]["campaign_name"] == "TikTok Campaign One"
    assert resolved["cmp-1"]["campaign_status"] == "ENABLE"
    assert captured_rows[0]["platform"] == "tiktok_ads"
    assert captured_rows[0]["account_id"] == "tt-acc-1"
    assert captured_rows[0]["campaign_id"] == "cmp-1"
    assert captured_rows[0]["name"] == "TikTok Campaign One"
    assert fake_conn.committed is True


def test_campaign_daily_report_schema_requests_campaign_name_dimension():
    schema = tiktok_ads_service._report_schema_for_grain("campaign_daily")
    assert "campaign_name" in schema.dimensions


def test_upsert_campaign_rows_persists_platform_campaign_entities(monkeypatch):
    fake_conn = _FakeConn()
    captured_entities: list[dict[str, object]] = []
    captured_fact_rows: list[dict[str, object]] = []

    rows = [
        TikTokCampaignDailyMetric(
            report_date=date(2026, 3, 20),
            account_id="tt-acc-entity",
            campaign_id="cmp-entity-1",
            campaign_name="Entity Campaign Name",
            spend=10.0,
            impressions=100,
            clicks=5,
            conversions=1.0,
            conversion_value=20.0,
            extra_metrics={"tiktok_ads": {"campaign_status": "ENABLE"}},
        )
    ]

    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(tiktok_ads_service, "_connect", lambda: fake_conn)

    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_platform_campaigns",
        lambda conn, payload: captured_entities.extend(payload) or len(payload),
    )
    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_campaign_performance_reports",
        lambda conn, payload: captured_fact_rows.extend(payload) or len(payload),
    )

    written = tiktok_ads_service._upsert_campaign_rows(
        rows,
        source_window_start=date(2026, 3, 20),
        source_window_end=date(2026, 3, 20),
    )

    assert written == 1
    assert len(captured_entities) == 1
    assert captured_entities[0]["platform"] == "tiktok_ads"
    assert captured_entities[0]["account_id"] == "tt-acc-entity"
    assert captured_entities[0]["campaign_id"] == "cmp-entity-1"
    assert captured_entities[0]["name"] == "Entity Campaign Name"
    assert captured_entities[0]["status"] == "ENABLE"
    assert isinstance(captured_entities[0]["payload_hash"], str) and len(captured_entities[0]["payload_hash"]) > 0
    assert captured_entities[0]["raw_payload"]["campaign_name"] == "Entity Campaign Name"
    assert len(captured_fact_rows) == 1
    assert fake_conn.committed is True


def test_campaign_daily_sync_uses_metadata_name_instead_of_campaign_id_fallback(monkeypatch):
    monkeypatch.setenv("FF_TIKTOK_INTEGRATION", "1")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")

    base_row = TikTokCampaignDailyMetric(
        report_date=date(2026, 3, 20),
        account_id="tt-acc-2",
        campaign_id="cmp-200",
        campaign_name="",
        spend=10.0,
        impressions=100,
        clicks=5,
        conversions=1.0,
        conversion_value=20.0,
        extra_metrics={"tiktok_ads": {"campaign_name": ""}},
    )

    monkeypatch.setattr(tiktok_ads_service, "_access_token_with_source", lambda: ("token", "database", None))
    monkeypatch.setattr(tiktok_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["tt-acc-2"])
    monkeypatch.setattr(tiktok_ads_service, "_probe_selected_advertiser_access", lambda **kwargs: {"status": "ok"})
    monkeypatch.setattr(tiktok_ads_service, "_fetch_campaign_daily_metrics", lambda **kwargs: [base_row])
    monkeypatch.setattr(
        tiktok_ads_service,
        "_consume_reporting_fetch_observability",
        lambda **kwargs: {"rows_downloaded": 1, "rows_mapped": 1, "zero_row_marker": None},
    )
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_campaign_metadata",
        lambda **kwargs: {
            "cmp-200": {
                "campaign_id": "cmp-200",
                "campaign_name": "Resolved TikTok Campaign",
                "campaign_status": "ENABLE",
                "raw_payload": {"campaign_id": "cmp-200"},
                "payload_hash": "h200",
            }
        },
    )

    captured_upsert_rows: list[dict[str, object]] = []

    def fake_upsert_campaign_rows(rows, *, source_window_start, source_window_end):
        captured_upsert_rows.extend(rows)
        return len(rows)

    monkeypatch.setattr(tiktok_ads_service, "_upsert_campaign_rows", fake_upsert_campaign_rows)
    monkeypatch.setattr(tiktok_ads_module.tiktok_snapshot_store, "upsert_snapshot", lambda payload: None)

    payload = tiktok_ads_service.sync_client(
        client_id=96,
        grain="campaign_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload["rows_written"] == 1
    assert captured_upsert_rows[0].campaign_id == "cmp-200"
    assert captured_upsert_rows[0].campaign_name == "Resolved TikTok Campaign"
    assert captured_upsert_rows[0].extra_metrics["tiktok_ads"]["campaign_name"] == "Resolved TikTok Campaign"
    assert captured_upsert_rows[0].extra_metrics["tiktok_ads"]["campaign_status"] == "ENABLE"


def test_campaign_daily_sync_keeps_campaign_id_fallback_when_metadata_name_missing(monkeypatch):
    monkeypatch.setenv("FF_TIKTOK_INTEGRATION", "1")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")

    base_row = TikTokCampaignDailyMetric(
        report_date=date(2026, 3, 20),
        account_id="tt-acc-3",
        campaign_id="cmp-300",
        campaign_name="",
        spend=12.0,
        impressions=120,
        clicks=6,
        conversions=2.0,
        conversion_value=30.0,
        extra_metrics={"tiktok_ads": {"campaign_name": ""}},
    )

    monkeypatch.setattr(tiktok_ads_service, "_access_token_with_source", lambda: ("token", "database", None))
    monkeypatch.setattr(tiktok_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["tt-acc-3"])
    monkeypatch.setattr(tiktok_ads_service, "_probe_selected_advertiser_access", lambda **kwargs: {"status": "ok"})
    monkeypatch.setattr(tiktok_ads_service, "_fetch_campaign_daily_metrics", lambda **kwargs: [base_row])
    monkeypatch.setattr(
        tiktok_ads_service,
        "_consume_reporting_fetch_observability",
        lambda **kwargs: {"rows_downloaded": 1, "rows_mapped": 1, "zero_row_marker": None},
    )
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_campaign_metadata",
        lambda **kwargs: {
            "cmp-300": {
                "campaign_id": "cmp-300",
                "campaign_name": "",
                "campaign_status": "",
                "raw_payload": {},
                "payload_hash": "h300",
            }
        },
    )

    captured_upsert_rows: list[dict[str, object]] = []
    monkeypatch.setattr(
        tiktok_ads_service,
        "_upsert_campaign_rows",
        lambda rows, *, source_window_start, source_window_end: captured_upsert_rows.extend(rows) or len(rows),
    )
    monkeypatch.setattr(tiktok_ads_module.tiktok_snapshot_store, "upsert_snapshot", lambda payload: None)

    payload = tiktok_ads_service.sync_client(
        client_id=96,
        grain="campaign_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload["rows_written"] == 1
    assert captured_upsert_rows[0].campaign_name == ""
