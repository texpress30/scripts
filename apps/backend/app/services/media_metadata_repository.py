from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_DRAFT,
    MEDIA_FILE_STATUS_READY,
    MediaFileKind,
    MediaFileSource,
    MediaStorageDescriptor,
    new_media_id,
    utcnow,
)
from app.services.mongo_provider import get_mongo_collection
from app.services.s3_provider import get_s3_bucket_name
from app.core.config import load_settings

_COLLECTION_NAME = "media_files"


class MediaMetadataRepository:
    def _filters_for_client(
        self,
        *,
        client_id: int,
        kind: str | None = None,
        status: str | None = None,
        include_deleted_by_default: bool = False,
    ) -> dict[str, Any]:
        filters: dict[str, Any] = {"client_id": int(client_id)}
        normalized_kind = str(kind or "").strip()
        if normalized_kind != "":
            filters["kind"] = normalized_kind
        normalized_status = str(status or "").strip()
        if normalized_status != "":
            filters["status"] = normalized_status
        elif include_deleted_by_default:
            filters["status"] = {"$ne": "purged"}
        else:
            filters["status"] = {"$nin": ["purged", "delete_requested"]}
        return filters

    def _collection(self):
        collection = get_mongo_collection(_COLLECTION_NAME)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for media metadata repository usage).")
        return collection

    def initialize_indexes(self) -> None:
        collection = self._collection()
        collection.create_index(
            [("storage.bucket", 1), ("storage.key", 1)],
            unique=True,
            name="ux_media_files_storage_bucket_key",
            partialFilterExpression={
                "storage.bucket": {"$exists": True, "$type": "string", "$ne": ""},
                "storage.key": {"$exists": True, "$type": "string", "$ne": ""},
            },
        )
        collection.create_index(
            [("client_id", 1), ("status", 1), ("created_at", -1)],
            name="ix_media_files_client_status_created_at",
        )
        collection.create_index(
            [("status", 1), ("deleted_at", 1)],
            name="ix_media_files_status_deleted_at",
        )

    def create_draft(
        self,
        *,
        client_id: int,
        kind: MediaFileKind,
        source: MediaFileSource,
        original_filename: str,
        mime_type: str,
        size_bytes: int | None = None,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None,
        storage_key: str = "",
        storage_bucket: str | None = None,
        media_id: str | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        settings = load_settings()
        bucket = str(storage_bucket or get_s3_bucket_name() or "").strip()
        storage = MediaStorageDescriptor(
            provider="s3",
            bucket=bucket,
            key=str(storage_key or "").strip(),
            region=str(settings.storage_s3_region or "").strip(),
        ).to_dict()
        payload: dict[str, Any] = {
            "media_id": str(media_id or "").strip() or new_media_id(),
            "client_id": int(client_id),
            "kind": str(kind),
            "source": str(source),
            "status": MEDIA_FILE_STATUS_DRAFT,
            "original_filename": str(original_filename or "").strip(),
            "mime_type": str(mime_type or "").strip(),
            "size_bytes": int(size_bytes) if size_bytes is not None else None,
            "checksum": str(checksum or "").strip() or None,
            "metadata": dict(metadata or {}),
            "storage": storage,
            "created_at": now,
            "updated_at": now,
            "uploaded_at": None,
            "deleted_at": None,
            "purged_at": None,
        }
        self._collection().insert_one(payload)
        return self._normalize(payload)

    def get_by_media_id(self, media_id: str) -> dict[str, Any] | None:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return None
        found = self._collection().find_one({"media_id": normalized_media_id})
        return self._normalize(found)

    def get_by_storage(self, *, bucket: str, key: str) -> dict[str, Any] | None:
        normalized_bucket = str(bucket or "").strip()
        normalized_key = str(key or "").strip()
        if normalized_bucket == "" or normalized_key == "":
            return None
        found = self._collection().find_one({"storage.bucket": normalized_bucket, "storage.key": normalized_key})
        return self._normalize(found)

    def list_for_client(
        self,
        *,
        client_id: int,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted_by_default: bool = False,
    ) -> list[dict[str, Any]]:
        filters = self._filters_for_client(
            client_id=client_id,
            kind=kind,
            status=status,
            include_deleted_by_default=include_deleted_by_default,
        )
        cursor = (
            self._collection()
            .find(filters)
            .sort([("created_at", -1), ("media_id", -1)])
            .skip(max(0, int(offset)))
            .limit(max(0, int(limit)))
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def count_for_client(
        self,
        *,
        client_id: int,
        kind: str | None = None,
        status: str | None = None,
        include_deleted_by_default: bool = False,
    ) -> int:
        filters = self._filters_for_client(
            client_id=client_id,
            kind=kind,
            status=status,
            include_deleted_by_default=include_deleted_by_default,
        )
        return int(self._collection().count_documents(filters) or 0)

    def mark_ready(
        self,
        *,
        media_id: str,
        size_bytes: int | None = None,
        mime_type: str | None = None,
        checksum: str | None = None,
        etag: str | None = None,
        version_id: str | None = None,
        uploaded_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return None
        now = utcnow()
        set_payload: dict[str, Any] = {
            "status": MEDIA_FILE_STATUS_READY,
            "updated_at": now,
            "uploaded_at": uploaded_at or now,
        }
        if size_bytes is not None:
            set_payload["size_bytes"] = int(size_bytes)
        if mime_type is not None:
            set_payload["mime_type"] = str(mime_type or "").strip() or None
        if checksum is not None:
            set_payload["checksum"] = str(checksum or "").strip() or None
        if etag is not None:
            set_payload["storage.etag"] = str(etag or "").strip() or None
        if version_id is not None:
            set_payload["storage.version_id"] = str(version_id or "").strip() or None
        if metadata is not None:
            set_payload["metadata"] = dict(metadata)
        self._collection().update_one({"media_id": normalized_media_id}, {"$set": set_payload})
        return self.get_by_media_id(normalized_media_id)

    def soft_delete(self, *, media_id: str, deleted_at: datetime | None = None) -> dict[str, Any] | None:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return None
        now = utcnow()
        self._collection().update_one(
            {"media_id": normalized_media_id},
            {
                "$set": {
                    "status": MEDIA_FILE_STATUS_DELETE_REQUESTED,
                    "deleted_at": deleted_at or now,
                    "updated_at": now,
                }
            },
        )
        return self.get_by_media_id(normalized_media_id)

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        internal_id = normalized.pop("_id", None)
        if internal_id is not None:
            normalized["mongo_id"] = str(internal_id)
        storage = normalized.get("storage")
        normalized["storage"] = dict(storage) if isinstance(storage, dict) else {}
        normalized["metadata"] = dict(normalized.get("metadata") or {})
        return normalized


media_metadata_repository = MediaMetadataRepository()
