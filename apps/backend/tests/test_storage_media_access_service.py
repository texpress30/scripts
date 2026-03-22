from __future__ import annotations

import pytest

from app.services import storage_media_access as service_module


class _FakeS3Client:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
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
        if self.should_fail:
            raise RuntimeError("S3 unavailable")
        return "https://signed.example/access"


def _ready_record(*, status: str = "ready", client_id: int = 44, mime_type: str = "image/png") -> dict[str, object]:
    return {
        "media_id": "media-1",
        "client_id": client_id,
        "status": status,
        "mime_type": mime_type,
        "original_filename": "Hero Banner @2x.png",
        "storage": {
            "bucket": "media-bucket",
            "key": "clients/44/image/media-1/Hero_Banner_2x.png",
        },
    }


def test_access_url_success_inline(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepository:
        def get_by_media_id(self, media_id: str):
            assert media_id == "media-1"
            return _ready_record()

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "get_s3_presigned_ttl_seconds", lambda: 900)

    payload = service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")

    assert payload["media_id"] == "media-1"
    assert payload["status"] == "ready"
    assert payload["method"] == "GET"
    assert payload["expires_in"] == 900
    assert payload["disposition"] == "inline"
    assert payload["filename"] == "Hero_Banner_2x.png"
    assert fake_s3.calls[0]["operation_name"] == "get_object"
    assert fake_s3.calls[0]["params"]["Bucket"] == "media-bucket"
    assert fake_s3.calls[0]["params"]["Key"] == "clients/44/image/media-1/Hero_Banner_2x.png"
    assert fake_s3.calls[0]["params"]["ResponseContentType"] == "image/png"
    assert fake_s3.calls[0]["params"]["ResponseContentDisposition"] == 'inline; filename="Hero_Banner_2x.png"'


def test_access_url_attachment_disposition(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _ready_record()

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "get_s3_presigned_ttl_seconds", lambda: 120)

    payload = service_module.storage_media_access_service.build_access_url(
        client_id=44,
        media_id="media-1",
        disposition="attachment",
    )

    assert payload["disposition"] == "attachment"
    assert fake_s3.calls[0]["params"]["ResponseContentDisposition"] == 'attachment; filename="Hero_Banner_2x.png"'


def test_access_url_omits_response_content_type_when_missing(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _ready_record(mime_type="")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "get_s3_presigned_ttl_seconds", lambda: 120)

    service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")
    assert "ResponseContentType" not in fake_s3.calls[0]["params"]


@pytest.mark.parametrize("status", ["draft", "delete_requested"])
def test_access_url_rejects_invalid_status(monkeypatch, status: str):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _ready_record(status=status)

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageMediaAccessError) as exc:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")
    assert exc.value.status_code == 409


def test_access_url_purged_is_not_found(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _ready_record(status="purged")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageMediaAccessError) as exc:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")
    assert exc.value.status_code == 404


def test_access_url_mismatch_and_missing_record(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, media_id: str):
            if media_id == "exists":
                return _ready_record(client_id=999)
            return None

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageMediaAccessError) as mismatch:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="exists")
    assert mismatch.value.status_code == 404

    with pytest.raises(service_module.StorageMediaAccessError) as missing:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="missing")
    assert missing.value.status_code == 404


def test_access_url_rejects_incomplete_storage(monkeypatch):
    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            record = _ready_record()
            record["storage"] = {"bucket": "media-bucket", "key": ""}
            return record

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())

    with pytest.raises(service_module.StorageMediaAccessError) as exc:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")
    assert exc.value.status_code == 409


def test_access_url_provider_unavailable(monkeypatch):
    fake_s3 = _FakeS3Client(should_fail=True)

    class FakeRepository:
        def get_by_media_id(self, _media_id: str):
            return _ready_record()

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepository())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)
    monkeypatch.setattr(service_module, "get_s3_presigned_ttl_seconds", lambda: 120)

    with pytest.raises(service_module.StorageMediaAccessError) as exc:
        service_module.storage_media_access_service.build_access_url(client_id=44, media_id="media-1")
    assert exc.value.status_code == 503


def test_sanitize_disposition_filename():
    assert service_module.sanitize_disposition_filename("  ") == "file"
    assert service_module.sanitize_disposition_filename('promo "spring".pdf') == "promo_spring_.pdf"
