from __future__ import annotations

from app.api import company as company_api
from app.services.auth import AuthUser


def _admin_user() -> AuthUser:
    return AuthUser(email="owner@example.com", role="agency_admin")


def test_get_company_settings_returns_logo_media_id_and_storage_client_id(monkeypatch):
    monkeypatch.setattr(company_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(company_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(company_api, "_resolve_logo_storage_client_id", lambda **_kwargs: 11)
    monkeypatch.setattr(
        company_api.company_settings_service,
        "get_settings",
        lambda **_kwargs: {
            "company_name": "Agency",
            "company_email": "owner@example.com",
            "company_phone_prefix": "+40",
            "company_phone": "0700",
            "company_website": "https://agency.example",
            "business_category": "",
            "business_niche": "",
            "platform_primary_use": "",
            "address_line1": "Street",
            "city": "Cluj",
            "postal_code": "400000",
            "region": "CJ",
            "country": "România",
            "timezone": "Europe/Bucharest",
            "logo_url": "https://preview.example/logo.png",
            "logo_media_id": "m_logo_1",
            "logo_storage_client_id": 11,
        },
    )

    payload = company_api.get_company_settings(user=_admin_user())
    assert payload.logo_url == "https://preview.example/logo.png"
    assert payload.logo_media_id == "m_logo_1"
    assert payload.logo_storage_client_id == 11


def test_update_company_settings_passes_logo_media_id_to_service(monkeypatch):
    monkeypatch.setattr(company_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(company_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(company_api, "_resolve_logo_storage_client_id", lambda **_kwargs: 12)

    captured: dict[str, object] = {}

    def _fake_update(**kwargs):
        captured.update(kwargs)
        return {
            "company_name": "Agency",
            "company_email": "owner@example.com",
            "company_phone_prefix": "+40",
            "company_phone": "0700",
            "company_website": "https://agency.example",
            "business_category": "",
            "business_niche": "",
            "platform_primary_use": "",
            "address_line1": "Street",
            "city": "Cluj",
            "postal_code": "400000",
            "region": "CJ",
            "country": "România",
            "timezone": "Europe/Bucharest",
            "logo_url": "https://preview.example/logo.png",
            "logo_media_id": "m_logo_2",
            "logo_storage_client_id": 12,
        }

    monkeypatch.setattr(company_api.company_settings_service, "update_settings", _fake_update)

    response = company_api.update_company_settings(
        payload=company_api.UpdateCompanySettingsRequest(
            company_name="Agency",
            company_email="owner@example.com",
            company_phone_prefix="+40",
            company_phone="0700",
            company_website="https://agency.example",
            business_category="",
            business_niche="",
            platform_primary_use="",
            address_line1="Street",
            city="Cluj",
            postal_code="400000",
            region="CJ",
            country="România",
            timezone="Europe/Bucharest",
            logo_url="",
            logo_media_id="m_logo_2",
        ),
        user=_admin_user(),
    )

    assert response.logo_media_id == "m_logo_2"
    assert captured.get("logo_storage_client_id") == 12
    sent_payload = captured.get("payload")
    assert isinstance(sent_payload, dict)
    assert sent_payload.get("logo_media_id") == "m_logo_2"
