"""``BigCommerceConnector`` — concrete ``BaseConnector`` that reads products
out of a BigCommerce store via the V3 catalog REST API and yields
normalised :class:`ProductData` rows.

Design
------
* Wraps the :class:`BigCommerceClient` from Task 2 (``X-Auth-Token``
  header, async httpx, V3+V2 URL builder, built-in pagination, rate-limit
  throttling). The credentials (a single per-store ``access_token``) are
  passed in via the ``credentials`` kwarg on the base class —
  ``feed_sync_service._get_connector`` is responsible for loading them
  out of ``integration_secrets`` and handing them in.
* ``fetch_products`` is an async generator. The existing
  ``FeedSyncService.run_sync`` pipeline batches the yielded rows into
  ``FeedProductsRepository.upsert_products_batch``, so the connector
  never talks to MongoDB directly.
* Pagination is page-based via BigCommerce's ``?page=N&limit=L`` API.
  We start at ``page=1, limit=250`` and stop when the response stops
  reporting a next page. The client's transparent rate-limit
  back-off automatically pauses long catalog scans.
* Categories + brands are fetched **once** at the start of every sync
  via paginated ``GET /v3/catalog/categories`` + ``GET /v3/catalog/brands``
  and cached as ``{id: name}`` maps so each per-product lookup is O(1)
  with no extra HTTP round-trip.
* Variants and images come back inline on the product list response when
  we ask for ``?include=variants,images,custom_fields`` — that's the
  major call-savings vs. Magento (no per-product follow-up requests).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, AsyncIterator

from app.integrations.bigcommerce import config as bc_config
from app.integrations.bigcommerce.client import (
    DEFAULT_API_VERSION,
    DEFAULT_PAGE_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    BigCommerceClient,
)
from app.integrations.bigcommerce.exceptions import (
    BigCommerceAPIError,
    BigCommerceAuthError,
    BigCommerceConnectionError,
    BigCommerceNotFoundError,
)
from app.integrations.bigcommerce.normalizer import normalize_bigcommerce_product
from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ValidationResult,
)


logger = logging.getLogger(__name__)


DEFAULT_PAGE_SIZE = DEFAULT_PAGE_LIMIT  # 250
MAX_PAGE_SIZE = DEFAULT_PAGE_LIMIT
DEFAULT_CURRENCY_FALLBACK = "USD"

PRODUCT_INCLUDE_PARAM = "variants,images,custom_fields"


class BigCommerceConnector(BaseConnector):
    """BigCommerce V3 catalog connector — paginates ``/catalog/products``,
    resolves categories + brands once per run, and yields normalised
    :class:`ProductData`.
    """

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
        *,
        client: BigCommerceClient | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        super().__init__(config, credentials)

        # ``store_hash`` may live either on the source's
        # ``bigcommerce_store_hash`` column (preferred) or — for backwards
        # compat with the wizard's free-form config — on the JSON config
        # blob's ``store_hash`` / ``store_url`` keys.
        raw_store_hash = str(
            config.get("bigcommerce_store_hash")
            or config.get("store_hash")
            or _extract_hash_from_store_url(config.get("store_url"))
            or ""
        ).strip().lower()
        self._store_hash: str = raw_store_hash

        self._page_size = min(max(int(page_size or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)

        # Mutable state populated on first run.
        self._store_domain: str = str(config.get("store_domain") or "")
        self._currency: str = str(config.get("currency") or "")
        self._categories_cache: dict[int, str] | None = None
        self._brands_cache: dict[int, str] | None = None
        self._client: BigCommerceClient | None = client

    # ------------------------------------------------------------------ utils

    def _build_client(self) -> BigCommerceClient:
        if self._client is not None:
            return self._client
        creds = self.credentials or {}
        access_token = creds.get("access_token", "")
        if not access_token:
            raise BigCommerceAuthError(
                "BigCommerce connector requires an access_token credential",
                status_code=None,
            )
        self._client = BigCommerceClient(
            store_hash=self._store_hash,
            access_token=access_token,
            api_version=DEFAULT_API_VERSION,
            timeout_seconds=float(
                self.config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS
            ),
        )
        return self._client

    # -------------------------------------------------------- abstract impls

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        if not self._store_hash:
            errors.append("bigcommerce_store_hash is required")
        else:
            try:
                self._store_hash = bc_config.validate_store_hash(self._store_hash)
            except ValueError as exc:
                errors.append(str(exc))

        access_token = (self.credentials or {}).get("access_token")
        if not access_token:
            errors.append("Missing BigCommerce access_token credential")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        validation = await self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(
                success=False,
                message="Invalid BigCommerce config",
                details={"errors": validation.errors},
            )
        try:
            client = self._build_client()
        except (ValueError, BigCommerceAuthError) as exc:
            return ConnectionTestResult(success=False, message=str(exc))

        try:
            data = await client.get("store", api_version="v2")
        except BigCommerceAuthError as exc:
            return ConnectionTestResult(
                success=False, message=f"Invalid credentials: {exc.message}"
            )
        except BigCommerceConnectionError as exc:
            return ConnectionTestResult(
                success=False, message=f"Connection failed: {exc.message}"
            )
        except BigCommerceAPIError as exc:
            return ConnectionTestResult(
                success=False, message=f"BigCommerce API error: {exc.message}"
            )

        if isinstance(data, dict):
            store_name = str(data.get("name") or "")
            currency = str(data.get("currency") or "")
            domain = str(data.get("domain") or data.get("secure_url") or "")
            # Cache for downstream fetch_products so we don't re-fetch.
            if currency and not self._currency:
                self._currency = currency
            if domain and not self._store_domain:
                self._store_domain = domain
            return ConnectionTestResult(
                success=True,
                message="Connected to BigCommerce",
                details={
                    "store_name": store_name,
                    "currency": currency,
                    "domain": domain,
                    "store_hash": self._store_hash,
                },
            )
        return ConnectionTestResult(
            success=False,
            message="BigCommerce returned an unexpected /v2/store payload",
        )

    async def get_product_count(self) -> int:
        client = self._build_client()
        try:
            response = await client.get(
                "catalog/products",
                params={"limit": 1, "page": 1, "is_visible": "true"},
            )
        except BigCommerceAPIError as exc:
            logger.warning("bigcommerce_product_count_failed err=%s", exc)
            return 0
        if not isinstance(response, dict):
            return 0
        meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
        pagination = (
            meta.get("pagination")
            if isinstance(meta.get("pagination"), dict)
            else {}
        )
        try:
            return int(pagination.get("total") or 0)
        except (TypeError, ValueError):
            return 0

    async def fetch_products(
        self, since: datetime | None = None
    ) -> AsyncIterator[ProductData]:
        """Async generator yielding one :class:`ProductData` per BC product.

        Variants come back inline on the list response (we pass
        ``include=variants,images,custom_fields``) so the per-product cost
        is exactly one HTTP request per page of 250 — a fraction of the
        Magento workload.
        """
        validation = await self.validate_config()
        if not validation.valid:
            raise ValueError(
                "BigCommerce connector config is invalid: "
                + "; ".join(validation.errors)
            )

        client = self._build_client()
        await self._bootstrap(client)

        assert self._currency, "bootstrap should have resolved currency"
        assert self._categories_cache is not None, (
            "bootstrap should have resolved categories"
        )
        assert self._brands_cache is not None, (
            "bootstrap should have resolved brands"
        )

        current_page = 1
        while True:
            params: dict[str, Any] = {
                "page": current_page,
                "limit": self._page_size,
                "include": PRODUCT_INCLUDE_PARAM,
                "is_visible": "true",
                "availability": "available",
            }
            if since is not None:
                # BigCommerce expects ``date_modified:min`` in URL-encoded
                # ISO-8601 form. The client uses urlencode under the hood.
                params["date_modified:min"] = since.strftime("%Y-%m-%dT%H:%M:%S")

            logger.info(
                "bigcommerce_fetch_products_page page=%d page_size=%d store_hash=%s",
                current_page,
                self._page_size,
                self._store_hash,
            )
            try:
                response = await client.get("catalog/products", params=params)
            except BigCommerceAPIError as exc:
                logger.warning(
                    "bigcommerce_fetch_products_error page=%d err=%s",
                    current_page,
                    exc,
                )
                raise

            if not isinstance(response, dict):
                break
            items = response.get("data") or []
            if not isinstance(items, list):
                break

            for raw_product in items:
                if not isinstance(raw_product, dict):
                    continue
                product = self._normalize(raw_product)
                if product is not None:
                    yield product

            meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
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
                response_current_page = int(
                    pagination.get("current_page") or current_page
                )
            except (TypeError, ValueError):
                response_current_page = current_page

            if total_pages <= 0 or response_current_page >= total_pages:
                break
            current_page += 1

    # ---------------------------------------------------------- internal api

    async def _bootstrap(self, client: BigCommerceClient) -> None:
        """Resolve store info, categories, and brands (one-shot per sync).

        ``test_connection`` may have already populated ``_currency`` and
        ``_store_domain`` for us — we skip the ``/v2/store`` round-trip in
        that case so smoke-testing the source doesn't double-charge the
        rate-limit budget.
        """
        if not self._currency or not self._store_domain:
            try:
                data = await client.get("store", api_version="v2")
            except BigCommerceAPIError as exc:
                logger.warning(
                    "bigcommerce_bootstrap_store_failed err=%s", exc
                )
                data = None
            if isinstance(data, dict):
                if not self._currency:
                    self._currency = (
                        str(data.get("currency") or "")
                        or DEFAULT_CURRENCY_FALLBACK
                    )
                if not self._store_domain:
                    self._store_domain = str(
                        data.get("domain")
                        or data.get("secure_url")
                        or ""
                    )
            if not self._currency:
                self._currency = DEFAULT_CURRENCY_FALLBACK

        if self._categories_cache is None:
            self._categories_cache = await self._fetch_categories(client)
            logger.info(
                "bigcommerce_categories_cache_loaded size=%d",
                len(self._categories_cache),
            )
        if self._brands_cache is None:
            self._brands_cache = await self._fetch_brands(client)
            logger.info(
                "bigcommerce_brands_cache_loaded size=%d",
                len(self._brands_cache),
            )

    async def _fetch_categories(
        self, client: BigCommerceClient
    ) -> dict[int, str]:
        """Walk every page of ``/v3/catalog/categories`` into ``{id: name}``."""
        try:
            rows = await client.get_all_pages(
                "catalog/categories",
                params={"is_visible": "true"},
                page_size=self._page_size,
            )
        except BigCommerceNotFoundError:
            return {}
        except BigCommerceAPIError as exc:
            logger.warning("bigcommerce_bootstrap_categories_failed err=%s", exc)
            return {}

        out: dict[int, str] = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                cid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            name = str(row.get("name") or "").strip()
            if cid and name:
                out[cid] = name
        return out

    async def _fetch_brands(self, client: BigCommerceClient) -> dict[int, str]:
        """Walk every page of ``/v3/catalog/brands`` into ``{id: name}``."""
        try:
            rows = await client.get_all_pages(
                "catalog/brands",
                page_size=self._page_size,
            )
        except BigCommerceNotFoundError:
            return {}
        except BigCommerceAPIError as exc:
            logger.warning("bigcommerce_bootstrap_brands_failed err=%s", exc)
            return {}

        out: dict[int, str] = {}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                bid = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            name = str(row.get("name") or "").strip()
            if bid and name:
                out[bid] = name
        return out

    def _normalize(self, raw_product: dict[str, Any]) -> ProductData | None:
        try:
            return normalize_bigcommerce_product(
                raw_product,
                store_domain=self._store_domain,
                currency=self._currency,
                categories_map=self._categories_cache or {},
                brands_map=self._brands_cache or {},
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "bigcommerce_normalize_failed product_id=%s",
                raw_product.get("id"),
            )
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_hash_from_store_url(store_url: Any) -> str:
    """Pull a store hash out of a ``stores/<hash>`` config blob.

    The CRUD ``claim`` endpoint stores ``config.store_url = "stores/abc123"``
    on the source row so the BigCommerce store_hash is recoverable from
    the JSON config alone, even if a future migration drops the dedicated
    column. This helper unwraps it.
    """
    if not store_url:
        return ""
    text = str(store_url).strip()
    if not text:
        return ""
    if text.startswith("stores/"):
        return text[len("stores/"):]
    return text
