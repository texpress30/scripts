from __future__ import annotations

from decimal import Decimal
import unittest

from app.services import client_data_store


class ClientDataStorePureTests(unittest.TestCase):
    def test_list_supported_sources_returns_exact_catalog_in_label_order(self):
        expected = [
            {"key": "call_center", "label": "Call Center"},
            {"key": "direct", "label": "Direct"},
            {"key": "google_ads", "label": "Google"},
            {"key": "linkedin_ads", "label": "LinkedIn"},
            {"key": "meta_ads", "label": "Meta"},
            {"key": "organic", "label": "Organic"},
            {"key": "pinterest_ads", "label": "Pinterest"},
            {"key": "quora_ads", "label": "Quora"},
            {"key": "reddit_ads", "label": "Reddit"},
            {"key": "referral", "label": "Referral"},
            {"key": "snapchat_ads", "label": "Snapchat"},
            {"key": "taboola_ads", "label": "Taboola"},
            {"key": "tiktok_ads", "label": "TikTok"},
            {"key": "unknown", "label": "Unknown"},
        ]
        self.assertEqual(client_data_store.list_supported_sources(), expected)

    def test_is_supported_source(self):
        self.assertTrue(client_data_store.is_supported_source("meta_ads"))
        self.assertTrue(client_data_store.is_supported_source("  TIKTOK_ADS  "))
        self.assertFalse(client_data_store.is_supported_source("facebook_ads"))
        self.assertFalse(client_data_store.is_supported_source(None))

    def test_get_source_label(self):
        self.assertEqual(client_data_store.get_source_label("google_ads"), "Google")
        self.assertEqual(client_data_store.get_source_label("  REDDIT_ADS "), "Reddit")
        self.assertIsNone(client_data_store.get_source_label("invalid"))
        self.assertIsNone(client_data_store.get_source_label(None))

    def test_formula_helpers_empty(self):
        entries: list[dict[str, object]] = []
        self.assertEqual(client_data_store.compute_sales_count(entries), 0)
        self.assertEqual(client_data_store.compute_revenue(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_cogs(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_custom_value_4(entries), Decimal("0"))
        self.assertEqual(client_data_store.compute_gross_profit(entries), Decimal("0"))

    def test_formula_helpers_simple_example(self):
        entries = [
            {"sale_price_amount": Decimal("100.50"), "actual_price_amount": Decimal("60.25")},
            {"sale_price_amount": 99, "actual_price_amount": "40.75"},
        ]
        self.assertEqual(client_data_store.compute_sales_count(entries), 2)
        self.assertEqual(client_data_store.compute_revenue(entries), Decimal("199.50"))
        self.assertEqual(client_data_store.compute_cogs(entries), Decimal("101.00"))
        self.assertEqual(client_data_store.compute_custom_value_4(entries), Decimal("199.50"))
        self.assertEqual(client_data_store.compute_gross_profit(entries), Decimal("98.50"))


if __name__ == "__main__":
    unittest.main()
