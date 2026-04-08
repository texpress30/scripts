"""Tests for :class:`app.integrations.magento.connector.MagentoConnector`.

Strategy: we pass a fake ``MagentoClient`` via the constructor's ``client``
kwarg and stub its ``.get()`` method with an ``AsyncMock`` that returns
canned Magento payloads. No HTTP, no DB, no real OAuth signing — just the
connector's paging / bootstrapping / configurable-expansion logic under
test.
"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock

from app.integrations.magento.connector import (
    MagentoConnector,
    _build_product_search_params,
)
from app.services.feed_management.connectors.base import (
    ConnectionTestResult,
    ProductData,
    ValidationResult,
)


_BASE_URL = "https://magento.example.com"
_STORE_CODE = "default"


_CATEGORY_TREE = {
    "id": 1,
    "name": "Root Catalog",
    "children_data": [
        {
            "id": 2,
            "name": "Default Category",
            "children_data": [
                {"id": 3, "name": "Clothing", "children_data": []},
                {"id": 7, "name": "Accessories", "children_data": []},
            ],
        }
    ],
}

_STORE_CONFIGS = [
    {
        "code": "default",
        "name": "Main Website Store",
        "base_currency_code": "EUR",
        "default_display_currency_code": "EUR",
        "base_media_url": "https://cdn.example.com/media/",
    }
]


def _simple_item(pid: int, *, type_id: str = "simple", price: float = 9.99) -> dict[str, Any]:
    return {
        "id": pid,
        "sku": f"SKU-{pid}",
        "name": f"Product {pid}",
        "type_id": type_id,
        "price": price,
        "status": 1,
        "visibility": 4,
        "custom_attributes": [
            {"attribute_code": "description", "value": f"Description {pid}"},
            {"attribute_code": "url_key", "value": f"product-{pid}"},
            {"attribute_code": "category_ids", "value": "3"},
        ],
        "media_gallery_entries": [
            {
                "file": f"/p/{pid}/image.jpg",
                "types": ["image"],
                "position": 1,
                "disabled": False,
            }
        ],
        "extension_attributes": {"stock_item": {"qty": pid, "is_in_stock": True}},
    }


def _make_connector(
    *,
    responses: dict[str, Any] | None = None,
    client: AsyncMock | None = None,
    credentials: dict[str, str] | None = None,
    page_size: int = 100,
    config: dict[str, Any] | None = None,
) -> tuple[MagentoConnector, AsyncMock]:
    """Build a ``MagentoConnector`` with a stubbed client.

    ``responses`` is an ``{endpoint: return_value_or_list}`` map. If the
    value is a list it is consumed one call at a time (for paginated
    ``products`` responses); otherwise it's returned for every matching
    call.
    """
    if client is None:
        client = AsyncMock()
        response_map: dict[str, list[Any]] = {}
        for endpoint, value in (responses or {}).items():
            response_map[endpoint] = value if isinstance(value, list) and _is_many(value) else [value]

        async def _fake_get(endpoint: str, *, params: dict[str, Any] | None = None):
            key = _match_endpoint(endpoint, response_map)
            queue = response_map.get(key)
            if queue is None:
                raise AssertionError(f"unmocked endpoint: {endpoint}")
            if len(queue) > 1:
                return queue.pop(0)
            return queue[0]

        client.get = AsyncMock(side_effect=_fake_get)

    # ``credentials={}`` means "no credentials" — distinguish from the
    # ``credentials=None`` default which gets a full happy-path dict.
    if credentials is None:
        creds = {
            "consumer_key": "ck",
            "consumer_secret": "cs",
            "access_token": "at",
            "access_token_secret": "ats",
        }
    else:
        creds = credentials
    merged_config: dict[str, Any] = {
        "magento_base_url": _BASE_URL,
        "magento_store_code": _STORE_CODE,
    }
    if config:
        merged_config.update(config)

    connector = MagentoConnector(
        config=merged_config,
        credentials=creds,
        client=client,
        page_size=page_size,
    )
    return connector, client


def _is_many(value: list[Any]) -> bool:
    """Heuristic: a list whose first element is itself a list-or-dict-payload
    means this is a queue of multi-turn responses (e.g. two product pages).
    We look for the canonical ``items`` / ``total_count`` shape in the first
    element to decide whether the outer list is a queue or a direct payload.
    """
    if not value:
        return False
    first = value[0]
    if isinstance(first, dict) and ("items" in first and "total_count" in first):
        return True
    if isinstance(first, list) or first is None:
        return True
    return False


def _match_endpoint(endpoint: str, response_map: dict[str, list[Any]]) -> str:
    # Exact match wins; otherwise pick the longest registered prefix that
    # matches the start of ``endpoint``. Lets tests register
    # ``"configurable-products"`` once and serve every child fetch.
    if endpoint in response_map:
        return endpoint
    best = ""
    for key in response_map:
        if endpoint.startswith(key) and len(key) > len(best):
            best = key
    return best


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _collect(connector: MagentoConnector) -> list[ProductData]:
    out: list[ProductData] = []
    async for product in connector.fetch_products():
        out.append(product)
    return out


# ---------------------------------------------------------------------------
# validate_config / test_connection
# ---------------------------------------------------------------------------


class ValidateConfigTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        connector, _ = _make_connector(responses={})
        result = _run(connector.validate_config())
        self.assertTrue(result.valid)

    def test_missing_credentials(self) -> None:
        connector, _ = _make_connector(responses={}, credentials={})
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)
        self.assertTrue(
            any("credentials" in e.lower() for e in result.errors),
            msg=result.errors,
        )

    def test_invalid_base_url(self) -> None:
        connector, _ = _make_connector(
            responses={}, config={"magento_base_url": "http://magento.example.com"}
        )
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)

    def test_missing_base_url(self) -> None:
        connector = MagentoConnector(
            config={},
            credentials={
                "consumer_key": "ck",
                "consumer_secret": "cs",
                "access_token": "at",
                "access_token_secret": "ats",
            },
            client=AsyncMock(),
        )
        result = _run(connector.validate_config())
        self.assertFalse(result.valid)


class TestConnectionTests(unittest.TestCase):
    def test_success_returns_store_details(self) -> None:
        connector, _ = _make_connector(
            responses={"store/storeConfigs": _STORE_CONFIGS},
        )
        result = _run(connector.test_connection())
        self.assertTrue(result.success)
        assert result.details is not None
        self.assertEqual(result.details["store_name"], "Main Website Store")
        self.assertEqual(result.details["base_currency"], "EUR")

    def test_validation_failure_short_circuits(self) -> None:
        connector, client = _make_connector(responses={}, credentials={})
        result = _run(connector.test_connection())
        self.assertFalse(result.success)
        client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PaginationTests(unittest.TestCase):
    def test_single_page_50_products_one_request(self) -> None:
        items = [_simple_item(i) for i in range(1, 51)]
        response = {
            "items": items,
            "total_count": 50,
            "search_criteria": {"page_size": 100, "current_page": 1},
        }
        connector, client = _make_connector(
            responses={
                "store/storeConfigs": _STORE_CONFIGS,
                "categories": _CATEGORY_TREE,
                "products": response,
            },
            page_size=100,
        )

        products = _run(_collect(connector))
        self.assertEqual(len(products), 50)
        # Exactly one /products call (plus bootstrap storeConfigs + categories)
        product_calls = [c for c in client.get.call_args_list if c.args[0] == "products"]
        self.assertEqual(len(product_calls), 1)

    def test_multiple_pages_250_products_three_requests(self) -> None:
        page_1 = {
            "items": [_simple_item(i) for i in range(1, 101)],
            "total_count": 250,
        }
        page_2 = {
            "items": [_simple_item(i) for i in range(101, 201)],
            "total_count": 250,
        }
        page_3 = {
            "items": [_simple_item(i) for i in range(201, 251)],
            "total_count": 250,
        }
        connector, client = _make_connector(
            responses={
                "store/storeConfigs": _STORE_CONFIGS,
                "categories": _CATEGORY_TREE,
                "products": [page_1, page_2, page_3],
            },
            page_size=100,
        )

        products = _run(_collect(connector))
        self.assertEqual(len(products), 250)
        product_calls = [c for c in client.get.call_args_list if c.args[0] == "products"]
        self.assertEqual(len(product_calls), 3)
        # Check that currentPage increments across calls
        pages = [
            int(c.kwargs["params"]["searchCriteria[currentPage]"])
            for c in product_calls
        ]
        self.assertEqual(pages, [1, 2, 3])


# ---------------------------------------------------------------------------
# Category cache — one lookup, not one per product
# ---------------------------------------------------------------------------


class CategoryCacheTests(unittest.TestCase):
    def test_200_products_only_one_categories_call(self) -> None:
        page_1 = {
            "items": [_simple_item(i) for i in range(1, 101)],
            "total_count": 200,
        }
        page_2 = {
            "items": [_simple_item(i) for i in range(101, 201)],
            "total_count": 200,
        }
        connector, client = _make_connector(
            responses={
                "store/storeConfigs": _STORE_CONFIGS,
                "categories": _CATEGORY_TREE,
                "products": [page_1, page_2],
            },
            page_size=100,
        )

        products = _run(_collect(connector))
        self.assertEqual(len(products), 200)
        # Every product must carry the resolved category name
        for p in products:
            self.assertEqual(p.category, "Clothing")
        categories_calls = [c for c in client.get.call_args_list if c.args[0] == "categories"]
        self.assertEqual(len(categories_calls), 1)

    def test_categories_endpoint_failure_does_not_break_sync(self) -> None:
        from app.integrations.magento.exceptions import MagentoNotFoundError

        async def _fake_get(endpoint, *, params=None):
            if endpoint == "store/storeConfigs":
                return _STORE_CONFIGS
            if endpoint == "categories":
                raise MagentoNotFoundError("categories endpoint missing")
            if endpoint == "products":
                return {"items": [_simple_item(1)], "total_count": 1}
            raise AssertionError(f"unmocked endpoint: {endpoint}")

        client = AsyncMock()
        client.get = AsyncMock(side_effect=_fake_get)
        connector, _ = _make_connector(responses={}, client=client)

        products = _run(_collect(connector))
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].category, "")


# ---------------------------------------------------------------------------
# Configurable product expansion
# ---------------------------------------------------------------------------


class ConfigurableExpansionTests(unittest.TestCase):
    def test_configurable_product_has_children_as_variants(self) -> None:
        parent = _simple_item(1000, type_id="configurable", price=49.99)
        children = [
            {
                "id": 1001,
                "sku": "SKU-1000-RED",
                "name": "Product 1000 - Red",
                "type_id": "simple",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 10}},
            },
            {
                "id": 1002,
                "sku": "SKU-1000-BLUE",
                "name": "Product 1000 - Blue",
                "type_id": "simple",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 7}},
            },
        ]

        async def _fake_get(endpoint, *, params=None):
            if endpoint == "store/storeConfigs":
                return _STORE_CONFIGS
            if endpoint == "categories":
                return _CATEGORY_TREE
            if endpoint == "products":
                return {"items": [parent], "total_count": 1}
            if endpoint.startswith("configurable-products/"):
                return children
            raise AssertionError(f"unmocked endpoint: {endpoint}")

        client = AsyncMock()
        client.get = AsyncMock(side_effect=_fake_get)
        connector, _ = _make_connector(responses={}, client=client)

        products = _run(_collect(connector))
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].id, "1000")
        self.assertEqual(len(products[0].variants), 2)
        self.assertEqual(products[0].variants[0].sku, "SKU-1000-RED")
        self.assertEqual(products[0].variants[1].sku, "SKU-1000-BLUE")

    def test_missing_children_endpoint_gracefully_ignored(self) -> None:
        from app.integrations.magento.exceptions import MagentoNotFoundError

        parent = _simple_item(2000, type_id="configurable")

        async def _fake_get(endpoint, *, params=None):
            if endpoint == "store/storeConfigs":
                return _STORE_CONFIGS
            if endpoint == "categories":
                return _CATEGORY_TREE
            if endpoint == "products":
                return {"items": [parent], "total_count": 1}
            if endpoint.startswith("configurable-products/"):
                raise MagentoNotFoundError("not found")
            raise AssertionError(f"unmocked endpoint: {endpoint}")

        client = AsyncMock()
        client.get = AsyncMock(side_effect=_fake_get)
        connector, _ = _make_connector(responses={}, client=client)

        products = _run(_collect(connector))
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].variants, [])


# ---------------------------------------------------------------------------
# get_product_count
# ---------------------------------------------------------------------------


class GetProductCountTests(unittest.TestCase):
    def test_returns_total_count_from_response(self) -> None:
        connector, _ = _make_connector(
            responses={"products": {"items": [], "total_count": 1234}},
        )
        count = _run(connector.get_product_count())
        self.assertEqual(count, 1234)

    def test_defaults_to_zero_on_missing_payload(self) -> None:
        connector, _ = _make_connector(responses={"products": {}})
        count = _run(connector.get_product_count())
        self.assertEqual(count, 0)


# ---------------------------------------------------------------------------
# searchCriteria builder
# ---------------------------------------------------------------------------


class SearchCriteriaTests(unittest.TestCase):
    def test_default_filters_status_and_visibility(self) -> None:
        params = _build_product_search_params(current_page=2, page_size=50, since=None)
        self.assertEqual(params["searchCriteria[currentPage]"], "2")
        self.assertEqual(params["searchCriteria[pageSize]"], "50")
        self.assertEqual(
            params["searchCriteria[filter_groups][0][filters][0][field]"], "status"
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][0][filters][0][value]"], "1"
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][1][filters][0][field]"], "visibility"
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][1][filters][0][value]"], "2,3,4"
        )
        self.assertNotIn(
            "searchCriteria[filter_groups][2][filters][0][field]", params
        )

    def test_since_adds_updated_at_filter(self) -> None:
        from datetime import datetime, timezone

        since = datetime(2026, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
        params = _build_product_search_params(
            current_page=1, page_size=100, since=since
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][2][filters][0][field]"],
            "updated_at",
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][2][filters][0][value]"],
            "2026-01-15 12:30:00",
        )
        self.assertEqual(
            params["searchCriteria[filter_groups][2][filters][0][condition_type]"],
            "gteq",
        )


if __name__ == "__main__":
    unittest.main()
