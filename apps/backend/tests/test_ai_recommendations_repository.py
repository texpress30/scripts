from __future__ import annotations

from datetime import datetime, timezone

from app.services import ai_recommendations_repository as repository_module


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        self.index_calls.append({"keys": list(keys), **kwargs})
        return kwargs.get("name", "index")

    def insert_one(self, payload: dict[str, object]):
        stored = dict(payload)
        stored["_id"] = f"id-{len(self.docs) + 1}"
        self.docs.append(stored)
        return {"inserted_id": stored["_id"]}

    def find_one(self, query: dict[str, object]):
        for item in self.docs:
            if self._matches(item, query):
                return dict(item)
        return None

    def find(self, query: dict[str, object]):
        return FakeCursor([dict(item) for item in self.docs if self._matches(item, query)])

    def find_one_and_update(self, query: dict[str, object], update: dict[str, object], upsert: bool = False, return_document=None):
        found = None
        for idx, item in enumerate(self.docs):
            if self._matches(item, query):
                found = dict(item)
                self.docs[idx] = found
                break
        if found is None:
            if not upsert:
                return None
            found = dict(query)
            found["_id"] = f"id-{len(self.docs) + 1}"
            self.docs.append(found)
        for key, value in dict(update.get("$inc") or {}).items():
            found[key] = int(found.get(key) or 0) + int(value)
        for key, value in dict(update.get("$set") or {}).items():
            found[key] = value
        for key, value in dict(update.get("$setOnInsert") or {}).items():
            found.setdefault(key, value)
        for key, value in dict(update.get("$push") or {}).items():
            found.setdefault(key, [])
            found[key] = list(found[key]) + [value]
        return dict(found)

    def _matches(self, payload: dict[str, object], query: dict[str, object]) -> bool:
        for key, value in query.items():
            if payload.get(key) != value:
                return False
        return True


class FakeCursor:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items

    def sort(self, keys):
        for key, direction in reversed(keys):
            reverse = int(direction) < 0
            self.items.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def limit(self, value: int):
        self.items = self.items[: int(value)]
        return self

    def __iter__(self):
        return iter(self.items)


def test_next_id_is_atomic_and_starts_at_1(monkeypatch):
    recommendations = FakeCollection()
    counters = FakeCollection()
    monkeypatch.setattr(
        repository_module,
        "get_mongo_collection",
        lambda name: counters if name == "ai_recommendation_counters" else recommendations,
    )

    first = repository_module.ai_recommendations_repository.next_recommendation_id()
    second = repository_module.ai_recommendations_repository.next_recommendation_id()

    assert first == 1
    assert second == 2


def test_create_get_list_update_and_actions(monkeypatch):
    recommendations = FakeCollection()
    counters = FakeCollection()
    monkeypatch.setattr(
        repository_module,
        "get_mongo_collection",
        lambda name: counters if name == "ai_recommendation_counters" else recommendations,
    )
    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc))

    created = repository_module.ai_recommendations_repository.create_recommendation(
        {
            "recommendation_id": 11,
            "client_id": 7,
            "payload": {"problema": "p"},
            "status": "new",
            "source": "rules+llm",
        }
    )
    assert created["id"] == 11

    updated = repository_module.ai_recommendations_repository.update_recommendation_and_append_action(
        client_id=7,
        recommendation_id=11,
        status="rejected",
        updated_at="2026-03-22T11:15:00+00:00",
        action={
            "recommendation_id": 11,
            "action": "dismiss",
            "actor": "owner@example.com",
            "status": "ok",
            "details": {"message": "dismissed"},
            "timestamp": "2026-03-22T11:15:00+00:00",
        },
    )

    assert updated is not None
    assert updated["status"] == "rejected"
    assert len(updated["actions"]) == 1

    fetched = repository_module.ai_recommendations_repository.get_recommendation(client_id=7, recommendation_id=11)
    assert fetched is not None and fetched["recommendation_id"] == 11

    listed = repository_module.ai_recommendations_repository.list_recommendations(client_id=7)
    assert len(listed) == 1
    assert listed[0]["recommendation_id"] == 11

    actions = repository_module.ai_recommendations_repository.list_actions(client_id=7)
    assert len(actions) == 1
    assert actions[0]["action"] == "dismiss"


def test_initialize_indexes(monkeypatch):
    recommendations = FakeCollection()
    counters = FakeCollection()
    monkeypatch.setattr(
        repository_module,
        "get_mongo_collection",
        lambda name: counters if name == "ai_recommendation_counters" else recommendations,
    )

    repository_module.ai_recommendations_repository.initialize_indexes()

    assert recommendations.index_calls[0]["name"] == "ux_ai_recommendations_recommendation_id"
    assert recommendations.index_calls[0]["unique"] is True
    assert recommendations.index_calls[1]["name"] == "ix_ai_recommendations_client_updated_at"
    assert counters.index_calls[0]["name"] == "ux_ai_recommendation_counters_name"
    assert counters.index_calls[0]["unique"] is True
