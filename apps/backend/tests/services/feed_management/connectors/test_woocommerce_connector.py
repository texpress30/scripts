from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feed_management.connectors.woocommerce_connector import WooCommerceConnector


def _connector(store_url="https://mystore.com", key="ck_test", secret="cs_test", **extra_config):
    config = {"store_url": store_url, **extra_config}
    creds = {"consumer_key": key, "consumer_secret": secret}
    return WooCommerceConnector(config=config, credentials=creds)


def _simple_product(pid=1, name="T-Shirt", price="19.99", **overrides):
    return {
        "id": pid,
        "name": name,
        "type": "simple",
        "status": "publish",
        "description": "<p>A nice shirt</p>",
        "short_description": "Nice shirt",
        "price": price,
        "regular_price": "24.99",
        "on_sale": True,
        "sku": f"SKU-{pid}",
        "stock_quantity": 10,
        "permalink": f"https://mystore.com/product/{pid}",
        "images": [{"src": f"https://img.test/{pid}.jpg"}],
        "categories": [{"id": 1, "name": "Clothing"}],
        "tags": [{"id": 1, "name": "summer"}],
        **overrides,
    }


def _variable_product(pid=100, name="Sneakers"):
    return {
        "id": pid,
        "name": name,
        "type": "variable",
        "status": "publish",
        "description": "Cool sneakers",
        "short_description": "Sneakers",
        "price": "49.99",
        "regular_price": "",
        "on_sale": False,
        "sku": "",
        "stock_quantity": None,
        "permalink": f"https://mystore.com/product/{pid}",
        "images": [{"src": f"https://img.test/{pid}.jpg"}],
        "categories": [{"id": 2, "name": "Shoes"}],
        "tags": [],
    }


def _variation(var_id, price="49.99", attrs=None, **overrides):
    return {
        "id": var_id,
        "price": price,
        "regular_price": price,
        "on_sale": False,
        "sku": f"VAR-{var_id}",
        "stock_quantity": 5,
        "image": {"src": f"https://img.test/var-{var_id}.jpg"},
        "attributes": attrs or [{"name": "Size", "option": "M"}],
        **overrides,
    }


class _FakeResponse:
    def __init__(self, data, status_code=200, headers=None):
        self._data = data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=self)


# -- validate_config ---------------------------------------------------------

class TestValidateConfig:
    def test_valid_config(self):
        result = asyncio.run(_connector().validate_config())
        assert result.valid

    def test_missing_store_url(self):
        result = asyncio.run(_connector(store_url="").validate_config())
        assert not result.valid
        assert any("store_url" in e for e in result.errors)

    def test_http_store_rejected(self):
        result = asyncio.run(_connector(store_url="http://mystore.com").validate_config())
        assert not result.valid
        assert any("HTTPS" in e for e in result.errors)

    def test_missing_credentials(self):
        c = WooCommerceConnector(config={"store_url": "https://mystore.com"}, credentials={})
        result = asyncio.run(c.validate_config())
        assert not result.valid
        assert len(result.errors) == 2  # key + secret


# -- mapping ------------------------------------------------------------------

class TestProductMapping:
    def test_simple_product_mapping(self):
        c = _connector()
        products = c._map_woo_product(_simple_product())
        assert len(products) == 1
        p = products[0]
        assert p.id == "1"
        assert p.title == "T-Shirt"
        assert p.price == 19.99
        assert p.compare_at_price == 24.99  # on_sale with higher regular_price
        assert p.sku == "SKU-1"
        assert p.category == "Clothing"
        assert p.tags == ["summer"]
        assert p.inventory_quantity == 10
        assert len(p.images) == 1
        assert p.url == "https://mystore.com/product/1"

    def test_variable_product_creates_per_variation(self):
        c = _connector()
        variations = [
            _variation(201, price="49.99", attrs=[{"name": "Size", "option": "S"}]),
            _variation(202, price="54.99", attrs=[{"name": "Size", "option": "L"}]),
        ]
        products = c._map_woo_product(_variable_product(), variations)
        assert len(products) == 2
        assert products[0].id == "100_201"
        assert products[0].title == "Sneakers - S"
        assert products[0].price == 49.99
        assert products[1].id == "100_202"
        assert products[1].title == "Sneakers - L"
        assert products[1].price == 54.99
        assert products[0].category == "Shoes"

    def test_product_no_images(self):
        c = _connector()
        products = c._map_woo_product(_simple_product(images=[]))
        assert products[0].images == []

    def test_product_no_categories(self):
        c = _connector()
        products = c._map_woo_product(_simple_product(categories=[]))
        assert products[0].category == ""

    def test_product_not_on_sale(self):
        c = _connector()
        products = c._map_woo_product(_simple_product(on_sale=False))
        assert products[0].compare_at_price is None

    def test_product_null_stock(self):
        c = _connector()
        products = c._map_woo_product(_simple_product(stock_quantity=None))
        assert products[0].inventory_quantity == 0


# -- fetch_products -----------------------------------------------------------

class TestFetchProducts:
    def test_single_page_simple_products(self):
        c = _connector()
        products_page = [_simple_product(pid=1), _simple_product(pid=2)]

        async def fake_get(url, **kwargs):
            if "/products" in url and "/variations" not in url:
                return _FakeResponse(products_page, headers={"X-WP-Total": "2", "X-WP-TotalPages": "1"})
            return _FakeResponse({})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            async def run():
                result = []
                async for p in c.fetch_products():
                    result.append(p)
                return result

            result = asyncio.run(run())

        assert len(result) == 2
        assert result[0].id == "1"
        assert result[1].id == "2"

    def test_pagination_two_pages(self):
        c = _connector()
        page1 = [_simple_product(pid=i) for i in range(1, 4)]
        page2 = [_simple_product(pid=4)]

        call_count = {"value": 0}

        async def fake_get(url, **kwargs):
            if "/products" in url and "/variations" not in url:
                call_count["value"] += 1
                params = kwargs.get("params", {})
                page = params.get("page", 1)
                if page == 1:
                    return _FakeResponse(page1, headers={"X-WP-Total": "4", "X-WP-TotalPages": "2"})
                return _FakeResponse(page2, headers={"X-WP-Total": "4", "X-WP-TotalPages": "2"})
            return _FakeResponse({})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            async def run():
                result = []
                async for p in c.fetch_products():
                    result.append(p)
                return result

            result = asyncio.run(run())

        assert len(result) == 4

    def test_variable_product_fetches_variations(self):
        c = _connector()
        products_page = [_variable_product(pid=100)]
        variations = [
            _variation(201, attrs=[{"name": "Color", "option": "Red"}]),
            _variation(202, attrs=[{"name": "Color", "option": "Blue"}]),
        ]

        async def fake_get(url, **kwargs):
            if "/variations" in url:
                return _FakeResponse(variations, headers={"X-WP-TotalPages": "1"})
            if "/products" in url:
                return _FakeResponse(products_page, headers={"X-WP-Total": "1", "X-WP-TotalPages": "1"})
            return _FakeResponse({})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            async def run():
                result = []
                async for p in c.fetch_products():
                    result.append(p)
                return result

            result = asyncio.run(run())

        assert len(result) == 2
        assert result[0].id == "100_201"
        assert result[0].title == "Sneakers - Red"
        assert result[1].id == "100_202"


# -- error handling -----------------------------------------------------------

class TestErrorHandling:
    def test_401_unauthorized(self):
        c = _connector()

        async def fake_get(url, **kwargs):
            resp = _FakeResponse({}, status_code=401)
            resp.raise_for_status()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(c.test_connection())

        assert not result.success
        assert "Authentication failed" in result.message

    def test_connection_error(self):
        c = _connector()

        async def fake_get(url, **kwargs):
            import httpx
            raise httpx.ConnectError("Connection refused")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = asyncio.run(c.test_connection())

        assert not result.success
        assert "Cannot connect" in result.message


# -- get_product_count --------------------------------------------------------

class TestProductCount:
    def test_count_from_header(self):
        c = _connector()

        async def fake_get(url, **kwargs):
            return _FakeResponse([], headers={"X-WP-Total": "42"})

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = fake_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            count = asyncio.run(c.get_product_count())

        assert count == 42
