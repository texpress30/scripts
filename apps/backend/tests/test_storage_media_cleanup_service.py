from __future__ import annotations

import pytest

from app.services import storage_media_cleanup as service_module


class _FakeS3Client:
    def __init__(self, failures: dict[str, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[dict[str, object]] = []

    def delete_object(self, **kwargs):
        self.calls.append(dict(kwargs))
        key = str(kwargs.get("Key") or "")
        if key in self.failures:
            raise self.failures[key]
        return {"DeleteMarker": True}


def _record(*, media_id: str, bucket: str = "media-bucket", key: str = "key", version_id: str | None = None) -> dict[str, object]:
    storage = {"bucket": bucket, "key": key}
    if version_id is not None:
        storage["version_id"] = version_id
    return {"media_id": media_id, "storage": storage}


def test_run_batch_selects_delete_requested_and_orders(monkeypatch):
    captured: dict[str, object] = {}
    fake_s3 = _FakeS3Client()

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            captured["limit"] = limit
            return [
                _record(media_id="m-old", key="old"),
                _record(media_id="m-new", key="new"),
            ]

        def mark_purged(self, *, media_id: str):
            captured.setdefault("purged", []).append(media_id)
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=2)

    assert captured["limit"] == 2
    assert [item["media_id"] for item in result["items"]] == ["m-old", "m-new"]
    assert result["purged"] == 2


def test_run_batch_delete_object_params_include_version(monkeypatch):
    fake_s3 = _FakeS3Client()

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [_record(media_id="m1", bucket="b1", key="k1", version_id="v1")]

        def mark_purged(self, *, media_id: str):
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=10)

    assert result["purged"] == 1
    assert fake_s3.calls[0] == {"Bucket": "b1", "Key": "k1", "VersionId": "v1"}


def test_run_batch_treats_missing_s3_object_as_success(monkeypatch):
    fake_s3 = _FakeS3Client(failures={"k1": RuntimeError("NoSuchKey")})

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [_record(media_id="m1", key="k1")]

        def mark_purged(self, *, media_id: str):
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=5)

    assert result["purged"] == 1
    assert result["failed"] == 0
    assert result["items"][0]["outcome"] == "purged"


def test_run_batch_skips_incomplete_storage_without_mark_purged(monkeypatch):
    calls = {"mark": 0}
    fake_s3 = _FakeS3Client()

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [_record(media_id="m1", bucket="", key="")]

        def mark_purged(self, *, media_id: str):
            calls["mark"] += 1
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=5)

    assert result["skipped"] == 1
    assert calls["mark"] == 0
    assert len(fake_s3.calls) == 0


def test_run_batch_continues_after_s3_failure(monkeypatch):
    fake_s3 = _FakeS3Client(failures={"bad": RuntimeError("AccessDenied")})
    purged: list[str] = []

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [
                _record(media_id="m1", key="bad"),
                _record(media_id="m2", key="good"),
            ]

        def mark_purged(self, *, media_id: str):
            purged.append(media_id)
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=10)

    assert result["processed"] == 2
    assert result["failed"] == 1
    assert result["purged"] == 1
    assert purged == ["m2"]


def test_run_batch_runtime_provider_errors(monkeypatch):
    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [_record(media_id="m1", key="k1")]

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: (_ for _ in ()).throw(RuntimeError("S3 missing")))

    with pytest.raises(service_module.StorageMediaCleanupError) as exc:
        service_module.storage_media_cleanup_service.run_batch(limit=10)
    assert exc.value.status_code == 503


def test_run_batch_runtime_mongo_errors(monkeypatch):
    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            raise RuntimeError("Mongo missing")

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())

    with pytest.raises(service_module.StorageMediaCleanupError) as exc:
        service_module.storage_media_cleanup_service.run_batch(limit=10)
    assert exc.value.status_code == 503


def test_run_batch_result_counts(monkeypatch):
    fake_s3 = _FakeS3Client(failures={"k-fail": RuntimeError("AccessDenied")})

    class FakeRepo:
        def list_cleanup_candidates(self, *, limit: int):
            return [
                _record(media_id="ok", key="k-ok"),
                _record(media_id="skip", bucket="", key=""),
                _record(media_id="fail", key="k-fail"),
            ]

        def mark_purged(self, *, media_id: str):
            return {"media_id": media_id}

    monkeypatch.setattr(service_module, "media_metadata_repository", FakeRepo())
    monkeypatch.setattr(service_module, "get_s3_client", lambda: fake_s3)

    result = service_module.storage_media_cleanup_service.run_batch(limit=10)

    assert result["processed"] == 3
    assert result["purged"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == 1
    assert len(result["items"]) == 3
