from app.services.feed_management.connectors.base import BaseConnector, ConnectionTestResult, ProductData, ProductVariant, ValidationResult
from app.services.feed_management.connectors.shopify_connector import ShopifyConnector
from app.services.feed_management.connectors.woocommerce_connector import WooCommerceConnector

__all__ = [
    "BaseConnector",
    "ConnectionTestResult",
    "ProductData",
    "ProductVariant",
    "ShopifyConnector",
    "ValidationResult",
    "WooCommerceConnector",
]
