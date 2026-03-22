from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import recommendations as recommendations_module


def _new_service(monkeypatch, *, mongo_enabled: bool) -> recommendations_module.RecommendationsService:
    monkeypatch.setattr(
        recommendations_module,
        "load_settings",
        lambda: SimpleNamespace(
            ai_recommendations_mongo_source_enabled=mongo_enabled,
            openai_api_key="",
        ),
    )
    return recommendations_module.RecommendationsService()


def _payload() -> recommendations_module.RecommendationPayload:
    return recommendations_module.RecommendationPayload(
        problema="p",
        cauza="c",
        actiune="a",
        impact_estimat="i",
        incredere=0.7,
        risc="mediu",
    )


def test_flag_off_keeps_in_memory_and_does_not_call_repository(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=False)
    monkeypatch.setattr(service, "_build_rule_based_payload", lambda _client_id: _payload())
    monkeypatch.setattr(service, "_refine_with_llm", lambda payload: payload)
    monkeypatch.setattr(
        recommendations_module.ai_recommendations_repository,
        "create_recommendation",
        lambda _payload: (_ for _ in ()).throw(AssertionError("must not call mongo repository when flag off")),
    )

    generated = service.generate_recommendations(9)
    listed = service.list_recommendations(9)

    assert generated[0]["id"] == 1
    assert len(listed) == 1


def test_generate_with_flag_on_creates_mongo_record_with_stable_numeric_id(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    monkeypatch.setattr(service, "_build_rule_based_payload", lambda _client_id: _payload())
    monkeypatch.setattr(service, "_refine_with_llm", lambda payload: payload)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "next_recommendation_id", lambda: 101)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        recommendations_module.ai_recommendations_repository,
        "create_recommendation",
        lambda payload: captured.setdefault("payload", dict(payload)) or dict(payload),
    )

    generated = service.generate_recommendations(12)

    assert generated[0]["id"] == 101
    assert captured["payload"]["recommendation_id"] == 101
    assert captured["payload"]["client_id"] == 12


def test_list_and_get_read_from_mongo_when_flag_on(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    record = {
        "recommendation_id": 8,
        "id": 8,
        "client_id": 7,
        "status": "new",
        "payload": {"problema": "p"},
        "source": "rules+llm",
        "created_at": "2026-03-22T10:00:00+00:00",
        "updated_at": "2026-03-22T10:00:00+00:00",
        "snoozed_until": None,
        "actions": [],
    }
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "list_recommendations", lambda **kwargs: [dict(record)])
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "get_recommendation", lambda **kwargs: dict(record))

    listed = service.list_recommendations(7)
    fetched = service.get_recommendation(7, 8)

    assert listed[0]["id"] == 8
    assert fetched["id"] == 8


def test_review_dismiss_and_snooze_update_mongo_and_append_actions(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    base_record = {
        "recommendation_id": 5,
        "id": 5,
        "client_id": 3,
        "status": "new",
        "payload": {"problema": "p"},
        "source": "rules+llm",
        "created_at": "2026-03-22T10:00:00+00:00",
        "updated_at": "2026-03-22T10:00:00+00:00",
        "snoozed_until": None,
        "actions": [],
    }
    state = {"status": "new", "snoozed_until": None}

    def _get(**kwargs):
        return {**dict(base_record), "status": state["status"], "snoozed_until": state["snoozed_until"]}

    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "get_recommendation", _get)
    updates: list[dict[str, object]] = []

    def _update(**kwargs):
        updates.append(dict(kwargs))
        state["status"] = kwargs["status"]
        state["snoozed_until"] = kwargs.get("snoozed_until")
        return {
            **dict(base_record),
            "status": kwargs["status"],
            "updated_at": kwargs["updated_at"],
            "snoozed_until": kwargs.get("snoozed_until"),
            "actions": [kwargs["action"]],
        }

    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "update_recommendation_and_append_action", _update)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "append_action", lambda **kwargs: None)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "update_recommendation_state", lambda **kwargs: None)

    dismissed = service.review_recommendation(client_id=3, recommendation_id=5, action="dismiss", actor="owner@example.com")
    snoozed = service.review_recommendation(client_id=3, recommendation_id=5, action="snooze", actor="owner@example.com", snooze_days=2)

    assert dismissed["status"] == "rejected"
    assert updates[0]["action"]["action"] == "dismiss"
    assert snoozed["status"] == "expired"
    assert "T" in str(snoozed["snoozed_until"])


def test_review_approve_keeps_approve_apply_flow_coherent(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    base_record = {
        "recommendation_id": 6,
        "id": 6,
        "client_id": 3,
        "status": "new",
        "payload": {"problema": "p"},
        "source": "rules+llm",
        "created_at": "2026-03-22T10:00:00+00:00",
        "updated_at": "2026-03-22T10:00:00+00:00",
        "snoozed_until": None,
        "actions": [],
    }
    state = {"status": "new"}
    actions: list[dict[str, object]] = []

    def _get(**kwargs):
        return {**dict(base_record), "status": state["status"], "actions": list(actions)}

    def _update_with_action(**kwargs):
        state["status"] = kwargs["status"]
        actions.append(dict(kwargs["action"]))
        return _get()

    def _append_action(**kwargs):
        actions.append(dict(kwargs["action"]))
        return _get()

    def _update_state(**kwargs):
        state["status"] = kwargs["status"]
        return _get()

    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "get_recommendation", _get)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "update_recommendation_and_append_action", _update_with_action)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "append_action", _append_action)
    monkeypatch.setattr(recommendations_module.ai_recommendations_repository, "update_recommendation_state", _update_state)
    monkeypatch.setattr(service, "_apply_platform_change", lambda **kwargs: {"status": "success", "message": "ok"})

    updated = service.review_recommendation(client_id=3, recommendation_id=6, action="approve", actor="owner@example.com")

    assert updated["status"] == "applied"
    assert any(item["action"] == "approve" for item in actions)
    assert any(item["action"] == "apply" and item["status"] == "queued" for item in actions)
    assert any(item["action"] == "apply" and item["status"] == "success" for item in actions)


def test_list_actions_reads_flattened_actions_from_mongo_when_flag_on(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    monkeypatch.setattr(
        recommendations_module.ai_recommendations_repository,
        "list_actions",
        lambda **kwargs: [{"recommendation_id": 1, "action": "dismiss"}],
    )

    actions = service.list_actions(8)

    assert actions == [{"recommendation_id": 1, "action": "dismiss"}]


def test_flag_on_mongo_unavailable_fails_predictably_without_in_memory_fallback(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    monkeypatch.setattr(service, "_build_rule_based_payload", lambda _client_id: _payload())
    monkeypatch.setattr(service, "_refine_with_llm", lambda payload: payload)
    monkeypatch.setattr(
        recommendations_module.ai_recommendations_repository,
        "next_recommendation_id",
        lambda: (_ for _ in ()).throw(RuntimeError("Mongo unavailable")),
    )

    with pytest.raises(RuntimeError, match="Mongo unavailable"):
        service.generate_recommendations(4)


def test_get_impact_report_remains_unchanged(monkeypatch):
    service = _new_service(monkeypatch, mongo_enabled=True)
    monkeypatch.setattr(
        recommendations_module.unified_dashboard_service,
        "get_client_dashboard",
        lambda _client_id: {"totals": {"spend": 100.0, "conversions": 10.0, "roas": 1.5}},
    )

    report = service.get_impact_report(77)

    assert report["client_id"] == 77
    assert [item["window_days"] for item in report["windows"]] == [3, 7, 14]
