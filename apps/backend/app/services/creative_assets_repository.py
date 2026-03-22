from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.mongo_provider import get_mongo_collection

_COLLECTION_NAME = "creative_assets"
_SCHEMA_VERSION = 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CreativeAssetsRepository:
    def _collection(self):
        collection = get_mongo_collection(_COLLECTION_NAME)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for creative assets repository usage).")
        return collection

    def initialize_indexes(self) -> None:
        collection = self._collection()
        collection.create_index(
            [("creative_id", 1)],
            unique=True,
            name="ux_creative_assets_creative_id",
        )
        collection.create_index(
            [("client_id", 1), ("updated_at", -1)],
            name="ix_creative_assets_client_updated_at",
        )

    def upsert_asset(self, asset: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_asset_input(asset)
        creative_id = int(normalized["creative_id"])
        now = _utcnow()
        set_payload = dict(normalized)
        set_payload["updated_at"] = now

        collection = self._collection()
        collection.update_one(
            {"creative_id": creative_id},
            {
                "$set": set_payload,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        found = collection.find_one({"creative_id": creative_id})
        return self._normalize(found) or {}

    def get_by_creative_id(self, creative_id: int) -> dict[str, Any] | None:
        normalized_creative_id = int(creative_id)
        if normalized_creative_id <= 0:
            return None
        found = self._collection().find_one({"creative_id": normalized_creative_id})
        return self._normalize(found)

    def list_assets(self, *, limit: int = 50, client_id: int | None = None) -> list[dict[str, Any]]:
        filters: dict[str, Any] = {}
        if client_id is not None:
            filters["client_id"] = int(client_id)
        cursor = (
            self._collection()
            .find(filters)
            .sort([("updated_at", -1), ("creative_id", -1)])
            .limit(max(0, int(limit)))
        )
        return [self._normalize(item) for item in cursor if isinstance(item, dict)]

    def _normalize_asset_input(self, asset: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(asset, dict):
            raise ValueError("asset must be a dictionary")
        creative_id = int(asset.get("creative_id") or asset.get("asset_id") or asset.get("id") or 0)
        if creative_id <= 0:
            raise ValueError("creative_id is required")

        normalized: dict[str, Any] = {
            "creative_id": creative_id,
            "id": int(asset.get("id") or creative_id),
            "asset_id": int(asset.get("asset_id") or creative_id),
            "name": str(asset.get("name") or "").strip(),
            "metadata": dict(asset.get("metadata") or {}),
            "creative_variants": [dict(item) for item in list(asset.get("creative_variants") or []) if isinstance(item, dict)],
            "performance_scores": dict(asset.get("performance_scores") or {}),
            "campaign_links": [dict(item) for item in list(asset.get("campaign_links") or []) if isinstance(item, dict)],
            "schema_version": int(asset.get("schema_version") or _SCHEMA_VERSION),
        }
        if asset.get("client_id") is not None:
            normalized["client_id"] = int(asset.get("client_id"))
        return normalized

    def _normalize(self, payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        normalized = dict(payload)
        internal_id = normalized.pop("_id", None)
        if internal_id is not None:
            normalized["mongo_id"] = str(internal_id)
        normalized["metadata"] = dict(normalized.get("metadata") or {})
        normalized["creative_variants"] = [dict(item) for item in list(normalized.get("creative_variants") or []) if isinstance(item, dict)]
        normalized["performance_scores"] = dict(normalized.get("performance_scores") or {})
        normalized["campaign_links"] = [dict(item) for item in list(normalized.get("campaign_links") or []) if isinstance(item, dict)]
        return normalized


creative_assets_repository = CreativeAssetsRepository()
