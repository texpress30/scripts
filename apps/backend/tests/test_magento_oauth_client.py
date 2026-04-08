"""Tests for ``app.integrations.magento.oauth`` + ``client`` + ``exceptions``.

Exercises:

* ``generate_oauth_signature`` — pure HMAC-SHA1 signature computation,
  including RFC 5849's canonical Twitter example to lock in byte-exact
  compatibility with a reference implementation.
* ``build_authorization_header`` — contains every required ``oauth_*``
  parameter, emits two different headers for consecutive calls (fresh
  nonce + timestamp).
* ``MagentoClient.build_url`` — URL construction for default and custom
  store codes.
* ``MagentoClient._request`` — error classification (401/403/404/429/5xx)
  exercised with a patched ``httpx.AsyncClient`` (same style as the
  existing WooCommerce tests).
* ``create_magento_client_from_source`` — factory loads source + creds
  from monkey-patched repo + secrets store, raises on missing fields.
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.magento import client as magento_client
from app.integrations.magento import service as magento_service
from app.integrations.magento.client import (
    DEFAULT_STORE_CODE,
    MagentoClient,
    create_magento_client_from_source,
)
from app.integrations.magento.exceptions import (
    MagentoAPIError,
    MagentoAuthError,
    MagentoConnectionError,
    MagentoNotFoundError,
    MagentoRateLimitError,
)
from app.integrations.magento.oauth import (
    build_authorization_header,
    generate_nonce,
    generate_oauth_signature,
    generate_timestamp,
    percent_encode,
)
from app.services.feed_management.models import (
    FeedSourceResponse,
    FeedSourceType,
)


_NOW = datetime(2026, 4, 7, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# oauth.py
# ---------------------------------------------------------------------------


class PercentEncodeTests(unittest.TestCase):
    def test_unreserved_characters_pass_through(self) -> None:
        self.assertEqual(percent_encode("abcXYZ123-._~"), "abcXYZ123-._~")

    def test_space_is_percent_20(self) -> None:
        self.assertEqual(percent_encode("hello world"), "hello%20world")

    def test_reserved_characters_are_encoded(self) -> None:
        self.assertEqual(percent_encode("a+b"), "a%2Bb")
        self.assertEqual(percent_encode("a/b"), "a%2Fb")
        self.assertEqual(percent_encode("a=b"), "a%3Db")
        self.assertEqual(percent_encode("a&b"), "a%26b")

    def test_non_ascii_uses_utf8(self) -> None:
        self.assertEqual(percent_encode("café"), "caf%C3%A9")


class GenerateSignatureTests(unittest.TestCase):
    """Byte-level HMAC-SHA1 checks using two fully deterministic vectors."""

    def test_twitter_canonical_example_matches_reference(self) -> None:
        """RFC-style vector straight out of the Twitter OAuth 1.0a docs.

        Any divergence from this string means our encoding/sorting/HMAC
        path has broken, so this test is the safety net for future
        refactors.
        """
        sig = generate_oauth_signature(
            http_method="POST",
            url="https://api.twitter.com/1.1/statuses/update.json?include_entities=true",
            params={
                "status": "Hello Ladies + Gentlemen, a signed OAuth request!",
                "oauth_consumer_key": "xvz1evFS4wEEPTGEFPHBog",
                "oauth_nonce": "kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg",
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": "1318622958",
                "oauth_token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
                "oauth_version": "1.0",
            },
            consumer_secret="kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
            token_secret="LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
        )
        self.assertEqual(sig, "hCtSmYh+iHYCEqBWrE7C7hYmtUk=")

    def test_deterministic_for_same_inputs(self) -> None:
        kwargs = dict(
            http_method="GET",
            url="https://store.example.com/rest/default/V1/products",
            params={
                "oauth_consumer_key": "ck_ABC",
                "oauth_token": "at_XYZ",
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_nonce": "fixed_nonce",
                "oauth_timestamp": "1700000000",
                "oauth_version": "1.0",
                "searchCriteria[pageSize]": "10",
            },
            consumer_secret="cs_ABC",
            token_secret="ats_XYZ",
        )
        sig1 = generate_oauth_signature(**kwargs)
        sig2 = generate_oauth_signature(**kwargs)
        self.assertEqual(sig1, sig2)

    def test_different_method_produces_different_signature(self) -> None:
        base_kwargs = dict(
            url="https://store.example.com/rest/default/V1/products",
            params={
                "oauth_consumer_key": "ck",
                "oauth_token": "at",
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_nonce": "n",
                "oauth_timestamp": "1",
                "oauth_version": "1.0",
            },
            consumer_secret="cs",
            token_secret="ats",
        )
        self.assertNotEqual(
            generate_oauth_signature(http_method="GET", **base_kwargs),
            generate_oauth_signature(http_method="POST", **base_kwargs),
        )

    def test_query_string_merged_into_base_string(self) -> None:
        """A query string baked into the URL must produce the same signature
        as the same parameter passed through ``params`` — signing must be
        invariant to where the parameter came from."""
        common_params = {
            "oauth_consumer_key": "ck",
            "oauth_token": "at",
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_nonce": "n",
            "oauth_timestamp": "1",
            "oauth_version": "1.0",
        }
        sig_url_q = generate_oauth_signature(
            http_method="GET",
            url="https://store.example.com/rest/default/V1/products?page=2",
            params=common_params,
            consumer_secret="cs",
            token_secret="ats",
        )
        sig_params_q = generate_oauth_signature(
            http_method="GET",
            url="https://store.example.com/rest/default/V1/products",
            params={**common_params, "page": "2"},
            consumer_secret="cs",
            token_secret="ats",
        )
        self.assertEqual(sig_url_q, sig_params_q)


class BuildAuthorizationHeaderTests(unittest.TestCase):
    _COMMON = dict(
        consumer_key="ck_test_consumer_key",
        consumer_secret="cs_test_consumer_secret",
        access_token="at_test_access_token",
        access_token_secret="ats_test_access_token_secret",
        http_method="GET",
        url="https://store.example.com/rest/default/V1/products",
    )

    def test_contains_every_mandatory_oauth_param(self) -> None:
        header = build_authorization_header(
            **self._COMMON,
            nonce="fixed_nonce_1234567890",
            timestamp="1700000000",
        )
        self.assertTrue(header.startswith("OAuth "))
        for required in (
            "oauth_consumer_key=",
            "oauth_nonce=",
            "oauth_signature=",
            "oauth_signature_method=",
            "oauth_timestamp=",
            "oauth_token=",
            "oauth_version=",
        ):
            self.assertIn(required, header)

    def test_header_values_are_quoted_and_percent_encoded(self) -> None:
        header = build_authorization_header(
            **self._COMMON,
            nonce="fixed",
            timestamp="1700000000",
        )
        # Every parameter must be wrapped in double quotes
        self.assertIn('oauth_consumer_key="ck_test_consumer_key"', header)
        # HMAC-SHA1 literally — the hyphen is unreserved so no encoding
        self.assertIn('oauth_signature_method="HMAC-SHA1"', header)
        self.assertIn('oauth_version="1.0"', header)

    def test_header_changes_per_request_when_nonce_and_timestamp_auto(self) -> None:
        h1 = build_authorization_header(**self._COMMON)
        h2 = build_authorization_header(**self._COMMON)
        self.assertNotEqual(h1, h2)  # fresh nonce (and often timestamp)

    def test_query_params_included_in_signature(self) -> None:
        h_no_params = build_authorization_header(
            **self._COMMON,
            nonce="fixed",
            timestamp="1700000000",
        )
        h_with_params = build_authorization_header(
            **self._COMMON,
            nonce="fixed",
            timestamp="1700000000",
            query_params={"searchCriteria[pageSize]": "10"},
        )
        # Same nonce+timestamp but different params → different signature
        self.assertNotEqual(h_no_params, h_with_params)

    def test_rejects_empty_consumer_key(self) -> None:
        kwargs = dict(self._COMMON)
        kwargs["consumer_key"] = ""
        with self.assertRaises(ValueError):
            build_authorization_header(**kwargs)


class NonceAndTimestampTests(unittest.TestCase):
    def test_generate_nonce_is_unique(self) -> None:
        values = {generate_nonce() for _ in range(20)}
        self.assertEqual(len(values), 20)

    def test_generate_timestamp_is_positive_int_string(self) -> None:
        ts = generate_timestamp()
        self.assertTrue(ts.isdigit())
        self.assertGreater(int(ts), 1_000_000_000)


# ---------------------------------------------------------------------------
# client.py — URL construction
# ---------------------------------------------------------------------------


class UrlConstructionTests(unittest.TestCase):
    def _client(self, *, base_url: str = "https://store.example.com", store_code: str = DEFAULT_STORE_CODE) -> MagentoClient:
        return MagentoClient(
            base_url=base_url,
            store_code=store_code,
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )

    def test_default_store_code(self) -> None:
        c = self._client()
        self.assertEqual(c.api_base_url, "https://store.example.com/rest/default/V1")
        self.assertEqual(c.build_url("products"), "https://store.example.com/rest/default/V1/products")

    def test_custom_store_code(self) -> None:
        c = self._client(store_code="ro_store")
        self.assertEqual(c.api_base_url, "https://store.example.com/rest/ro_store/V1")
        self.assertEqual(
            c.build_url("products"),
            "https://store.example.com/rest/ro_store/V1/products",
        )

    def test_trailing_slash_on_base_url_stripped(self) -> None:
        c = self._client(base_url="https://store.example.com/")
        self.assertEqual(c.base_url, "https://store.example.com")

    def test_leading_slash_on_endpoint_tolerated(self) -> None:
        c = self._client()
        self.assertEqual(
            c.build_url("/products"),
            "https://store.example.com/rest/default/V1/products",
        )

    def test_empty_endpoint_returns_api_base(self) -> None:
        c = self._client()
        self.assertEqual(c.build_url(""), "https://store.example.com/rest/default/V1")

    def test_rejects_missing_credentials(self) -> None:
        with self.assertRaises(ValueError):
            MagentoClient(
                base_url="https://store.example.com",
                consumer_key="",
                consumer_secret="cs",
                access_token="at",
                access_token_secret="ats",
            )


# ---------------------------------------------------------------------------
# client.py — HTTP error classification
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        data: Any | None = None,
        text: str = "",
        content: bytes | None = None,
    ) -> None:
        self.status_code = status_code
        self._data = data
        self.text = text or (str(data) if data is not None else "")
        self.content = content if content is not None else self.text.encode("utf-8")
        self.url = "https://store.example.com/rest/default/V1/products"

    def json(self) -> Any:
        if self._data is None:
            raise ValueError("no json body")
        return self._data


def _patched_client(response: _FakeResponse):
    """Build an AsyncMock-backed ``httpx.AsyncClient`` stand-in that
    returns ``response`` from every ``request`` call.
    """
    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class ClientHttpErrorsTests(unittest.TestCase):
    def _client(self) -> MagentoClient:
        return MagentoClient(
            base_url="https://store.example.com",
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_200_returns_parsed_json(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=200, data={"items": [{"id": 1}]})
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            result = self._run(c.get("products"))
        self.assertEqual(result, {"items": [{"id": 1}]})

    def test_401_raises_auth_error(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=401, text='{"message":"Unauthorized"}')
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            with self.assertRaises(MagentoAuthError) as ctx:
                self._run(c.get("products"))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_403_raises_auth_error(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=403, text='{"message":"Forbidden"}')
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            with self.assertRaises(MagentoAuthError) as ctx:
                self._run(c.get("products"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_404_raises_not_found(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=404, text='{"message":"Not Found"}')
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            with self.assertRaises(MagentoNotFoundError) as ctx:
                self._run(c.get("products/999"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_429_raises_rate_limit(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=429, text="rate limited")
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            with self.assertRaises(MagentoRateLimitError) as ctx:
                self._run(c.get("products"))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_500_raises_generic_api_error(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=500, text='{"message":"boom"}')
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            with self.assertRaises(MagentoAPIError) as ctx:
                self._run(c.get("products"))
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertNotIsInstance(ctx.exception, MagentoAuthError)
        self.assertNotIsInstance(ctx.exception, MagentoNotFoundError)
        self.assertNotIsInstance(ctx.exception, MagentoRateLimitError)

    def test_connect_error_raises_connection_error(self) -> None:
        import httpx

        c = self._client()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("DNS fail"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch.object(magento_client.httpx, "AsyncClient", return_value=mock_client):
            with self.assertRaises(MagentoConnectionError):
                self._run(c.get("products"))

    def test_read_timeout_raises_connection_error(self) -> None:
        import httpx

        c = self._client()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=httpx.ReadTimeout("read timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch.object(magento_client.httpx, "AsyncClient", return_value=mock_client):
            with self.assertRaises(MagentoConnectionError):
                self._run(c.get("products"))

    def test_204_no_content_returns_none(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=204, content=b"")
        with patch.object(magento_client.httpx, "AsyncClient", return_value=_patched_client(response)):
            result = self._run(c.delete("products/1"))
        self.assertIsNone(result)

    def test_post_sends_json_body(self) -> None:
        c = self._client()
        response = _FakeResponse(status_code=200, data={"ok": True})
        mock_client = _patched_client(response)
        with patch.object(magento_client.httpx, "AsyncClient", return_value=mock_client):
            self._run(c.post("products", json_body={"sku": "abc"}))
        # Verify request() was called with json= kwarg
        args, kwargs = mock_client.request.call_args
        self.assertEqual(kwargs.get("json"), {"sku": "abc"})
        self.assertEqual(args[0], "POST")


# ---------------------------------------------------------------------------
# Factory create_magento_client_from_source
# ---------------------------------------------------------------------------


def _magento_source(**overrides) -> FeedSourceResponse:
    base = dict(
        id="src-magento-1",
        subaccount_id=42,
        source_type=FeedSourceType.magento,
        name="Main Magento",
        config={},
        credentials_secret_id=None,
        is_active=True,
        catalog_type="product",
        catalog_variant="physical_products",
        magento_base_url="https://magento.example.com",
        magento_store_code="default",
        connection_status="connected",
        has_token=True,
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(overrides)
    return FeedSourceResponse(**base)


class FactoryFromSourceTests(unittest.TestCase):
    def test_happy_path_returns_ready_to_use_client(self) -> None:
        with patch(
            "app.services.feed_management.repository.FeedSourceRepository.get_by_id",
            return_value=_magento_source(),
        ), patch.object(
            magento_service,
            "get_magento_credentials",
            return_value={
                "consumer_key": "ck_abcdef1234",
                "consumer_secret": "cs_abcdef1234",
                "access_token": "at_abcdef1234",
                "access_token_secret": "ats_abcdef1234",
            },
        ):
            client = create_magento_client_from_source("src-magento-1")
        self.assertIsInstance(client, MagentoClient)
        self.assertEqual(client.base_url, "https://magento.example.com")
        self.assertEqual(client.store_code, "default")
        self.assertEqual(
            client.api_base_url,
            "https://magento.example.com/rest/default/V1",
        )

    def test_raises_value_error_when_source_is_not_magento(self) -> None:
        with patch(
            "app.services.feed_management.repository.FeedSourceRepository.get_by_id",
            return_value=_magento_source(source_type=FeedSourceType.shopify),
        ):
            with self.assertRaises(ValueError):
                create_magento_client_from_source("src-1")

    def test_raises_value_error_when_base_url_missing(self) -> None:
        with patch(
            "app.services.feed_management.repository.FeedSourceRepository.get_by_id",
            return_value=_magento_source(magento_base_url=None),
        ):
            with self.assertRaises(ValueError):
                create_magento_client_from_source("src-1")

    def test_raises_auth_error_when_credentials_missing(self) -> None:
        with patch(
            "app.services.feed_management.repository.FeedSourceRepository.get_by_id",
            return_value=_magento_source(),
        ), patch.object(
            magento_service,
            "get_magento_credentials",
            return_value=None,
        ):
            with self.assertRaises(MagentoAuthError):
                create_magento_client_from_source("src-magento-1")

    def test_custom_store_code_propagated(self) -> None:
        with patch(
            "app.services.feed_management.repository.FeedSourceRepository.get_by_id",
            return_value=_magento_source(magento_store_code="ro_store"),
        ), patch.object(
            magento_service,
            "get_magento_credentials",
            return_value={
                "consumer_key": "ck",
                "consumer_secret": "cs",
                "access_token": "at",
                "access_token_secret": "ats",
            },
        ):
            client = create_magento_client_from_source("src-magento-1")
        self.assertEqual(client.store_code, "ro_store")
        self.assertEqual(
            client.api_base_url,
            "https://magento.example.com/rest/ro_store/V1",
        )


if __name__ == "__main__":
    unittest.main()
