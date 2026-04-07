"""Tests for the Shopify-products mapping additions and rate-limit handling.

These cover the new fields surfaced in ``ProductData.raw_data``:
size/color/material/gtin/weight/availability/sale_price/additional_image_links,
plus the leaky-bucket throttle on the HTTP layer.
"""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.feed_management.connectors import shopify_connector
from app.services.feed_management.connectors.shopify_connector import ShopifyConnector


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_PRODUCT_OPTIONS = {
    "id": 5001,
    "title": "Hoodie",
    "body_html": "<p>Cozy</p>",
    "product_type": "Apparel",
    "handle": "hoodie",
    "tags": "winter",
    "vendor": "AcmeBrand",
    "status": "active",
    "images": [
        {"id": 1, "src": "https://cdn.shopify.com/hoodie-1.jpg"},
        {"id": 2, "src": "https://cdn.shopify.com/hoodie-2.jpg"},
        {"id": 3, "src": "https://cdn.shopify.com/hoodie-3.jpg"},
    ],
    "options": [
        {"name": "Size", "position": 1},
        {"name": "Color", "position": 2},
    ],
    "variants": [
        {
            "id": 6001,
            "title": "S / Red",
            "option1": "S",
            "option2": "Red",
            "price": "49.00",
            "compare_at_price": "59.00",
            "sku": "HOOD-S-RED",
            "barcode": "1234567890123",
            "inventory_quantity": 10,
            "inventory_policy": "deny",
            "weight": 0.6,
            "weight_unit": "kg",
        },
        {
            "id": 6002,
            "title": "M / Blue",
            "option1": "M",
            "option2": "Blue",
            "price": "49.00",
            "compare_at_price": None,
            "sku": "HOOD-M-BLUE",
            "barcode": "",
            "inventory_quantity": 0,
            "inventory_policy": "continue",
            "weight": 0.65,
            "weight_unit": "kg",
        },
        {
            "id": 6003,
            "title": "L / Green",
            "option1": "L",
            "option2": "Green",
            "price": "49.00",
            "compare_at_price": "49.00",  # equal to price → not on sale
            "sku": "HOOD-L-GREEN",
            "barcode": "9876543210987",
            "inventory_quantity": 0,
            "inventory_policy": "deny",
            "weight": 0.7,
            "weight_unit": "kg",
        },
    ],
}


class TestExtendedMapping(unittest.TestCase):
    def setUp(self):
        self.connector = ShopifyConnector(
            config={"store_url": "teststore.myshopify.com"},
            credentials={"access_token": "tok"},
        )
        self.connector._shop_currency = "RON"

    def test_three_variants_become_three_rows(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(len(results), 3)

    def test_size_and_color_extracted_from_options(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["size"], "S")
        self.assertEqual(results[0].raw_data["color"], "Red")
        self.assertEqual(results[1].raw_data["size"], "M")
        self.assertEqual(results[1].raw_data["color"], "Blue")
        self.assertEqual(results[2].raw_data["size"], "L")
        self.assertEqual(results[2].raw_data["color"], "Green")

    def test_brand_and_link_in_raw_data(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        first = results[0]
        self.assertEqual(first.raw_data["brand"], "AcmeBrand")
        self.assertEqual(first.raw_data["link"], "https://teststore.myshopify.com/products/hoodie")
        self.assertEqual(first.raw_data["image_link"], "https://cdn.shopify.com/hoodie-1.jpg")

    def test_additional_image_links_excludes_first_image(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        additional = json.loads(results[0].raw_data["additional_image_links"])
        self.assertEqual(
            additional,
            [
                "https://cdn.shopify.com/hoodie-2.jpg",
                "https://cdn.shopify.com/hoodie-3.jpg",
            ],
        )

    def test_gtin_from_barcode(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["gtin"], "1234567890123")
        self.assertEqual(results[1].raw_data["gtin"], "")
        self.assertEqual(results[2].raw_data["gtin"], "9876543210987")

    def test_availability_in_stock_when_inventory_positive(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["availability"], "in_stock")

    def test_availability_in_stock_when_inventory_zero_but_continue(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        # M/Blue has inventory=0 but inventory_policy=continue → in_stock
        self.assertEqual(results[1].raw_data["availability"], "in_stock")

    def test_availability_out_of_stock_when_inventory_zero_and_deny(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        # L/Green has inventory=0 and inventory_policy=deny → out_of_stock
        self.assertEqual(results[2].raw_data["availability"], "out_of_stock")

    def test_sale_price_set_when_compare_at_higher(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["sale_price"], "49.00")

    def test_sale_price_empty_when_compare_at_equal_or_lower(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[1].raw_data["sale_price"], "")
        self.assertEqual(results[2].raw_data["sale_price"], "")

    def test_weight_formatted_with_unit(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["weight"], "0.6 kg")
        self.assertEqual(results[0].raw_data["weight_unit"], "kg")

    def test_mpn_falls_back_to_sku(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["mpn"], "HOOD-S-RED")
        self.assertEqual(results[0].raw_data["sku"], "HOOD-S-RED")

    def test_condition_defaults_to_new(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertEqual(results[0].raw_data["condition"], "new")

    def test_is_active_reflects_product_status(self):
        results = self.connector._map_shopify_product(_PRODUCT_OPTIONS)
        self.assertTrue(results[0].raw_data["is_active"])

        archived = dict(_PRODUCT_OPTIONS, status="archived")
        results_archived = self.connector._map_shopify_product(archived)
        self.assertFalse(results_archived[0].raw_data["is_active"])

    def test_no_options_means_empty_size_color_material(self):
        product_no_options = {
            "id": 7001,
            "title": "Plain",
            "body_html": "",
            "handle": "plain",
            "tags": "",
            "vendor": "",
            "status": "active",
            "images": [],
            "options": [],
            "variants": [
                {
                    "id": 8001,
                    "title": "Default Title",
                    "price": "10.00",
                    "sku": "PLAIN-1",
                    "inventory_quantity": 5,
                    "inventory_policy": "deny",
                }
            ],
        }
        results = self.connector._map_shopify_product(product_no_options)
        self.assertEqual(results[0].raw_data["size"], "")
        self.assertEqual(results[0].raw_data["color"], "")
        self.assertEqual(results[0].raw_data["material"], "")


class TestRateLimitThrottle(unittest.TestCase):
    def test_throttle_when_bucket_above_threshold(self):
        sleep_calls = []
        with patch.object(shopify_connector.time, "sleep", side_effect=lambda s: sleep_calls.append(s)):
            shopify_connector._throttle_for_bucket("36/40")
        self.assertEqual(sleep_calls, [1.0])

    def test_no_throttle_when_bucket_low(self):
        sleep_calls = []
        with patch.object(shopify_connector.time, "sleep", side_effect=lambda s: sleep_calls.append(s)):
            shopify_connector._throttle_for_bucket("10/40")
        self.assertEqual(sleep_calls, [])

    def test_no_throttle_when_header_missing(self):
        sleep_calls = []
        with patch.object(shopify_connector.time, "sleep", side_effect=lambda s: sleep_calls.append(s)):
            shopify_connector._throttle_for_bucket(None)
        self.assertEqual(sleep_calls, [])

    def test_request_retries_on_429(self):
        attempts = [0]

        class _Resp:
            def __init__(self, status_code, headers=None):
                self.status_code = status_code
                self.headers = headers or {}

            def raise_for_status(self):
                if self.status_code >= 400:
                    import requests as _req
                    raise _req.HTTPError(response=self)

        def _fake_request(method, url, headers=None, auth=None, params=None, timeout=None):
            attempts[0] += 1
            if attempts[0] == 1:
                return _Resp(429, {"Retry-After": "0"})
            return _Resp(200, {"X-Shopify-Shop-Api-Call-Limit": "5/40"})

        with (
            patch.object(shopify_connector.requests, "request", side_effect=_fake_request),
            patch.object(shopify_connector.time, "sleep", lambda s: None),
        ):
            resp = shopify_connector._request("GET", "https://x/admin/api/products.json", {"access_token": "t"})

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(attempts[0], 2)


class TestSyncServiceTokenBridge(unittest.TestCase):
    """sync_service._get_connector should pull the OAuth token by shop_domain
    when the source carries one (PR #930 storage scheme)."""

    def test_oauth_token_lookup_by_shop_domain(self):
        from datetime import datetime, timezone

        from app.services.feed_management.models import FeedSourceResponse, FeedSourceType
        from app.services.feed_management.sync_service import _get_connector

        source = FeedSourceResponse(
            id="src-1",
            subaccount_id=42,
            source_type=FeedSourceType.shopify,
            name="Main",
            config={},
            credentials_secret_id=None,
            is_active=True,
            shop_domain="my-store.myshopify.com",
            connection_status="connected",
            has_token=True,
            created_at=datetime(2026, 4, 7, tzinfo=timezone.utc),
            updated_at=datetime(2026, 4, 7, tzinfo=timezone.utc),
        )

        with patch(
            "app.integrations.shopify.service.get_access_token_for_shop",
            return_value="shpua_LIVE",
        ):
            connector = _get_connector(source)

        self.assertEqual(connector.credentials.get("access_token"), "shpua_LIVE")
        self.assertEqual(connector.config.get("store_url"), "my-store.myshopify.com")


if __name__ == "__main__":
    unittest.main()
