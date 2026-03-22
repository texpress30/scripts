from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import storage_upload_init as service_module


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_presigned_url(self, operation_name: str, *, Params, ExpiresIn: int, HttpMethod: str):
        self.calls.append(
            {
                "operation_name": operation_name,
                "params": dict(Params),
                "expires_in": ExpiresIn,
                "http_method": HttpMethod,
            }
        )
        return "https://signed.example/upload"


def test_init_upload_creates_draft_and_generates_presigned_url(monkeypatch):
    fake_s3 = _FakeS3Client()
    calls: dict[str, object] = {"indexes": 0}

    class FakeRepository:
        def initialize_indexes(self):
            calls["indexes"] = int(calls["indexes"]) + 1

        def create_draft(self, **kwargs):
            calls["draft"] = kwargs
            return {
                "media_id": kwargs["media_id"],
                "status": "draft",
                "storage": {
                    "bucket": kwargs["storage_bucket"],
                    "key": kwargs["storage_key"],
                },
            }

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="media-bucket", storage_s3_region="eu-central-1"))
    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "get_s3_presigned_ttl_seconds", lambda: 900)
    monkeypatch.setattr(service_module, "new_media_id", lambda: "media123")

    service = service_module.StorageUploadInitService()
    payload = service.init_upload(
        client_id=77,
        kind="image",
        original_filename="My File@2x!.png",
        mime_type="image/png",
        size_bytes=123,
        metadata={"folder": "hero"},
    )

    assert calls["indexes"] == 1
    assert calls["draft"]["source"] == "user_upload"
    assert calls["draft"]["storage_key"] == "clients/77/image/media123/My_File_2x_.png"
    assert payload["bucket"] == "media-bucket"
    assert payload["key"] == "clients/77/image/media123/My_File_2x_.png"
    assert payload["upload"]["method"] == "PUT"
    assert payload["upload"]["expires_in"] == 900
    assert payload["upload"]["headers"]["Content-Type"] == "image/png"
    assert fake_s3.calls[0]["params"]["Bucket"] == "media-bucket"
    assert fake_s3.calls[0]["params"]["ContentType"] == "image/png"


def test_init_upload_missing_s3_config_returns_runtime_error(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_s3_bucket="", storage_s3_region=""))
    service = service_module.StorageUploadInitService()

    with pytest.raises(service_module.StorageUploadInitError) as exc:
        service.init_upload(
            client_id=1,
            kind="video",
            original_filename="clip.mp4",
            mime_type="video/mp4",
        )

    assert exc.value.status_code == 503


def test_sanitize_filename_fallback():
    assert service_module.sanitize_filename("  ") == "file"
    assert service_module.sanitize_filename("invoice 2026#.pdf") == "invoice_2026_.pdf"
