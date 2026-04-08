"""Pure unit tests for ``app.integrations.magento.normalizer``.

The normalizer is a pure function library — every test here runs without
any HTTP client, DB, or Mongo provider. This is the safety net for the
``Magento product JSON → ProductData`` mapping.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from app.integrations.magento.normalizer import (
    build_image_urls,
    build_media_base_url,
    build_product_url,
    build_variants,
    extract_custom_attribute,
    extract_inventory_quantity,
    extract_tags,
    flatten_category_tree,
    flatten_raw,
    normalize_magento_product,
    resolve_category_name,
    resolve_special_price,
)


def _simple_raw(**overrides: Any) -> dict[str, Any]:
    """Build a plausible Magento 2 simple product payload."""
    base: dict[str, Any] = {
        "id": 12345,
        "sku": "SKU-001",
        "name": "Sample Product",
        "type_id": "simple",
        "price": 99.90,
        "status": 1,
        "visibility": 4,
        "custom_attributes": [
            {"attribute_code": "description", "value": "<p>Long description</p>"},
            {"attribute_code": "short_description", "value": "<p>Short</p>"},
            {"attribute_code": "url_key", "value": "sample-product"},
            {"attribute_code": "category_ids", "value": ["3", "5"]},
            {"attribute_code": "meta_keywords", "value": "sample, demo, product"},
        ],
        "media_gallery_entries": [
            {
                "file": "/s/a/sample-1.jpg",
                "position": 1,
                "types": ["image", "small_image", "thumbnail"],
                "disabled": False,
            },
            {
                "file": "/s/a/sample-2.jpg",
                "position": 2,
                "types": [],
                "disabled": False,
            },
        ],
        "extension_attributes": {
            "stock_item": {"qty": 42, "is_in_stock": True},
        },
    }
    base.update(overrides)
    return base


def _categories_map() -> dict[str, str]:
    return {"3": "Clothing", "5": "T-Shirts", "7": "Accessories"}


# ---------------------------------------------------------------------------
# extract_custom_attribute
# ---------------------------------------------------------------------------


class ExtractCustomAttributeTests(unittest.TestCase):
    def test_returns_value_when_present(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "color", "value": "red"}]}
        self.assertEqual(extract_custom_attribute(raw, "color"), "red")

    def test_returns_default_when_missing(self) -> None:
        self.assertEqual(extract_custom_attribute({}, "color", default="blue"), "blue")
        self.assertEqual(
            extract_custom_attribute({"custom_attributes": []}, "color", default="blue"),
            "blue",
        )

    def test_handles_non_list_custom_attributes(self) -> None:
        self.assertIsNone(extract_custom_attribute({"custom_attributes": "bad"}, "x"))


# ---------------------------------------------------------------------------
# resolve_special_price
# ---------------------------------------------------------------------------


class ResolveSpecialPriceTests(unittest.TestCase):
    _NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    def _raw(self, **attrs: Any) -> dict[str, Any]:
        return {
            "custom_attributes": [
                {"attribute_code": k, "value": v} for k, v in attrs.items()
            ]
        }

    def test_active_special_returns_regular_as_compare_at(self) -> None:
        raw = self._raw(
            special_price="79.90",
            special_from_date="2026-01-01 00:00:00",
            special_to_date="2026-12-31 23:59:59",
        )
        self.assertEqual(resolve_special_price(raw, price=99.90, now=self._NOW), 99.90)

    def test_expired_special_returns_none(self) -> None:
        raw = self._raw(
            special_price="79.90",
            special_from_date="2025-01-01 00:00:00",
            special_to_date="2025-12-31 23:59:59",
        )
        self.assertIsNone(resolve_special_price(raw, price=99.90, now=self._NOW))

    def test_not_yet_active_special_returns_none(self) -> None:
        raw = self._raw(
            special_price="79.90",
            special_from_date="2027-01-01 00:00:00",
        )
        self.assertIsNone(resolve_special_price(raw, price=99.90, now=self._NOW))

    def test_no_window_means_always_active(self) -> None:
        raw = self._raw(special_price="79.90")
        self.assertEqual(resolve_special_price(raw, price=99.90, now=self._NOW), 99.90)

    def test_special_gte_price_returns_none(self) -> None:
        raw = self._raw(special_price="99.90")
        self.assertIsNone(resolve_special_price(raw, price=99.90, now=self._NOW))

    def test_missing_special_returns_none(self) -> None:
        self.assertIsNone(resolve_special_price({}, price=99.90, now=self._NOW))


# ---------------------------------------------------------------------------
# build_image_urls
# ---------------------------------------------------------------------------


class BuildImageUrlsTests(unittest.TestCase):
    def test_primary_image_comes_first(self) -> None:
        raw = {
            "media_gallery_entries": [
                {"file": "/b/other.jpg", "position": 2, "types": [], "disabled": False},
                {
                    "file": "/a/primary.jpg",
                    "position": 3,
                    "types": ["image", "small_image"],
                    "disabled": False,
                },
                {"file": "/c/more.jpg", "position": 1, "types": [], "disabled": False},
            ]
        }
        urls = build_image_urls(raw, "https://store.example.com/media/catalog/product")
        self.assertEqual(
            urls,
            [
                "https://store.example.com/media/catalog/product/a/primary.jpg",
                "https://store.example.com/media/catalog/product/c/more.jpg",
                "https://store.example.com/media/catalog/product/b/other.jpg",
            ],
        )

    def test_disabled_images_skipped(self) -> None:
        raw = {
            "media_gallery_entries": [
                {"file": "/a/on.jpg", "position": 1, "types": ["image"], "disabled": False},
                {"file": "/b/off.jpg", "position": 2, "types": [], "disabled": True},
            ]
        }
        urls = build_image_urls(raw, "https://store.example.com/media/catalog/product")
        self.assertEqual(urls, ["https://store.example.com/media/catalog/product/a/on.jpg"])

    def test_empty_gallery_returns_empty(self) -> None:
        self.assertEqual(
            build_image_urls({}, "https://store.example.com/media/catalog/product"),
            [],
        )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


class CategoryHelpersTests(unittest.TestCase):
    def test_flatten_category_tree_walks_recursively(self) -> None:
        tree = {
            "id": 1,
            "name": "Root Catalog",
            "children_data": [
                {
                    "id": 2,
                    "name": "Default Category",
                    "children_data": [
                        {"id": 3, "name": "Clothing", "children_data": [
                            {"id": 5, "name": "T-Shirts", "children_data": []},
                        ]},
                        {"id": 7, "name": "Accessories", "children_data": []},
                    ],
                }
            ],
        }
        flat = flatten_category_tree(tree)
        self.assertEqual(flat["3"], "Clothing")
        self.assertEqual(flat["5"], "T-Shirts")
        self.assertEqual(flat["7"], "Accessories")
        # Root nodes are included too (caller can filter if desired)
        self.assertEqual(flat["1"], "Root Catalog")

    def test_flatten_empty_tree(self) -> None:
        self.assertEqual(flatten_category_tree(None), {})
        self.assertEqual(flatten_category_tree({}), {})

    def test_resolve_category_name_returns_first_hit(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "category_ids", "value": ["3", "5"]}]}
        self.assertEqual(resolve_category_name(raw, _categories_map()), "Clothing")

    def test_resolve_category_name_handles_csv_string(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "category_ids", "value": "5,3"}]}
        self.assertEqual(resolve_category_name(raw, _categories_map()), "T-Shirts")

    def test_resolve_category_name_empty_when_no_match(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "category_ids", "value": "99"}]}
        self.assertEqual(resolve_category_name(raw, _categories_map()), "")


# ---------------------------------------------------------------------------
# URL + tags + inventory
# ---------------------------------------------------------------------------


class MiscHelpersTests(unittest.TestCase):
    def test_build_product_url_appends_suffix(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "url_key", "value": "sample-product"}]}
        self.assertEqual(
            build_product_url(raw, "https://store.example.com"),
            "https://store.example.com/sample-product.html",
        )

    def test_build_product_url_custom_suffix(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "url_key", "value": "sample"}]}
        self.assertEqual(
            build_product_url(raw, "https://store.example.com", url_suffix=""),
            "https://store.example.com/sample",
        )

    def test_build_product_url_missing_key(self) -> None:
        self.assertEqual(build_product_url({}, "https://store.example.com"), "")

    def test_extract_tags_from_meta_keywords(self) -> None:
        raw = {"custom_attributes": [{"attribute_code": "meta_keywords", "value": "a, b, c"}]}
        self.assertEqual(extract_tags(raw), ["a", "b", "c"])

    def test_extract_tags_empty(self) -> None:
        self.assertEqual(extract_tags({}), [])

    def test_extract_inventory_quantity(self) -> None:
        raw = {"extension_attributes": {"stock_item": {"qty": 25}}}
        self.assertEqual(extract_inventory_quantity(raw), 25)

    def test_extract_inventory_quantity_missing(self) -> None:
        self.assertEqual(extract_inventory_quantity({}), 0)
        self.assertEqual(extract_inventory_quantity({"extension_attributes": {}}), 0)

    def test_build_media_base_url(self) -> None:
        self.assertEqual(
            build_media_base_url("https://store.example.com/"),
            "https://store.example.com/media/catalog/product",
        )


# ---------------------------------------------------------------------------
# flatten_raw
# ---------------------------------------------------------------------------


class FlattenRawTests(unittest.TestCase):
    def test_copies_scalar_fields_and_hoists_custom_attributes(self) -> None:
        raw = _simple_raw()
        flat = flatten_raw(raw)
        self.assertEqual(flat["id"], 12345)
        self.assertEqual(flat["sku"], "SKU-001")
        self.assertEqual(flat["type_id"], "simple")
        self.assertEqual(flat["description"], "Long description")
        self.assertEqual(flat["url_key"], "sample-product")
        self.assertEqual(flat["stock_quantity"], 42)
        self.assertTrue(flat["is_in_stock"])
        self.assertEqual(flat["image_count"], 2)


# ---------------------------------------------------------------------------
# build_variants
# ---------------------------------------------------------------------------


class BuildVariantsTests(unittest.TestCase):
    def test_children_become_variants(self) -> None:
        children = [
            {
                "sku": "SKU-001-RED-S",
                "name": "Sample - Red - S",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 5}},
            },
            {
                "sku": "SKU-001-RED-M",
                "name": "Sample - Red - M",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 0}},
            },
        ]
        variants = build_variants(children)
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0].sku, "SKU-001-RED-S")
        self.assertEqual(variants[0].price, 49.99)
        self.assertEqual(variants[0].inventory_quantity, 5)
        self.assertEqual(variants[1].inventory_quantity, 0)

    def test_no_children_returns_empty(self) -> None:
        self.assertEqual(build_variants(None), [])
        self.assertEqual(build_variants([]), [])


# ---------------------------------------------------------------------------
# normalize_magento_product — end to end
# ---------------------------------------------------------------------------


class NormalizeSimpleProductTests(unittest.TestCase):
    def test_maps_every_field(self) -> None:
        product = normalize_magento_product(
            _simple_raw(),
            storefront_base_url="https://store.example.com",
            currency="EUR",
            categories_map=_categories_map(),
        )
        self.assertEqual(product.id, "12345")
        self.assertEqual(product.sku, "SKU-001")
        self.assertEqual(product.title, "Sample Product")
        self.assertEqual(product.description, "Long description")
        self.assertEqual(product.price, 99.90)
        self.assertIsNone(product.compare_at_price)
        self.assertEqual(product.currency, "EUR")
        self.assertEqual(
            product.images,
            [
                "https://store.example.com/media/catalog/product/s/a/sample-1.jpg",
                "https://store.example.com/media/catalog/product/s/a/sample-2.jpg",
            ],
        )
        self.assertEqual(product.variants, [])
        self.assertEqual(product.category, "Clothing")
        self.assertEqual(product.tags, ["sample", "demo", "product"])
        self.assertEqual(product.inventory_quantity, 42)
        self.assertEqual(product.url, "https://store.example.com/sample-product.html")
        # raw_data is a flat presentable dict, not the literal Magento JSON
        self.assertEqual(product.raw_data["id"], 12345)
        self.assertEqual(product.raw_data["type_id"], "simple")
        self.assertEqual(product.raw_data["stock_quantity"], 42)

    def test_missing_description_defaults_to_empty(self) -> None:
        raw = _simple_raw(custom_attributes=[
            {"attribute_code": "url_key", "value": "x"},
        ])
        product = normalize_magento_product(
            raw,
            storefront_base_url="https://store.example.com",
            currency="EUR",
        )
        self.assertEqual(product.description, "")

    def test_special_price_expired_sets_no_compare_at(self) -> None:
        raw = _simple_raw(custom_attributes=[
            {"attribute_code": "special_price", "value": "79.90"},
            {"attribute_code": "special_to_date", "value": "2025-12-31 00:00:00"},
            {"attribute_code": "category_ids", "value": "3"},
        ])
        product = normalize_magento_product(
            raw,
            storefront_base_url="https://store.example.com",
            currency="EUR",
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.assertIsNone(product.compare_at_price)

    def test_special_price_active_sets_compare_at(self) -> None:
        raw = _simple_raw(custom_attributes=[
            {"attribute_code": "special_price", "value": "79.90"},
            {"attribute_code": "special_from_date", "value": "2026-01-01 00:00:00"},
            {"attribute_code": "special_to_date", "value": "2026-12-31 00:00:00"},
            {"attribute_code": "category_ids", "value": "3"},
        ])
        product = normalize_magento_product(
            raw,
            storefront_base_url="https://store.example.com",
            currency="EUR",
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(product.compare_at_price, 99.90)

    def test_missing_category_ids_returns_empty_category(self) -> None:
        raw = _simple_raw(custom_attributes=[
            {"attribute_code": "url_key", "value": "x"},
        ])
        product = normalize_magento_product(
            raw,
            storefront_base_url="https://store.example.com",
            currency="EUR",
            categories_map=_categories_map(),
        )
        self.assertEqual(product.category, "")


class NormalizeConfigurableProductTests(unittest.TestCase):
    def test_children_become_variants(self) -> None:
        parent = _simple_raw(
            id=5000,
            sku="CONFIG-001",
            name="Configurable Product",
            type_id="configurable",
            price=0.0,
        )
        children = [
            {
                "id": 5001,
                "sku": "CONFIG-001-RED",
                "name": "Configurable - Red",
                "type_id": "simple",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 10}},
            },
            {
                "id": 5002,
                "sku": "CONFIG-001-BLUE",
                "name": "Configurable - Blue",
                "type_id": "simple",
                "price": 49.99,
                "extension_attributes": {"stock_item": {"qty": 3}},
            },
        ]
        product = normalize_magento_product(
            parent,
            storefront_base_url="https://store.example.com",
            currency="EUR",
            categories_map=_categories_map(),
            children=children,
        )
        self.assertEqual(product.id, "5000")
        self.assertEqual(len(product.variants), 2)
        self.assertEqual(product.variants[0].sku, "CONFIG-001-RED")
        self.assertEqual(product.variants[0].inventory_quantity, 10)
        self.assertEqual(product.variants[1].sku, "CONFIG-001-BLUE")


if __name__ == "__main__":
    unittest.main()
