from __future__ import annotations

import pytest

from app.services import storage_media_delete as service_module


def _record(*, media_id: str = "m1", client_id: int = 7, status: str = "ready") -> dict[str, object]:
    return {
        "media_id": media_id,
        "client_id": client_id,
        "status": status,
        "kind": "image",
        "original_filename": "hero.png",
        "deleted_at": None,
        "updated_at": "2026-03-22T12:00:00Z",
        "storage": {"bucket": "media-bucket", "key": "clients/7/image/m1/hero.png"},
    }


def test_soft_delete_ready_marks_delete_requested(monkeypatch):
    calls: dict[str, object] = {}

    class FakeRepo:
        def get_by_media_id(self, media_id: str):
            assert media_id == "m1"
            return _record(status="ready")

        def soft_delete(self, *, media_id: str):
            calls["soft_delete"] = media_id
            payload = _record(status="delete_requested")
            payload["deleted_at"] = "2026-03-22T12:05:00Z"
            payload["updated_at"] = "2026-03-22T12:05:00Z"
            return payload

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    payload = service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert calls["soft_delete"] == "m1"
    assert payload["status"] == "delete_requested"
    assert payload["deleted_at"] == "2026-03-22T12:05:00Z"


def test_soft_delete_draft_marks_delete_requested(monkeypatch):
    class FakeRepo:
        def get_by_media_id(self, _media_id: str):
            return _record(status="draft")

        def soft_delete(self, *, media_id: str):
            payload = _record(status="delete_requested")
            payload["deleted_at"] = "now"
            payload["updated_at"] = "now"
            return payload

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    payload = service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert payload["status"] == "delete_requested"


def test_soft_delete_idempotent_for_delete_requested(monkeypatch):
    calls = {"soft_delete": 0}

    class FakeRepo:
        def get_by_media_id(self, _media_id: str):
            payload = _record(status="delete_requested")
            payload["deleted_at"] = "already"
            return payload

        def soft_delete(self, *, media_id: str):
            calls["soft_delete"] += 1
            return _record(status="delete_requested")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    payload = service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert calls["soft_delete"] == 0
    assert payload["status"] == "delete_requested"
    assert payload["deleted_at"] == "already"


def test_soft_delete_purged_not_found(monkeypatch):
    class FakeRepo:
        def get_by_media_id(self, _media_id: str):
            return _record(status="purged")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    with pytest.raises(service_module.StorageMediaDeleteError) as exc:
        service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert exc.value.status_code == 404


def test_soft_delete_missing_or_mismatch_not_found(monkeypatch):
    class FakeRepo:
        def get_by_media_id(self, media_id: str):
            if media_id == "m1":
                return _record(client_id=99, status="ready")
            return None

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    with pytest.raises(service_module.StorageMediaDeleteError) as mismatch:
        service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert mismatch.value.status_code == 404

    with pytest.raises(service_module.StorageMediaDeleteError) as missing:
        service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="missing")
    assert missing.value.status_code == 404


def test_soft_delete_runtime_error_bubbles(monkeypatch):
    class FakeRepo:
        def get_by_media_id(self, _media_id: str):
            raise RuntimeError("Mongo not configured")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    with pytest.raises(RuntimeError):
        service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")


def test_soft_delete_flow_does_not_depend_on_s3_symbols(monkeypatch):
    class FakeRepo:
        def get_by_media_id(self, _media_id: str):
            return _record(status="ready")

        def soft_delete(self, *, media_id: str):
            payload = _record(status="delete_requested")
            payload["deleted_at"] = "now"
            payload["updated_at"] = "now"
            return payload

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    assert not hasattr(service_module, "get_s3_client")
    assert not hasattr(service_module, "get_s3_presigned_ttl_seconds")

    payload = service_module.storage_media_delete_service.soft_delete_media(client_id=7, media_id="m1")
    assert payload["status"] == "delete_requested"
