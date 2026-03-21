from __future__ import annotations

from datetime import date

from app.services import tiktok_ads as tiktok_ads_module
from app.services.tiktok_ads import TikTokAdGroupDailyMetric, TikTokCampaignDailyMetric, tiktok_ads_service


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


def test_resolve_campaign_metadata_fetches_all_ids_and_prefers_api_name(monkeypatch):
    captured_fetch_campaign_ids: list[str] = []
    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: True)

    def fake_fetch_campaign_metadata_by_ids(**kwargs):
        captured_fetch_campaign_ids.extend(kwargs.get("campaign_ids") or [])
        return {
            "cmp-api": {
                "campaign_id": "cmp-api",
                "campaign_name": "Name From API",
                "campaign_status": "ENABLE",
                "raw_payload": {"campaign_id": "cmp-api", "campaign_name": "Name From API"},
                "payload_hash": "hash-cmp-api",
            }
        }

    monkeypatch.setattr(tiktok_ads_service, "_fetch_campaign_metadata_by_ids", fake_fetch_campaign_metadata_by_ids)

    resolved = tiktok_ads_service._resolve_and_persist_campaign_metadata(
        account_id="tt-acc-fetch-all",
        access_token="token",
        campaign_ids=["cmp-api", "cmp-report-only"],
        report_campaign_name_by_id={"cmp-api": "Report Name", "cmp-report-only": "Report Only Name"},
    )

    assert sorted(captured_fetch_campaign_ids) == ["cmp-api", "cmp-report-only"]
    assert resolved["cmp-api"]["campaign_name"] == "Name From API"
    assert resolved["cmp-report-only"]["campaign_name"] == "Report Only Name"


def test_resolve_ad_group_metadata_fetches_all_ids_and_prefers_api_name(monkeypatch):
    captured_fetch_ad_group_ids: list[str] = []
    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: True)

    def fake_fetch_ad_group_metadata_by_ids(**kwargs):
        captured_fetch_ad_group_ids.extend(kwargs.get("ad_group_ids") or [])
        return {
            "ag-api": {
                "ad_group_id": "ag-api",
                "ad_group_name": "AdGroup From API",
                "campaign_id": "cmp-api",
                "campaign_name": "Campaign From API",
                "ad_group_status": "ENABLE",
                "raw_payload": {"adgroup_id": "ag-api", "adgroup_name": "AdGroup From API", "campaign_id": "cmp-api"},
                "payload_hash": "hash-ag-api",
            }
        }

    monkeypatch.setattr(tiktok_ads_service, "_fetch_ad_group_metadata_by_ids", fake_fetch_ad_group_metadata_by_ids)

    resolved = tiktok_ads_service._resolve_and_persist_ad_group_metadata(
        account_id="tt-acc-adg-fetch-all",
        access_token="token",
        ad_group_ids=["ag-api", "ag-report-only"],
        report_ad_group_name_by_id={"ag-api": "Report AdGroup", "ag-report-only": "Report Only AdGroup"},
    )

    assert sorted(captured_fetch_ad_group_ids) == ["ag-api", "ag-report-only"]
    assert resolved["ag-api"]["ad_group_name"] == "AdGroup From API"
    assert resolved["ag-report-only"]["ad_group_name"] == "Report Only AdGroup"


def test_fetch_campaign_metadata_by_ids_maps_status_and_full_raw_payload(monkeypatch):
    monkeypatch.setattr(tiktok_ads_service, "_campaign_get_endpoint", lambda: "https://example.test/campaign/get/")
    monkeypatch.setattr(
        tiktok_ads_service,
        "_http_json",
        lambda **kwargs: {
            "data": {
                "list": [
                    {
                        "campaign_id": "123",
                        "campaign_name": "My Campaign",
                        "status": "CAMPAIGN_STATUS_ENABLE",
                        "objective_type": "CONVERSIONS",
                    }
                ],
                "page_info": {"total_page": 1},
            }
        },
    )

    payload = tiktok_ads_service._fetch_campaign_metadata_by_ids(
        account_id="acc-1",
        access_token="token",
        campaign_ids=["123"],
    )

    assert payload["123"]["campaign_name"] == "My Campaign"
    assert payload["123"]["campaign_status"] == "CAMPAIGN_STATUS_ENABLE"
    assert payload["123"]["raw_payload"]["objective_type"] == "CONVERSIONS"


def test_fetch_ad_group_metadata_by_ids_maps_campaign_id_status_and_full_raw_payload(monkeypatch):
    monkeypatch.setattr(tiktok_ads_service, "_adgroup_get_endpoint", lambda: "https://example.test/adgroup/get/")
    monkeypatch.setattr(
        tiktok_ads_service,
        "_http_json",
        lambda **kwargs: {
            "data": {
                "list": [
                    {
                        "ad_group_id": "ag-1",
                        "ad_group_name": "Ad Group A",
                        "campaign_id": "cmp-1",
                        "status": "ADGROUP_STATUS_ENABLE",
                        "placement_type": "PLACEMENT_FEED",
                    }
                ],
                "page_info": {"total_page": 1},
            }
        },
    )

    payload = tiktok_ads_service._fetch_ad_group_metadata_by_ids(
        account_id="acc-1",
        access_token="token",
        ad_group_ids=["ag-1"],
    )

    assert payload["ag-1"]["ad_group_name"] == "Ad Group A"
    assert payload["ag-1"]["campaign_id"] == "cmp-1"
    assert payload["ag-1"]["ad_group_status"] == "ADGROUP_STATUS_ENABLE"
    assert payload["ag-1"]["raw_payload"]["placement_type"] == "PLACEMENT_FEED"


def test_campaign_daily_report_schema_does_not_request_campaign_name_dimension():
    schema = tiktok_ads_service._report_schema_for_grain("campaign_daily")
    assert "campaign_name" not in schema.dimensions


def test_fetch_campaign_daily_metrics_request_params_exclude_campaign_name_dimension(monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    captured_request_params: dict[str, object] = {}

    def fake_report_integrated_get(**kwargs):
        captured_request_params["dimensions"] = list(kwargs.get("dimensions") or [])
        return {"code": 0, "data": {"list": []}}

    monkeypatch.setattr(tiktok_ads_service, "_report_integrated_get", fake_report_integrated_get)

    payload = tiktok_ads_service._fetch_campaign_daily_metrics(
        account_id="tt-acc-params",
        access_token="token",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload == []
    dimensions = captured_request_params.get("dimensions")
    assert isinstance(dimensions, list)
    assert dimensions == ["stat_time_day", "campaign_id"]
    assert "campaign_name" not in dimensions


def test_report_query_params_guard_removes_campaign_name_for_campaign_data_level():
    params = tiktok_ads_service._build_report_integrated_query_params(
        account_id="tt-acc-guard",
        report_type="BASIC",
        service_type="AUCTION",
        query_mode="REGULAR",
        data_level="AUCTION_CAMPAIGN",
        dimensions=["stat_time_day", "campaign_id", "campaign_name"],
        metrics=["spend"],
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )
    assert params["dimensions"] == ["stat_time_day", "campaign_id"]


def test_ad_group_daily_report_schema_keeps_supported_dimensions_only():
    schema = tiktok_ads_service._report_schema_for_grain("ad_group_daily")
    assert schema.dimensions == ("stat_time_day", "campaign_id", "ad_group_id")


def test_fetch_ad_group_daily_metrics_request_params_exclude_campaign_dimensions(monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    captured_request_params: dict[str, object] = {}

    def fake_report_integrated_get(**kwargs):
        captured_request_params["dimensions"] = list(kwargs.get("dimensions") or [])
        return {"code": 0, "data": {"list": []}}

    monkeypatch.setattr(tiktok_ads_service, "_report_integrated_get", fake_report_integrated_get)

    payload = tiktok_ads_service._fetch_ad_group_daily_metrics(
        account_id="tt-acc-adgroup-params",
        access_token="token",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload == []
    dimensions = captured_request_params.get("dimensions")
    assert isinstance(dimensions, list)
    assert dimensions == ["stat_time_day", "campaign_id", "ad_group_id"]
    assert "adgroup_name" not in dimensions


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
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_campaign_metadata",
        lambda **kwargs: {
            "cmp-entity-1": {
                "campaign_id": "cmp-entity-1",
                "campaign_name": "Entity Campaign Name",
                "campaign_status": "ENABLE",
                "raw_payload": {"campaign_id": "cmp-entity-1", "campaign_name": "Entity Campaign Name", "operation_status": "ENABLE"},
                "payload_hash": "hash-entity-1",
            }
        },
    )

    written = tiktok_ads_service._upsert_campaign_rows(
        rows,
        source_window_start=date(2026, 3, 20),
        source_window_end=date(2026, 3, 20),
        access_token="token",
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


def test_upsert_campaign_rows_skips_empty_campaign_metadata_rows(monkeypatch):
    fake_conn = _FakeConn()
    captured_entities: list[dict[str, object]] = []
    captured_fact_rows: list[dict[str, object]] = []

    rows = [
        TikTokCampaignDailyMetric(
            report_date=date(2026, 3, 20),
            account_id="tt-acc-empty-metadata",
            campaign_id="cmp-empty-1",
            campaign_name="",
            spend=10.0,
            impressions=100,
            clicks=5,
            conversions=1.0,
            conversion_value=20.0,
            extra_metrics={"tiktok_ads": {}},
        )
    ]

    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(tiktok_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_campaign_metadata",
        lambda **kwargs: {
            "cmp-empty-1": {
                "campaign_id": "cmp-empty-1",
                "campaign_name": "",
                "campaign_status": "",
                "raw_payload": {},
                "payload_hash": None,
            }
        },
    )
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
        access_token="token",
    )

    assert written == 1
    assert captured_entities == []
    assert len(captured_fact_rows) == 1
    assert fake_conn.committed is True


def test_upsert_ad_group_rows_persists_platform_ad_groups_before_facts(monkeypatch):
    fake_conn = _FakeConn()
    call_order: list[str] = []
    captured_ad_groups: list[dict[str, object]] = []
    captured_fact_rows: list[dict[str, object]] = []

    rows = [
        TikTokAdGroupDailyMetric(
            report_date=date(2026, 3, 20),
            account_id="tt-acc-adg",
            ad_group_id="adg-1",
            ad_group_name="Ad Group One",
            campaign_id="cmp-1",
            campaign_name="Campaign One",
            spend=11.0,
            impressions=111,
            clicks=6,
            conversions=1.0,
            conversion_value=22.0,
            extra_metrics={"tiktok_ads": {}},
        )
    ]

    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(tiktok_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_ad_group_metadata",
        lambda **kwargs: {
            "adg-1": {
                "ad_group_id": "adg-1",
                "ad_group_name": "Ad Group One",
                "campaign_id": "cmp-1",
                "campaign_name": "Campaign One",
                "ad_group_status": "ENABLE",
                "raw_payload": {"adgroup_id": "adg-1"},
                "payload_hash": "hash-adg-1",
            }
        },
    )
    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_platform_ad_groups",
        lambda conn, payload: call_order.append("ad_groups") or captured_ad_groups.extend(payload) or len(payload),
    )
    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_ad_group_performance_reports",
        lambda conn, payload: call_order.append("facts") or captured_fact_rows.extend(payload) or len(payload),
    )

    written = tiktok_ads_service._upsert_ad_group_rows(
        rows,
        source_window_start=date(2026, 3, 20),
        source_window_end=date(2026, 3, 20),
        access_token="token",
    )

    assert written == 1
    assert call_order == ["ad_groups", "facts"]
    assert len(captured_ad_groups) == 1
    assert captured_ad_groups[0]["ad_group_id"] == "adg-1"
    assert captured_ad_groups[0]["campaign_id"] == "cmp-1"
    assert len(captured_fact_rows) == 1
    assert fake_conn.committed is True


def test_upsert_ad_group_rows_skips_empty_ad_group_metadata_rows(monkeypatch):
    fake_conn = _FakeConn()
    captured_ad_groups: list[dict[str, object]] = []
    captured_fact_rows: list[dict[str, object]] = []

    rows = [
        TikTokAdGroupDailyMetric(
            report_date=date(2026, 3, 20),
            account_id="tt-acc-empty-adg",
            ad_group_id="adg-empty-1",
            ad_group_name="",
            campaign_id="",
            campaign_name="",
            spend=11.0,
            impressions=111,
            clicks=6,
            conversions=1.0,
            conversion_value=22.0,
            extra_metrics={"tiktok_ads": {}},
        )
    ]

    monkeypatch.setattr(tiktok_ads_service, "_is_test_mode", lambda: False)
    monkeypatch.setattr(tiktok_ads_service, "_connect", lambda: fake_conn)
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_ad_group_metadata",
        lambda **kwargs: {
            "adg-empty-1": {
                "ad_group_id": "adg-empty-1",
                "ad_group_name": "",
                "campaign_id": "",
                "campaign_name": "",
                "ad_group_status": "",
                "raw_payload": {},
                "payload_hash": None,
            }
        },
    )
    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_platform_ad_groups",
        lambda conn, payload: captured_ad_groups.extend(payload) or len(payload),
    )
    monkeypatch.setattr(
        tiktok_ads_module,
        "upsert_ad_group_performance_reports",
        lambda conn, payload: captured_fact_rows.extend(payload) or len(payload),
    )

    written = tiktok_ads_service._upsert_ad_group_rows(
        rows,
        source_window_start=date(2026, 3, 20),
        source_window_end=date(2026, 3, 20),
        access_token="token",
    )

    assert written == 1
    assert captured_ad_groups == []
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

    def fake_upsert_campaign_rows(rows, *, source_window_start, source_window_end, access_token=None):
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
        lambda rows, *, source_window_start, source_window_end, access_token=None: captured_upsert_rows.extend(rows) or len(rows),
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


def test_campaign_daily_sync_continues_when_campaign_metadata_fetch_fails(monkeypatch):
    monkeypatch.setenv("FF_TIKTOK_INTEGRATION", "1")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")

    base_row = TikTokCampaignDailyMetric(
        report_date=date(2026, 3, 20),
        account_id="tt-acc-4",
        campaign_id="cmp-400",
        campaign_name="",
        spend=7.0,
        impressions=70,
        clicks=4,
        conversions=1.0,
        conversion_value=14.0,
        extra_metrics={"tiktok_ads": {}},
    )

    monkeypatch.setattr(tiktok_ads_service, "_access_token_with_source", lambda: ("token", "database", None))
    monkeypatch.setattr(tiktok_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["tt-acc-4"])
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
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("campaign/get failed")),
    )
    monkeypatch.setattr(tiktok_ads_module.tiktok_snapshot_store, "upsert_snapshot", lambda payload: None)

    captured_upsert_rows: list[TikTokCampaignDailyMetric] = []
    monkeypatch.setattr(
        tiktok_ads_service,
        "_upsert_campaign_rows",
        lambda rows, *, source_window_start, source_window_end, access_token=None: captured_upsert_rows.extend(rows) or len(rows),
    )

    payload = tiktok_ads_service.sync_client(
        client_id=96,
        grain="campaign_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload["rows_written"] == 1
    assert captured_upsert_rows[0].campaign_id == "cmp-400"
    assert captured_upsert_rows[0].campaign_name == ""


def test_ad_group_daily_sync_enriches_campaign_id_and_ad_group_name_from_metadata(monkeypatch):
    monkeypatch.setenv("FF_TIKTOK_INTEGRATION", "1")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")

    base_row = TikTokAdGroupDailyMetric(
        report_date=date(2026, 3, 20),
        account_id="tt-acc-ag-1",
        ad_group_id="ag-200",
        ad_group_name="",
        campaign_id="",
        campaign_name="",
        spend=6.0,
        impressions=60,
        clicks=3,
        conversions=1.0,
        conversion_value=12.0,
        extra_metrics={"tiktok_ads": {}},
    )

    monkeypatch.setattr(tiktok_ads_service, "_access_token_with_source", lambda: ("token", "database", None))
    monkeypatch.setattr(tiktok_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["tt-acc-ag-1"])
    monkeypatch.setattr(tiktok_ads_service, "_probe_selected_advertiser_access", lambda **kwargs: {"status": "ok"})
    monkeypatch.setattr(tiktok_ads_service, "_fetch_ad_group_daily_metrics", lambda **kwargs: [base_row])
    monkeypatch.setattr(
        tiktok_ads_service,
        "_consume_reporting_fetch_observability",
        lambda **kwargs: {"rows_downloaded": 1, "rows_mapped": 1, "zero_row_marker": None},
    )
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_ad_group_metadata",
        lambda **kwargs: {
            "ag-200": {
                "ad_group_id": "ag-200",
                "ad_group_name": "Resolved Ad Group",
                "campaign_id": "cmp-200",
                "campaign_name": "Campaign From Adgroup",
                "ad_group_status": "ENABLE",
                "raw_payload": {"adgroup_id": "ag-200"},
                "payload_hash": "ag-h-200",
            }
        },
    )
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_campaign_metadata",
        lambda **kwargs: {
            "cmp-200": {
                "campaign_id": "cmp-200",
                "campaign_name": "Resolved Campaign",
                "campaign_status": "ENABLE",
                "raw_payload": {"campaign_id": "cmp-200"},
                "payload_hash": "cmp-h-200",
            }
        },
    )

    captured_upsert_rows: list[TikTokAdGroupDailyMetric] = []
    monkeypatch.setattr(
        tiktok_ads_service,
        "_upsert_ad_group_rows",
        lambda rows, *, source_window_start, source_window_end, access_token=None: captured_upsert_rows.extend(rows) or len(rows),
    )
    monkeypatch.setattr(tiktok_ads_module.tiktok_snapshot_store, "upsert_snapshot", lambda payload: None)

    payload = tiktok_ads_service.sync_client(
        client_id=96,
        grain="ad_group_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload["rows_written"] == 1
    assert captured_upsert_rows[0].campaign_id == "cmp-200"
    assert captured_upsert_rows[0].campaign_name == "Resolved Campaign"
    assert captured_upsert_rows[0].ad_group_name == "Resolved Ad Group"
    assert captured_upsert_rows[0].extra_metrics["tiktok_ads"]["campaign_id"] == "cmp-200"
    assert captured_upsert_rows[0].extra_metrics["tiktok_ads"]["ad_group_name"] == "Resolved Ad Group"


def test_ad_group_daily_sync_uses_ad_group_id_fallback_when_name_missing(monkeypatch):
    monkeypatch.setenv("FF_TIKTOK_INTEGRATION", "1")
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")

    base_row = TikTokAdGroupDailyMetric(
        report_date=date(2026, 3, 20),
        account_id="tt-acc-ag-2",
        ad_group_id="ag-300",
        ad_group_name="",
        campaign_id="cmp-300",
        campaign_name="",
        spend=4.0,
        impressions=40,
        clicks=2,
        conversions=0.0,
        conversion_value=0.0,
        extra_metrics={"tiktok_ads": {}},
    )

    monkeypatch.setattr(tiktok_ads_service, "_access_token_with_source", lambda: ("token", "database", None))
    monkeypatch.setattr(tiktok_ads_service, "_resolve_target_account_ids", lambda **kwargs: ["tt-acc-ag-2"])
    monkeypatch.setattr(tiktok_ads_service, "_probe_selected_advertiser_access", lambda **kwargs: {"status": "ok"})
    monkeypatch.setattr(tiktok_ads_service, "_fetch_ad_group_daily_metrics", lambda **kwargs: [base_row])
    monkeypatch.setattr(
        tiktok_ads_service,
        "_consume_reporting_fetch_observability",
        lambda **kwargs: {"rows_downloaded": 1, "rows_mapped": 1, "zero_row_marker": None},
    )
    monkeypatch.setattr(
        tiktok_ads_service,
        "_resolve_and_persist_ad_group_metadata",
        lambda **kwargs: {
            "ag-300": {
                "ad_group_id": "ag-300",
                "ad_group_name": "",
                "campaign_id": "cmp-300",
                "campaign_name": "",
                "ad_group_status": "",
                "raw_payload": {},
                "payload_hash": "ag-h-300",
            }
        },
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
                "payload_hash": "cmp-h-300",
            }
        },
    )

    captured_upsert_rows: list[TikTokAdGroupDailyMetric] = []
    monkeypatch.setattr(
        tiktok_ads_service,
        "_upsert_ad_group_rows",
        lambda rows, *, source_window_start, source_window_end, access_token=None: captured_upsert_rows.extend(rows) or len(rows),
    )
    monkeypatch.setattr(tiktok_ads_module.tiktok_snapshot_store, "upsert_snapshot", lambda payload: None)

    payload = tiktok_ads_service.sync_client(
        client_id=96,
        grain="ad_group_daily",
        start_date=date(2026, 3, 20),
        end_date=date(2026, 3, 20),
    )

    assert payload["rows_written"] == 1
    assert captured_upsert_rows[0].campaign_id == "cmp-300"
    assert captured_upsert_rows[0].ad_group_name == ""
