from datetime import date

from app.services import dashboard as dashboard_service_module
from app.services.dashboard import unified_dashboard_service


def test_agency_dashboard_summary_includes_generic_integration_health_contract():
    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_list_clients = dashboard_service_module.client_registry_service.list_clients
    original_google_status = dashboard_service_module.google_ads_service.integration_status
    original_meta_status = dashboard_service_module.meta_ads_service.integration_status
    original_tiktok_status = dashboard_service_module.tiktok_ads_service.integration_status

    try:
        unified_dashboard_service._is_test_mode = lambda: True
        dashboard_service_module.client_registry_service.list_clients = lambda: []
        dashboard_service_module.google_ads_service.integration_status = lambda: {
            "platform": "google_ads",
            "status": "connected",
            "accounts_found": 4,
            "rows_in_db_last_30_days": 321,
            "last_sync_at": "2026-03-08T10:00:00Z",
            "last_error": None,
            "message": "Google ready",
        }
        dashboard_service_module.meta_ads_service.integration_status = lambda: {
            "provider": "meta_ads",
            "status": "connected",
            "message": "Meta connected",
            "token_updated_at": "2026-03-08T09:00:00Z",
            "oauth_configured": True,
            "has_usable_token": True,
        }
        dashboard_service_module.tiktok_ads_service.integration_status = lambda: {
            "provider": "tiktok_ads",
            "status": "connected",
            "message": "TikTok Business OAuth token is available.",
            "token_updated_at": "2026-03-08T08:00:00Z",
            "oauth_configured": True,
            "has_usable_token": True,
        }

        payload = unified_dashboard_service.get_agency_dashboard(start_date=date(2026, 3, 1), end_date=date(2026, 3, 7))
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        dashboard_service_module.client_registry_service.list_clients = original_list_clients
        dashboard_service_module.google_ads_service.integration_status = original_google_status
        dashboard_service_module.meta_ads_service.integration_status = original_meta_status
        dashboard_service_module.tiktok_ads_service.integration_status = original_tiktok_status

    # backward-compatible base fields
    assert "date_range" in payload
    assert "active_clients" in payload
    assert "totals" in payload
    assert "top_clients" in payload
    assert "currency" in payload

    assert "integration_health" in payload
    health = payload["integration_health"]
    assert isinstance(health, list)
    assert len(health) >= 5

    by_platform = {str(item.get("platform")): item for item in health}
    assert set(["google_ads", "meta_ads", "tiktok_ads", "pinterest_ads", "snapchat_ads"]).issubset(set(by_platform.keys()))

    google_item = by_platform["google_ads"]
    assert google_item["status"] == "connected"
    assert google_item["last_sync_at"] == "2026-03-08T10:00:00Z"
    assert "accounts=4" in str(google_item.get("details") or "")
    assert "rows30=321" in str(google_item.get("details") or "")

    meta_item = by_platform["meta_ads"]
    assert meta_item["status"] == "connected"
    assert meta_item["details"] == "Meta connected"
    assert meta_item["last_sync_at"] == "2026-03-08T09:00:00Z"
    assert meta_item["last_error"] is None

    tiktok_item = by_platform["tiktok_ads"]
    assert tiktok_item["status"] == "connected"
    assert tiktok_item["details"] == "TikTok Business OAuth token is available."
    assert tiktok_item["last_sync_at"] == "2026-03-08T08:00:00Z"
    assert tiktok_item["last_error"] is None

    assert by_platform["pinterest_ads"]["status"] == "disabled"
    assert by_platform["snapchat_ads"]["status"] == "disabled"


def test_meta_last_error_is_only_set_when_meta_status_is_error():
    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_list_clients = dashboard_service_module.client_registry_service.list_clients
    original_google_status = dashboard_service_module.google_ads_service.integration_status
    original_meta_status = dashboard_service_module.meta_ads_service.integration_status
    original_tiktok_status = dashboard_service_module.tiktok_ads_service.integration_status

    try:
        unified_dashboard_service._is_test_mode = lambda: True
        dashboard_service_module.client_registry_service.list_clients = lambda: []
        dashboard_service_module.google_ads_service.integration_status = lambda: {"status": "connected"}
        dashboard_service_module.meta_ads_service.integration_status = lambda: {
            "status": "error",
            "message": "Meta token expired",
            "token_updated_at": "2026-03-08T09:00:00Z",
        }
        dashboard_service_module.tiktok_ads_service.integration_status = lambda: {
            "status": "pending",
            "message": "TikTok Business OAuth is configured but no usable token is stored yet.",
            "token_updated_at": None,
        }

        payload = unified_dashboard_service.get_agency_dashboard(start_date=date(2026, 3, 1), end_date=date(2026, 3, 7))
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        dashboard_service_module.client_registry_service.list_clients = original_list_clients
        dashboard_service_module.google_ads_service.integration_status = original_google_status
        dashboard_service_module.meta_ads_service.integration_status = original_meta_status
        dashboard_service_module.tiktok_ads_service.integration_status = original_tiktok_status

    meta_item = next(item for item in payload["integration_health"] if item.get("platform") == "meta_ads")
    assert meta_item["status"] == "error"
    assert meta_item["last_error"] == "Meta token expired"

    tiktok_item = next(item for item in payload["integration_health"] if item.get("platform") == "tiktok_ads")
    assert tiktok_item["status"] == "pending"
    assert tiktok_item["details"] == "TikTok Business OAuth is configured but no usable token is stored yet."
    assert tiktok_item["last_error"] is None


def test_tiktok_last_error_is_only_set_when_tiktok_status_is_error():
    original_is_test_mode = unified_dashboard_service._is_test_mode
    original_list_clients = dashboard_service_module.client_registry_service.list_clients
    original_google_status = dashboard_service_module.google_ads_service.integration_status
    original_meta_status = dashboard_service_module.meta_ads_service.integration_status
    original_tiktok_status = dashboard_service_module.tiktok_ads_service.integration_status

    try:
        unified_dashboard_service._is_test_mode = lambda: True
        dashboard_service_module.client_registry_service.list_clients = lambda: []
        dashboard_service_module.google_ads_service.integration_status = lambda: {"status": "connected"}
        dashboard_service_module.meta_ads_service.integration_status = lambda: {"status": "connected", "message": "Meta connected"}
        dashboard_service_module.tiktok_ads_service.integration_status = lambda: {
            "status": "error",
            "message": "TikTok token refresh failed",
            "token_updated_at": "2026-03-08T08:00:00Z",
        }

        payload = unified_dashboard_service.get_agency_dashboard(start_date=date(2026, 3, 1), end_date=date(2026, 3, 7))
    finally:
        unified_dashboard_service._is_test_mode = original_is_test_mode
        dashboard_service_module.client_registry_service.list_clients = original_list_clients
        dashboard_service_module.google_ads_service.integration_status = original_google_status
        dashboard_service_module.meta_ads_service.integration_status = original_meta_status
        dashboard_service_module.tiktok_ads_service.integration_status = original_tiktok_status

    tiktok_item = next(item for item in payload["integration_health"] if item.get("platform") == "tiktok_ads")
    assert tiktok_item["status"] == "error"
    assert tiktok_item["details"] == "TikTok token refresh failed"
    assert tiktok_item["last_error"] == "TikTok token refresh failed"
