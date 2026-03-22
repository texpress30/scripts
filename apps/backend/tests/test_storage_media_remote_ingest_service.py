from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import storage_media_remote_ingest as service_module
from app.services.storage_media_ingest import StorageMediaIngestResult


class _FakeResponse:
    def __init__(self, *, status: int = 200, headers: dict[str, str] | None = None, body: bytes = b"ok") -> None:
        self.status = status
        self.headers = dict(headers or {})
        self._body = bytes(body)

    def read(self, _size: int = -1) -> bytes:
        return bytes(self._body)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _result() -> StorageMediaIngestResult:
    return StorageMediaIngestResult(
        media_id="m1",
        status="ready",
        client_id=1,
        kind="image",
        source="backend_ingest",
        bucket="b",
        key="k",
        region="r",
        mime_type="image/png",
        size_bytes=2,
    )


def test_upload_from_url_downloads_and_delegates(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["timeout"] = timeout
        return _FakeResponse(headers={"Content-Type": "image/png"}, body=b"hi")

    class FakeIngest:
        def upload_bytes(self, **kwargs):
            captured["ingest"] = kwargs
            return _result()

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=12, storage_media_remote_fetch_max_bytes=100))
    monkeypatch.setattr(service_module, "urlopen", _fake_urlopen)
    monkeypatch.setattr(service_module, "storage_media_ingest_service", FakeIngest())

    result = service_module.storage_media_remote_ingest_service.upload_from_url(
        client_id=1,
        kind="image",
        source="backend_ingest",
        remote_url="https://cdn.example.com/path/file.png",
        metadata={"a": 1},
        request_headers={"Authorization": "Bearer token"},
    )

    assert result.media_id == "m1"
    assert captured["timeout"] == 12
    assert captured["ingest"]["original_filename"] == "file.png"
    assert captured["ingest"]["mime_type"] == "image/png"
    assert captured["ingest"]["content"] == b"hi"
    assert captured["ingest"]["metadata"] == {"a": 1}


def test_explicit_filename_and_mime_type_have_priority(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=100))
    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(headers={"Content-Type": "image/png; charset=utf-8"}, body=b"ab"))

    class FakeIngest:
        def upload_bytes(self, **kwargs):
            captured.update(kwargs)
            return _result()

    monkeypatch.setattr(service_module, "storage_media_ingest_service", FakeIngest())

    service_module.storage_media_remote_ingest_service.upload_from_url(
        client_id=1,
        kind="image",
        source="backend_ingest",
        remote_url="https://cdn.example.com/path/source.jpg",
        original_filename="explicit.bin",
        mime_type="application/custom",
    )

    assert captured["original_filename"] == "explicit.bin"
    assert captured["mime_type"] == "application/custom"


def test_filename_and_mime_fallbacks(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=100))
    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(headers={}, body=b"ab"))

    class FakeIngest:
        def upload_bytes(self, **kwargs):
            captured.update(kwargs)
            return _result()

    monkeypatch.setattr(service_module, "storage_media_ingest_service", FakeIngest())

    service_module.storage_media_remote_ingest_service.upload_from_url(
        client_id=1,
        kind="document",
        source="platform_sync",
        remote_url="https://cdn.example.com/",
    )

    assert captured["original_filename"] == "download.bin"
    assert captured["mime_type"] == "application/octet-stream"


def test_invalid_scheme_and_local_host_rejected(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=100))

    with pytest.raises(service_module.StorageMediaRemoteIngestError):
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="ftp://example.com/a.png",
        )

    with pytest.raises(service_module.StorageMediaRemoteIngestError):
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="http://127.0.0.1/a.png",
        )


def test_non_2xx_and_network_timeout_errors(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=100))

    with pytest.raises(service_module.StorageMediaRemoteIngestError):
        monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(status=404, body=b"x"))
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="https://cdn.example.com/a.png",
        )

    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: (_ for _ in ()).throw(RuntimeError("timeout")))
    with pytest.raises(service_module.StorageMediaRemoteIngestError) as exc:
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="https://cdn.example.com/a.png",
        )
    assert exc.value.status_code == 503


def test_content_length_and_body_limits(monkeypatch):
    calls = {"ingest": 0}

    class FakeIngest:
        def upload_bytes(self, **kwargs):
            calls["ingest"] += 1
            return _result()

    monkeypatch.setattr(service_module, "storage_media_ingest_service", FakeIngest())
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=3))

    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(headers={"Content-Length": "10"}, body=b"abc"))
    with pytest.raises(service_module.StorageMediaRemoteIngestError):
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="https://cdn.example.com/a.png",
        )

    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(headers={}, body=b"abcd"))
    with pytest.raises(service_module.StorageMediaRemoteIngestError):
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="https://cdn.example.com/a.png",
        )

    assert calls["ingest"] == 0


def test_ingest_error_is_propagated(monkeypatch):
    monkeypatch.setattr(service_module, "load_settings", lambda: SimpleNamespace(storage_media_remote_fetch_timeout_seconds=5, storage_media_remote_fetch_max_bytes=100))
    monkeypatch.setattr(service_module, "urlopen", lambda request, timeout: _FakeResponse(headers={}, body=b"ab"))

    class FakeIngest:
        def upload_bytes(self, **kwargs):
            raise service_module.StorageMediaIngestError("ingest failed", status_code=503)

    monkeypatch.setattr(service_module, "storage_media_ingest_service", FakeIngest())

    with pytest.raises(service_module.StorageMediaIngestError):
        service_module.storage_media_remote_ingest_service.upload_from_url(
            client_id=1,
            kind="image",
            source="backend_ingest",
            remote_url="https://cdn.example.com/a.png",
        )


def test_no_remote_ingest_endpoint_added():
    storage_api_source = Path("/workspace/scripts/apps/backend/app/api/storage.py").read_text()
    assert "/from-url" not in storage_api_source
