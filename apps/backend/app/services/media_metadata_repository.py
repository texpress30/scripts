from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_DRAFT,
    MEDIA_FILE_STATUS_READY,
    MEDIA_FILE_STATUS_PURGED,
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


_FOLDER_FILTER_ROOT = object()  # sentinel for "root folder only (folder_id = null)"


class MediaMetadataRepository:
    FOLDER_ROOT: Any = _FOLDER_FILTER_ROOT

    def _filters_for_client(
        self,
        *,
        client_id: int,
        kind: str | None = None,
        status: str | None = None,
        include_deleted_by_default: bool = False,
        folder_id: Any = None,
        search: str | None = None,
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
        if folder_id is _FOLDER_FILTER_ROOT:
            filters["folder_id"] = None
        elif folder_id is not None:
            normalized_folder_id = str(folder_id or "").strip()
            if normalized_folder_id != "":
                filters["folder_id"] = normalized_folder_id
        normalized_search = str(search or "").strip()
        if normalized_search != "":
            import re

            safe_search = re.escape(normalized_search)
            filters["$or"] = [
                {"display_name": {"$regex": safe_search, "$options": "i"}},
                {"original_filename": {"$regex": safe_search, "$options": "i"}},
            ]
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
                "storage.bucket": {"$type": "string", "$gt": ""},
                "storage.key": {"$type": "string", "$gt": ""},
            },
        )
        collection.create_index(
            [("client_id", 1), ("status", 1), ("created_at", -1)],
            name="ix_media_files_client_status_created_at",
        )
        collection.create_index(
            [("client_id", 1), ("folder_id", 1), ("status", 1), ("created_at", -1)],
            name="ix_media_files_client_folder_status_created_at",
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
        folder_id: str | None = None,
        display_name: str | None = None,
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
        resolved_display_name = str(display_name or "").strip() or str(original_filename or "").strip()
        payload: dict[str, Any] = {
            "media_id": str(media_id or "").strip() or new_media_id(),
            "client_id": int(client_id),
            "kind": str(kind),
            "source": str(source),
            "status": MEDIA_FILE_STATUS_DRAFT,
            "original_filename": str(original_filename or "").strip(),
            "display_name": resolved_display_name,
            "folder_id": str(folder_id or "").strip() or None,
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

    def create_ready(
        self,
        *,
        client_id: int,
        kind: MediaFileKind,
        source: MediaFileSource,
        original_filename: str,
        mime_type: str,
        storage_bucket: str,
        storage_key: str,
        storage_region: str,
        size_bytes: int | None = None,
        etag: str | None = None,
        version_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        folder_id: str | None = None,
        display_name: str | None = None,
        media_id: str | None = None,
    ) -> dict[str, Any]:
        """Insert a media_files row that's already 'ready' (used by auto-ingest of assets
        already present in S3, e.g. enriched-catalog renders)."""
        now = utcnow()
        storage = MediaStorageDescriptor(
            provider="s3",
            bucket=str(storage_bucket or "").strip(),
            key=str(storage_key or "").strip(),
            region=str(storage_region or "").strip(),
            etag=etag,
            version_id=version_id,
        ).to_dict()
        resolved_display_name = str(display_name or "").strip() or str(original_filename or "").strip()
        payload: dict[str, Any] = {
            "media_id": str(media_id or "").strip() or new_media_id(),
            "client_id": int(client_id),
            "kind": str(kind),
            "source": str(source),
            "status": MEDIA_FILE_STATUS_READY,
            "original_filename": str(original_filename or "").strip(),
            "display_name": resolved_display_name,
            "folder_id": str(folder_id or "").strip() or None,
            "mime_type": str(mime_type or "").strip(),
            "size_bytes": int(size_bytes) if size_bytes is not None else None,
            "checksum": None,
            "metadata": dict(metadata or {}),
            "storage": storage,
            "created_at": now,
            "updated_at": now,
            "uploaded_at": now,
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

    _SORT_FIELDS: dict[str, tuple[str, int]] = {
        "newest": ("created_at", -1),
        "oldest": ("created_at", 1),
        "name_asc": ("display_name", 1),
        "name_desc": ("display_name", -1),
        "size_asc": ("size_bytes", 1),
        "size_desc": ("size_bytes", -1),
    }

    def list_for_client(
        self,
        *,
        client_id: int,
        kind: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted_by_default: bool = False,
        folder_id: Any = None,
        search: str | None = None,
        sort: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = self._filters_for_client(
            client_id=client_id,
            kind=kind,
            status=status,
            include_deleted_by_default=include_deleted_by_default,
            folder_id=folder_id,
            search=search,
        )
        sort_field, sort_direction = self._SORT_FIELDS.get(
            str(sort or "").strip().lower(),
            ("created_at", -1),
        )
        cursor = (
            self._collection()
            .find(filters)
            .sort([(sort_field, sort_direction), ("media_id", -1)])
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
        folder_id: Any = None,
        search: str | None = None,
    ) -> int:
        filters = self._filters_for_client(
            client_id=client_id,
            kind=kind,
            status=status,
            include_deleted_by_default=include_deleted_by_default,
            folder_id=folder_id,
            search=search,
        )
        return int(self._collection().count_documents(filters) or 0)

    def update_attributes(
        self,
        *,
        media_id: str,
        display_name: str | None = None,
        folder_id: Any = None,
        clear_folder: bool = False,
    ) -> dict[str, Any] | None:
        """Rename (`display_name`) and/or move (`folder_id`) an existing media record."""
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return None
        set_payload: dict[str, Any] = {"updated_at": utcnow()}
        if display_name is not None:
            normalized_display_name = str(display_name or "").strip()
            if normalized_display_name != "":
                set_payload["display_name"] = normalized_display_name
        if clear_folder:
            set_payload["folder_id"] = None
        elif folder_id is not None:
            normalized_folder_id = str(folder_id or "").strip() or None
            set_payload["folder_id"] = normalized_folder_id
        if len(set_payload) == 1:  # only updated_at — nothing meaningful to change
            return self.get_by_media_id(normalized_media_id)
        self._collection().update_one({"media_id": normalized_media_id}, {"$set": set_payload})
        return self.get_by_media_id(normalized_media_id)

    def find_media_ids_referencing_folder(self, *, client_id: int, folder_id: str) -> int:
        normalized_folder_id = str(folder_id or "").strip()
        if normalized_folder_id == "":
            return 0
        return int(
            self._collection().count_documents(
                {
                    "client_id": int(client_id),
                    "folder_id": normalized_folder_id,
                    "status": {"$nin": ["purged", "delete_requested"]},
                }
            )
            or 0
        )

    def summarize_for_client(self, *, client_id: int) -> dict[str, int]:
        """Return {"total_files": N, "total_bytes": N} for a sub-account's
        active (non-deleted, non-draft) media. Used by the UI to show a
        "Stocare X MB utilizați" widget."""
        pipeline = [
            {
                "$match": {
                    "client_id": int(client_id),
                    "status": {"$nin": ["purged", "delete_requested", "draft"]},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_files": {"$sum": 1},
                    "total_bytes": {"$sum": {"$ifNull": ["$size_bytes", 0]}},
                }
            },
        ]
        try:
            results = list(self._collection().aggregate(pipeline))
        except Exception:  # noqa: BLE001
            return {"total_files": 0, "total_bytes": 0}
        if not results:
            return {"total_files": 0, "total_bytes": 0}
        record = results[0] or {}
        return {
            "total_files": int(record.get("total_files") or 0),
            "total_bytes": int(record.get("total_bytes") or 0),
        }

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


    def list_cleanup_candidates(self, *, limit: int = 100) -> list[dict[str, Any]]:
        resolved_limit = max(0, int(limit))
        cursor = (
            self._collection()
            .find({"status": MEDIA_FILE_STATUS_DELETE_REQUESTED})
            .sort([("deleted_at", 1), ("created_at", 1), ("media_id", 1)])
            .limit(resolved_limit)
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def mark_purged(self, *, media_id: str, purged_at: datetime | None = None) -> dict[str, Any] | None:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            return None
        now = utcnow()
        self._collection().update_one(
            {"media_id": normalized_media_id},
            {
                "$set": {
                    "status": MEDIA_FILE_STATUS_PURGED,
                    "purged_at": purged_at or now,
                    "updated_at": now,
                }
            },
        )
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
        # Back-fill fields added after the collection was first created so callers can
        # rely on their presence without worrying about legacy records.
        if "folder_id" not in normalized:
            normalized["folder_id"] = None
        else:
            normalized["folder_id"] = str(normalized.get("folder_id") or "").strip() or None
        if "display_name" not in normalized or not normalized.get("display_name"):
            normalized["display_name"] = str(normalized.get("original_filename") or "")
        return normalized


media_metadata_repository = MediaMetadataRepository()
