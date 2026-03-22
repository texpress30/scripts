from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import media_metadata_repository as repository_module
from app.services.media_metadata_models import MEDIA_FILE_STATUS_DELETE_REQUESTED, MEDIA_FILE_STATUS_DRAFT, MEDIA_FILE_STATUS_READY


class _InsertResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []
        self.index_calls: list[dict[str, object]] = []

    def create_index(self, keys, **kwargs):
        self.index_calls.append({"keys": list(keys), **kwargs})
        return kwargs.get("name", "index")

    def insert_one(self, payload: dict[str, object]):
        stored = dict(payload)
        stored["_id"] = f"mongo-{len(self.docs) + 1}"
        self.docs.append(stored)
        return _InsertResult(stored["_id"])

    def find_one(self, query: dict[str, object]):
        for doc in self.docs:
            if all(self._get_field(doc, key) == value for key, value in query.items()):
                return dict(doc)
        return None

    def update_one(self, query: dict[str, object], update: dict[str, dict[str, object]]):
        target = self.find_one(query)
        if target is None:
            return
        set_payload = update.get("$set", {})
        for key, value in set_payload.items():
            self._set_field(target, key, value)
        for idx, existing in enumerate(self.docs):
            if existing.get("_id") == target.get("_id"):
                self.docs[idx] = target
                break

    def _get_field(self, payload: dict[str, object], key: str):
        if "." not in key:
            return payload.get(key)
        current: object = payload
        for part in key.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _set_field(self, payload: dict[str, object], key: str, value: object):
        if "." not in key:
            payload[key] = value
            return
        parts = key.split(".")
        cursor = payload
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                child = {}
                cursor[part] = child
            cursor = child
        cursor[parts[-1]] = value


def _settings():
    return SimpleNamespace(storage_s3_region="eu-west-1")


def test_create_draft_defaults(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_draft(
        client_id=10,
        kind="image",
        source="user_upload",
        original_filename="hero.png",
        mime_type="image/png",
    )

    assert created is not None
    assert created["status"] == MEDIA_FILE_STATUS_DRAFT
    assert created["client_id"] == 10
    assert created["storage"]["provider"] == "s3"
    assert created["storage"]["bucket"] == "assets-bucket"
    assert created["storage"]["key"] == ""
    assert created["storage"]["region"] == "eu-west-1"
    assert "media_id" in created and isinstance(created["media_id"], str)


def test_get_by_media_id_and_storage(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_draft(
        client_id=20,
        kind="video",
        source="backend_ingest",
        original_filename="clip.mp4",
        mime_type="video/mp4",
        storage_key="clients/20/clip.mp4",
    )

    by_id = repository_module.media_metadata_repository.get_by_media_id(created["media_id"])
    by_storage = repository_module.media_metadata_repository.get_by_storage(bucket="assets-bucket", key="clients/20/clip.mp4")

    assert by_id is not None and by_id["media_id"] == created["media_id"]
    assert by_storage is not None and by_storage["media_id"] == created["media_id"]


def test_mark_ready_and_soft_delete(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_draft(
        client_id=30,
        kind="document",
        source="platform_sync",
        original_filename="brief.pdf",
        mime_type="application/pdf",
    )

    ready = repository_module.media_metadata_repository.mark_ready(
        media_id=created["media_id"],
        size_bytes=123,
        checksum="sha256:abc",
        etag="etag-1",
        version_id="v1",
    )
    deleted = repository_module.media_metadata_repository.soft_delete(media_id=created["media_id"])

    assert ready is not None
    assert ready["status"] == MEDIA_FILE_STATUS_READY
    assert ready["size_bytes"] == 123
    assert ready["checksum"] == "sha256:abc"
    assert ready["storage"]["etag"] == "etag-1"
    assert ready["storage"]["version_id"] == "v1"
    assert deleted is not None
    assert deleted["status"] == MEDIA_FILE_STATUS_DELETE_REQUESTED
    assert deleted["deleted_at"] is not None


def test_initialize_indexes(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    repository_module.media_metadata_repository.initialize_indexes()

    assert len(fake_collection.index_calls) == 3
    assert fake_collection.index_calls[0]["name"] == "ux_media_files_storage_bucket_key"
    assert fake_collection.index_calls[0]["unique"] is True
    assert fake_collection.index_calls[1]["name"] == "ix_media_files_client_status_created_at"
    assert fake_collection.index_calls[2]["name"] == "ix_media_files_status_deleted_at"


def test_repository_raises_when_mongo_not_configured(monkeypatch):
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: None)

    with pytest.raises(RuntimeError):
        repository_module.media_metadata_repository.get_by_media_id("abc123")
