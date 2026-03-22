from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import creative_assets_repository as repository_module


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        self.index_calls.append({"keys": list(keys), **kwargs})
        return kwargs.get("name", "index")

    def find_one(self, query: dict[str, object]):
        for doc in self.docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def update_one(self, query: dict[str, object], update: dict[str, dict[str, object]], upsert: bool = False):
        target = self.find_one(query)
        set_payload = dict(update.get("$set") or {})
        set_on_insert = dict(update.get("$setOnInsert") or {})
        if target is None:
            if not upsert:
                return
            target = dict(query)
            target.update(set_on_insert)
            target.update(set_payload)
            target["_id"] = f"mongo-{len(self.docs) + 1}"
            self.docs.append(target)
            return
        target.update(set_payload)
        for idx, existing in enumerate(self.docs):
            if existing.get("_id") == target.get("_id"):
                self.docs[idx] = target
                break

    def find(self, query: dict[str, object]):
        matches = [dict(doc) for doc in self.docs if self._matches(doc, query)]
        return FakeCursor(matches)

    def _matches(self, payload: dict[str, object], query: dict[str, object]) -> bool:
        for key, value in query.items():
            if payload.get(key) != value:
                return False
        return True


class FakeCursor:
    def __init__(self, docs: list[dict[str, object]]) -> None:
        self.docs = docs

    def sort(self, keys):
        for key, order in reversed(keys):
            reverse = int(order) < 0
            self.docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def limit(self, value: int):
        self.docs = self.docs[: int(value)]
        return self

    def __iter__(self):
        return iter(self.docs)


def _asset_payload(*, creative_id: int, client_id: int = 101, name: str = "Asset One") -> dict[str, object]:
    return {
        "id": creative_id,
        "creative_id": creative_id,
        "asset_id": creative_id,
        "client_id": client_id,
        "name": name,
        "metadata": {
            "format": "image",
            "dimensions": "1080x1080",
            "objective_fit": "conversion",
            "platform_fit": ["meta", "google"],
            "language": "ro",
            "brand_tags": ["promo"],
            "legal_status": "pending",
            "approval_status": "draft",
        },
        "creative_variants": [
            {"id": 1, "headline": "H1", "body": "B1", "cta": "Learn", "media": "hero_v1", "media_id": "m_hero_v1"},
        ],
        "performance_scores": {"ctr": 1.2},
        "campaign_links": [{"id": 1, "campaign_id": 7, "ad_set_id": 9}],
        "publish_history": [{"id": 10, "asset_id": creative_id, "channel": "meta", "native_id": "n-1", "status": "published"}],
    }


def test_upsert_asset_creates_document(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=11))

    assert created["creative_id"] == 11
    assert created["id"] == 11
    assert created["client_id"] == 101
    assert created["metadata"]["format"] == "image"
    assert len(created["creative_variants"]) == 1
    assert created["creative_variants"][0]["media_id"] == "m_hero_v1"
    assert created["publish_history"][0]["id"] == 10
    assert created["created_at"] is not None
    assert created["updated_at"] is not None


def test_get_by_creative_id_returns_document(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=21))

    found = repository_module.creative_assets_repository.get_by_creative_id(21)

    assert found is not None
    assert found["creative_id"] == 21
    assert found["name"] == "Asset One"
    assert found["publish_history"][0]["channel"] == "meta"


def test_second_upsert_updates_existing_keeps_created_at_and_updates_updated_at(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc))
    first = repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=31, name="Asset A"))
    first_created_at = first["created_at"]
    first_updated_at = first["updated_at"]

    first_updated_at = (
        first_updated_at
        if isinstance(first_updated_at, datetime)
        else datetime.fromisoformat(str(first_updated_at).replace("Z", "+00:00"))
    )
    frozen_now = datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(repository_module, "_utcnow", lambda: frozen_now)
    second_payload = _asset_payload(creative_id=31, name="Asset A v2")
    second_payload["creative_variants"] = [{"id": 2, "headline": "H2", "body": "B2", "cta": "Buy", "media": "hero_v2"}]
    updated = repository_module.creative_assets_repository.upsert_asset(second_payload)

    assert len(fake_collection.docs) == 1
    assert updated["creative_id"] == 31
    assert updated["name"] == "Asset A v2"
    assert updated["creative_variants"][0]["media_id"] is None
    assert updated["created_at"] == first_created_at
    assert updated["updated_at"] > first_updated_at


def test_list_assets_orders_by_updated_at_desc_and_filters_by_client_id(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 10, 0, tzinfo=timezone.utc))
    repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=41, client_id=100, name="First"))
    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 11, 0, tzinfo=timezone.utc))
    repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=42, client_id=200, name="Second"))
    monkeypatch.setattr(repository_module, "_utcnow", lambda: datetime(2026, 3, 22, 12, 0, tzinfo=timezone.utc))
    repository_module.creative_assets_repository.upsert_asset(_asset_payload(creative_id=43, client_id=100, name="Third"))

    listed = repository_module.creative_assets_repository.list_assets(limit=10)
    filtered = repository_module.creative_assets_repository.list_assets(limit=10, client_id=100)

    assert [item["creative_id"] for item in listed] == [43, 42, 41]
    assert [item["creative_id"] for item in filtered] == [43, 41]


def test_repository_raises_runtime_error_when_mongo_not_configured(monkeypatch):
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: None)

    with pytest.raises(RuntimeError):
        repository_module.creative_assets_repository.get_by_creative_id(1)


def test_initialize_indexes(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    repository_module.creative_assets_repository.initialize_indexes()

    assert len(fake_collection.index_calls) == 2
    assert fake_collection.index_calls[0]["name"] == "ux_creative_assets_creative_id"
    assert fake_collection.index_calls[0]["unique"] is True
    assert fake_collection.index_calls[1]["name"] == "ix_creative_assets_client_updated_at"


def test_normalize_old_document_without_media_id_remains_compatible(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)
    payload = _asset_payload(creative_id=51)
    payload["creative_variants"] = [{"id": 1, "headline": "H1", "body": "B1", "cta": "Learn", "media": "legacy"}]

    created = repository_module.creative_assets_repository.upsert_asset(payload)

    assert created["creative_variants"][0]["media"] == "legacy"
    assert created["creative_variants"][0]["media_id"] is None
