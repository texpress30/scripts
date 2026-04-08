"""Tests for ``app.integrations.bigcommerce.client`` + factories.

Mirror style of ``tests/test_magento_oauth_client.py`` — no live HTTP, no
DB. ``httpx.AsyncClient`` is monkey-patched with a tiny fake that returns
fixed responses, so the test suite stays hermetic.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

from app.services.feed_management.models import FeedSourceType
from app.services.integration_secrets_store import IntegrationSecretValue


def _reload_bc_modules():
    import app.integrations.bigcommerce.config as cfg

    importlib.reload(cfg)
    import app.integrations.bigcommerce.service as svc

    importlib.reload(svc)
    import app.integrations.bigcommerce.client as client_mod

    importlib.reload(client_mod)
    return cfg, svc, client_mod


def _set_env() -> None:
    os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
    os.environ["BC_CLIENT_ID"] = "voxel-bc-client-id"
    os.environ["BC_CLIENT_SECRET"] = "voxel-bc-client-secret"
    os.environ["BC_CLIENT_UUID"] = "bc-account-uuid"
    os.environ["BC_REDIRECT_URI"] = "https://admin.example.com/integrations/bigcommerce/auth/callback"


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        data: Any | None = None,
        text: str = "",
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        url: str = "https://api.bigcommerce.com/stores/abc123/v3/catalog/products",
    ) -> None:
        self.status_code = status_code
        self._data = data
        self.text = text or (str(data) if data is not None else "")
        self.content = content if content is not None else self.text.encode("utf-8")
        self.url = url
        self.headers = headers or {}

    def json(self) -> Any:
        if self._data is None:
            raise ValueError("no json body")
        return self._data


def _patched_async_client(*responses: _FakeResponse):
    """Build an AsyncMock-backed ``httpx.AsyncClient`` returning a sequence
    of responses (one per call).
    """
    iterator = iter(responses)

    async def _request(method, url, **kwargs):
        try:
            return next(iterator)
        except StopIteration:
            raise AssertionError(
                "FakeAsyncClient ran out of programmed responses"
            )

    mock_client = AsyncMock()
    mock_client.request = _request
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    # AsyncClient(timeout=...) is invoked with a kwarg — return our fake.
    factory = lambda *_, **__: mock_client  # noqa: E731
    return factory, mock_client


class UrlConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        self.cfg, _, self.client_mod = _reload_bc_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bc_modules()

    def _client(self, **kwargs) -> Any:
        return self.client_mod.BigCommerceClient(
            store_hash="abc123",
            access_token="bc_TOKEN",
            **kwargs,
        )

    def test_v3_url_construction(self) -> None:
        c = self._client()
        self.assertEqual(
            c.build_url("catalog/products"),
            "https://api.bigcommerce.com/stores/abc123/v3/catalog/products",
        )

    def test_v2_url_construction_via_kwarg(self) -> None:
        c = self._client()
        self.assertEqual(
            c.build_url("store", api_version="v2"),
            "https://api.bigcommerce.com/stores/abc123/v2/store",
        )

    def test_v2_url_construction_via_default(self) -> None:
        c = self._client(api_version="v2")
        self.assertEqual(
            c.build_url("store"),
            "https://api.bigcommerce.com/stores/abc123/v2/store",
        )

    def test_leading_slash_on_endpoint_tolerated(self) -> None:
        c = self._client()
        self.assertEqual(
            c.build_url("/catalog/products"),
            "https://api.bigcommerce.com/stores/abc123/v3/catalog/products",
        )

    def test_empty_endpoint_returns_api_base(self) -> None:
        c = self._client()
        self.assertEqual(
            c.build_url(""),
            "https://api.bigcommerce.com/stores/abc123/v3",
        )

    def test_rejects_missing_token(self) -> None:
        with self.assertRaises(ValueError):
            self.client_mod.BigCommerceClient(
                store_hash="abc123", access_token=""
            )

    def test_rejects_unsupported_api_version(self) -> None:
        with self.assertRaises(ValueError):
            self._client(api_version="v4")

    def test_rejects_invalid_store_hash(self) -> None:
        with self.assertRaises(ValueError):
            self.client_mod.BigCommerceClient(
                store_hash="abc/123", access_token="bc_TOKEN"
            )


class AuthHeaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, _, self.client_mod = _reload_bc_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bc_modules()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_request_includes_x_auth_token_header(self) -> None:
        captured: dict[str, Any] = {}

        async def _request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            return _FakeResponse(status_code=200, data={"data": []})

        mock_client = AsyncMock()
        mock_client.request = _request
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        c = self.client_mod.BigCommerceClient(
            store_hash="abc123", access_token="bc_TESTTOKEN"
        )
        with patch.object(
            self.client_mod.httpx, "AsyncClient", return_value=mock_client
        ):
            self._run(c.get("catalog/products"))

        self.assertEqual(captured["headers"]["X-Auth-Token"], "bc_TESTTOKEN")
        self.assertEqual(captured["headers"]["Accept"], "application/json")
        self.assertIn("OmarosaAgency", captured["headers"]["User-Agent"])
        self.assertEqual(captured["method"], "GET")


class HttpErrorClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, _, self.client_mod = _reload_bc_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bc_modules()

    def _client(self):
        return self.client_mod.BigCommerceClient(
            store_hash="abc123", access_token="bc_TOKEN"
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_200_returns_parsed_json(self) -> None:
        response = _FakeResponse(status_code=200, data={"data": [{"id": 1}]})
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            result = self._run(self._client().get("catalog/products"))
        self.assertEqual(result, {"data": [{"id": 1}]})

    def test_204_returns_none(self) -> None:
        response = _FakeResponse(status_code=204, text="", content=b"")
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            result = self._run(self._client().delete("catalog/products/1"))
        self.assertIsNone(result)

    def test_401_raises_auth_error(self) -> None:
        response = _FakeResponse(status_code=401, text='{"title":"Unauthorized"}')
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with self.assertRaises(self.client_mod.BigCommerceAuthError) as ctx:
                self._run(self._client().get("catalog/products"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_403_raises_auth_error(self) -> None:
        response = _FakeResponse(status_code=403, text='{"title":"Forbidden"}')
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with self.assertRaises(self.client_mod.BigCommerceAuthError) as ctx:
                self._run(self._client().get("catalog/products"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_404_raises_not_found(self) -> None:
        response = _FakeResponse(status_code=404, text='{"title":"Not Found"}')
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with self.assertRaises(self.client_mod.BigCommerceNotFoundError) as ctx:
                self._run(self._client().get("catalog/products/999"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_500_raises_server_error(self) -> None:
        response = _FakeResponse(status_code=500, text='{"title":"boom"}')
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with self.assertRaises(self.client_mod.BigCommerceServerError) as ctx:
                self._run(self._client().get("catalog/products"))
        self.assertEqual(ctx.exception.status_code, 500)

    def test_unknown_400_raises_generic_api_error(self) -> None:
        response = _FakeResponse(status_code=418, text="I'm a teapot")
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with self.assertRaises(self.client_mod.BigCommerceAPIError) as ctx:
                self._run(self._client().get("catalog/products"))
        self.assertEqual(ctx.exception.status_code, 418)

    def test_429_retries_once_then_succeeds(self) -> None:
        first = _FakeResponse(
            status_code=429,
            text='{"title":"rate limit"}',
            headers={"X-Rate-Limit-Time-Reset-Ms": "0"},
        )
        second = _FakeResponse(status_code=200, data={"data": [{"id": 7}]})
        factory, _ = _patched_async_client(first, second)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with patch.object(self.client_mod.asyncio, "sleep", new=AsyncMock()):
                result = self._run(self._client().get("catalog/products"))
        self.assertEqual(result, {"data": [{"id": 7}]})

    def test_429_retries_only_once(self) -> None:
        first = _FakeResponse(
            status_code=429, headers={"X-Rate-Limit-Time-Reset-Ms": "0"}
        )
        second = _FakeResponse(
            status_code=429, headers={"X-Rate-Limit-Time-Reset-Ms": "0"}
        )
        factory, _ = _patched_async_client(first, second)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with patch.object(self.client_mod.asyncio, "sleep", new=AsyncMock()):
                with self.assertRaises(self.client_mod.BigCommerceRateLimitError):
                    self._run(self._client().get("catalog/products"))

    def test_low_remaining_budget_triggers_throttle(self) -> None:
        sleeper = AsyncMock()
        response = _FakeResponse(
            status_code=200,
            data={"data": []},
            headers={
                "X-Rate-Limit-Requests-Left": "2",
                "X-Rate-Limit-Time-Reset-Ms": "5000",
            },
        )
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            with patch.object(self.client_mod.asyncio, "sleep", new=sleeper):
                self._run(self._client().get("catalog/products"))
        sleeper.assert_awaited()
        # 5000 ms → 5.0 s
        called_with = sleeper.call_args.args[0]
        self.assertGreaterEqual(called_with, 1.0)


class GetAllPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, _, self.client_mod = _reload_bc_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bc_modules()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_walks_three_pages(self) -> None:
        page1 = _FakeResponse(
            status_code=200,
            data={
                "data": [{"id": 1}, {"id": 2}],
                "meta": {
                    "pagination": {
                        "current_page": 1,
                        "total_pages": 3,
                    }
                },
            },
        )
        page2 = _FakeResponse(
            status_code=200,
            data={
                "data": [{"id": 3}, {"id": 4}],
                "meta": {
                    "pagination": {
                        "current_page": 2,
                        "total_pages": 3,
                    }
                },
            },
        )
        page3 = _FakeResponse(
            status_code=200,
            data={
                "data": [{"id": 5}],
                "meta": {
                    "pagination": {
                        "current_page": 3,
                        "total_pages": 3,
                    }
                },
            },
        )
        factory, _ = _patched_async_client(page1, page2, page3)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            client = self.client_mod.BigCommerceClient(
                store_hash="abc123", access_token="bc_TOKEN"
            )
            result = self._run(client.get_all_pages("catalog/products"))
        self.assertEqual([item["id"] for item in result], [1, 2, 3, 4, 5])

    def test_returns_empty_list_when_meta_missing(self) -> None:
        response = _FakeResponse(
            status_code=200,
            data={"data": []},
        )
        factory, _ = _patched_async_client(response)
        with patch.object(self.client_mod.httpx, "AsyncClient", side_effect=factory):
            client = self.client_mod.BigCommerceClient(
                store_hash="abc123", access_token="bc_TOKEN"
            )
            result = self._run(client.get_all_pages("catalog/products"))
        self.assertEqual(result, [])

    def test_rejects_invalid_page_size(self) -> None:
        client = self.client_mod.BigCommerceClient(
            store_hash="abc123", access_token="bc_TOKEN"
        )
        with self.assertRaises(ValueError):
            self._run(client.get_all_pages("catalog/products", page_size=0))
        with self.assertRaises(ValueError):
            self._run(client.get_all_pages("catalog/products", page_size=251))


class FactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        _set_env()
        _, self.svc, self.client_mod = _reload_bc_modules()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        _reload_bc_modules()

    def test_create_from_store_hash_happy_path(self) -> None:
        with patch.object(
            self.client_mod.bc_service,
            "get_bigcommerce_credentials",
            return_value={
                "access_token": "bc_PERSIST",
                "scope": "store_v2_products_read_only",
            },
        ):
            client = self.client_mod.create_bc_client_from_store_hash("abc123")
        self.assertEqual(client.store_hash, "abc123")
        self.assertEqual(client.api_version, "v3")

    def test_create_from_store_hash_missing_credentials(self) -> None:
        with patch.object(
            self.client_mod.bc_service,
            "get_bigcommerce_credentials",
            return_value=None,
        ):
            with self.assertRaises(self.client_mod.BigCommerceAuthError):
                self.client_mod.create_bc_client_from_store_hash("abc123")

    def test_create_from_source_id_happy_path(self) -> None:
        from app.services.feed_management.models import FeedSourceResponse

        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        fake_source = FeedSourceResponse(
            id="src-1",
            subaccount_id=42,
            source_type=FeedSourceType.bigcommerce,
            name="My BC Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            bigcommerce_store_hash="abc123",
            connection_status="connected",
            has_token=True,
            created_at=now,
            updated_at=now,
        )

        from app.services.feed_management.repository import FeedSourceRepository

        with patch.object(
            FeedSourceRepository, "get_by_id", return_value=fake_source
        ), patch.object(
            self.client_mod.bc_service,
            "get_bigcommerce_credentials",
            return_value={"access_token": "bc_TOKEN"},
        ):
            client = self.client_mod.create_bc_client_from_source("src-1")
        self.assertEqual(client.store_hash, "abc123")

    def test_create_from_source_id_wrong_type(self) -> None:
        from app.services.feed_management.models import FeedSourceResponse

        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        fake_source = FeedSourceResponse(
            id="src-1",
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="My Shopify Store",
            config={},
            credentials_secret_id=None,
            is_active=True,
            shop_domain="store.myshopify.com",
            connection_status="connected",
            has_token=True,
            created_at=now,
            updated_at=now,
        )
        from app.services.feed_management.repository import FeedSourceRepository

        with patch.object(
            FeedSourceRepository, "get_by_id", return_value=fake_source
        ):
            with self.assertRaises(ValueError):
                self.client_mod.create_bc_client_from_source("src-1")

    def test_create_from_source_id_missing_store_hash(self) -> None:
        from app.services.feed_management.models import FeedSourceResponse

        now = datetime(2026, 4, 8, tzinfo=timezone.utc)
        fake_source = FeedSourceResponse(
            id="src-1",
            subaccount_id=42,
            source_type=FeedSourceType.bigcommerce,
            name="No hash",
            config={},
            credentials_secret_id=None,
            is_active=True,
            bigcommerce_store_hash=None,
            connection_status="pending",
            has_token=False,
            created_at=now,
            updated_at=now,
        )
        from app.services.feed_management.repository import FeedSourceRepository

        with patch.object(
            FeedSourceRepository, "get_by_id", return_value=fake_source
        ):
            with self.assertRaises(ValueError):
                self.client_mod.create_bc_client_from_source("src-1")


if __name__ == "__main__":
    unittest.main()
