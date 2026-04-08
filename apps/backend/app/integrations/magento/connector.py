"""``MagentoConnector`` — concrete ``BaseConnector`` that reads products
out of a Magento 2 store via the REST API and yields normalised
:class:`ProductData` rows.

Design
------
* Wraps the :class:`MagentoClient` from Task 2 (OAuth 1.0a signing,
  async httpx). Credentials are passed in via the ``credentials`` kwarg
  on the base class — ``feed_sync_service._get_connector`` is
  responsible for loading them out of ``integration_secrets`` and
  handing them in.
* ``fetch_products`` is an async generator. The existing
  ``FeedSyncService.run_sync`` pipeline batches the yielded rows into
  ``FeedProductsRepository.upsert_products_batch``, so the connector
  never talks to Mongo directly.
* Pagination is page-based per Magento 2's ``searchCriteria[currentPage]``
  + ``searchCriteria[pageSize]`` API. We stop when ``currentPage *
  pageSize >= total_count`` (so a single request is enough when the
  store has fewer than ``pageSize`` products).
* Categories are fetched **once** per sync session via
  ``GET /categories`` and flattened into a ``{id: name}`` map so each
  product lookup is O(1) with no extra HTTP round-trip.
* Configurable products: after fetching each page we collect the
  ``configurable`` SKUs and fire a concurrent batch of
  ``GET /configurable-products/{sku}/children`` calls. The resolved
  children become ``ProductData.variants``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, AsyncIterator

from app.integrations.magento import config as magento_config
from app.integrations.magento.client import (
    DEFAULT_STORE_CODE,
    DEFAULT_TIMEOUT_SECONDS,
    MagentoClient,
)
from app.integrations.magento.exceptions import (
    MagentoAPIError,
    MagentoAuthError,
    MagentoConnectionError,
    MagentoNotFoundError,
    MagentoRateLimitError,
)
from app.integrations.magento.normalizer import (
    build_media_base_url,
    flatten_category_tree,
    normalize_magento_product,
)
from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ValidationResult,
)


logger = logging.getLogger(__name__)


DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 300
DEFAULT_CURRENCY_FALLBACK = "USD"
CONFIGURABLE_CHILDREN_CONCURRENCY = 4


class MagentoConnector(BaseConnector):
    """Magento 2 REST connector — paginates ``/products``, resolves
    categories once per run, and yields normalised :class:`ProductData`.
    """

    def __init__(
        self,
        config: dict[str, Any],
        credentials: dict[str, str] | None = None,
        *,
        client: MagentoClient | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        super().__init__(config, credentials)

        raw_base_url = str(config.get("magento_base_url") or config.get("store_url") or "").strip()
        self._store_code = str(
            config.get("magento_store_code") or DEFAULT_STORE_CODE
        )
        self._page_size = min(max(int(page_size or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)

        # The configured storefront URL. Normalisation is deferred to the
        # MagentoClient constructor which raises ValueError for bad inputs;
        # validate_config() surfaces any issue as a ValidationResult instead
        # of blowing up the __init__.
        self._storefront_base_url: str = raw_base_url
        self._media_base_url: str = ""  # populated on first run
        self._currency: str = str(config.get("currency") or "")
        self._category_cache: dict[str, str] | None = None
        self._client: MagentoClient | None = client

    # ------------------------------------------------------------------ utils

    def _build_client(self) -> MagentoClient:
        if self._client is not None:
            return self._client
        creds = self.credentials or {}
        self._client = MagentoClient(
            base_url=self._storefront_base_url,
            store_code=self._store_code,
            consumer_key=creds.get("consumer_key", ""),
            consumer_secret=creds.get("consumer_secret", ""),
            access_token=creds.get("access_token", ""),
            access_token_secret=creds.get("access_token_secret", ""),
            timeout_seconds=float(self.config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
        )
        return self._client

    # -------------------------------------------------------- abstract impls

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        if not self._storefront_base_url:
            errors.append("magento_base_url is required")
        else:
            try:
                self._storefront_base_url = magento_config.validate_magento_base_url(
                    self._storefront_base_url
                )
            except ValueError as exc:
                errors.append(str(exc))
        try:
            self._store_code = magento_config.validate_magento_store_code(self._store_code)
        except ValueError as exc:
            errors.append(str(exc))

        required = ("consumer_key", "consumer_secret", "access_token", "access_token_secret")
        missing = [k for k in required if not (self.credentials or {}).get(k)]
        if missing:
            errors.append(
                "Missing Magento OAuth 1.0a credentials: " + ", ".join(missing)
            )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        validation = await self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(
                success=False,
                message="Invalid Magento config",
                details={"errors": validation.errors},
            )
        try:
            client = self._build_client()
        except ValueError as exc:
            return ConnectionTestResult(success=False, message=str(exc))

        try:
            data = await client.get("store/storeConfigs")
        except MagentoAuthError as exc:
            return ConnectionTestResult(
                success=False, message=f"Invalid credentials: {exc.message}"
            )
        except MagentoConnectionError as exc:
            return ConnectionTestResult(
                success=False, message=f"Connection failed: {exc.message}"
            )
        except MagentoAPIError as exc:
            return ConnectionTestResult(
                success=False, message=f"Magento API error: {exc.message}"
            )

        if isinstance(data, list) and data:
            first = data[0] if isinstance(data[0], dict) else {}
            store_name = str(first.get("name") or first.get("code") or "")
            currency = str(
                first.get("base_currency_code")
                or first.get("default_display_currency_code")
                or ""
            )
            if currency and not self._currency:
                self._currency = currency
            return ConnectionTestResult(
                success=True,
                message="Connected to Magento",
                details={
                    "store_name": store_name,
                    "base_currency": currency,
                    "store_code": self._store_code,
                },
            )
        return ConnectionTestResult(
            success=False,
            message="Magento returned an unexpected /store/storeConfigs payload",
        )

    async def get_product_count(self) -> int:
        client = self._build_client()
        try:
            response = await client.get(
                "products",
                params=_build_product_search_params(
                    current_page=1, page_size=1, since=None
                ),
            )
        except MagentoAPIError as exc:
            logger.warning("magento_product_count_failed err=%s", exc)
            return 0
        if not isinstance(response, dict):
            return 0
        return int(response.get("total_count") or 0)

    async def fetch_products(
        self, since: datetime | None = None
    ) -> AsyncIterator[ProductData]:
        """Async generator yielding one :class:`ProductData` per product
        (configurable parents are expanded with their children as variants).
        """
        validation = await self.validate_config()
        if not validation.valid:
            raise ValueError(
                "Magento connector config is invalid: " + "; ".join(validation.errors)
            )

        client = self._build_client()
        await self._bootstrap(client)

        assert self._currency, "bootstrap should have resolved currency"
        assert self._category_cache is not None, "bootstrap should have resolved categories"

        current_page = 1
        seen = 0
        while True:
            logger.info(
                "magento_fetch_products_page page=%d page_size=%d store_code=%s",
                current_page,
                self._page_size,
                self._store_code,
            )
            try:
                response = await client.get(
                    "products",
                    params=_build_product_search_params(
                        current_page=current_page,
                        page_size=self._page_size,
                        since=since,
                    ),
                )
            except (MagentoConnectionError, MagentoRateLimitError) as exc:
                logger.warning(
                    "magento_fetch_products_retryable_error page=%d err=%s",
                    current_page,
                    exc,
                )
                raise

            if not isinstance(response, dict):
                break
            items = response.get("items") or []
            if not isinstance(items, list):
                break

            total_count = int(response.get("total_count") or 0)

            # Pre-fetch configurable children for this page in one batch so
            # downstream yielding is O(1) per product.
            children_by_sku = await self._fetch_configurable_children(client, items)

            for raw_product in items:
                if not isinstance(raw_product, dict):
                    continue
                product = self._normalize(raw_product, children_by_sku)
                if product is not None:
                    yield product
                seen += 1

            if len(items) < self._page_size:
                break
            if total_count and seen >= total_count:
                break
            current_page += 1

    # ---------------------------------------------------------- internal api

    async def _bootstrap(self, client: MagentoClient) -> None:
        """Resolve currency + media base URL + category map (one-shot)."""
        # Resolve currency + media base via /store/storeConfigs (same call as
        # test_connection). Cheap, universally available.
        if not self._currency or not self._media_base_url:
            try:
                data = await client.get("store/storeConfigs")
            except MagentoAPIError as exc:
                logger.warning(
                    "magento_bootstrap_store_configs_failed err=%s", exc
                )
                data = None
            if isinstance(data, list) and data and isinstance(data[0], dict):
                first = data[0]
                if not self._currency:
                    self._currency = str(
                        first.get("base_currency_code")
                        or first.get("default_display_currency_code")
                        or DEFAULT_CURRENCY_FALLBACK
                    )
                base_media_url = str(first.get("base_media_url") or "").strip()
                if base_media_url:
                    self._media_base_url = base_media_url.rstrip("/") + "/catalog/product"
            if not self._currency:
                self._currency = DEFAULT_CURRENCY_FALLBACK
            if not self._media_base_url:
                # Fall back to the storefront base URL — Magento ships
                # with /media/catalog/product by default.
                self._media_base_url = build_media_base_url(self._storefront_base_url)

        if self._category_cache is None:
            try:
                tree = await client.get("categories")
            except MagentoNotFoundError:
                self._category_cache = {}
            except MagentoAPIError as exc:
                logger.warning("magento_bootstrap_categories_failed err=%s", exc)
                self._category_cache = {}
            else:
                self._category_cache = flatten_category_tree(
                    tree if isinstance(tree, dict) else None
                )
            logger.info(
                "magento_category_cache_loaded size=%d",
                len(self._category_cache or {}),
            )

    async def _fetch_configurable_children(
        self,
        client: MagentoClient,
        items: list[Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """Batch-fetch children for every configurable SKU on this page."""
        configurable_skus = [
            str(p.get("sku") or "")
            for p in items
            if isinstance(p, dict)
            and str(p.get("type_id") or "").lower() == "configurable"
            and p.get("sku")
        ]
        if not configurable_skus:
            return {}

        semaphore = asyncio.Semaphore(CONFIGURABLE_CHILDREN_CONCURRENCY)

        async def _fetch(sku: str) -> tuple[str, list[dict[str, Any]]]:
            async with semaphore:
                try:
                    data = await client.get(f"configurable-products/{sku}/children")
                except MagentoNotFoundError:
                    return sku, []
                except MagentoAPIError as exc:
                    logger.warning(
                        "magento_children_fetch_failed sku=%s err=%s", sku, exc
                    )
                    return sku, []
            if isinstance(data, list):
                return sku, [c for c in data if isinstance(c, dict)]
            return sku, []

        results = await asyncio.gather(*[_fetch(sku) for sku in configurable_skus])
        return dict(results)

    def _normalize(
        self,
        raw_product: dict[str, Any],
        children_by_sku: dict[str, list[dict[str, Any]]],
    ) -> ProductData | None:
        try:
            children = None
            if str(raw_product.get("type_id") or "").lower() == "configurable":
                children = children_by_sku.get(str(raw_product.get("sku") or ""))
            return normalize_magento_product(
                raw_product,
                storefront_base_url=self._storefront_base_url,
                currency=self._currency,
                categories_map=self._category_cache or {},
                media_base_url=self._media_base_url,
                children=children,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "magento_normalize_failed sku=%s", raw_product.get("sku")
            )
            return None


# ---------------------------------------------------------------------------
# searchCriteria builder
# ---------------------------------------------------------------------------


def _build_product_search_params(
    *,
    current_page: int,
    page_size: int,
    since: datetime | None,
) -> dict[str, str]:
    """Construct the ``searchCriteria`` query params for ``GET /products``.

    Applies three standing filters:

    * ``status = 1``      (enabled)
    * ``visibility IN (2, 3, 4)``  (catalog, search, both)
    * ``updated_at >= since``  (only when ``since`` is provided)

    Multiple filters in the same ``filter_groups`` entry are OR'ed together
    by Magento; separate groups are AND'ed. We use one group per constraint
    so the combined predicate is ``status AND visibility [AND updated_at]``.
    """
    params: dict[str, str] = {
        "searchCriteria[currentPage]": str(current_page),
        "searchCriteria[pageSize]": str(page_size),
        "searchCriteria[sortOrders][0][field]": "entity_id",
        "searchCriteria[sortOrders][0][direction]": "ASC",
        # status = 1
        "searchCriteria[filter_groups][0][filters][0][field]": "status",
        "searchCriteria[filter_groups][0][filters][0][value]": "1",
        "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
        # visibility IN (2, 3, 4)
        "searchCriteria[filter_groups][1][filters][0][field]": "visibility",
        "searchCriteria[filter_groups][1][filters][0][value]": "2,3,4",
        "searchCriteria[filter_groups][1][filters][0][condition_type]": "in",
    }
    if since is not None:
        params["searchCriteria[filter_groups][2][filters][0][field]"] = "updated_at"
        params["searchCriteria[filter_groups][2][filters][0][value]"] = since.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        params["searchCriteria[filter_groups][2][filters][0][condition_type]"] = "gteq"
    return params
