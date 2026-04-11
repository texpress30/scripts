from __future__ import annotations

from datetime import datetime
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.services.media_metadata_models import utcnow
from app.services.mongo_provider import get_mongo_collection

_COLLECTION_NAME = "media_folders"

FOLDER_STATUS_ACTIVE = "active"
FOLDER_STATUS_DELETED = "deleted"


def _coerce_object_id(value: str | None) -> ObjectId | None:
    """Convert a hex string to ObjectId, returning None on empty/invalid input."""
    candidate = str(value or "").strip()
    if candidate == "":
        return None
    try:
        return ObjectId(candidate)
    except (InvalidId, TypeError, ValueError):
        return None


class MediaFolderRepository:
    def _collection(self):
        collection = get_mongo_collection(_COLLECTION_NAME)
        if collection is None:
            raise RuntimeError(
                "Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for media folder repository usage)."
            )
        return collection

    def initialize_indexes(self) -> None:
        collection = self._collection()
        collection.create_index(
            [("client_id", 1), ("parent_folder_id", 1), ("name", 1)],
            name="ux_media_folders_client_parent_name_active",
            unique=True,
            partialFilterExpression={"status": FOLDER_STATUS_ACTIVE},
        )
        collection.create_index(
            [("client_id", 1), ("parent_folder_id", 1), ("name", 1)],
            name="ix_media_folders_client_parent_name",
        )
        collection.create_index(
            [("client_id", 1), ("status", 1)],
            name="ix_media_folders_client_status",
        )

    def create(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
        name: str,
        system: bool = False,
    ) -> dict[str, Any]:
        now = utcnow()
        payload: dict[str, Any] = {
            "client_id": int(client_id),
            "parent_folder_id": str(parent_folder_id).strip() if parent_folder_id else None,
            "name": str(name or "").strip(),
            "system": bool(system),
            "status": FOLDER_STATUS_ACTIVE,
            "created_at": now,
            "updated_at": now,
        }
        result = self._collection().insert_one(payload)
        payload["_id"] = result.inserted_id
        return self._normalize(payload)

    def get_by_id(self, *, client_id: int, folder_id: str) -> dict[str, Any] | None:
        oid = _coerce_object_id(folder_id)
        if oid is None:
            return None
        found = self._collection().find_one({"_id": oid, "client_id": int(client_id)})
        return self._normalize(found)

    def find_active_by_name(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
        name: str,
    ) -> dict[str, Any] | None:
        normalized_name = str(name or "").strip()
        if normalized_name == "":
            return None
        filters: dict[str, Any] = {
            "client_id": int(client_id),
            "parent_folder_id": str(parent_folder_id).strip() if parent_folder_id else None,
            "name": normalized_name,
            "status": FOLDER_STATUS_ACTIVE,
        }
        return self._normalize(self._collection().find_one(filters))

    def list_children(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
    ) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {
            "client_id": int(client_id),
            "parent_folder_id": str(parent_folder_id).strip() if parent_folder_id else None,
            "status": FOLDER_STATUS_ACTIVE,
        }
        cursor = self._collection().find(filters).sort([("name", 1)])
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def update(
        self,
        *,
        client_id: int,
        folder_id: str,
        name: str | None = None,
        parent_folder_id: str | None = None,
        clear_parent: bool = False,
    ) -> dict[str, Any] | None:
        oid = _coerce_object_id(folder_id)
        if oid is None:
            return None
        set_payload: dict[str, Any] = {"updated_at": utcnow()}
        if name is not None:
            set_payload["name"] = str(name or "").strip()
        if clear_parent:
            set_payload["parent_folder_id"] = None
        elif parent_folder_id is not None:
            set_payload["parent_folder_id"] = str(parent_folder_id).strip() or None
        self._collection().update_one(
            {"_id": oid, "client_id": int(client_id)},
            {"$set": set_payload},
        )
        return self.get_by_id(client_id=client_id, folder_id=folder_id)

    def soft_delete(self, *, client_id: int, folder_id: str) -> dict[str, Any] | None:
        oid = _coerce_object_id(folder_id)
        if oid is None:
            return None
        now = utcnow()
        self._collection().update_one(
            {"_id": oid, "client_id": int(client_id)},
            {
                "$set": {
                    "status": FOLDER_STATUS_DELETED,
                    "deleted_at": now,
                    "updated_at": now,
                }
            },
        )
        return self.get_by_id(client_id=client_id, folder_id=folder_id)

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized: dict[str, Any] = {
            "folder_id": str(payload.get("_id")) if payload.get("_id") is not None else "",
            "client_id": int(payload.get("client_id") or 0),
            "parent_folder_id": str(payload.get("parent_folder_id") or "").strip() or None,
            "name": str(payload.get("name") or "").strip(),
            "system": bool(payload.get("system") or False),
            "status": str(payload.get("status") or "").strip() or FOLDER_STATUS_ACTIVE,
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "deleted_at": payload.get("deleted_at"),
        }
        return normalized


media_folder_repository = MediaFolderRepository()
