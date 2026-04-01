"""Shopify connector skeleton.

TODO: Implement full Shopify Admin API integration in a future task.
- Use Shopify Admin REST API or GraphQL Admin API
- Endpoint: GET /admin/api/{api_version}/products.json
- Pagination via Link headers or GraphQL cursor
- Rate limiting: 2 requests/second for REST, cost-based for GraphQL
- Requires: shop URL, API key, API secret key (stored in integration_secrets)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncIterator

from app.services.feed_management.connectors.base import (
    BaseConnector,
    ConnectionTestResult,
    ProductData,
    ValidationResult,
)


class ShopifyConnector(BaseConnector):
    """Connector for Shopify stores via Admin API.

    This is a skeleton implementation. The actual API calls will be
    implemented in a dedicated task once the base infrastructure is
    validated end-to-end.
    """

    async def validate_config(self) -> ValidationResult:
        errors: list[str] = []
        if not self.config.get("store_url"):
            errors.append("store_url is required (e.g. myshop.myshopify.com)")
        if not self.credentials.get("api_key"):
            errors.append("api_key credential is required")
        if not self.credentials.get("api_secret_key"):
            errors.append("api_secret_key credential is required")
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def test_connection(self) -> ConnectionTestResult:
        """Placeholder: returns success without actually connecting.

        TODO: Implement real connection test via GET /admin/api/{version}/shop.json
        """
        validation = await self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(success=False, message="Invalid config", details={"errors": validation.errors})
        return ConnectionTestResult(
            success=True,
            message="Shopify connector config is valid (connection test not yet implemented)",
            details={"store_url": self.config.get("store_url")},
        )

    async def fetch_products(self, since: datetime | None = None) -> AsyncIterator[ProductData]:
        """Not yet implemented.

        TODO: Implement via Shopify Admin API
        - GET /admin/api/{version}/products.json?updated_at_min={since}
        - Handle pagination via Link headers
        - Map Shopify product JSON to ProductData
        """
        raise NotImplementedError(
            "Shopify product fetching is not yet implemented. "
            "This connector skeleton will be completed in the Shopify integration task."
        )
        # Make this an async generator so the type signature is correct
        yield  # pragma: no cover

    async def get_product_count(self) -> int:
        """Not yet implemented.

        TODO: Implement via GET /admin/api/{version}/products/count.json
        """
        raise NotImplementedError(
            "Shopify product count is not yet implemented. "
            "This connector skeleton will be completed in the Shopify integration task."
        )
