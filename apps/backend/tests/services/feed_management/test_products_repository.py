from __future__ import annotations

import re
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

from app.services.feed_management.connectors.base import ProductData
from app.services.feed_management import products_repository as repo_module
from app.services.feed_management.products_repository import FeedProductsRepository

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)


class _FakeBulkWriteResult:
    def __init__(self, upserted: int, modified: int) -> None:
        self.upserted_count = upserted
        self.modified_count = modified


class _FakeDeleteResult:
    def __init__(self, deleted: int) -> None:
        self.deleted_count = deleted


class _FakeCursor:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = list(items)

    def sort(self, keys):
        for key, direction in reversed(keys):
            reverse = int(direction) < 0
            self._items.sort(key=lambda item: item.get(key, ""), reverse=reverse)
        return self

    def skip(self, n: int):
        self._items = self._items[n:]
        return self

    def limit(self, n: int):
        self._items = self._items[:n]
        return self

    def __iter__(self):
        return iter(self._items)


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []
        self.indexes: list[dict[str, Any]] = []

    def create_index(self, keys, **kwargs):
        self.indexes.append({"keys": list(keys), **kwargs})

    def insert_one(self, doc: dict[str, Any]):
        stored = dict(doc)
        stored["_id"] = f"oid-{len(self.docs) + 1}"
        self.docs.append(stored)

    def update_one(self, query: dict, update: dict, upsert: bool = False):
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return
        if upsert and "$set" in update:
            new_doc = dict(update.get("$setOnInsert", {}))
            new_doc.update(update["$set"])
            new_doc["_id"] = f"oid-{len(self.docs) + 1}"
            self.docs.append(new_doc)

    def bulk_write(self, operations, ordered: bool = True):
        upserted = 0
        modified = 0
        for op in operations:
            query = op._filter
            update = op._doc
            found = False
            for doc in self.docs:
                if self._matches(doc, query):
                    if "$set" in update:
                        doc.update(update["$set"])
                    modified += 1
                    found = True
                    break
            if not found:
                new_doc = dict(update.get("$setOnInsert", {}))
                if "$set" in update:
                    new_doc.update(update["$set"])
                new_doc["_id"] = f"oid-{len(self.docs) + 1}"
                self.docs.append(new_doc)
                upserted += 1
        return _FakeBulkWriteResult(upserted, modified)

    def find_one(self, query: dict[str, Any]):
        for doc in self.docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query: dict[str, Any]):
        matched = [dict(doc) for doc in self.docs if self._matches(doc, query)]
        return _FakeCursor(matched)

    def count_documents(self, query: dict[str, Any]) -> int:
        return sum(1 for doc in self.docs if self._matches(doc, query))

    def delete_many(self, query: dict[str, Any]):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]
        return _FakeDeleteResult(before - len(self.docs))

    def distinct(self, field: str, query: dict[str, Any]):
        values = set()
        for doc in self.docs:
            if self._matches(doc, query):
                val = self._get_nested(doc, field)
                if val:
                    values.add(val)
        return list(values)

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(doc, clause) for clause in value):
                    return False
                continue
            doc_val = self._get_nested(doc, key)
            if isinstance(value, dict):
                if "$regex" in value:
                    pattern = value["$regex"]
                    flags = re.IGNORECASE if "i" in value.get("$options", "") else 0
                    if not re.search(pattern, str(doc_val or ""), flags):
                        return False
                continue
            if doc_val != value:
                return False
        return True

    def _get_nested(self, doc: dict, key: str) -> Any:
        parts = key.split(".")
        current: Any = doc
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


def _make_product(product_id: str = "prod-1", title: str = "Test Product", category: str = "Shoes") -> ProductData:
    return ProductData(
        id=product_id,
        title=title,
        description=f"Description for {title}",
        price=29.99,
        currency="USD",
        category=category,
        sku=f"SKU-{product_id}",
    )


class TestFeedProductsRepository(unittest.TestCase):
    def setUp(self):
        self.fake = FakeCollection()
        self.repo = FeedProductsRepository()
        self.patcher_collection = patch.object(
            self.repo, "_collection", return_value=self.fake,
        )
        self.patcher_utcnow = patch.object(
            repo_module, "_utcnow", return_value=_NOW,
        )
        self.patcher_collection.start()
        self.patcher_utcnow.start()

    def tearDown(self):
        self.patcher_collection.stop()
        self.patcher_utcnow.stop()

    def test_upsert_single_product(self):
        product = _make_product()
        result = self.repo.upsert_product("src-1", product)
        self.assertEqual(result, "prod-1")
        self.assertEqual(len(self.fake.docs), 1)
        doc = self.fake.docs[0]
        self.assertEqual(doc["feed_source_id"], "src-1")
        self.assertEqual(doc["product_id"], "prod-1")
        self.assertEqual(doc["data"]["title"], "Test Product")

    def test_upsert_updates_existing(self):
        product = _make_product()
        self.repo.upsert_product("src-1", product)
        updated = _make_product(title="Updated Product")
        self.repo.upsert_product("src-1", updated)
        self.assertEqual(len(self.fake.docs), 1)
        self.assertEqual(self.fake.docs[0]["data"]["title"], "Updated Product")

    def test_upsert_batch(self):
        products = [_make_product(f"p-{i}", f"Product {i}") for i in range(5)]
        count = self.repo.upsert_products_batch("src-1", products)
        self.assertEqual(count, 5)
        self.assertEqual(len(self.fake.docs), 5)

    def test_upsert_batch_empty(self):
        count = self.repo.upsert_products_batch("src-1", [])
        self.assertEqual(count, 0)

    def test_get_product(self):
        self.repo.upsert_product("src-1", _make_product())
        result = self.repo.get_product("src-1", "prod-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["product_id"], "prod-1")
        self.assertNotIn("_id", result)

    def test_get_product_not_found(self):
        result = self.repo.get_product("src-1", "nonexistent")
        self.assertIsNone(result)

    def test_list_products_with_pagination(self):
        for i in range(10):
            self.repo.upsert_product("src-1", _make_product(f"p-{i}", f"Product {i}"))
        results = self.repo.list_products("src-1", skip=2, limit=3)
        self.assertEqual(len(results), 3)

    def test_list_products_respects_source(self):
        self.repo.upsert_product("src-1", _make_product("p-1"))
        self.repo.upsert_product("src-2", _make_product("p-2"))
        results = self.repo.list_products("src-1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["product_id"], "p-1")

    def test_search_by_title(self):
        self.repo.upsert_product("src-1", _make_product("p-1", "Red Sneakers"))
        self.repo.upsert_product("src-1", _make_product("p-2", "Blue Boots"))
        self.repo.upsert_product("src-1", _make_product("p-3", "Red Hat"))
        results = self.repo.list_products("src-1", search="red")
        self.assertEqual(len(results), 2)

    def test_filter_by_category(self):
        self.repo.upsert_product("src-1", _make_product("p-1", category="Shoes"))
        self.repo.upsert_product("src-1", _make_product("p-2", category="Hats"))
        self.repo.upsert_product("src-1", _make_product("p-3", category="Shoes"))
        results = self.repo.list_products("src-1", category="Shoes")
        self.assertEqual(len(results), 2)

    def test_count_products(self):
        for i in range(5):
            self.repo.upsert_product("src-1", _make_product(f"p-{i}"))
        self.assertEqual(self.repo.count_products("src-1"), 5)

    def test_count_with_search(self):
        self.repo.upsert_product("src-1", _make_product("p-1", "Alpha"))
        self.repo.upsert_product("src-1", _make_product("p-2", "Beta"))
        count = self.repo.count_products("src-1", search="alpha")
        self.assertEqual(count, 1)

    def test_delete_by_source(self):
        for i in range(3):
            self.repo.upsert_product("src-1", _make_product(f"p-{i}"))
        self.repo.upsert_product("src-2", _make_product("other"))
        deleted = self.repo.delete_products_by_source("src-1")
        self.assertEqual(deleted, 3)
        self.assertEqual(len(self.fake.docs), 1)
        self.assertEqual(self.fake.docs[0]["feed_source_id"], "src-2")

    def test_get_distinct_categories(self):
        self.repo.upsert_product("src-1", _make_product("p-1", category="Shoes"))
        self.repo.upsert_product("src-1", _make_product("p-2", category="Hats"))
        self.repo.upsert_product("src-1", _make_product("p-3", category="Shoes"))
        cats = self.repo.get_distinct_categories("src-1")
        self.assertEqual(sorted(cats), ["Hats", "Shoes"])


if __name__ == "__main__":
    unittest.main()
