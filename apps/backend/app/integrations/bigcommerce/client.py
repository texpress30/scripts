"""Async HTTP client for the BigCommerce Store REST API.

Design notes
------------
* **One ``httpx.AsyncClient`` per request** — same pattern as the Magento
  and WooCommerce connectors. Keeps the client stateless, releases sockets
  on crash and lets tests monkey-patch ``httpx.AsyncClient`` without
  managing a long-lived instance.
* **Per-store credentials live in memory only for the lifetime of a single
  client instance.** Callers should instantiate via the factories
  :func:`create_bc_client_from_store_hash` (load from
  ``integration_secrets_store``) or :func:`create_bc_client_from_source`
  (resolve via ``feed_sources.bigcommerce_store_hash`` first).
* **Auth = ``X-Auth-Token`` header.** BigCommerce OAuth tokens never expire,
  so there is no refresh logic — a 401 means the merchant uninstalled or
  rotated the app and the caller should surface a reconnect prompt.
* **URL builder supports both V3 and V2.** V3 is the modern catalog API
  (used everywhere); V2 still hosts a handful of endpoints (notably
  ``/v2/store`` for the test-connection probe).
* **Built-in pagination via :py:meth:`get_all_pages`** — iterates
  ``?page=N&limit=250`` until ``meta.pagination.total_pages`` is exhausted.
* **Rate-limit handling.** BigCommerce caps V3 to 150 req / 30s per store
  and surfaces the budget via the ``X-Rate-Limit-Requests-Left`` and
  ``X-Rate-Limit-Time-Reset-Ms`` headers. We back off automatically when
  fewer than 5 requests remain, and we transparently retry once on a 429.
* **Exceptions are classified**: 401/403 → :class:`BigCommerceAuthError`,
  404 → :class:`BigCommerceNotFoundError`, 429 → :class:`BigCommerceRateLimitError`,
  5xx → :class:`BigCommerceServerError`, transport errors →
  :class:`BigCommerceConnectionError`, anything else (malformed JSON,
  unexpected 4xx) → :class:`BigCommerceAPIError`.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
from typing import Any

import httpx

from app.integrations.bigcommerce import config as bc_config
from app.integrations.bigcommerce import service as bc_service
from app.integrations.bigcommerce.exceptions import (
    BigCommerceAPIError,
    BigCommerceAuthError,
    BigCommerceConnectionError,
    BigCommerceNotFoundError,
    BigCommerceRateLimitError,
    BigCommerceServerError,
)


logger = logging.getLogger(__name__)


DEFAULT_TIMEOUT_SECONDS: float = 30.0
TEST_CONNECTION_TIMEOUT_SECONDS: float = 12.0
DEFAULT_USER_AGENT: str = "OmarosaAgency/1.0 (+https://admin.omarosa.ro)"

DEFAULT_API_VERSION: str = "v3"
SUPPORTED_API_VERSIONS: tuple[str, ...] = ("v2", "v3")
DEFAULT_PAGE_LIMIT: int = 250
MAX_PAGE_LIMIT: int = 250

# Headers BigCommerce sets to advertise the rate-limit budget.
HEADER_RATE_LIMIT_LEFT: str = "X-Rate-Limit-Requests-Left"
HEADER_RATE_LIMIT_RESET_MS: str = "X-Rate-Limit-Time-Reset-Ms"
RATE_LIMIT_LOW_WATER_MARK: int = 5
RATE_LIMIT_FALLBACK_SLEEP_SECONDS: float = 1.0


def _mask_token(token: str | None) -> str:
    if not token:
        return ""
    value = str(token)
    if len(value) <= 8:
        return "***"
    return f"{value[:6]}***"


class BigCommerceClient:
    """Async HTTP client for the BigCommerce REST API.

    Parameters
    ----------
    store_hash:
        BigCommerce store hash (e.g. ``"abc123"``). Validated by
        :func:`bc_config.validate_store_hash` at init time.
    access_token:
        Permanent OAuth 2.0 token. BigCommerce tokens don't expire, so the
        client never refreshes — a 401 always means the merchant
        uninstalled / rotated the app and the caller must reconnect.
    api_version:
        ``"v3"`` (default) or ``"v2"``. Some store-info endpoints still
        live under ``/v2/store``; everything else (catalog, customers,
        orders) is on V3. The version can also be overridden per request
        via the ``api_version=`` keyword on :py:meth:`get` / :py:meth:`post`
        / etc.
    timeout_seconds:
        Per-request timeout (connect + read). Defaults to 30s; 12s for
        the snappy test-connection probe.
    user_agent:
        Identifiable User-Agent header sent on every request.
    """

    def __init__(
        self,
        *,
        store_hash: str,
        access_token: str,
        api_version: str = DEFAULT_API_VERSION,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        if api_version not in SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported BigCommerce API version: {api_version!r} "
                f"(expected one of {SUPPORTED_API_VERSIONS})"
            )

        self._store_hash = bc_config.validate_store_hash(store_hash)
        self._access_token = access_token
        self._api_version = api_version
        self._timeout = float(timeout_seconds)
        self._user_agent = user_agent

    # ------------------------------------------------------------------ url

    @property
    def store_hash(self) -> str:
        return self._store_hash

    @property
    def api_version(self) -> str:
        return self._api_version

    def _api_base(self, api_version: str | None = None) -> str:
        version = api_version or self._api_version
        if version not in SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported BigCommerce API version: {version!r}"
            )
        return f"{bc_config.BC_API_URL}/stores/{self._store_hash}/{version}"

    def build_url(
        self,
        endpoint: str,
        *,
        api_version: str | None = None,
    ) -> str:
        """Join ``endpoint`` onto the versioned store API base URL.

        Leading slashes on ``endpoint`` are tolerated so callers can use
        either ``"catalog/products"`` or ``"/catalog/products"``.
        """
        path = str(endpoint or "").lstrip("/")
        base = self._api_base(api_version)
        if not path:
            return base
        return f"{base}/{path}"

    # ------------------------------------------------------------------ core

    def _build_headers(self, *, has_body: bool) -> dict[str, str]:
        headers: dict[str, str] = {
            "X-Auth-Token": self._access_token,
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    async def _maybe_throttle(self, response: httpx.Response) -> None:
        """Sleep when BigCommerce reports the budget is nearly exhausted.

        BigCommerce surfaces remaining requests via ``X-Rate-Limit-Requests-Left``
        and the time until the window resets via ``X-Rate-Limit-Time-Reset-Ms``.
        We back off when fewer than ``RATE_LIMIT_LOW_WATER_MARK`` requests
        remain so the *next* call doesn't hit a 429.
        """
        try:
            left_header = response.headers.get(HEADER_RATE_LIMIT_LEFT)
            if left_header is None:
                return
            requests_left = int(left_header)
        except (TypeError, ValueError):
            return

        if requests_left > RATE_LIMIT_LOW_WATER_MARK:
            return

        try:
            reset_ms = int(response.headers.get(HEADER_RATE_LIMIT_RESET_MS) or 0)
        except (TypeError, ValueError):
            reset_ms = 0
        sleep_seconds = max(reset_ms / 1000.0, RATE_LIMIT_FALLBACK_SLEEP_SECONDS)
        logger.info(
            "bigcommerce_client_throttle store_hash=%s requests_left=%d sleep_s=%.2f",
            self._store_hash,
            requests_left,
            sleep_seconds,
        )
        await asyncio.sleep(sleep_seconds)

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        api_version: str | None = None,
        _retried_after_429: bool = False,
    ) -> Any:
        url = self.build_url(endpoint, api_version=api_version)
        headers = self._build_headers(has_body=json_body is not None)

        # Stringify query params so httpx doesn't trip on bool/int.
        string_params: dict[str, str] = {}
        if params:
            for key, value in params.items():
                if value is None:
                    continue
                string_params[str(key)] = str(value)

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
                "bigcommerce_client_connect_error url=%s store_hash=%s err=%s",
                url,
                self._store_hash,
                exc,
            )
            raise BigCommerceConnectionError(
                f"Cannot reach BigCommerce at {url}"
            ) from exc
        except httpx.ReadTimeout as exc:
            logger.warning(
                "bigcommerce_client_read_timeout url=%s store_hash=%s",
                url,
                self._store_hash,
            )
            raise BigCommerceConnectionError(
                f"BigCommerce read timeout at {url}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "bigcommerce_client_transport_error url=%s store_hash=%s err=%s",
                url,
                self._store_hash,
                exc,
            )
            raise BigCommerceConnectionError(f"HTTP transport error: {exc}") from exc

        # Honour the rate-limit budget BEFORE classifying the status so a
        # successful 200 still parks us when the window is almost spent.
        await self._maybe_throttle(response)

        # Transparent single retry on 429 — give BigCommerce the time it
        # advertised, then re-issue the same request.
        if response.status_code == 429 and not _retried_after_429:
            try:
                reset_ms = int(response.headers.get(HEADER_RATE_LIMIT_RESET_MS) or 0)
            except (TypeError, ValueError):
                reset_ms = 0
            sleep_seconds = max(
                reset_ms / 1000.0, RATE_LIMIT_FALLBACK_SLEEP_SECONDS
            )
            logger.info(
                "bigcommerce_client_429_retry store_hash=%s sleep_s=%.2f",
                self._store_hash,
                sleep_seconds,
            )
            await asyncio.sleep(sleep_seconds)
            return await self._request(
                method,
                endpoint,
                params=params,
                json_body=json_body,
                api_version=api_version,
                _retried_after_429=True,
            )

        self._raise_for_status(response)

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except (_json.JSONDecodeError, ValueError) as exc:
            raise BigCommerceAPIError(
                "BigCommerce returned a non-JSON response",
                status_code=response.status_code,
                body=response.text[:500],
            ) from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        status_code = response.status_code
        if 200 <= status_code < 300:
            return

        body = response.text[:500] if response.text else None

        if status_code == 401:
            raise BigCommerceAuthError(
                "Unauthorized — invalid or revoked BigCommerce access token",
                status_code=status_code,
                body=body,
            )
        if status_code == 403:
            raise BigCommerceAuthError(
                "Forbidden — BigCommerce app lacks the required scope",
                status_code=status_code,
                body=body,
            )
        if status_code == 404:
            raise BigCommerceNotFoundError(
                f"BigCommerce resource not found: {response.url}",
                status_code=status_code,
                body=body,
            )
        if status_code == 429:
            raise BigCommerceRateLimitError(
                "BigCommerce rate limit exceeded — back off and retry later",
                status_code=status_code,
                body=body,
            )
        if 500 <= status_code < 600:
            raise BigCommerceServerError(
                f"BigCommerce server error: HTTP {status_code}",
                status_code=status_code,
                body=body,
            )
        raise BigCommerceAPIError(
            f"BigCommerce API returned HTTP {status_code}",
            status_code=status_code,
            body=body,
        )

    # ------------------------------------------------------------------ verbs

    async def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        api_version: str | None = None,
    ) -> Any:
        return await self._request(
            "GET", endpoint, params=params, api_version=api_version
        )

    async def post(
        self,
        endpoint: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        api_version: str | None = None,
    ) -> Any:
        return await self._request(
            "POST",
            endpoint,
            params=params,
            json_body=json_body,
            api_version=api_version,
        )

    async def put(
        self,
        endpoint: str,
        *,
        json_body: Any | None = None,
        params: dict[str, Any] | None = None,
        api_version: str | None = None,
    ) -> Any:
        return await self._request(
            "PUT",
            endpoint,
            params=params,
            json_body=json_body,
            api_version=api_version,
        )

    async def delete(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        api_version: str | None = None,
    ) -> Any:
        return await self._request(
            "DELETE",
            endpoint,
            params=params,
            api_version=api_version,
        )

    # ------------------------------------------------------------------ pagination

    async def get_all_pages(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        page_size: int = DEFAULT_PAGE_LIMIT,
        api_version: str | None = None,
    ) -> list[Any]:
        """Fetch every page of a paginated V3 endpoint and return the merged data.

        BigCommerce V3 list endpoints accept ``?page=N&limit=L`` and return
        a body of the shape::

            {
              "data": [...],
              "meta": {
                "pagination": {
                  "total_pages": 7,
                  "current_page": 1,
                  ...
                }
              }
            }

        We start at page 1 and walk forward until ``current_page >=
        total_pages`` (or the response stops including a pagination block).
        Each call goes through the rate-limit aware ``_request`` so a long
        scan automatically pauses when the merchant's budget is nearly
        exhausted.
        """
        if page_size <= 0 or page_size > MAX_PAGE_LIMIT:
            raise ValueError(
                f"page_size must be in (0, {MAX_PAGE_LIMIT}]; got {page_size}"
            )

        merged: list[Any] = []
        current_page = 1
        total_pages = 1

        while True:
            page_params: dict[str, Any] = dict(params or {})
            page_params["page"] = current_page
            page_params["limit"] = page_size

            payload = await self.get(
                endpoint, params=page_params, api_version=api_version
            )
            if not isinstance(payload, dict):
                # Non-paginated endpoints just return a list — fall back to
                # appending whatever we got and stop.
                if isinstance(payload, list):
                    merged.extend(payload)
                return merged

            data = payload.get("data")
            if isinstance(data, list):
                merged.extend(data)

            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            pagination = (
                meta.get("pagination")
                if isinstance(meta.get("pagination"), dict)
                else {}
            )
            try:
                total_pages = int(pagination.get("total_pages") or 0)
            except (TypeError, ValueError):
                total_pages = 0
            try:
                current_page = int(pagination.get("current_page") or current_page)
            except (TypeError, ValueError):
                pass

            if total_pages <= 0 or current_page >= total_pages:
                return merged
            current_page += 1


# ---------------------------------------------------------------------------
# Factories — load credentials from secrets store / feed_sources row
# ---------------------------------------------------------------------------


def create_bc_client_from_store_hash(
    store_hash: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_version: str = DEFAULT_API_VERSION,
) -> BigCommerceClient:
    """Hydrate a :class:`BigCommerceClient` directly from the secrets store.

    Looks up the per-store credential bag (encrypted Fernet) by
    ``store_hash`` and returns a ready-to-use client. Raises
    :class:`BigCommerceAuthError` when no credentials are stored — the
    caller can then surface a "this store hasn't installed the app yet"
    error.
    """
    creds = bc_service.get_bigcommerce_credentials(store_hash)
    if creds is None or not creds.get("access_token"):
        raise BigCommerceAuthError(
            f"No BigCommerce credentials stored for store_hash={store_hash!r}",
            status_code=None,
        )
    return BigCommerceClient(
        store_hash=store_hash,
        access_token=creds["access_token"],
        api_version=api_version,
        timeout_seconds=timeout_seconds,
    )


def create_bc_client_from_source(
    source_id: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    api_version: str = DEFAULT_API_VERSION,
) -> BigCommerceClient:
    """Hydrate a :class:`BigCommerceClient` from a ``feed_sources`` row id.

    Loads the row from PostgreSQL, verifies it is a BigCommerce source
    with a ``bigcommerce_store_hash`` set, and delegates to
    :func:`create_bc_client_from_store_hash`. Raises ``ValueError`` for
    schema mismatches and :class:`BigCommerceAuthError` when credentials
    are missing.
    """
    from app.services.feed_management.models import FeedSourceType
    from app.services.feed_management.repository import FeedSourceRepository

    repo = FeedSourceRepository()
    source = repo.get_by_id(source_id)
    if source.source_type != FeedSourceType.bigcommerce:
        raise ValueError(
            f"Source {source_id} is not a BigCommerce source "
            f"(got {source.source_type.value!r})"
        )
    if not source.bigcommerce_store_hash:
        raise ValueError(
            f"Source {source_id} has no bigcommerce_store_hash configured"
        )

    return create_bc_client_from_store_hash(
        source.bigcommerce_store_hash,
        timeout_seconds=timeout_seconds,
        api_version=api_version,
    )
