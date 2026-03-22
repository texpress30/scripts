from __future__ import annotations

from typing import Any

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_PURGED,
    MediaFileKind,
    MediaFileStatus,
)
from app.services.media_metadata_repository import media_metadata_repository

_SUPPORTED_KINDS: tuple[str, ...] = ("image", "video", "document")
_SUPPORTED_STATUSES: tuple[str, ...] = ("draft", "ready", "delete_requested", "purged")
_DEFAULT_LIMIT = 25
_MAX_LIMIT = 100


class StorageMediaReadError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class StorageMediaReadService:
    def list_media(
        self,
        *,
        client_id: int,
        kind: MediaFileKind | None = None,
        status: MediaFileStatus | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaReadError("client_id must be a positive integer", status_code=400)

        normalized_kind = str(kind or "").strip()
        normalized_status = str(status or "").strip()
        if normalized_kind != "" and normalized_kind not in _SUPPORTED_KINDS:
            raise StorageMediaReadError("kind must be one of: image, video, document", status_code=400)
        if normalized_status != "" and normalized_status not in _SUPPORTED_STATUSES:
            raise StorageMediaReadError("status is invalid", status_code=400)

        resolved_limit = _DEFAULT_LIMIT if limit is None else int(limit)
        if resolved_limit <= 0:
            resolved_limit = _DEFAULT_LIMIT
        resolved_limit = min(resolved_limit, _MAX_LIMIT)
        resolved_offset = 0 if offset is None else max(0, int(offset))

        items = media_metadata_repository.list_for_client(
            client_id=normalized_client_id,
            kind=normalized_kind or None,
            status=normalized_status or None,
            limit=resolved_limit,
            offset=resolved_offset,
            include_deleted_by_default=False,
        )
        total = media_metadata_repository.count_for_client(
            client_id=normalized_client_id,
            kind=normalized_kind or None,
            status=normalized_status or None,
            include_deleted_by_default=False,
        )
        return {
            "items": [self._list_item(item) for item in items],
            "limit": resolved_limit,
            "offset": resolved_offset,
            "total": int(total),
        }

    def get_media_detail(self, *, client_id: int, media_id: str) -> dict[str, Any]:
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaReadError("client_id must be a positive integer", status_code=400)

        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageMediaReadError("media_id is required", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageMediaReadError("Media record not found", status_code=404)
        if int(record.get("client_id") or 0) != normalized_client_id:
            raise StorageMediaReadError("Media record not found", status_code=404)

        record_status = str(record.get("status") or "").strip()
        if record_status == MEDIA_FILE_STATUS_PURGED:
            raise StorageMediaReadError("Media record not found", status_code=404)
        return self._detail_item(record)

    def _list_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "media_id": str(item.get("media_id") or ""),
            "client_id": int(item.get("client_id") or 0),
            "kind": str(item.get("kind") or ""),
            "source": str(item.get("source") or ""),
            "status": str(item.get("status") or ""),
            "original_filename": str(item.get("original_filename") or ""),
            "mime_type": str(item.get("mime_type") or ""),
            "size_bytes": int(item.get("size_bytes")) if item.get("size_bytes") is not None else None,
            "created_at": item.get("created_at"),
            "uploaded_at": item.get("uploaded_at"),
        }

    def _detail_item(self, item: dict[str, Any]) -> dict[str, Any]:
        storage = item.get("storage") if isinstance(item.get("storage"), dict) else {}
        payload = self._list_item(item)
        payload.update(
            {
                "metadata": dict(item.get("metadata") or {}),
                "storage": {
                    "provider": str(storage.get("provider") or ""),
                    "bucket": str(storage.get("bucket") or ""),
                    "key": str(storage.get("key") or ""),
                    "region": str(storage.get("region") or ""),
                    "etag": str(storage.get("etag") or "").strip() or None,
                    "version_id": str(storage.get("version_id") or "").strip() or None,
                },
                "updated_at": item.get("updated_at"),
                "deleted_at": item.get("deleted_at"),
                "purged_at": item.get("purged_at"),
            }
        )
        return payload


storage_media_read_service = StorageMediaReadService()
