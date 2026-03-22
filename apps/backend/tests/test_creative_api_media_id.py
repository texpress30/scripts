from __future__ import annotations

import pytest

from app.api import creative as creative_api


class _User:
    email = "owner@example.com"
    role = "agency_owner"
    scope_type = "agency"
    scope_id = 1
    memberships = []


def test_add_variant_media_id_validation_error_maps_to_400(monkeypatch):
    monkeypatch.setattr(creative_api, "_resolve_asset_client_id", lambda _asset_id: 12)
    monkeypatch.setattr(creative_api, "enforce_agency_navigation_access", lambda **kwargs: None)
    monkeypatch.setattr(creative_api, "enforce_action_scope", lambda **kwargs: None)
    monkeypatch.setattr(creative_api, "enforce_subaccount_module_access", lambda **kwargs: None)
    monkeypatch.setattr(creative_api.rate_limiter_service, "check", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        creative_api.creative_workflow_service,
        "add_variant",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            creative_api.CreativeWorkflowValidationError("media_id requires CREATIVE_WORKFLOW_MEDIA_ID_LINKING_ENABLED=true")
        ),
    )

    payload = creative_api.AddVariantRequest(headline="H", body="B", cta="CTA", media="", media_id="m_1")
    with pytest.raises(creative_api.HTTPException) as exc:
        creative_api.add_variant(101, payload, user=_User())

    assert exc.value.status_code == 400
    assert "CREATIVE_WORKFLOW_MEDIA_ID_LINKING_ENABLED" in str(exc.value.detail)


def test_add_variant_passes_media_id_to_service(monkeypatch):
    monkeypatch.setattr(creative_api, "_resolve_asset_client_id", lambda _asset_id: 12)
    monkeypatch.setattr(creative_api, "enforce_agency_navigation_access", lambda **kwargs: None)
    monkeypatch.setattr(creative_api, "enforce_action_scope", lambda **kwargs: None)
    monkeypatch.setattr(creative_api, "enforce_subaccount_module_access", lambda **kwargs: None)
    monkeypatch.setattr(creative_api.rate_limiter_service, "check", lambda *args, **kwargs: None)
    captured: dict[str, object] = {}

    def _add_variant(asset_id: int, headline: str, body: str, cta: str, media: str, **kwargs):
        captured["asset_id"] = asset_id
        captured["headline"] = headline
        captured["media"] = media
        captured["media_id"] = kwargs.get("media_id")
        return {"id": 1, "asset_id": asset_id, "headline": headline, "body": body, "cta": cta, "media": media, "media_id": kwargs.get("media_id")}

    monkeypatch.setattr(creative_api.creative_workflow_service, "add_variant", _add_variant)

    payload = creative_api.AddVariantRequest(headline="H", body="B", cta="CTA", media="legacy", media_id="m_2")
    response = creative_api.add_variant(55, payload, user=_User())

    assert captured["asset_id"] == 55
    assert captured["media"] == "legacy"
    assert captured["media_id"] == "m_2"
    assert response["media_id"] == "m_2"
