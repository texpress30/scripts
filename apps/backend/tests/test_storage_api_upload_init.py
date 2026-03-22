from __future__ import annotations

import sys
import types

import pytest

from app.services.auth import AuthUser
from app.services.storage_upload_complete import StorageUploadCompleteError
from app.services.storage_upload_init import StorageUploadInitError
from app.services.storage_media_read import StorageMediaReadError


class _FakeHTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _FakeAPIRouter:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get(self, *args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    def post(self, *args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    def delete(self, *args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator


def _install_fake_fastapi_module() -> None:
    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.APIRouter = _FakeAPIRouter
    fake_fastapi.Depends = lambda x: x
    fake_fastapi.Query = lambda default=None, **_kwargs: default
    fake_fastapi.Header = lambda default=None, **_kwargs: default
    fake_fastapi.HTTPException = _FakeHTTPException
    fake_fastapi.status = types.SimpleNamespace(
        HTTP_503_SERVICE_UNAVAILABLE=503,
        HTTP_500_INTERNAL_SERVER_ERROR=500,
    )
    sys.modules["fastapi"] = fake_fastapi


def _install_fake_pydantic_module() -> None:
    fake_pydantic = types.ModuleType("pydantic")

    class _FakeBaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_pydantic.BaseModel = _FakeBaseModel
    fake_pydantic.Field = lambda default=None, default_factory=None, **_kwargs: default_factory() if default_factory is not None else default
    sys.modules["pydantic"] = fake_pydantic


def _admin_user() -> AuthUser:
    return AuthUser(email="admin@example.com", role="agency_admin")


def test_storage_upload_init_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_upload_init_service,
        "init_upload",
        lambda **_kwargs: {
            "media_id": "m1",
            "status": "draft",
            "bucket": "media-bucket",
            "key": "clients/1/image/m1/file.png",
            "region": "eu-central-1",
            "upload": {
                "method": "PUT",
                "url": "https://signed.example/upload",
                "expires_in": 900,
                "headers": {"Content-Type": "image/png"},
            },
        },
    )

    response = storage_api.init_direct_upload(
        payload=storage_api.StorageUploadInitRequest(
            client_id=1,
            kind="image",
            original_filename="file.png",
            mime_type="image/png",
        ),
        user=_admin_user(),
    )

    assert response.media_id == "m1"
    assert response.upload["method"] == "PUT"
    assert response.upload["headers"]["Content-Type"] == "image/png"


def test_storage_upload_init_endpoint_maps_runtime_unavailable(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    def _raise_error(**_kwargs):
        raise StorageUploadInitError("Storage unavailable", status_code=503)

    monkeypatch.setattr(storage_api.storage_upload_init_service, "init_upload", _raise_error)

    with pytest.raises(Exception) as exc:
        storage_api.init_direct_upload(
            payload=storage_api.StorageUploadInitRequest(
                client_id=1,
                kind="image",
                original_filename="file.png",
                mime_type="image/png",
            ),
            user=_admin_user(),
        )

    assert getattr(exc.value, "status_code", None) == 503


def test_storage_upload_init_endpoint_logs_and_maps_runtime_error(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    logged: list[tuple[str, tuple[object, ...]]] = []

    class _FakeLogger:
        def warning(self, *_args, **_kwargs):
            return None

        def exception(self, message, *args, **_kwargs):
            logged.append((message, args))

    monkeypatch.setattr(storage_api, "logger", _FakeLogger())
    monkeypatch.setattr(
        storage_api.storage_upload_init_service,
        "init_upload",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("Storage metadata repository is unavailable for upload initialization.")),
    )

    with pytest.raises(Exception) as exc:
        storage_api.init_direct_upload(
            payload=storage_api.StorageUploadInitRequest(
                client_id=123,
                kind="image",
                original_filename="logo.png",
                mime_type="image/png",
            ),
            user=_admin_user(),
        )

    assert getattr(exc.value, "status_code", None) == 503
    assert "Storage metadata repository is unavailable for upload initialization." in str(getattr(exc.value, "detail", ""))
    assert logged
    assert logged[0][0] == "storage_upload_init_runtime_error client_id=%s kind=%s original_filename=%s"
    assert logged[0][1] == (123, "image", "logo.png")


def test_storage_upload_complete_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_upload_complete_service,
        "complete_upload",
        lambda **_kwargs: {
            "media_id": "m1",
            "status": "ready",
            "bucket": "media-bucket",
            "key": "clients/1/image/m1/file.png",
            "region": "eu-central-1",
            "mime_type": "image/png",
            "size_bytes": 111,
            "uploaded_at": "2026-03-22T12:00:00Z",
            "etag": '"abc"',
            "version_id": "v1",
        },
    )

    response = storage_api.complete_direct_upload(
        payload=storage_api.StorageUploadCompleteRequest(
            client_id=1,
            media_id="m1",
        ),
        user=_admin_user(),
    )

    assert response.media_id == "m1"
    assert response.status == "ready"
    assert response.size_bytes == 111


def test_storage_upload_complete_endpoint_maps_runtime_unavailable(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    def _raise_error(**_kwargs):
        raise StorageUploadCompleteError("Storage unavailable", status_code=503)

    monkeypatch.setattr(storage_api.storage_upload_complete_service, "complete_upload", _raise_error)

    with pytest.raises(Exception) as exc:
        storage_api.complete_direct_upload(
            payload=storage_api.StorageUploadCompleteRequest(
                client_id=1,
                media_id="m1",
            ),
            user=_admin_user(),
        )

    assert getattr(exc.value, "status_code", None) == 503


def test_storage_media_list_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_media_read_service,
        "list_media",
        lambda **_kwargs: {
            "items": [
                {
                    "media_id": "m1",
                    "client_id": 1,
                    "kind": "image",
                    "source": "user_upload",
                    "status": "ready",
                    "original_filename": "f.png",
                    "mime_type": "image/png",
                    "size_bytes": 100,
                    "created_at": "2026-03-22T12:00:00Z",
                    "uploaded_at": "2026-03-22T12:05:00Z",
                }
            ],
            "limit": 25,
            "offset": 0,
            "total": 1,
        },
    )

    response = storage_api.list_media(client_id=1, kind=None, status_filter=None, limit=25, offset=0, user=_admin_user())
    assert response.total == 1
    assert response.items[0]["media_id"] == "m1"


def test_storage_media_detail_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_media_read_service,
        "get_media_detail",
        lambda **_kwargs: {
            "media_id": "m1",
            "client_id": 1,
            "kind": "image",
            "source": "user_upload",
            "status": "ready",
            "original_filename": "f.png",
            "mime_type": "image/png",
            "size_bytes": 100,
            "created_at": "2026-03-22T12:00:00Z",
            "uploaded_at": "2026-03-22T12:05:00Z",
            "metadata": {},
            "storage": {
                "provider": "s3",
                "bucket": "media-bucket",
                "key": "clients/1/image/m1/f.png",
                "region": "eu-central-1",
                "etag": None,
                "version_id": None,
            },
            "updated_at": "2026-03-22T12:05:00Z",
            "deleted_at": None,
            "purged_at": None,
        },
    )

    response = storage_api.get_media_detail(media_id="m1", client_id=1, user=_admin_user())
    assert response.media_id == "m1"
    assert response.storage["bucket"] == "media-bucket"


def test_storage_media_endpoint_maps_runtime_unavailable(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    def _raise_error(**_kwargs):
        raise StorageMediaReadError("Mongo unavailable", status_code=503)

    monkeypatch.setattr(storage_api.storage_media_read_service, "list_media", _raise_error)

    with pytest.raises(Exception) as exc:
        storage_api.list_media(client_id=1, kind=None, status_filter=None, limit=25, offset=0, user=_admin_user())

    assert getattr(exc.value, "status_code", None) == 503


def test_storage_media_access_url_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_media_access_service,
        "build_access_url",
        lambda **_kwargs: {
            "media_id": "m1",
            "status": "ready",
            "mime_type": "image/png",
            "method": "GET",
            "url": "https://signed.example/access",
            "expires_in": 900,
            "disposition": "inline",
            "filename": "f.png",
        },
    )

    response = storage_api.get_media_access_url(media_id="m1", client_id=1, disposition="inline", user=_admin_user())
    assert response.media_id == "m1"
    assert response.method == "GET"


def test_storage_media_access_url_endpoint_maps_runtime_unavailable(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    def _raise_error(**_kwargs):
        raise storage_api.StorageMediaAccessError("S3 unavailable", status_code=503)

    monkeypatch.setattr(storage_api.storage_media_access_service, "build_access_url", _raise_error)

    with pytest.raises(Exception) as exc:
        storage_api.get_media_access_url(media_id="m1", client_id=1, disposition="inline", user=_admin_user())

    assert getattr(exc.value, "status_code", None) == 503


def test_storage_media_delete_endpoint_returns_payload(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)
    monkeypatch.setattr(
        storage_api.storage_media_delete_service,
        "soft_delete_media",
        lambda **_kwargs: {
            "media_id": "m1",
            "status": "delete_requested",
            "client_id": 1,
            "kind": "image",
            "original_filename": "f.png",
            "deleted_at": "2026-03-22T12:05:00Z",
            "updated_at": "2026-03-22T12:05:00Z",
        },
    )

    response = storage_api.soft_delete_media(media_id="m1", client_id=1, user=_admin_user())
    assert response.media_id == "m1"
    assert response.status == "delete_requested"


def test_storage_media_delete_endpoint_maps_runtime_unavailable(monkeypatch):
    _install_fake_fastapi_module()
    _install_fake_pydantic_module()
    from app.api import storage as storage_api

    monkeypatch.setattr(storage_api, "enforce_action_scope", lambda **_kwargs: None)
    monkeypatch.setattr(storage_api, "enforce_agency_navigation_access", lambda **_kwargs: None)

    def _raise_error(**_kwargs):
        raise storage_api.StorageMediaDeleteError("Mongo unavailable", status_code=503)

    monkeypatch.setattr(storage_api.storage_media_delete_service, "soft_delete_media", _raise_error)

    with pytest.raises(Exception) as exc:
        storage_api.soft_delete_media(media_id="m1", client_id=1, user=_admin_user())

    assert getattr(exc.value, "status_code", None) == 503
