from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.services.feed_management.connectors.base import ProductData
from app.services.mongo_provider import get_mongo_collection

_COLLECTION = "feed_products"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedProductsRepository:
    def _collection(self):
        collection = get_mongo_collection(_COLLECTION)
        if collection is None:
            raise RuntimeError("Mongo is not configured (MONGO_URI/MONGO_DATABASE are required for feed products)")
        return collection

    def initialize_indexes(self) -> None:
        self._collection().create_index(
            [("feed_source_id", 1), ("product_id", 1)],
            unique=True,
            name="ux_feed_products_source_product",
        )
        self._collection().create_index(
            [("feed_source_id", 1), ("updated_at", -1)],
            name="ix_feed_products_source_updated",
        )
        self._collection().create_index(
            [("data.title", "text"), ("data.description", "text")],
            name="ix_feed_products_text_search",
        )

    def upsert_product(self, feed_source_id: str, product: ProductData) -> str:
        now = _utcnow()
        doc = {
            "feed_source_id": str(feed_source_id),
            "product_id": str(product.id),
            "data": product.model_dump(),
            "updated_at": now.isoformat(),
        }
        self._collection().update_one(
            {"feed_source_id": str(feed_source_id), "product_id": str(product.id)},
            {
                "$set": doc,
                "$setOnInsert": {"synced_at": now.isoformat()},
            },
            upsert=True,
        )
        return str(product.id)

    def upsert_products_batch(self, feed_source_id: str, products: list[ProductData]) -> int:
        if not products:
            return 0
        from pymongo import UpdateOne
        now = _utcnow()
        ops = []
        for product in products:
            doc = {
                "feed_source_id": str(feed_source_id),
                "product_id": str(product.id),
                "data": product.model_dump(),
                "updated_at": now.isoformat(),
            }
            ops.append(UpdateOne(
                {"feed_source_id": str(feed_source_id), "product_id": str(product.id)},
                {"$set": doc, "$setOnInsert": {"synced_at": now.isoformat()}},
                upsert=True,
            ))
        result = self._collection().bulk_write(ops, ordered=False)
        return result.upserted_count + result.modified_count

    def get_product(self, feed_source_id: str, product_id: str) -> dict[str, Any] | None:
        doc = self._collection().find_one(
            {"feed_source_id": str(feed_source_id), "product_id": str(product_id)}
        )
        return self._normalize(doc)

    def list_products(
        self,
        feed_source_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        query = self._build_query(feed_source_id, search=search, category=category)
        cursor = (
            self._collection()
            .find(query)
            .sort([("updated_at", -1)])
            .skip(max(0, skip))
            .limit(min(max(1, limit), 200))
        )
        return [self._normalize(doc) for doc in cursor if doc]

    def count_products(
        self,
        feed_source_id: str,
        *,
        search: str | None = None,
        category: str | None = None,
    ) -> int:
        query = self._build_query(feed_source_id, search=search, category=category)
        return self._collection().count_documents(query)

    def delete_products_by_source(self, feed_source_id: str) -> int:
        result = self._collection().delete_many({"feed_source_id": str(feed_source_id)})
        return result.deleted_count

    def get_distinct_categories(self, feed_source_id: str) -> list[str]:
        values = self._collection().distinct("data.category", {"feed_source_id": str(feed_source_id)})
        return sorted([str(v) for v in values if v])

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_query(
        self,
        feed_source_id: str,
        *,
        search: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"feed_source_id": str(feed_source_id)}
        if search:
            escaped = re.escape(str(search).strip())
            query["$or"] = [
                {"data.title": {"$regex": escaped, "$options": "i"}},
                {"data.description": {"$regex": escaped, "$options": "i"}},
            ]
        if category:
            query["data.category"] = str(category)
        return query

    def _normalize(self, doc: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(doc, dict):
            return None
        result = dict(doc)
        result.pop("_id", None)
        return result


feed_products_repository = FeedProductsRepository()
