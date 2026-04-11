from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services import media_folder_repository as folder_repo_module
from app.services import media_metadata_repository as metadata_repo_module
from app.services.media_folder_repository import FOLDER_STATUS_ACTIVE, FOLDER_STATUS_DELETED, MediaFolderRepository
from app.services.media_folder_service import MediaFolderError, MediaFolderService


class FakeFolderCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, object]] = []

    def create_index(self, *args, **kwargs):
        return kwargs.get("name", "index")

    def insert_one(self, payload: dict[str, object]):
        stored = dict(payload)
        stored["_id"] = f"fid-{uuid4().hex[:8]}"
        self.docs.append(stored)
        result = SimpleNamespace(inserted_id=stored["_id"])
        return result

    def find_one(self, query: dict[str, object]):
        for doc in self.docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query: dict[str, object]):
        matches = [dict(doc) for doc in self.docs if self._matches(doc, query)]
        return FakeCursor(matches)

    def update_one(self, query: dict[str, object], update: dict[str, object]):
        target = self.find_one(query)
        if target is None:
            return
        set_payload = update.get("$set", {}) or {}
        for key, value in set_payload.items():
            target[key] = value
        for idx, existing in enumerate(self.docs):
            if existing.get("_id") == target.get("_id"):
                self.docs[idx] = target
                break

    def count_documents(self, query: dict[str, object]) -> int:
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def _matches(self, doc: dict[str, object], query: dict[str, object]) -> bool:
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
                continue
            if actual != expected:
                return False
        return True


class FakeCursor:
    def __init__(self, docs: list[dict[str, object]]):
        self.docs = list(docs)

    def sort(self, key, order: int | None = None):
        if isinstance(key, list):
            for sort_key, sort_order in reversed(key):
                reverse = int(sort_order) < 0
                self.docs.sort(key=lambda item: item.get(sort_key) or "", reverse=reverse)
            return self
        reverse = int(order or 1) < 0
        self.docs.sort(key=lambda item: item.get(key) or "", reverse=reverse)
        return self

    def skip(self, value: int):
        self.docs = self.docs[int(value):]
        return self

    def limit(self, value: int):
        self.docs = self.docs[: int(value)]
        return self

    def __iter__(self):
        return iter(self.docs)


@pytest.fixture
def folder_service(monkeypatch):
    fake_collection = FakeFolderCollection()
    monkeypatch.setattr(folder_repo_module, "get_mongo_collection", lambda _name: fake_collection)
    monkeypatch.setattr(
        metadata_repo_module.media_metadata_repository,
        "count_for_client",
        lambda **kwargs: 0,
    )
    # Monkeypatch bson ObjectId validation so tests can use simple hex strings.
    import app.services.media_folder_repository as repo

    def _always_ok_object_id(value):
        candidate = str(value or "").strip()
        if candidate == "":
            return None
        return candidate

    monkeypatch.setattr(repo, "_coerce_object_id", _always_ok_object_id)

    # Make the inserted_id non-ObjectId so _normalize still works
    service = MediaFolderService()
    return service, fake_collection


def test_create_folder_happy_path(folder_service):
    service, _ = folder_service

    folder = service.create_folder(client_id=1, parent_folder_id=None, name="Assets")
    assert folder["name"] == "Assets"
    assert folder["parent_folder_id"] is None
    assert folder["status"] == FOLDER_STATUS_ACTIVE
    assert folder["system"] is False


def test_create_folder_rejects_duplicate_name(folder_service):
    service, _ = folder_service
    service.create_folder(client_id=1, parent_folder_id=None, name="Assets")
    with pytest.raises(MediaFolderError) as exc_info:
        service.create_folder(client_id=1, parent_folder_id=None, name="Assets")
    assert exc_info.value.status_code == 409


def test_create_folder_rejects_invalid_name(folder_service):
    service, _ = folder_service
    with pytest.raises(MediaFolderError):
        service.create_folder(client_id=1, parent_folder_id=None, name="   ")
    with pytest.raises(MediaFolderError):
        service.create_folder(client_id=1, parent_folder_id=None, name="bad/name")


def test_rename_folder(folder_service):
    service, _ = folder_service
    folder = service.create_folder(client_id=1, parent_folder_id=None, name="Old")
    renamed = service.rename_folder(client_id=1, folder_id=folder["folder_id"], name="New")
    assert renamed["name"] == "New"


def test_rename_folder_rejects_collision(folder_service):
    service, _ = folder_service
    service.create_folder(client_id=1, parent_folder_id=None, name="A")
    other = service.create_folder(client_id=1, parent_folder_id=None, name="B")
    with pytest.raises(MediaFolderError) as exc_info:
        service.rename_folder(client_id=1, folder_id=other["folder_id"], name="A")
    assert exc_info.value.status_code == 409


def test_move_folder_prevents_cycle(folder_service):
    service, _ = folder_service
    parent = service.create_folder(client_id=1, parent_folder_id=None, name="Parent")
    child = service.create_folder(client_id=1, parent_folder_id=parent["folder_id"], name="Child")
    with pytest.raises(MediaFolderError):
        service.move_folder(
            client_id=1,
            folder_id=parent["folder_id"],
            new_parent_folder_id=child["folder_id"],
        )


def test_delete_empty_folder(folder_service):
    service, _ = folder_service
    folder = service.create_folder(client_id=1, parent_folder_id=None, name="Delete me")
    deleted = service.delete_folder(client_id=1, folder_id=folder["folder_id"])
    assert deleted["status"] == FOLDER_STATUS_DELETED


def test_delete_folder_with_children_refuses(folder_service, monkeypatch):
    service, _ = folder_service
    parent = service.create_folder(client_id=1, parent_folder_id=None, name="Parent")
    service.create_folder(client_id=1, parent_folder_id=parent["folder_id"], name="Child")
    with pytest.raises(MediaFolderError) as exc_info:
        service.delete_folder(client_id=1, folder_id=parent["folder_id"])
    assert exc_info.value.status_code == 409


def test_delete_folder_with_files_refuses(folder_service, monkeypatch):
    service, _ = folder_service
    folder = service.create_folder(client_id=1, parent_folder_id=None, name="WithFiles")

    # Pretend the folder contains one file so the empty check fails.
    monkeypatch.setattr(
        metadata_repo_module.media_metadata_repository,
        "count_for_client",
        lambda **kwargs: 1 if kwargs.get("folder_id") == folder["folder_id"] else 0,
    )
    with pytest.raises(MediaFolderError) as exc_info:
        service.delete_folder(client_id=1, folder_id=folder["folder_id"])
    assert exc_info.value.status_code == 409


def test_ensure_system_folder_is_idempotent_and_non_deletable(folder_service):
    service, _ = folder_service
    first = service.ensure_system_folder(client_id=1, parent_folder_id=None, name="Enriched Catalog")
    second = service.ensure_system_folder(client_id=1, parent_folder_id=None, name="Enriched Catalog")
    assert first["folder_id"] == second["folder_id"]
    assert first["system"] is True
    with pytest.raises(MediaFolderError) as exc_info:
        service.delete_folder(client_id=1, folder_id=first["folder_id"])
    assert exc_info.value.status_code == 403
    with pytest.raises(MediaFolderError):
        service.rename_folder(client_id=1, folder_id=first["folder_id"], name="Other")


def test_list_children_filters_by_parent(folder_service):
    service, _ = folder_service
    parent = service.create_folder(client_id=1, parent_folder_id=None, name="Root")
    child = service.create_folder(client_id=1, parent_folder_id=parent["folder_id"], name="Nested")

    root_children = service.list_children(client_id=1, parent_folder_id=None)
    nested_children = service.list_children(client_id=1, parent_folder_id=parent["folder_id"])

    assert any(item["folder_id"] == parent["folder_id"] for item in root_children)
    assert nested_children[0]["folder_id"] == child["folder_id"]
