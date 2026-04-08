"""Async HTTP client for the Magento 2 REST API with automatic
OAuth 1.0a request signing.

Design notes
------------
* **One httpx.AsyncClient per request.** The existing WooCommerce
  connector follows the same pattern (``async with httpx.AsyncClient`` inside
  each call). It keeps the connector stateless, avoids leaking connections
  on crash, and lets tests monkey-patch ``httpx.AsyncClient`` without
  having to manage a long-lived instance.
* **Credentials live in memory only for the lifetime of a single client
  instance.** Callers should instantiate :class:`MagentoClient` via
  :func:`create_magento_client_from_source` which loads them from
  ``integration_secrets_store`` on demand.
* **Signing is JSON-body-safe**: the OAuth 1.0a signature only covers
  the HTTP method, the canonicalised URL and the query string — never the
  JSON request body. This matches the Magento 2 REST convention.
* **Exceptions are classified**: 401/403 → :class:`MagentoAuthError`,
  404 → :class:`MagentoNotFoundError`, 429 → :class:`MagentoRateLimitError`,
  transport errors (DNS, TCP, TLS, timeouts) →
  :class:`MagentoConnectionError`, everything else (5xx, unexpected 4xx,
  malformed JSON) → :class:`MagentoAPIError`.
"""

from __future__ import annotations

import json as _json
import logging
from typing import Any

import httpx

from app.integrations.magento import service as magento_service
from app.integrations.magento.config import (
    DEFAULT_STORE_CODE,
    validate_magento_base_url,
    validate_magento_store_code,
)
from app.integrations.magento.exceptions import (
    MagentoAPIError,
    MagentoAuthError,
    MagentoConnectionError,
    MagentoNotFoundError,
    MagentoRateLimitError,
)
from app.integrations.magento.oauth import build_authorization_header


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "OmarosaAgency/1.0 (+https://admin.omarosa.ro)"
REST_PREFIX = "rest"
REST_API_VERSION = "V1"


def _mask(value: str | None) -> str:
    if not value:
        return ""
    v = str(value)
    if len(v) <= 8:
        return "*" * len(v)
    return f"****{v[-4:]}"


class MagentoClient:
    """Async HTTP client that signs every Magento 2 REST call with OAuth 1.0a.

    Parameters
    ----------
    base_url:
        Storefront base URL (``https://store.example.com``). Normalised by
        :func:`validate_magento_base_url` — trailing slash stripped, scheme
        rules enforced.
    store_code:
        Magento store view code. Defaults to ``"default"`` and is validated
        by :func:`validate_magento_store_code`.
    consumer_key / consumer_secret / access_token / access_token_secret:
        The four OAuth 1.0a credentials minted by the merchant in
        ``System → Extensions → Integrations``. Required; empty strings
        raise ``ValueError`` at init time.
    timeout_seconds:
        Per-request timeout (connect + read). Defaults to 30s.
    user_agent:
        Identifiable User-Agent header sent on every request.
    """

    def __init__(
        self,
        *,
        base_url: str,
        store_code: str = DEFAULT_STORE_CODE,
        consumer_key: str,
        consumer_secret: str,
        access_token: str,
        access_token_secret: str,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
            raise ValueError("All four Magento OAuth 1.0a credentials are required")

        self._base_url = validate_magento_base_url(base_url)
        self._store_code = validate_magento_store_code(store_code)
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_token = access_token
        self._access_token_secret = access_token_secret
        self._timeout = float(timeout_seconds)
        self._user_agent = user_agent

    # ------------------------------------------------------------------ URL

    @property
    def base_url(self) -> str:
        """The cleaned storefront base URL (no trailing slash)."""
        return self._base_url

    @property
    def store_code(self) -> str:
        return self._store_code

    @property
    def api_base_url(self) -> str:
        """Versioned REST endpoint — e.g. ``https://store/rest/default/V1``."""
        return f"{self._base_url}/{REST_PREFIX}/{self._store_code}/{REST_API_VERSION}"

    def build_url(self, endpoint: str) -> str:
        """Join ``endpoint`` onto :pyattr:`api_base_url`.

        Leading slashes on ``endpoint`` are tolerated so callers can use
        either ``"products"`` or ``"/products"``.
        """
        path = str(endpoint or "").lstrip("/")
        if not path:
            return self.api_base_url
        return f"{self.api_base_url}/{path}"

    # ------------------------------------------------------------------ auth

    def _build_auth_header(
        self,
        *,
        method: str,
        url: str,
        query_params: dict[str, str] | None,
    ) -> str:
        return build_authorization_header(
            consumer_key=self._consumer_key,
            consumer_secret=self._consumer_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
            http_method=method,
            url=url,
            query_params=query_params,
        )

    # ------------------------------------------------------------------ core

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        url = self.build_url(endpoint)

        # Stringify query params for signing (OAuth 1.0a normalises strings).
        string_params: dict[str, str] = {}
        if params:
            for key, value in params.items():
                string_params[str(key)] = "" if value is None else str(value)

        auth_header = self._build_auth_header(
            method=method,
            url=url,
            query_params=string_params or None,
        )

        headers: dict[str, str] = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    url,
                    params=string_params or None,
                    json=json_body,
                    headers=headers,
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            logger.warning(
                "magento_client_connect_error url=%s consumer_key=%s err=%s",
                url,
                _mask(self._consumer_key),
                exc,
            )
            raise MagentoConnectionError(f"Cannot reach Magento at {url}") from exc
        except httpx.ReadTimeout as exc:
            logger.warning(
                "magento_client_read_timeout url=%s consumer_key=%s",
                url,
                _mask(self._consumer_key),
            )
            raise MagentoConnectionError(f"Magento read timeout at {url}") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "magento_client_transport_error url=%s consumer_key=%s err=%s",
                url,
                _mask(self._consumer_key),
                exc,
            )
            raise MagentoConnectionError(f"HTTP transport error: {exc}") from exc

        self._raise_for_status(response)

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except (_json.JSONDecodeError, ValueError) as exc:
            raise MagentoAPIError(
                "Magento returned a non-JSON response",
                status_code=response.status_code,
                body=response.text[:500],
            ) from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return

        # Truncate the body before it gets into an exception — Magento can echo
        # huge debug traces on 5xx and we never want those in audit logs.
        body = response.text[:500] if response.text else None

        if status in (401,):
            raise MagentoAuthError(
                "Unauthorized — invalid or expired Magento OAuth credentials",
                status_code=status,
                body=body,
            )
        if status == 403:
            raise MagentoAuthError(
                "Forbidden — Magento Integration lacks permission for this resource",
                status_code=status,
                body=body,
            )
        if status == 404:
            raise MagentoNotFoundError(
                f"Magento resource not found: {response.url}",
                status_code=status,
                body=body,
            )
        if status == 429:
            raise MagentoRateLimitError(
                "Magento rate limit exceeded — back off and retry",
                status_code=status,
                body=body,
            )
        raise MagentoAPIError(
            f"Magento API returned HTTP {status}",
            status_code=status,
            body=body,
        )

    # ------------------------------------------------------------------ verbs

    async def get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", endpoint, params=params, json_body=json_body)

    async def put(
        self,
        endpoint: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("PUT", endpoint, params=params, json_body=json_body)

    async def delete(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("DELETE", endpoint, params=params)


# ---------------------------------------------------------------------------
# Factory — load credentials from the secrets store + routing from feed_sources
# ---------------------------------------------------------------------------


def create_magento_client_from_source(
    source_id: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> MagentoClient:
    """Hydrate a :class:`MagentoClient` from a ``feed_sources`` row id.

    Loads the row from PostgreSQL, verifies it is a Magento source with a
    ``magento_base_url``, fetches the four OAuth 1.0a credentials from
    ``integration_secrets_store`` (decrypted on read) and returns a ready-
    to-use client. Raises :class:`MagentoAuthError` when the credentials
    row is missing or partial — the caller can then surface a reconnect
    prompt in the UI.
    """
    from app.services.feed_management.models import FeedSourceType
    from app.services.feed_management.repository import FeedSourceRepository

    repo = FeedSourceRepository()
    source = repo.get_by_id(source_id)
    if source.source_type != FeedSourceType.magento:
        raise ValueError(
            f"Source {source_id} is not a Magento source (got {source.source_type.value!r})"
        )
    if not source.magento_base_url:
        raise ValueError(f"Source {source_id} has no magento_base_url configured")

    credentials = magento_service.get_magento_credentials(source_id)
    if credentials is None:
        raise MagentoAuthError(
            f"No Magento OAuth credentials stored for source {source_id}",
            status_code=None,
        )

    return MagentoClient(
        base_url=source.magento_base_url,
        store_code=source.magento_store_code or DEFAULT_STORE_CODE,
        consumer_key=credentials["consumer_key"],
        consumer_secret=credentials["consumer_secret"],
        access_token=credentials["access_token"],
        access_token_secret=credentials["access_token_secret"],
        timeout_seconds=timeout_seconds,
    )
