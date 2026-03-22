from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import storage_media_read as service_module


def _record(*, media_id: str, client_id: int, kind: str, status: str, created_at: datetime) -> dict[str, object]:
    return {
        "media_id": media_id,
        "client_id": client_id,
        "kind": kind,
        "source": "user_upload",
        "status": status,
        "original_filename": f"{media_id}.png",
        "mime_type": "image/png",
        "size_bytes": 10,
        "created_at": created_at,
        "uploaded_at": None,
        "updated_at": created_at,
        "deleted_at": None,
        "purged_at": None,
        "metadata": {},
        "storage": {
            "provider": "s3",
            "bucket": "media-bucket",
            "key": f"clients/{client_id}/image/{media_id}/file.png",
            "region": "eu-central-1",
            "etag": None,
            "version_id": None,
        },
    }


def test_list_media_uses_filters_pagination_and_count(monkeypatch):
    now = datetime.now(timezone.utc)
    calls: dict[str, object] = {}

    class FakeRepo:
        def list_for_client(self, **kwargs):
            calls["list"] = kwargs
            return [_record(media_id="m2", client_id=7, kind="image", status="ready", created_at=now)]

        def count_for_client(self, **kwargs):
            calls["count"] = kwargs
            return 12

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    payload = service_module.storage_media_read_service.list_media(
        client_id=7,
        kind="image",
        status="ready",
        limit=10,
        offset=5,
    )

    assert payload["limit"] == 10
    assert payload["offset"] == 5
    assert payload["total"] == 12
    assert payload["items"][0]["media_id"] == "m2"
    assert calls["list"]["client_id"] == 7
    assert calls["list"]["kind"] == "image"
    assert calls["list"]["status"] == "ready"
    assert calls["list"]["include_deleted_by_default"] is False


def test_list_media_default_status_excludes_deleted(monkeypatch):
    calls: dict[str, object] = {}

    class FakeRepo:
        def list_for_client(self, **kwargs):
            calls["list"] = kwargs
            return []

        def count_for_client(self, **kwargs):
            calls["count"] = kwargs
            return 0

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    service_module.storage_media_read_service.list_media(client_id=9)
    assert calls["list"]["status"] is None
    assert calls["list"]["include_deleted_by_default"] is False


def test_detail_success_and_purged_behavior(monkeypatch):
    now = datetime.now(timezone.utc)

    class FakeRepo:
        def get_by_media_id(self, media_id: str):
            if media_id == "ready":
                return _record(media_id="ready", client_id=5, kind="image", status="ready", created_at=now)
            if media_id == "purged":
                return _record(media_id="purged", client_id=5, kind="image", status="purged", created_at=now)
            return None

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    detail = service_module.storage_media_read_service.get_media_detail(client_id=5, media_id="ready")
    assert detail["media_id"] == "ready"
    assert detail["storage"]["bucket"] == "media-bucket"

    with pytest.raises(service_module.StorageMediaReadError) as exc:
        service_module.storage_media_read_service.get_media_detail(client_id=5, media_id="purged")
    assert exc.value.status_code == 404


def test_detail_client_mismatch_and_not_found(monkeypatch):
    now = datetime.now(timezone.utc)

    class FakeRepo:
        def get_by_media_id(self, media_id: str):
            if media_id == "exists":
                return _record(media_id="exists", client_id=11, kind="image", status="ready", created_at=now)
            return None

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    with pytest.raises(service_module.StorageMediaReadError) as mismatch:
        service_module.storage_media_read_service.get_media_detail(client_id=10, media_id="exists")
    assert mismatch.value.status_code == 404

    with pytest.raises(service_module.StorageMediaReadError) as missing:
        service_module.storage_media_read_service.get_media_detail(client_id=10, media_id="missing")
    assert missing.value.status_code == 404


def test_list_media_runtime_error_bubbles(monkeypatch):
    class FakeRepo:
        def list_for_client(self, **kwargs):
            raise RuntimeError("Mongo not configured")

        def count_for_client(self, **kwargs):
            return 0

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    with pytest.raises(RuntimeError):
        service_module.storage_media_read_service.list_media(client_id=1)
