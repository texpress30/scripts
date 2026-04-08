"""Tests for :class:`app.integrations.bigcommerce.connector.BigCommerceConnector`.

Strategy: pass a fake ``BigCommerceClient`` via the constructor's ``client``
kwarg and stub its async methods (``.get()``, ``.get_all_pages()``) with
``AsyncMock`` instances that return canned BC payloads. No HTTP, no DB —
just the connector's bootstrap / paging / normalization wiring under test.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from app.integrations.bigcommerce.connector import BigCommerceConnector
from app.services.feed_management.connectors.base import ProductData
from app.services.feed_management.models import FeedSourceType


_STORE_HASH = "abc123"


def _store_payload() -> dict[str, Any]:
    return {
        "name": "Test BC Store",
        "domain": "store.example.com",
        "secure_url": "https://store.example.com",
        "currency": "USD",
    }


def _category_row(cid: int, name: str) -> dict[str, Any]:
    return {"id": cid, "name": name, "is_visible": True}


def _brand_row(bid: int, name: str) -> dict[str, Any]:
    return {"id": bid, "name": name}


def _product(pid: int, *, sale: float | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": pid,
        "name": f"Product {pid}",
        "sku": f"SKU-{pid}",
        "description": f"<p>Description {pid}</p>",
        "price": 100.0 + pid,
        "sale_price": sale if sale is not None else 0,
        "categories": [10],
        "brand_id": 5,
        "inventory_level": 50 + pid,
        "is_visible": True,
        "availability": "available",
        "custom_url": {"url": f"/product-{pid}/"},
        "images": [
            {
                "id": pid * 10,
                "url_standard": f"https://cdn.bc.com/{pid}.jpg",
                "is_thumbnail": True,
                "sort_order": 0,
            }
        ],
        "variants": [],
        "custom_fields": [],
        "search_keywords": "",
    }
    return body


def _products_page(items: list[dict[str, Any]], current: int, total: int) -> dict[str, Any]:
    return {
        "data": items,
        "meta": {
            "pagination": {
                "current_page": current,
                "total_pages": total,
                "total": len(items) * total,
                "per_page": len(items) or 250,
            }
        },
    }


def _make_fake_client(
    *,
    store_payload: dict[str, Any] | None = None,
    category_pages: list[dict[str, Any]] | None = None,
    brand_pages: list[dict[str, Any]] | None = None,
    product_pages: list[dict[str, Any]] | None = None,
) -> AsyncMock:
    """Build an AsyncMock BigCommerceClient.

    The mock dispatches on (endpoint, api_version) so the connector code
    can call ``.get("store", api_version="v2")`` for the store info,
    ``.get("catalog/products", ...)`` for paginated product fetches and
    ``.get_all_pages("catalog/categories", ...)`` for categories/brands.
    """
    client = AsyncMock()
    client.store_hash = _STORE_HASH

    products_iter = iter(product_pages or [])

    async def _get(endpoint, *, params=None, api_version=None):
        if endpoint == "store" and api_version == "v2":
            return store_payload
        if endpoint == "catalog/products":
            return next(products_iter)
        return None

    async def _get_all_pages(endpoint, *, params=None, page_size=None, api_version=None):
        if endpoint == "catalog/categories":
            return category_pages or []
        if endpoint == "catalog/brands":
            return brand_pages or []
        return []

    client.get = AsyncMock(side_effect=_get)
    client.get_all_pages = AsyncMock(side_effect=_get_all_pages)
    return client


def _make_connector(
    *,
    fake_client: AsyncMock | None = None,
    config: dict[str, Any] | None = None,
    credentials: dict[str, str] | None = None,
    page_size: int = 250,
) -> BigCommerceConnector:
    cfg = config if config is not None else {"bigcommerce_store_hash": _STORE_HASH}
    creds = credentials if credentials is not None else {"access_token": "bc_TOKEN"}
    return BigCommerceConnector(
        config=cfg,
        credentials=creds,
        client=fake_client,
        page_size=page_size,
    )


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _collect(connector: BigCommerceConnector) -> list[ProductData]:
    out: list[ProductData] = []
    async for product in connector.fetch_products():
        out.append(product)
    return out


class ValidateConfigTests(unittest.TestCase):
    def test_valid_config(self) -> None:
        connector = _make_connector()
        result = _run(connector.validate_config())
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_missing_store_hash(self) -> None:
        connector = BigCommerceConnector(
            config={}, credentials={"access_token": "bc_TOKEN"}
        )
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)
        self.assertTrue(any("store_hash" in e for e in result.errors))

    def test_missing_access_token(self) -> None:
        connector = _make_connector(credentials={})
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)
        self.assertTrue(any("access_token" in e for e in result.errors))

    def test_invalid_store_hash(self) -> None:
        connector = BigCommerceConnector(
            config={"bigcommerce_store_hash": "abc/123"},
            credentials={"access_token": "bc_TOKEN"},
        )
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)

    def test_extracts_hash_from_store_url(self) -> None:
        connector = BigCommerceConnector(
            config={"store_url": "stores/abc123"},
            credentials={"access_token": "bc_TOKEN"},
        )
        result = _run(connector.validate_config())
        self.assertTrue(result.valid)


class TestConnectionTests(unittest.TestCase):
    def test_test_connection_success_caches_currency_and_domain(self) -> None:
        client = _make_fake_client(store_payload=_store_payload())
        connector = _make_connector(fake_client=client)

        result = _run(connector.test_connection())
        self.assertTrue(result.success)
        self.assertEqual(result.details["store_name"], "Test BC Store")
        self.assertEqual(result.details["currency"], "USD")
        # Cached for the subsequent fetch_products bootstrap.
        self.assertEqual(connector._currency, "USD")
        self.assertEqual(connector._store_domain, "store.example.com")

    def test_test_connection_invalid_config(self) -> None:
        connector = BigCommerceConnector(
            config={}, credentials={"access_token": "bc_TOKEN"}
        )
        result = _run(connector.test_connection())
        self.assertFalse(result.success)
        self.assertIn("Invalid", result.message)


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_fetches_store_categories_and_brands(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[
                _category_row(10, "Outerwear"),
                _category_row(20, "Jackets"),
            ],
            brand_pages=[_brand_row(5, "Acme")],
            product_pages=[_products_page([_product(1)], current=1, total=1)],
        )
        connector = _make_connector(fake_client=client)

        result = _run(_collect(connector))
        self.assertEqual(len(result), 1)

        # store info fetched once
        store_calls = [
            call
            for call in client.get.call_args_list
            if call.args[0] == "store"
        ]
        self.assertEqual(len(store_calls), 1)
        self.assertEqual(store_calls[0].kwargs.get("api_version"), "v2")

        # categories + brands fetched once via get_all_pages
        cat_calls = [
            call
            for call in client.get_all_pages.call_args_list
            if call.args[0] == "catalog/categories"
        ]
        brand_calls = [
            call
            for call in client.get_all_pages.call_args_list
            if call.args[0] == "catalog/brands"
        ]
        self.assertEqual(len(cat_calls), 1)
        self.assertEqual(len(brand_calls), 1)

        # category + brand caches populated
        self.assertEqual(connector._categories_cache, {10: "Outerwear", 20: "Jackets"})
        self.assertEqual(connector._brands_cache, {5: "Acme"})

    def test_bootstrap_skips_store_when_already_cached(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[],
            brand_pages=[],
            product_pages=[_products_page([_product(1)], current=1, total=1)],
        )
        connector = _make_connector(
            fake_client=client,
            config={
                "bigcommerce_store_hash": _STORE_HASH,
                "currency": "EUR",
                "store_domain": "preset.example.com",
            },
        )

        _run(_collect(connector))

        store_calls = [
            call
            for call in client.get.call_args_list
            if call.args[0] == "store"
        ]
        # No /v2/store fetch — currency + domain came in via the config.
        self.assertEqual(len(store_calls), 0)
        self.assertEqual(connector._currency, "EUR")

    def test_categories_fetched_once_across_two_pages(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[_category_row(10, "Outerwear")],
            brand_pages=[],
            product_pages=[
                _products_page([_product(1), _product(2)], current=1, total=2),
                _products_page([_product(3), _product(4)], current=2, total=2),
            ],
        )
        connector = _make_connector(fake_client=client)

        _run(_collect(connector))

        cat_calls = [
            call
            for call in client.get_all_pages.call_args_list
            if call.args[0] == "catalog/categories"
        ]
        self.assertEqual(len(cat_calls), 1)


class PaginationTests(unittest.TestCase):
    def test_single_page(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[_category_row(10, "Outerwear")],
            brand_pages=[_brand_row(5, "Acme")],
            product_pages=[
                _products_page(
                    [_product(1), _product(2), _product(3)], current=1, total=1
                )
            ],
        )
        connector = _make_connector(fake_client=client)

        result = _run(_collect(connector))
        self.assertEqual([p.id for p in result], ["1", "2", "3"])

        product_calls = [
            call
            for call in client.get.call_args_list
            if call.args[0] == "catalog/products"
        ]
        self.assertEqual(len(product_calls), 1)

    def test_multiple_pages(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[],
            brand_pages=[],
            product_pages=[
                _products_page([_product(1), _product(2)], current=1, total=3),
                _products_page([_product(3), _product(4)], current=2, total=3),
                _products_page([_product(5)], current=3, total=3),
            ],
        )
        connector = _make_connector(fake_client=client)

        result = _run(_collect(connector))
        self.assertEqual([p.id for p in result], ["1", "2", "3", "4", "5"])

        product_calls = [
            call
            for call in client.get.call_args_list
            if call.args[0] == "catalog/products"
        ]
        self.assertEqual(len(product_calls), 3)

    def test_filters_invisible_products_via_query_param(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[],
            brand_pages=[],
            product_pages=[_products_page([_product(1)], current=1, total=1)],
        )
        connector = _make_connector(fake_client=client)
        _run(_collect(connector))

        product_call = next(
            call
            for call in client.get.call_args_list
            if call.args[0] == "catalog/products"
        )
        params = product_call.kwargs.get("params") or {}
        self.assertEqual(params.get("is_visible"), "true")
        self.assertEqual(params.get("availability"), "available")
        self.assertEqual(
            params.get("include"), "variants,images,custom_fields"
        )
        self.assertEqual(params.get("limit"), 250)
        self.assertEqual(params.get("page"), 1)

    def test_since_filter_added_when_provided(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[],
            brand_pages=[],
            product_pages=[_products_page([], current=1, total=1)],
        )
        connector = _make_connector(fake_client=client)

        async def _drive():
            async for _ in connector.fetch_products(
                since=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
            ):
                pass

        _run(_drive())
        product_call = next(
            call
            for call in client.get.call_args_list
            if call.args[0] == "catalog/products"
        )
        params = product_call.kwargs.get("params") or {}
        self.assertIn("date_modified:min", params)


class NormalizationWiringTests(unittest.TestCase):
    def test_yielded_products_are_fully_normalized(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[_category_row(10, "Outerwear")],
            brand_pages=[_brand_row(5, "Acme")],
            product_pages=[
                _products_page([_product(1, sale=49.99)], current=1, total=1)
            ],
        )
        connector = _make_connector(fake_client=client)

        result = _run(_collect(connector))
        self.assertEqual(len(result), 1)
        product = result[0]
        self.assertEqual(product.id, "1")
        self.assertEqual(product.title, "Product 1")
        self.assertEqual(product.currency, "USD")
        self.assertEqual(product.category, "Outerwear")
        self.assertIn("Acme", product.tags)
        # Sale flip: BC sale_price=49.99 < price=101.0
        self.assertEqual(product.price, 49.99)
        self.assertEqual(product.compare_at_price, 101.0)
        self.assertEqual(
            product.url, "https://store.example.com/product-1/"
        )

    def test_normalize_failure_yields_nothing_for_that_product(self) -> None:
        client = _make_fake_client(
            store_payload=_store_payload(),
            category_pages=[],
            brand_pages=[],
            product_pages=[
                _products_page([_product(1), _product(2)], current=1, total=1)
            ],
        )
        connector = _make_connector(fake_client=client)

        with patch(
            "app.integrations.bigcommerce.connector.normalize_bigcommerce_product",
            side_effect=[RuntimeError("boom"), _run_normalize_real(_product(2))],
        ):
            result = _run(_collect(connector))
        # First product errored → skipped, second yielded
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "2")


def _run_normalize_real(raw):
    from app.integrations.bigcommerce.normalizer import (
        normalize_bigcommerce_product,
    )

    return normalize_bigcommerce_product(
        raw,
        store_domain="store.example.com",
        currency="USD",
        categories_map={},
        brands_map={},
    )


class GetProductCountTests(unittest.TestCase):
    def test_reads_total_from_meta_pagination(self) -> None:
        client = AsyncMock()

        async def _get(endpoint, *, params=None, api_version=None):
            return {
                "data": [],
                "meta": {"pagination": {"total": 1234}},
            }

        client.get = AsyncMock(side_effect=_get)
        connector = _make_connector(fake_client=client)

        count = _run(connector.get_product_count())
        self.assertEqual(count, 1234)

    def test_returns_zero_on_unexpected_payload(self) -> None:
        client = AsyncMock()
        client.get = AsyncMock(return_value="not a dict")
        connector = _make_connector(fake_client=client)
        self.assertEqual(_run(connector.get_product_count()), 0)


class SyncServiceWiringTests(unittest.TestCase):
    def test_get_connector_returns_bigcommerce_for_bigcommerce_source(self) -> None:
        from datetime import datetime, timezone
        from unittest.mock import patch

        from app.services.feed_management.models import FeedSourceResponse
        from app.services.feed_management.sync_service import _get_connector

        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        source = FeedSourceResponse(
            id="src-1",
            subaccount_id=42,
            source_type=FeedSourceType.bigcommerce,
            name="My BC Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            bigcommerce_store_hash=_STORE_HASH,
            connection_status="connected",
            has_token=True,
            created_at=now,
            updated_at=now,
        )
        with patch(
            "app.integrations.bigcommerce.service.get_bigcommerce_credentials",
            return_value={"access_token": "bc_TOKEN", "scope": "x"},
        ):
            connector = _get_connector(source)

        self.assertIsInstance(connector, BigCommerceConnector)
        self.assertEqual(connector._store_hash, _STORE_HASH)
        self.assertEqual(
            connector.credentials.get("access_token"), "bc_TOKEN"
        )

    def test_get_connector_warns_when_no_credentials(self) -> None:
        from datetime import datetime, timezone
        from unittest.mock import patch

        from app.services.feed_management.models import FeedSourceResponse
        from app.services.feed_management.sync_service import _get_connector

        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        source = FeedSourceResponse(
            id="src-2",
            subaccount_id=42,
            source_type=FeedSourceType.bigcommerce,
            name="No Token Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            bigcommerce_store_hash=_STORE_HASH,
            connection_status="pending",
            has_token=False,
            created_at=now,
            updated_at=now,
        )
        with patch(
            "app.integrations.bigcommerce.service.get_bigcommerce_credentials",
            return_value=None,
        ):
            connector = _get_connector(source)
        # Connector still constructed (validation happens at runtime).
        self.assertIsInstance(connector, BigCommerceConnector)
        self.assertEqual(connector.credentials, {})


if __name__ == "__main__":
    unittest.main()
