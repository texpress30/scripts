from __future__ import annotations

import pytest

from app.services import storage_media_delete as delete_module
from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_READY,
)
from app.services.media_reference_checker import MediaReference
from app.services.storage_media_delete import StorageMediaDeleteError, storage_media_delete_service


def _make_media_record(
    *,
    client_id: int = 42,
    media_id: str = "mid-1",
    status: str = MEDIA_FILE_STATUS_READY,
) -> dict[str, object]:
    return {
        "media_id": media_id,
        "client_id": client_id,
        "kind": "image",
        "source": "user_upload",
        "status": status,
        "original_filename": "logo.png",
        "display_name": "logo.png",
        "folder_id": None,
    }


def test_soft_delete_rejects_when_referenced(monkeypatch):
    record = _make_media_record()
    monkeypatch.setattr(
        delete_module.media_metadata_repository,
        "get_by_media_id",
        lambda media_id: record if media_id == "mid-1" else None,
    )

    reference = MediaReference(
        kind="subaccount_business_profile",
        entity_id=42,
        entity_label="Test Sub - Profil Business (logo)",
        field="logo_media_id",
    )
    monkeypatch.setattr(
        delete_module.media_reference_checker,
        "find_references",
        lambda media_id: [reference],
    )

    calls: dict[str, object] = {"soft_delete": 0}

    def _fake_soft_delete(**kwargs):
        calls["soft_delete"] += 1
        return record

    monkeypatch.setattr(
        delete_module.media_metadata_repository,
        "soft_delete",
        _fake_soft_delete,
    )

    with pytest.raises(StorageMediaDeleteError) as exc_info:
        storage_media_delete_service.soft_delete_media(client_id=42, media_id="mid-1")

    assert exc_info.value.status_code == 409
    assert exc_info.value.references
    assert exc_info.value.references[0]["kind"] == "subaccount_business_profile"
    assert calls["soft_delete"] == 0  # delete never happened


def test_soft_delete_proceeds_when_no_references(monkeypatch):
    record = _make_media_record()
    deleted_record = dict(record)
    deleted_record["status"] = MEDIA_FILE_STATUS_DELETE_REQUESTED
    deleted_record["deleted_at"] = "2026-04-11T00:00:00+00:00"

    monkeypatch.setattr(
        delete_module.media_metadata_repository,
        "get_by_media_id",
        lambda media_id: record if media_id == "mid-1" else None,
    )
    monkeypatch.setattr(
        delete_module.media_reference_checker,
        "find_references",
        lambda media_id: [],
    )
    monkeypatch.setattr(
        delete_module.media_metadata_repository,
        "soft_delete",
        lambda **kwargs: deleted_record,
    )

    response = storage_media_delete_service.soft_delete_media(client_id=42, media_id="mid-1")
    assert response["status"] == MEDIA_FILE_STATUS_DELETE_REQUESTED
    assert response["media_id"] == "mid-1"
