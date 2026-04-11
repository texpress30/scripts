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
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query: dict[str, object]):
        matches = [dict(doc) for doc in self.docs if self._matches(doc, query)]
        return FakeCursor(matches)

    def count_documents(self, query: dict[str, object]) -> int:
        return sum(1 for doc in self.docs if self._matches(doc, query))

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

    def _matches(self, payload: dict[str, object], query: dict[str, object]) -> bool:
        for key, value in query.items():
            current = self._get_field(payload, key)
            if isinstance(value, dict):
                if "$ne" in value and current == value["$ne"]:
                    return False
                if "$nin" in value and current in value["$nin"]:
                    return False
                continue
            if current != value:
                return False
        return True

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


class FakeCursor:
    def __init__(self, docs: list[dict[str, object]]) -> None:
        self.docs = list(docs)

    def sort(self, key, order: int | None = None):
        if isinstance(key, list):
            for sort_key, sort_order in reversed(key):
                reverse = int(sort_order) < 0
                self.docs.sort(key=lambda item: item.get(sort_key), reverse=reverse)
            return self
        reverse = int(order or 1) < 0
        self.docs.sort(key=lambda item: item.get(key), reverse=reverse)
        return self

    def skip(self, value: int):
        self.docs = self.docs[int(value) :]
        return self

    def limit(self, value: int):
        self.docs = self.docs[: int(value)]
        return self

    def __iter__(self):
        return iter(self.docs)


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

    index_names = [call["name"] for call in fake_collection.index_calls]
    assert "ux_media_files_storage_bucket_key" in index_names
    assert "ix_media_files_client_status_created_at" in index_names
    assert "ix_media_files_client_folder_status_created_at" in index_names
    assert "ix_media_files_status_deleted_at" in index_names
    unique_index = fake_collection.index_calls[0]
    assert unique_index["name"] == "ux_media_files_storage_bucket_key"
    assert unique_index["unique"] is True


def test_create_draft_persists_folder_and_display_name(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_draft(
        client_id=11,
        kind="image",
        source="user_upload",
        original_filename="hero.png",
        mime_type="image/png",
        folder_id="folder-1",
        display_name="Hero Banner",
    )

    assert created["folder_id"] == "folder-1"
    assert created["display_name"] == "Hero Banner"


def test_create_ready_for_existing_asset(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_ready(
        client_id=12,
        kind="image",
        source="enriched_catalog",
        original_filename="render.png",
        mime_type="image/png",
        storage_bucket="assets-bucket",
        storage_key="enriched-catalog/42/render.png",
        storage_region="eu-west-1",
        size_bytes=4096,
        folder_id="system-folder",
        metadata={"enriched_catalog": {"output_feed_id": 42}},
    )

    assert created["status"] == MEDIA_FILE_STATUS_READY
    assert created["source"] == "enriched_catalog"
    assert created["folder_id"] == "system-folder"
    assert created["storage"]["key"] == "enriched-catalog/42/render.png"
    assert created["metadata"] == {"enriched_catalog": {"output_feed_id": 42}}


def test_update_attributes_renames_and_moves(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    created = repository_module.media_metadata_repository.create_draft(
        client_id=13,
        kind="image",
        source="user_upload",
        original_filename="original.png",
        mime_type="image/png",
    )

    renamed = repository_module.media_metadata_repository.update_attributes(
        media_id=created["media_id"],
        display_name="Renamed",
        folder_id="new-folder",
    )
    assert renamed is not None
    assert renamed["display_name"] == "Renamed"
    assert renamed["folder_id"] == "new-folder"

    cleared = repository_module.media_metadata_repository.update_attributes(
        media_id=created["media_id"],
        clear_folder=True,
    )
    assert cleared is not None
    assert cleared["folder_id"] is None


def test_list_for_client_filters_by_folder(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    repository_module.media_metadata_repository.create_draft(
        client_id=14,
        kind="image",
        source="user_upload",
        original_filename="root.png",
        mime_type="image/png",
    )
    repository_module.media_metadata_repository.create_draft(
        client_id=14,
        kind="image",
        source="user_upload",
        original_filename="nested.png",
        mime_type="image/png",
        folder_id="folder-42",
    )

    in_root = repository_module.media_metadata_repository.list_for_client(
        client_id=14,
        folder_id=repository_module.media_metadata_repository.FOLDER_ROOT,
    )
    in_folder = repository_module.media_metadata_repository.list_for_client(
        client_id=14,
        folder_id="folder-42",
    )

    assert len(in_root) == 1
    assert in_root[0]["original_filename"] == "root.png"
    assert len(in_folder) == 1
    assert in_folder[0]["original_filename"] == "nested.png"


def test_repository_raises_when_mongo_not_configured(monkeypatch):
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: None)

    with pytest.raises(RuntimeError):
        repository_module.media_metadata_repository.get_by_media_id("abc123")


def test_list_and_count_for_client(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    a = repository_module.media_metadata_repository.create_draft(
        client_id=1,
        kind="image",
        source="user_upload",
        original_filename="a.png",
        mime_type="image/png",
    )
    b = repository_module.media_metadata_repository.create_draft(
        client_id=1,
        kind="video",
        source="user_upload",
        original_filename="b.mp4",
        mime_type="video/mp4",
    )
    c = repository_module.media_metadata_repository.create_draft(
        client_id=2,
        kind="image",
        source="user_upload",
        original_filename="c.png",
        mime_type="image/png",
    )

    # newest first due created_at desc; skip first, get second only
    listed = repository_module.media_metadata_repository.list_for_client(client_id=1, limit=1, offset=1)
    total = repository_module.media_metadata_repository.count_for_client(client_id=1)
    filtered_kind = repository_module.media_metadata_repository.list_for_client(client_id=1, kind="image", limit=10, offset=0)

    assert total == 2
    assert len(listed) == 1
    assert listed[0]["media_id"] == a["media_id"]
    assert len(filtered_kind) == 1
    assert filtered_kind[0]["client_id"] == 1
    assert filtered_kind[0]["kind"] == "image"
    assert c["client_id"] == 2


def test_cleanup_candidates_and_mark_purged(monkeypatch):
    fake_collection = FakeCollection()
    monkeypatch.setattr(repository_module, "load_settings", _settings)
    monkeypatch.setattr(repository_module, "get_s3_bucket_name", lambda: "assets-bucket")
    monkeypatch.setattr(repository_module, "get_mongo_collection", lambda _name: fake_collection)

    first = repository_module.media_metadata_repository.create_draft(
        client_id=1,
        kind="image",
        source="user_upload",
        original_filename="a.png",
        mime_type="image/png",
        media_id="m1",
    )
    second = repository_module.media_metadata_repository.create_draft(
        client_id=1,
        kind="image",
        source="user_upload",
        original_filename="b.png",
        mime_type="image/png",
        media_id="m2",
    )
    third = repository_module.media_metadata_repository.create_draft(
        client_id=1,
        kind="image",
        source="user_upload",
        original_filename="c.png",
        mime_type="image/png",
        media_id="m3",
    )

    repository_module.media_metadata_repository.soft_delete(media_id=second["media_id"])
    repository_module.media_metadata_repository.soft_delete(media_id=first["media_id"])

    candidates = repository_module.media_metadata_repository.list_cleanup_candidates(limit=10)
    assert [item["media_id"] for item in candidates] == [second["media_id"], first["media_id"]]

    purged = repository_module.media_metadata_repository.mark_purged(media_id=first["media_id"])
    assert purged is not None
    assert purged["status"] == "purged"
    assert purged["purged_at"] is not None
    assert purged["deleted_at"] is not None
    assert third["status"] == "draft"
