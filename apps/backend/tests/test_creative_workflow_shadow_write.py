from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import creative_workflow as workflow_module


def _new_service_with_flag(monkeypatch, *, enabled: bool) -> workflow_module.CreativeWorkflowService:
    monkeypatch.setattr(
        workflow_module,
        "load_settings",
        lambda: SimpleNamespace(creative_workflow_mongo_shadow_write_enabled=enabled),
    )
    return workflow_module.CreativeWorkflowService()


def _create_asset(service: workflow_module.CreativeWorkflowService) -> dict[str, object]:
    return service.create_asset(
        client_id=12,
        name="Creative 1",
        format="image",
        dimensions="1080x1080",
        objective_fit="conversion",
        platform_fit=["meta"],
        language="ro",
        brand_tags=["launch"],
        legal_status="pending",
        approval_status="draft",
    )


def test_shadow_write_flag_off_does_not_call_mongo_repositories(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False)
    upsert_calls: list[dict[str, object]] = []
    counter_calls: list[str] = []
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: upsert_calls.append(payload) or payload)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: counter_calls.append("asset") or 999)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_variant_id", lambda: counter_calls.append("variant") or 999)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_link_id", lambda: counter_calls.append("link") or 999)

    asset = _create_asset(service)
    service.add_variant(int(asset["id"]), "H", "B", "CTA", "media")
    service.link_to_campaign(int(asset["id"]), campaign_id=1, ad_set_id=2)
    service.update_approval(int(asset["id"]), legal_status="approved", approval_status="approved")
    service.set_performance_scores(int(asset["id"]), scores={"meta": 77.0})
    service.generate_variants(int(asset["id"]), count=2)

    assert upsert_calls == []
    assert counter_calls == []


def test_create_asset_flag_on_uses_counter_and_upsert(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 41)
    upsert_calls: list[dict[str, object]] = []
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: upsert_calls.append(dict(payload)) or payload)

    asset = _create_asset(service)

    assert asset["id"] == 41
    assert service._next_asset_id == 42
    assert len(upsert_calls) == 1
    assert upsert_calls[0]["id"] == 41


def test_add_variant_flag_on_uses_counter_and_upsert(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 10)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: payload)
    asset = _create_asset(service)

    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_variant_id", lambda: 72)
    upsert_calls: list[dict[str, object]] = []
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: upsert_calls.append(dict(payload)) or payload)
    variant = service.add_variant(int(asset["id"]), "H", "B", "CTA", "media")

    assert variant["id"] == 72
    assert service._next_variant_id == 73
    assert len(upsert_calls) == 1
    assert upsert_calls[0]["creative_variants"][0]["id"] == 72


def test_link_to_campaign_flag_on_uses_counter_and_upsert(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 20)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: payload)
    asset = _create_asset(service)

    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_link_id", lambda: 33)
    upsert_calls: list[dict[str, object]] = []
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: upsert_calls.append(dict(payload)) or payload)
    link = service.link_to_campaign(int(asset["id"]), campaign_id=201, ad_set_id=301)

    assert link["id"] == 33
    assert service._next_link_id == 34
    assert len(upsert_calls) == 1
    assert upsert_calls[0]["campaign_links"][0]["id"] == 33


def test_generate_update_scores_and_approval_persist_final_asset(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 101)
    variant_counter = {"value": 500}

    def _next_variant():
        value = variant_counter["value"]
        variant_counter["value"] += 1
        return value

    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_variant_id", _next_variant)
    upsert_calls: list[dict[str, object]] = []
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: upsert_calls.append(dict(payload)) or payload)

    asset = _create_asset(service)
    service.generate_variants(int(asset["id"]), count=3)
    service.update_approval(int(asset["id"]), legal_status="approved", approval_status="approved")
    service.set_performance_scores(int(asset["id"]), {"meta": 91.5})

    assert len(upsert_calls) == 4
    assert upsert_calls[1]["creative_variants"][-1]["id"] == 502
    assert upsert_calls[2]["metadata"]["approval_status"] == "approved"
    assert upsert_calls[3]["performance_scores"]["meta"] == 91.5


def test_upsert_failure_is_non_blocking(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 7)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: (_ for _ in ()).throw(RuntimeError("boom")))

    asset = _create_asset(service)

    assert asset["id"] == 7
    assert service.get_asset(7)["id"] == 7


def test_local_counters_stay_compatible_after_mongo_allocations(monkeypatch):
    flag_state = {"enabled": True}
    monkeypatch.setattr(
        workflow_module,
        "load_settings",
        lambda: SimpleNamespace(creative_workflow_mongo_shadow_write_enabled=flag_state["enabled"]),
    )
    service = workflow_module.CreativeWorkflowService()
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: payload)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 15)
    first = _create_asset(service)

    flag_state["enabled"] = False
    second = _create_asset(service)

    assert first["id"] == 15
    assert second["id"] == 16


def test_publish_to_channel_remains_unchanged(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_asset_id", lambda: 1)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: payload)
    asset = _create_asset(service)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_variant_id", lambda: 2)
    variant = service.add_variant(int(asset["id"]), "H", "B", "CTA", "media")

    called = {"publish": 0}
    original_next_publish_id = service._next_publish_id
    published = service.publish_to_channel(int(asset["id"]), "meta", int(variant["id"]))
    called["publish"] += 1

    assert called["publish"] == 1
    assert published["native_object_type"] == "ad_creative"
    assert service._next_publish_id == original_next_publish_id + 1
