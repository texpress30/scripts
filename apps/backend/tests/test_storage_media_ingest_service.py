from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import storage_media_ingest as service_module


class _FakeS3Client:
    def __init__(self, *, should_fail: bool = False, payload: dict[str, object] | None = None) -> None:
        self.should_fail = should_fail
        self.payload = payload or {"ETag": '"etag-1"'}
        self.calls: list[dict[str, object]] = []

    def put_object(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.should_fail:
            raise RuntimeError("S3 unavailable")
        return dict(self.payload)


def test_upload_bytes_success_marks_ready(monkeypatch):
    fake_s3 = _FakeS3Client(payload={"ETag": '"etag-1"', "VersionId": "v1"})
    calls: dict[str, object] = {}

    class FakeRepo:
        def create_draft(self, **kwargs):
            calls["draft"] = kwargs
            return {
                "media_id": kwargs["media_id"],
                "client_id": kwargs["client_id"],
                "kind": kwargs["kind"],
                "source": kwargs["source"],
                "status": "draft",
            }

        def mark_ready(self, **kwargs):
            calls["ready"] = kwargs
            return {
                "media_id": kwargs["media_id"],
                "status": "ready",
                "client_id": 10,
                "kind": "image",
                "source": "backend_ingest",
                "mime_type": kwargs["mime_type"],
                "size_bytes": kwargs["size_bytes"],
                "uploaded_at": kwargs["uploaded_at"],
            }

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))
    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "new_media_id", lambda: "media123")

    payload = service_module.storage_media_ingest_service.upload_bytes(
        client_id=10,
        kind="image",
        source="backend_ingest",
        original_filename="My File@2x!.png",
        mime_type="image/png",
        content=b"hello-bytes",
        metadata={"origin": "cron"},
    )

    assert calls["draft"]["size_bytes"] == len(b"hello-bytes")
    assert calls["draft"]["storage_key"] == "clients/10/image/media123/My_File_2x_.png"
    assert fake_s3.calls[0]["Bucket"] == "media-bucket"
    assert fake_s3.calls[0]["Key"] == "clients/10/image/media123/My_File_2x_.png"
    assert fake_s3.calls[0]["Body"] == b"hello-bytes"
    assert fake_s3.calls[0]["ContentType"] == "image/png"
    assert calls["ready"]["etag"] == '"etag-1"'
    assert calls["ready"]["version_id"] == "v1"
    assert payload.status == "ready"
    assert payload.version_id == "v1"


def test_upload_bytes_invalid_source_rejected(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))

    with pytest.raises(service_module.StorageMediaIngestError) as exc:
        service_module.storage_media_ingest_service.upload_bytes(
            client_id=10,
            kind="image",
            source="user_upload",
            original_filename="a.png",
            mime_type="image/png",
            content=b"x",
        )
    assert exc.value.status_code == 400


def test_upload_bytes_missing_config_returns_503(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="", storage_s3_region=""))

    with pytest.raises(service_module.StorageMediaIngestError) as exc:
        service_module.storage_media_ingest_service.upload_bytes(
            client_id=1,
            kind="image",
            source="backend_ingest",
            original_filename="a.png",
            mime_type="image/png",
            content=b"x",
        )
    assert exc.value.status_code == 503


def test_create_draft_failure_does_not_call_s3(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepo:
        def create_draft(self, **kwargs):
            raise RuntimeError("Mongo unavailable")

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))
    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    with pytest.raises(RuntimeError):
        service_module.storage_media_ingest_service.upload_bytes(
            client_id=1,
            kind="image",
            source="backend_ingest",
            original_filename="a.png",
            mime_type="image/png",
            content=b"x",
        )
    assert len(fake_s3.calls) == 0


def test_put_object_failure_does_not_mark_ready(monkeypatch):
    fake_s3 = _FakeS3Client(should_fail=True)
    calls = {"ready": 0}

    class FakeRepo:
        def create_draft(self, **kwargs):
            return {"media_id": kwargs["media_id"]}

        def mark_ready(self, **kwargs):
            calls["ready"] += 1
            return {"media_id": kwargs["media_id"], "status": "ready"}

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))
    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    with pytest.raises(service_module.StorageMediaIngestError) as exc:
        service_module.storage_media_ingest_service.upload_bytes(
            client_id=1,
            kind="image",
            source="platform_sync",
            original_filename="a.png",
            mime_type="image/png",
            content=b"x",
        )
    assert exc.value.status_code == 503
    assert calls["ready"] == 0


def test_mark_ready_failure_after_upload_is_propagated(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepo:
        def create_draft(self, **kwargs):
            return {"media_id": kwargs["media_id"]}

        def mark_ready(self, **kwargs):
            return None

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))
    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    with pytest.raises(service_module.StorageMediaIngestError) as exc:
        service_module.storage_media_ingest_service.upload_bytes(
            client_id=1,
            kind="document",
            source="backend_ingest",
            original_filename="a.pdf",
            mime_type="application/pdf",
            content=b"pdf",
        )
    assert exc.value.status_code == 500


def test_no_ingest_endpoint_added():
    storage_api_source = Path("/workspace/scripts/apps/backend/app/api/storage.py").read_text()
    assert "/ingest" not in storage_api_source
