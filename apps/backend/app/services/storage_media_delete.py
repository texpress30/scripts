from __future__ import annotations

from typing import Any

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_DRAFT,
    MEDIA_FILE_STATUS_PURGED,
    MEDIA_FILE_STATUS_READY,
)
from app.services.media_metadata_repository import media_metadata_repository
from app.services.media_reference_checker import media_reference_checker


class StorageMediaDeleteError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        references: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.references = list(references or [])


class StorageMediaDeleteService:
    def soft_delete_media(self, *, client_id: int, media_id: str) -> dict[str, Any]:
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaDeleteError("client_id must be a positive integer", status_code=400)

        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageMediaDeleteError("media_id is required", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageMediaDeleteError("Media record not found", status_code=404)
        if int(record.get("client_id") or 0) != normalized_client_id:
            raise StorageMediaDeleteError("Media record not found", status_code=404)

        status = str(record.get("status") or "").strip().lower()
        if status == MEDIA_FILE_STATUS_PURGED:
            raise StorageMediaDeleteError("Media record not found", status_code=404)

        if status == MEDIA_FILE_STATUS_DELETE_REQUESTED:
            return self._response_payload(record)

        if status not in {MEDIA_FILE_STATUS_DRAFT, MEDIA_FILE_STATUS_READY}:
            raise StorageMediaDeleteError(f"Media record cannot be soft-deleted from status={status}", status_code=409)

        references = media_reference_checker.find_references(media_id=normalized_media_id)
        if references:
            raise StorageMediaDeleteError(
                "Media is still referenced by other records. Unlink it there first before deleting.",
                status_code=409,
                references=media_reference_checker.serialize_references(references),
            )

        deleted = media_metadata_repository.soft_delete(media_id=normalized_media_id)
        if deleted is None:
            raise StorageMediaDeleteError("Failed to soft-delete media record", status_code=500)
        return self._response_payload(deleted)

    def _response_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "media_id": str(record.get("media_id") or ""),
            "status": str(record.get("status") or ""),
            "client_id": int(record.get("client_id") or 0),
            "kind": str(record.get("kind") or ""),
            "original_filename": str(record.get("original_filename") or ""),
            "deleted_at": record.get("deleted_at"),
            "updated_at": record.get("updated_at"),
        }


storage_media_delete_service = StorageMediaDeleteService()
