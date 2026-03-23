from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import storage_upload_complete as service_module


class _FakeS3Client:
    def __init__(self, payload=None, *, should_fail: bool = False, fail_message: str = "NotFound") -> None:
        self.payload = payload or {}
        self.should_fail = should_fail
        self.fail_message = fail_message
        self.calls: list[dict[str, str]] = []

    def head_object(self, *, Bucket: str, Key: str):
        self.calls.append({"Bucket": Bucket, "Key": Key})
        if self.should_fail:
            raise RuntimeError(self.fail_message)
        return dict(self.payload)


def _draft_record(*, status: str = "draft", client_id: int = 44) -> dict[str, object]:
    return {
        "media_id": "media-1",
        "client_id": client_id,
        "status": status,
        "mime_type": "image/png",
        "size_bytes": None,
        "uploaded_at": None,
        "storage": {
            "bucket": "media-bucket",
            "key": "clients/44/image/media-1/file.png",
            "region": "eu-central-1",
            "etag": None,
            "version_id": None,
        },
    }


def test_complete_upload_success_marks_ready(monkeypatch):
    fake_s3 = _FakeS3Client(
        payload={
            "ContentLength": 456,
            "ContentType": "image/webp",
            "ETag": '"abc123"',
            "VersionId": "v2",
        }
    )
    calls: dict[str, object] = {}

    class FakeRepository:
        def get_by_media_id(self, media_id: str):
            calls["get_by_media_id"] = media_id
            return _draft_record()

        def mark_ready(self, **kwargs):
            calls["mark_ready"] = kwargs
            updated = _draft_record(status="ready")
            updated["mime_type"] = kwargs.get("mime_type")
            updated["size_bytes"] = kwargs.get("size_bytes")
            updated["uploaded_at"] = kwargs.get("uploaded_at")
            updated["storage"]["etag"] = kwargs.get("etag")
            updated["storage"]["version_id"] = kwargs.get("version_id")
            return updated

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    payload = service_module.storage_upload_complete_service.complete_upload(client_id=44, media_id="media-1")

    assert calls["get_by_media_id"] == "media-1"
    assert fake_s3.calls[0] == {"Bucket": "media-bucket", "Key": "clients/44/image/media-1/file.png"}
    assert calls["mark_ready"]["size_bytes"] == 456
    assert calls["mark_ready"]["mime_type"] == "image/webp"
    assert calls["mark_ready"]["etag"] == '"abc123"'
    assert calls["mark_ready"]["version_id"] == "v2"
    assert isinstance(calls["mark_ready"]["uploaded_at"], datetime)
    assert calls["mark_ready"]["uploaded_at"].tzinfo == timezone.utc
    assert payload["status"] == "ready"
    assert payload["size_bytes"] == 456


def test_complete_upload_not_found(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return None

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageUploadCompleteError) as exc:
        service_module.storage_upload_complete_service.complete_upload(client_id=10, media_id="missing")
    assert exc.value.status_code == 404


def test_complete_upload_client_mismatch(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _draft_record(client_id=99)

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageUploadCompleteError) as exc:
        service_module.storage_upload_complete_service.complete_upload(client_id=10, media_id="media-1")
    assert exc.value.status_code == 404


def test_complete_upload_missing_object_does_not_mark_ready(monkeypatch):
    fake_s3 = _FakeS3Client(should_fail=True, fail_message="NotFound")
    calls: dict[str, int] = {"mark_ready": 0}

    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _draft_record()

        def mark_ready(self, **_kwargs):
            calls["mark_ready"] += 1
            return _draft_record(status="ready")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    with pytest.raises(service_module.StorageUploadCompleteError) as exc:
        service_module.storage_upload_complete_service.complete_upload(client_id=44, media_id="media-1")

    assert exc.value.status_code == 409
    assert calls["mark_ready"] == 0


def test_complete_upload_rejects_delete_requested(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _draft_record(status="delete_requested")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageUploadCompleteError) as exc:
        service_module.storage_upload_complete_service.complete_upload(client_id=44, media_id="media-1")

    assert exc.value.status_code == 409


def test_complete_upload_idempotent_when_already_ready(monkeypatch):
    ready_record = _draft_record(status="ready")
    ready_record["uploaded_at"] = datetime.now(timezone.utc)
    ready_record["size_bytes"] = 321

    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return ready_record

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: _FakeS3Client(should_fail=True))

    payload = service_module.storage_upload_complete_service.complete_upload(client_id=44, media_id="media-1")
    assert payload["status"] == "ready"
    assert payload["size_bytes"] == 321
