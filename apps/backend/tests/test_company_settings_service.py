from __future__ import annotations

from app.services import company_settings as service_module


class _FakeCursor:
    def __init__(self, row, calls: list[tuple[str, tuple[object, ...] | None]]):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params=None):
        if params is None:
            self._calls.append((sql.strip(), None))
        else:
            self._calls.append((sql.strip(), tuple(params)))

    def fetchone(self):
        return self._row


class _FakeConnection:
    def __init__(self, row, calls: list[tuple[str, tuple[object, ...] | None]]):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return _FakeCursor(self._row, self._calls)

    def commit(self):
        return None


def test_get_settings_prefers_storage_preview_when_logo_media_id_present(monkeypatch):
    calls: list[tuple[str, tuple[object, ...] | None]] = []
    row = (
        "Agency",
        "agency@example.com",
        "+40",
        "0700",
        "https://agency.example",
        "Services",
        "B2B",
        "Analytics",
        "Street",
        "Cluj",
        "400000",
        "CJ",
        "România",
        "Europe/Bucharest",
        "https://legacy.example/logo.png",
        "m_logo_1",
    )

    service = service_module.CompanySettingsService()
    monkeypatch.setattr(service, "_ensure_company", lambda **_kwargs: None)
    monkeypatch.setattr(service, "_connect", lambda: _FakeConnection(row, calls))
    monkeypatch.setattr(
        service_module.storage_media_access_service,
        "build_access_url",
        lambda **_kwargs: {"url": "https://preview.example/logo.png"},
    )

    payload = service.get_settings(owner_email="owner@example.com", logo_storage_client_id=11)
    assert payload["logo_url"] == "https://preview.example/logo.png"
    assert payload["logo_media_id"] == "m_logo_1"
    assert payload["logo_storage_client_id"] == 11


def test_get_settings_falls_back_to_legacy_logo_when_preview_generation_fails(monkeypatch):
    calls: list[tuple[str, tuple[object, ...] | None]] = []
    row = (
        "Agency",
        "agency@example.com",
        "+40",
        "0700",
        "https://agency.example",
        "Services",
        "B2B",
        "Analytics",
        "Street",
        "Cluj",
        "400000",
        "CJ",
        "România",
        "Europe/Bucharest",
        "https://legacy.example/logo.png",
        "m_logo_1",
    )

    service = service_module.CompanySettingsService()
    monkeypatch.setattr(service, "_ensure_company", lambda **_kwargs: None)
    monkeypatch.setattr(service, "_connect", lambda: _FakeConnection(row, calls))
    monkeypatch.setattr(
        service_module.storage_media_access_service,
        "build_access_url",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    payload = service.get_settings(owner_email="owner@example.com", logo_storage_client_id=11)
    assert payload["logo_url"] == "https://legacy.example/logo.png"
    assert payload["logo_media_id"] == "m_logo_1"


def test_update_settings_persists_logo_media_id(monkeypatch):
    calls: list[tuple[str, tuple[object, ...] | None]] = []
    row = (
        "Agency",
        "agency@example.com",
        "+40",
        "0700",
        "https://agency.example",
        "Services",
        "B2B",
        "Analytics",
        "Street",
        "Cluj",
        "400000",
        "CJ",
        "România",
        "Europe/Bucharest",
        "https://legacy.example/logo.png",
        "m_logo_2",
    )

    service = service_module.CompanySettingsService()
    monkeypatch.setattr(service, "_ensure_company", lambda **_kwargs: None)
    monkeypatch.setattr(service, "_connect", lambda: _FakeConnection(row, calls))
    monkeypatch.setattr(
        service_module.storage_media_access_service,
        "build_access_url",
        lambda **_kwargs: {"url": "https://preview.example/logo2.png"},
    )

    payload = service.update_settings(
        owner_email="owner@example.com",
        payload={
            "company_name": "Agency",
            "company_email": "agency@example.com",
            "company_phone_prefix": "+40",
            "company_phone": "0700",
            "company_website": "https://agency.example",
            "business_category": "Services",
            "business_niche": "B2B",
            "platform_primary_use": "Analytics",
            "address_line1": "Street",
            "city": "Cluj",
            "postal_code": "400000",
            "region": "CJ",
            "country": "România",
            "timezone": "Europe/Bucharest",
            "logo_url": "",
            "logo_media_id": "m_logo_2",
        },
        logo_storage_client_id=11,
    )

    assert payload["logo_media_id"] == "m_logo_2"
    update_sql, update_params = next(item for item in calls if item[0].startswith("UPDATE companies"))
    assert "logo_media_id = %s" in update_sql
    assert update_params is not None
    assert "m_logo_2" in update_params
