from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.mongo_provider import get_mongo_collection

_COLLECTION_NAME = "creative_counters"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _return_document_after() -> Any:
    from pymongo import ReturnDocument

    return ReturnDocument.AFTER


class CreativeCountersRepository:
    def _collection(self):
        collection = get_mongo_collection(_COLLECTION_NAME)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for creative counters repository usage).")
        return collection

    def initialize_indexes(self) -> None:
        self._collection().create_index(
            [("counter_name", 1)],
            unique=True,
            name="ux_creative_counters_counter_name",
        )

    def next_id(self, counter_name: str) -> int:
        normalized_counter_name = str(counter_name or "").strip().lower()
        if normalized_counter_name == "":
            raise ValueError("counter_name is required")
        now = _utcnow()
        document = self._collection().find_one_and_update(
            {"counter_name": normalized_counter_name},
            {
                "$inc": {"value": 1},
                "$set": {"updated_at": now},
                "$setOnInsert": {
                    "counter_name": normalized_counter_name,
                    "created_at": now,
                },
            },
            upsert=True,
            return_document=_return_document_after(),
        )
        if not isinstance(document, dict):
            raise RuntimeError(f"Failed to allocate next id for counter '{normalized_counter_name}'")
        return int(document.get("value") or 0)

    def next_asset_id(self) -> int:
        return self.next_id("asset")

    def next_variant_id(self) -> int:
        return self.next_id("variant")

    def next_link_id(self) -> int:
        return self.next_id("link")

    def next_publish_id(self) -> int:
        return self.next_id("publish")


creative_counters_repository = CreativeCountersRepository()
