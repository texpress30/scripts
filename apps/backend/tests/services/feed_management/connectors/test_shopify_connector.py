from __future__ import annotations

import asyncio
import json
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.feed_management.connectors.shopify_connector import (
    ShopifyConnector,
    _normalize_shop_url,
    _parse_next_page_url,
    _strip_html,
)

_SHOP_JSON = {
    "shop": {
        "id": 12345,
        "name": "Test Store",
        "domain": "teststore.myshopify.com",
        "currency": "EUR",
        "plan_display_name": "Basic",
    }
}

_PRODUCT_SIMPLE = {
    "id": 1001,
    "title": "Simple T-Shirt",
    "body_html": "<p>A <strong>basic</strong> cotton t-shirt.</p>",
    "product_type": "Apparel",
    "handle": "simple-t-shirt",
    "tags": "cotton, casual, summer",
    "images": [
        {"id": 1, "src": "https://cdn.shopify.com/shirt1.jpg"},
        {"id": 2, "src": "https://cdn.shopify.com/shirt2.jpg"},
    ],
    "variants": [
        {
            "id": 2001,
            "title": "Small",
            "price": "19.99",
            "compare_at_price": "29.99",
            "sku": "TSHIRT-S",
            "inventory_quantity": 50,
        },
        {
            "id": 2002,
            "title": "Large",
            "price": "19.99",
            "compare_at_price": None,
            "sku": "TSHIRT-L",
            "inventory_quantity": 30,
        },
    ],
}

_PRODUCT_NO_VARIANTS = {
    "id": 1002,
    "title": "Gift Card",
    "body_html": "",
    "product_type": "Gift Cards",
    "handle": "gift-card",
    "tags": "",
    "images": [],
    "variants": [],
}

_PRODUCT_DEFAULT_VARIANT = {
    "id": 1003,
    "title": "Poster",
    "body_html": "A nice poster",
    "product_type": "Art",
    "handle": "poster",
    "tags": "art",
    "images": [{"id": 3, "src": "https://cdn.shopify.com/poster.jpg"}],
    "variants": [
        {
            "id": 3001,
            "title": "Default Title",
            "price": "15.00",
            "compare_at_price": "",
            "sku": "POSTER-001",
            "inventory_quantity": 100,
        },
    ],
}


def _run(coro):
    """Helper to run async code in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect(aiter):
    """Collect all items from an async iterator."""
    items = []
    async for item in aiter:
        items.append(item)
    return items


class TestHelperFunctions(unittest.TestCase):
    def test_normalize_shop_url_full_domain(self):
        self.assertEqual(_normalize_shop_url("myshop.myshopify.com"), "myshop.myshopify.com")

    def test_normalize_shop_url_short_name(self):
        self.assertEqual(_normalize_shop_url("myshop"), "myshop.myshopify.com")

    def test_normalize_shop_url_with_https(self):
        self.assertEqual(_normalize_shop_url("https://myshop.myshopify.com"), "myshop.myshopify.com")

    def test_normalize_shop_url_trailing_slash(self):
        self.assertEqual(_normalize_shop_url("myshop.myshopify.com/"), "myshop.myshopify.com")

    def test_strip_html(self):
        self.assertEqual(_strip_html("<p>Hello <b>world</b></p>"), "Hello world")

    def test_strip_html_entities(self):
        self.assertEqual(_strip_html("Price &amp; value"), "Price & value")

    def test_strip_html_empty(self):
        self.assertEqual(_strip_html(""), "")
        self.assertEqual(_strip_html(None), "")

    def test_parse_next_page_url_present(self):
        link = '<https://shop.myshopify.com/admin/api/2024-01/products.json?page_info=abc>; rel="next"'
        result = _parse_next_page_url(link)
        self.assertEqual(result, "https://shop.myshopify.com/admin/api/2024-01/products.json?page_info=abc")

    def test_parse_next_page_url_with_prev(self):
        link = (
            '<https://shop.myshopify.com/products.json?page_info=prev>; rel="previous", '
            '<https://shop.myshopify.com/products.json?page_info=next>; rel="next"'
        )
        result = _parse_next_page_url(link)
        self.assertEqual(result, "https://shop.myshopify.com/products.json?page_info=next")

    def test_parse_next_page_url_none(self):
        self.assertIsNone(_parse_next_page_url(None))
        self.assertIsNone(_parse_next_page_url('<https://url>; rel="previous"'))


class TestValidateConfig(unittest.TestCase):
    def test_valid_with_access_token(self):
        c = ShopifyConnector(
            config={"store_url": "myshop.myshopify.com"},
            credentials={"access_token": "shpat_xxxx"},
        )
        result = _run(c.validate_config())
        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])

    def test_valid_with_api_keys(self):
        c = ShopifyConnector(
            config={"store_url": "myshop"},
            credentials={"api_key": "key", "api_secret_key": "secret"},
        )
        result = _run(c.validate_config())
        self.assertTrue(result.valid)

    def test_missing_store_url(self):
        c = ShopifyConnector(config={}, credentials={"access_token": "tok"})
        result = _run(c.validate_config())
        self.assertFalse(result.valid)
        self.assertTrue(any("store_url" in e for e in result.errors))

    def test_invalid_store_url(self):
        c = ShopifyConnector(
            config={"store_url": "not a valid url!!!"},
            credentials={"access_token": "tok"},
        )
        result = _run(c.validate_config())
        self.assertFalse(result.valid)

    def test_missing_credentials(self):
        c = ShopifyConnector(config={"store_url": "myshop"}, credentials={})
        result = _run(c.validate_config())
        self.assertFalse(result.valid)
        self.assertTrue(any("credentials" in e.lower() or "access_token" in e.lower() for e in result.errors))


class TestMapShopifyProduct(unittest.TestCase):
    def setUp(self):
        self.connector = ShopifyConnector(
            config={"store_url": "teststore.myshopify.com"},
            credentials={"access_token": "tok"},
        )
        self.connector._shop_currency = "EUR"

    def test_product_with_variants(self):
        results = self.connector._map_shopify_product(_PRODUCT_SIMPLE)
        self.assertEqual(len(results), 2)

        small = results[0]
        self.assertEqual(small.id, "1001_2001")
        self.assertEqual(small.title, "Simple T-Shirt - Small")
        self.assertEqual(small.description, "A basic cotton t-shirt.")
        self.assertEqual(small.price, 19.99)
        self.assertEqual(small.compare_at_price, 29.99)
        self.assertEqual(small.currency, "EUR")
        self.assertEqual(small.sku, "TSHIRT-S")
        self.assertEqual(small.inventory_quantity, 50)
        self.assertEqual(small.category, "Apparel")
        self.assertEqual(small.tags, ["cotton", "casual", "summer"])
        self.assertEqual(len(small.images), 2)
        self.assertIn("simple-t-shirt", small.url)

        large = results[1]
        self.assertEqual(large.id, "1001_2002")
        self.assertEqual(large.title, "Simple T-Shirt - Large")
        self.assertIsNone(large.compare_at_price)

    def test_product_no_variants(self):
        results = self.connector._map_shopify_product(_PRODUCT_NO_VARIANTS)
        self.assertEqual(len(results), 1)
        p = results[0]
        self.assertEqual(p.id, "1002")
        self.assertEqual(p.title, "Gift Card")
        self.assertEqual(p.images, [])
        self.assertEqual(p.tags, [])

    def test_product_default_title_variant(self):
        results = self.connector._map_shopify_product(_PRODUCT_DEFAULT_VARIANT)
        self.assertEqual(len(results), 1)
        p = results[0]
        self.assertEqual(p.title, "Poster")  # "Default Title" should NOT be appended
        self.assertEqual(p.sku, "POSTER-001")
        self.assertIsNone(p.compare_at_price)  # empty string → None

    def test_variants_list_shared(self):
        results = self.connector._map_shopify_product(_PRODUCT_SIMPLE)
        # Both variants should carry the full variants list
        self.assertEqual(len(results[0].variants), 2)
        self.assertEqual(len(results[1].variants), 2)


class _FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200, headers: dict | None = None):
        self._json = json_data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            exc = type("HTTPError", (Exception,), {})()
            exc.response = self
            raise exc


class TestTestConnection(unittest.TestCase):
    def test_successful_connection(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "tok"},
        )
        with patch("app.services.feed_management.connectors.shopify_connector._request") as mock_req:
            mock_req.return_value = _FakeResponse(_SHOP_JSON)
            result = _run(c.test_connection())
        self.assertTrue(result.success)
        self.assertIn("Test Store", result.message)
        self.assertEqual(result.details["currency"], "EUR")

    def test_invalid_config_skips_request(self):
        c = ShopifyConnector(config={}, credentials={})
        result = _run(c.test_connection())
        self.assertFalse(result.success)
        self.assertIn("Invalid config", result.message)


class TestFetchProducts(unittest.TestCase):
    def test_single_page(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "tok"},
        )
        shop_resp = _FakeResponse(_SHOP_JSON)
        products_resp = _FakeResponse({"products": [_PRODUCT_SIMPLE, _PRODUCT_NO_VARIANTS]})

        call_count = [0]
        def _mock_request(method, url, credentials, params=None):
            call_count[0] += 1
            if "shop.json" in url:
                return shop_resp
            return products_resp

        with patch("app.services.feed_management.connectors.shopify_connector._request", side_effect=_mock_request):
            results = _run(_collect(c.fetch_products()))

        # 2 variants from PRODUCT_SIMPLE + 1 from PRODUCT_NO_VARIANTS = 3
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].currency, "EUR")

    def test_pagination(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "tok"},
        )
        page1_resp = _FakeResponse(
            {"products": [_PRODUCT_SIMPLE]},
            headers={"Link": '<https://teststore.myshopify.com/admin/api/2024-01/products.json?page_info=pg2>; rel="next"'},
        )
        page2_resp = _FakeResponse({"products": [_PRODUCT_NO_VARIANTS]})

        call_urls = []
        def _mock_request(method, url, credentials, params=None):
            call_urls.append(url)
            if "shop.json" in url:
                return _FakeResponse(_SHOP_JSON)
            if "page_info=pg2" in url:
                return page2_resp
            return page1_resp

        with patch("app.services.feed_management.connectors.shopify_connector._request", side_effect=_mock_request):
            results = _run(_collect(c.fetch_products()))

        # 2 from PRODUCT_SIMPLE + 1 from PRODUCT_NO_VARIANTS
        self.assertEqual(len(results), 3)
        # Verify pagination URL was fetched
        self.assertTrue(any("page_info=pg2" in u for u in call_urls))

    def test_since_parameter(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "tok"},
        )
        captured_params = {}
        def _mock_request(method, url, credentials, params=None):
            if "products.json" in url and params:
                captured_params.update(params)
            if "shop.json" in url:
                return _FakeResponse(_SHOP_JSON)
            return _FakeResponse({"products": []})

        since = datetime(2024, 6, 1, tzinfo=timezone.utc)
        with patch("app.services.feed_management.connectors.shopify_connector._request", side_effect=_mock_request):
            _run(_collect(c.fetch_products(since=since)))

        self.assertIn("updated_at_min", captured_params)


class TestGetProductCount(unittest.TestCase):
    def test_count(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "tok"},
        )
        with patch("app.services.feed_management.connectors.shopify_connector._request") as mock_req:
            mock_req.return_value = _FakeResponse({"count": 142})
            count = _run(c.get_product_count())
        self.assertEqual(count, 142)


class TestErrorHandling(unittest.TestCase):
    def test_auth_error(self):
        c = ShopifyConnector(
            config={"store_url": "teststore"},
            credentials={"access_token": "bad_token"},
        )
        import requests as req_lib

        def _mock_request(method, url, credentials, params=None):
            resp = MagicMock()
            resp.status_code = 401
            exc = req_lib.HTTPError(response=resp)
            raise exc

        with patch("app.services.feed_management.connectors.shopify_connector._request", side_effect=_mock_request):
            result = _run(c.test_connection())
        self.assertFalse(result.success)
        self.assertIn("Authentication failed", result.message)

    def test_store_not_found(self):
        c = ShopifyConnector(
            config={"store_url": "nonexistent"},
            credentials={"access_token": "tok"},
        )
        import requests as req_lib

        def _mock_request(method, url, credentials, params=None):
            resp = MagicMock()
            resp.status_code = 404
            exc = req_lib.HTTPError(response=resp)
            raise exc

        with patch("app.services.feed_management.connectors.shopify_connector._request", side_effect=_mock_request):
            result = _run(c.test_connection())
        self.assertFalse(result.success)
        self.assertIn("not found", result.message.lower())


if __name__ == "__main__":
    unittest.main()
