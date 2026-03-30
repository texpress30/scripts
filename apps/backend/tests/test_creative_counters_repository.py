from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import creative_counters_repository as repository_module


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        self.index_calls.append({"keys": list(keys), **kwargs})
        return kwargs.get("name", "index")

    def find_one_and_update(self, query, update, *, upsert: bool, return_document):
        target = self._find_doc(query)
        if target is None:
            if not upsert:
                return None
            target = {"_id": f"mongo-{len(self.docs) + 1}"}
            self.docs.append(target)

        for key, value in dict(update.get("$setOnInsert") or {}).items():
            if key not in target:
                target[key] = value
        for key, value in dict(update.get("$set") or {}).items():
            target[key] = value
        for key, value in dict(update.get("$inc") or {}).items():
            target[key] = int(target.get(key) or 0) + int(value)

        return dict(target)

    def _find_doc(self, query: dict[str, object]) -> dict[str, object] | None:
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None


def test_next_id_asset_starts_from_one(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    monkeypatch.setattr(repository_module, "_return_document_after", lambda: "after")

    allocated = repository_module.creative_counters_repository.next_id("asset")

    assert allocated == 1


def test_next_id_increments_for_same_counter(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    monkeypatch.setattr(repository_module, "_return_document_after", lambda: "after")

    first = repository_module.creative_counters_repository.next_id("asset")
    second = repository_module.creative_counters_repository.next_id("asset")

    assert first == 1
    assert second == 2


def test_counters_are_independent(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    monkeypatch.setattr(repository_module, "_return_document_after", lambda: "after")

    asset_first = repository_module.creative_counters_repository.next_id("asset")
    variant_first = repository_module.creative_counters_repository.next_id("variant")
    asset_second = repository_module.creative_counters_repository.next_id("asset")

    assert asset_first == 1
    assert variant_first == 1
    assert asset_second == 2


def test_helpers_delegate_to_expected_counter_names(monkeypatch):
    called_names: list[str] = []
    original_next_id = repository_module.creative_counters_repository.next_id

    def _capture(counter_name: str) -> int:
        called_names.append(counter_name)
        return 99

    monkeypatch.setattr(repository_module.creative_counters_repository, "next_id", _capture)
    try:
        assert repository_module.creative_counters_repository.next_asset_id() == 99
        assert repository_module.creative_counters_repository.next_variant_id() == 99
        assert repository_module.creative_counters_repository.next_link_id() == 99
        assert repository_module.creative_counters_repository.next_publish_id() == 99
    finally:
        monkeypatch.setattr(repository_module.creative_counters_repository, "next_id", original_next_id)

    assert called_names == ["asset", "variant", "link", "publish"]


def test_counter_document_updated_at_changes(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    monkeypatch.setattr(repository_module, "_return_document_after", lambda: "after")
    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc))
    repository_module.creative_counters_repository.next_id("publish")

    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc))
    repository_module.creative_counters_repository.next_id("publish")

    publish_doc = fake_collection.docs[0]
    assert publish_doc["counter_name"] == "publish"
    assert publish_doc["value"] == 2
    assert publish_doc["updated_at"] == datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc)


def test_repository_raises_when_mongo_not_configured(monkeypatch):
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: None)

    with pytest.raises(RuntimeError):
        repository_module.creative_counters_repository.next_id("asset")


def test_initialize_indexes(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    repository_module.creative_counters_repository.initialize_indexes()

    assert len(fake_collection.index_calls) == 1
    assert fake_collection.index_calls[0]["name"] == "ux_creative_counters_counter_name"
    assert fake_collection.index_calls[0]["unique"] is True
