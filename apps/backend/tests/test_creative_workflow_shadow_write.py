from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import creative_workflow as workflow_module


def _new_service_with_flag(
    monkeypatch,
    *,
    enabled: bool,
    read_through_enabled: bool = False,
) -> workflow_module.CreativeWorkflowService:
    monkeypatch.setattr(
        workflow_module,
        "load_settings",
        lambda: SimpleNamespace(
            creative_workflow_mongo_shadow_write_enabled=enabled,
            creative_workflow_mongo_read_through_enabled=read_through_enabled,
        ),
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


def _mongo_asset_payload(*, asset_id: int, client_id: int = 55) -> dict[str, object]:
    return {
        "id": asset_id,
        "creative_id": asset_id,
        "client_id": client_id,
        "name": f"Mongo Asset {asset_id}",
        "metadata": {
            "format": "image",
            "dimensions": "1080x1080",
            "objective_fit": "traffic",
            "platform_fit": ["meta"],
            "language": "ro",
            "brand_tags": ["mongo"],
            "legal_status": "pending",
            "approval_status": "draft",
        },
        "creative_variants": [{"id": 200, "headline": "H", "body": "B", "cta": "CTA", "media": "m"}],
        "performance_scores": {"meta": 10.0},
        "campaign_links": [{"id": 300, "campaign_id": 1, "ad_set_id": 2}],
    }


def test_read_through_off_does_not_call_mongo_repository(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=False)
    calls = {"get": 0}
    monkeypatch.setattr(workflow_module.creative_assets_repository, "get_by_creative_id", lambda _asset_id: calls.__setitem__("get", calls["get"] + 1))

    with pytest.raises(ValueError):
        service.get_asset(999)

    assert calls["get"] == 0


def test_get_asset_read_through_hydrates_from_mongo_and_reuses_local(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    calls = {"get": 0}

    def _get_from_mongo(asset_id: int):
        calls["get"] += 1
        return _mongo_asset_payload(asset_id=asset_id)

    monkeypatch.setattr(workflow_module.creative_assets_repository, "get_by_creative_id", _get_from_mongo)
    first = service.get_asset(123)
    second = service.get_asset(123)

    assert first["id"] == 123
    assert second["id"] == 123
    assert calls["get"] == 1


def test_local_asset_has_priority_over_mongo(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    local = _create_asset(service)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "get_by_creative_id", lambda _asset_id: _mongo_asset_payload(asset_id=int(local["id"]), client_id=999))

    resolved = service.get_asset(int(local["id"]))

    assert resolved["client_id"] == 12
    assert resolved["name"] == "Creative 1"


def test_mutations_continue_on_hydrated_asset(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=True, read_through_enabled=True)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "get_by_creative_id", lambda asset_id: _mongo_asset_payload(asset_id=asset_id))
    monkeypatch.setattr(workflow_module.creative_assets_repository, "upsert_asset", lambda payload: payload)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_variant_id", lambda: 901)
    monkeypatch.setattr(workflow_module.creative_counters_repository, "next_link_id", lambda: 902)

    variant = service.add_variant(321, "H2", "B2", "CTA2", "media2")
    generated = service.generate_variants(321, count=1)
    updated = service.update_approval(321, legal_status="approved", approval_status="approved")
    link = service.link_to_campaign(321, campaign_id=10, ad_set_id=20)
    perf = service.set_performance_scores(321, {"meta": 22.2})

    assert variant["id"] == 901
    assert len(generated) == 1
    assert updated["metadata"]["approval_status"] == "approved"
    assert link["id"] == 902
    assert perf["performance_scores"]["meta"] == 22.2


def test_list_assets_merges_mongo_without_overwriting_or_duplicates(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    local = _create_asset(service)

    mongo_payloads = [
        _mongo_asset_payload(asset_id=int(local["id"]), client_id=999),
        _mongo_asset_payload(asset_id=444, client_id=12),
    ]
    monkeypatch.setattr(workflow_module.creative_assets_repository, "list_assets", lambda **kwargs: mongo_payloads)

    items = service.list_assets(client_id=12)
    ids = sorted(int(item["id"]) for item in items)

    assert ids == [int(local["id"]), 444]
    local_item = next(item for item in items if int(item["id"]) == int(local["id"]))
    assert local_item["name"] == "Creative 1"


def test_hydration_syncs_local_counters(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    monkeypatch.setattr(workflow_module.creative_assets_repository, "get_by_creative_id", lambda asset_id: _mongo_asset_payload(asset_id=asset_id))
    hydrated = service.get_asset(700)
    next_local = _create_asset(service)

    assert hydrated["id"] == 700
    assert next_local["id"] >= 701


def test_list_assets_continues_when_mongo_read_fails(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    local = _create_asset(service)
    monkeypatch.setattr(
        workflow_module.creative_assets_repository,
        "list_assets",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("mongo down")),
    )

    items = service.list_assets(client_id=12)

    assert len(items) == 1
    assert items[0]["id"] == local["id"]


def test_get_asset_on_missing_local_with_mongo_error_remains_predictable(monkeypatch):
    service = _new_service_with_flag(monkeypatch, enabled=False, read_through_enabled=True)
    monkeypatch.setattr(
        workflow_module.creative_assets_repository,
        "get_by_creative_id",
        lambda _asset_id: (_ for _ in ()).throw(RuntimeError("mongo down")),
    )

    with pytest.raises(ValueError):
        service.get_asset(888)
