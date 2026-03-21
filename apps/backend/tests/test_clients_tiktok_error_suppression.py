from app.api.clients import _suppress_stale_tiktok_feature_flag_errors


def test_suppress_stale_tiktok_feature_flag_error_when_sync_enabled_and_not_active() -> None:
    items = [
        {
            "id": "tt_1",
            "last_error": "TikTok integration is disabled by feature flag.",
            "last_error_category": "integration_disabled",
            "last_error_details": {"provider_error_message": "TikTok integration is disabled by feature flag."},
            "has_active_sync": False,
        }
    ]

    _suppress_stale_tiktok_feature_flag_errors(items=items, sync_enabled=True)

    assert items[0]["last_error"] is None
    assert items[0]["last_error_category"] is None
    assert items[0]["last_error_details"] is None
