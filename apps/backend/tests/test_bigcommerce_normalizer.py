"""Tests for ``app.integrations.bigcommerce.normalizer`` (pure functions).

These tests don't touch the network, the DB or the BigCommerceClient — they
only exercise the BC product → :class:`ProductData` projection. Style mirrors
``tests/test_magento_normalizer.py``.
"""

from __future__ import annotations

import unittest

from app.integrations.bigcommerce.normalizer import (
    build_product_url,
    extract_image_urls,
    extract_tags,
    flatten_raw,
    normalize_bigcommerce_product,
    normalize_price,
    normalize_variants,
    resolve_brand_name,
    resolve_primary_category,
)
from app.services.feed_management.connectors.base import strip_html


def _sample_product(**overrides) -> dict:
    base = {
        "id": 77,
        "name": "Winter Jacket",
        "type": "physical",
        "sku": "WJ-001",
        "description": "<p>Cozy <b>winter</b> jacket.</p>",
        "price": 129.99,
        "sale_price": 99.99,
        "retail_price": 149.99,
        "cost_price": 65.00,
        "weight": 2.5,
        "categories": [18, 23],
        "brand_id": 5,
        "inventory_level": 45,
        "inventory_tracking": "product",
        "is_visible": True,
        "availability": "available",
        "search_keywords": "jacket, winter, outerwear",
        "custom_url": {"url": "/winter-jacket/", "is_customized": True},
        "images": [
            {
                "id": 1,
                "url_standard": "https://cdn.bc.com/images/77/standard.jpg",
                "url_zoom": "https://cdn.bc.com/images/77/zoom.jpg",
                "is_thumbnail": True,
                "sort_order": 0,
            },
            {
                "id": 2,
                "url_standard": "https://cdn.bc.com/images/77/back.jpg",
                "is_thumbnail": False,
                "sort_order": 1,
            },
        ],
        "variants": [
            {
                "id": 11,
                "sku": "WJ-001-S",
                "option_values": [{"option_display_name": "Size", "label": "Small"}],
                "price": None,
                "sale_price": None,
                "inventory_level": 15,
            },
            {
                "id": 12,
                "sku": "WJ-001-M",
                "option_values": [{"option_display_name": "Size", "label": "Medium"}],
                "price": 129.99,
                "sale_price": 89.99,
                "inventory_level": 20,
            },
        ],
        "custom_fields": [
            {"id": 1, "name": "Material", "value": "Polyester"},
            {"id": 2, "name": "Care", "value": "Hand wash"},
        ],
    }
    base.update(overrides)
    return base


class StripHtmlTests(unittest.TestCase):
    def test_strips_simple_tags(self) -> None:
        self.assertEqual(strip_html("<p>Hello <b>world</b></p>"), "Hello world")

    def test_decodes_entities(self) -> None:
        self.assertEqual(strip_html("Tom &amp; Jerry"), "Tom & Jerry")

    def test_handles_none(self) -> None:
        self.assertEqual(strip_html(None), "")

    def test_preserves_paragraph_breaks(self) -> None:
        result = strip_html("<p>One</p><p>Two</p>")
        self.assertIn("One", result)
        self.assertIn("Two", result)


class NormalizePriceTests(unittest.TestCase):
    def test_no_sale_price_returns_base_only(self) -> None:
        display, compare = normalize_price(129.99, 0)
        self.assertEqual(display, 129.99)
        self.assertIsNone(compare)

    def test_sale_price_lower_than_price_flips(self) -> None:
        display, compare = normalize_price(129.99, 99.99)
        self.assertEqual(display, 99.99)
        self.assertEqual(compare, 129.99)

    def test_sale_equals_price_returns_no_compare(self) -> None:
        display, compare = normalize_price(50.0, 50.0)
        self.assertEqual(display, 50.0)
        self.assertIsNone(compare)

    def test_sale_higher_than_price_ignored(self) -> None:
        display, compare = normalize_price(50.0, 60.0)
        self.assertEqual(display, 50.0)
        self.assertIsNone(compare)

    def test_string_inputs_parsed(self) -> None:
        display, compare = normalize_price("129.99", "99.99")
        self.assertEqual(display, 99.99)
        self.assertEqual(compare, 129.99)

    def test_none_inputs_default_to_zero(self) -> None:
        display, compare = normalize_price(None, None)
        self.assertEqual(display, 0.0)
        self.assertIsNone(compare)


class ExtractImageUrlsTests(unittest.TestCase):
    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(extract_image_urls([]), [])

    def test_none_returns_empty(self) -> None:
        self.assertEqual(extract_image_urls(None), [])

    def test_thumbnail_first_then_sort_order(self) -> None:
        images = [
            {
                "id": 3,
                "url_standard": "https://cdn.bc.com/c.jpg",
                "is_thumbnail": False,
                "sort_order": 0,
            },
            {
                "id": 1,
                "url_standard": "https://cdn.bc.com/a.jpg",
                "is_thumbnail": True,
                "sort_order": 5,
            },
            {
                "id": 2,
                "url_standard": "https://cdn.bc.com/b.jpg",
                "is_thumbnail": False,
                "sort_order": 1,
            },
        ]
        urls = extract_image_urls(images)
        self.assertEqual(
            urls,
            [
                "https://cdn.bc.com/a.jpg",  # thumbnail
                "https://cdn.bc.com/c.jpg",  # sort_order 0
                "https://cdn.bc.com/b.jpg",  # sort_order 1
            ],
        )

    def test_falls_back_to_zoom_then_thumbnail(self) -> None:
        images = [
            {
                "id": 1,
                "url_zoom": "https://cdn.bc.com/zoom.jpg",
                "sort_order": 0,
            },
        ]
        self.assertEqual(extract_image_urls(images), ["https://cdn.bc.com/zoom.jpg"])

    def test_drops_entries_without_url(self) -> None:
        images = [
            {"id": 1, "sort_order": 0},
            {"id": 2, "url_standard": "https://cdn.bc.com/x.jpg", "sort_order": 1},
        ]
        self.assertEqual(extract_image_urls(images), ["https://cdn.bc.com/x.jpg"])


class BuildProductUrlTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        url = build_product_url(
            "store.example.com", {"url": "/winter-jacket/"}
        )
        self.assertEqual(url, "https://store.example.com/winter-jacket/")

    def test_https_domain_passes_through(self) -> None:
        url = build_product_url(
            "https://store.example.com", {"url": "/winter-jacket/"}
        )
        self.assertEqual(url, "https://store.example.com/winter-jacket/")

    def test_strips_trailing_slash_on_domain(self) -> None:
        url = build_product_url(
            "https://store.example.com/", {"url": "/winter-jacket/"}
        )
        self.assertEqual(url, "https://store.example.com/winter-jacket/")

    def test_missing_custom_url_returns_empty(self) -> None:
        self.assertEqual(build_product_url("store.example.com", None), "")
        self.assertEqual(build_product_url("store.example.com", {}), "")
        self.assertEqual(
            build_product_url("store.example.com", {"url": ""}), ""
        )

    def test_missing_domain_returns_slug_only(self) -> None:
        url = build_product_url("", {"url": "/winter-jacket/"})
        self.assertEqual(url, "/winter-jacket/")


class ResolveCategoryTests(unittest.TestCase):
    def test_first_resolvable_category_wins(self) -> None:
        product = {"categories": [99, 18, 23]}
        cat_map = {18: "Outerwear", 23: "Jackets"}
        self.assertEqual(resolve_primary_category(product, cat_map), "Outerwear")

    def test_no_categories_returns_empty(self) -> None:
        self.assertEqual(resolve_primary_category({}, {}), "")
        self.assertEqual(
            resolve_primary_category({"categories": []}, {1: "X"}), ""
        )

    def test_skips_unresolved_ids(self) -> None:
        product = {"categories": [999, 18]}
        self.assertEqual(
            resolve_primary_category(product, {18: "Outerwear"}), "Outerwear"
        )


class ResolveBrandTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        self.assertEqual(
            resolve_brand_name({"brand_id": 5}, {5: "Acme"}), "Acme"
        )

    def test_missing_returns_empty(self) -> None:
        self.assertEqual(resolve_brand_name({}, {}), "")
        self.assertEqual(resolve_brand_name({"brand_id": 0}, {5: "Acme"}), "")
        self.assertEqual(resolve_brand_name({"brand_id": 999}, {5: "Acme"}), "")


class ExtractTagsTests(unittest.TestCase):
    def test_combines_keywords_and_custom_fields(self) -> None:
        product = {
            "search_keywords": "jacket, winter, outerwear",
            "custom_fields": [
                {"name": "Material", "value": "Polyester"},
                {"name": "Care", "value": "Hand wash"},
            ],
        }
        tags = extract_tags(product)
        self.assertIn("jacket", tags)
        self.assertIn("winter", tags)
        self.assertIn("outerwear", tags)
        self.assertIn("Material:Polyester", tags)
        self.assertIn("Care:Hand wash", tags)

    def test_dedupes(self) -> None:
        product = {"search_keywords": "jacket, jacket, winter"}
        tags = extract_tags(product)
        self.assertEqual(tags.count("jacket"), 1)

    def test_handles_missing(self) -> None:
        self.assertEqual(extract_tags({}), [])


class NormalizeVariantsTests(unittest.TestCase):
    def test_inherits_parent_price_when_variant_has_none(self) -> None:
        variants = [
            {
                "id": 1,
                "sku": "V1",
                "price": None,
                "sale_price": None,
                "inventory_level": 5,
                "option_values": [{"label": "Small"}],
            }
        ]
        result = normalize_variants(variants, fallback_price=99.99)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].sku, "V1")
        self.assertEqual(result[0].price, 99.99)
        self.assertIsNone(result[0].compare_at_price)
        self.assertEqual(result[0].inventory_quantity, 5)
        self.assertEqual(result[0].title, "Small")

    def test_variant_with_own_sale_price_flips_correctly(self) -> None:
        variants = [
            {
                "id": 1,
                "sku": "V2",
                "price": 129.99,
                "sale_price": 89.99,
                "inventory_level": 10,
                "option_values": [{"label": "Medium"}],
            }
        ]
        result = normalize_variants(variants)
        self.assertEqual(result[0].price, 89.99)
        self.assertEqual(result[0].compare_at_price, 129.99)

    def test_concatenates_multiple_options(self) -> None:
        variants = [
            {
                "id": 1,
                "sku": "V3",
                "option_values": [{"label": "Red"}, {"label": "Large"}],
            }
        ]
        result = normalize_variants(variants)
        self.assertEqual(result[0].title, "Red / Large")

    def test_empty_list(self) -> None:
        self.assertEqual(normalize_variants([]), [])
        self.assertEqual(normalize_variants(None), [])


class FlattenRawTests(unittest.TestCase):
    def test_copies_scalar_keys(self) -> None:
        product = _sample_product()
        flat = flatten_raw(product)
        self.assertEqual(flat["id"], 77)
        self.assertEqual(flat["sku"], "WJ-001")
        self.assertEqual(flat["price"], 129.99)
        self.assertEqual(flat["sale_price"], 99.99)
        self.assertEqual(flat["weight"], 2.5)

    def test_strips_html_from_description(self) -> None:
        product = _sample_product()
        flat = flatten_raw(product)
        self.assertEqual(flat["description"], "Cozy winter jacket.")

    def test_hoists_brand_and_category(self) -> None:
        flat = flatten_raw(
            _sample_product(), brand_name="Acme", category_name="Outerwear"
        )
        self.assertEqual(flat["brand"], "Acme")
        self.assertEqual(flat["category"], "Outerwear")

    def test_image_count(self) -> None:
        flat = flatten_raw(_sample_product())
        self.assertEqual(flat["image_count"], 2)

    def test_custom_url_extracted(self) -> None:
        flat = flatten_raw(_sample_product())
        self.assertEqual(flat["custom_url"], "/winter-jacket/")


class NormalizeBigcommerceProductTests(unittest.TestCase):
    def test_happy_path(self) -> None:
        result = normalize_bigcommerce_product(
            _sample_product(),
            store_domain="store.example.com",
            currency="USD",
            categories_map={18: "Outerwear", 23: "Jackets"},
            brands_map={5: "Acme"},
        )

        self.assertEqual(result.id, "77")
        self.assertEqual(result.title, "Winter Jacket")
        self.assertEqual(result.description, "Cozy winter jacket.")
        # Sale flip: BC sale_price=99.99, price=129.99 → display=99.99, compare=129.99
        self.assertEqual(result.price, 99.99)
        self.assertEqual(result.compare_at_price, 129.99)
        self.assertEqual(result.currency, "USD")
        self.assertEqual(
            result.images,
            [
                "https://cdn.bc.com/images/77/standard.jpg",
                "https://cdn.bc.com/images/77/back.jpg",
            ],
        )
        self.assertEqual(result.category, "Outerwear")
        self.assertIn("Acme", result.tags)
        self.assertIn("jacket", result.tags)
        self.assertIn("Material:Polyester", result.tags)
        self.assertEqual(result.inventory_quantity, 45)
        self.assertEqual(result.sku, "WJ-001")
        self.assertEqual(
            result.url, "https://store.example.com/winter-jacket/"
        )
        self.assertEqual(len(result.variants), 2)

    def test_no_sale_price(self) -> None:
        product = _sample_product(sale_price=0)
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
            categories_map={},
            brands_map={},
        )
        self.assertEqual(result.price, 129.99)
        self.assertIsNone(result.compare_at_price)

    def test_missing_description(self) -> None:
        product = _sample_product(description=None)
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
        )
        self.assertEqual(result.description, "")

    def test_missing_images(self) -> None:
        product = _sample_product(images=[])
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
        )
        self.assertEqual(result.images, [])

    def test_missing_categories(self) -> None:
        product = _sample_product(categories=[])
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
            categories_map={18: "Outerwear"},
        )
        self.assertEqual(result.category, "")

    def test_html_description_stripped(self) -> None:
        product = _sample_product(
            description='<p>Get the <strong>best</strong> jacket.</p><br/>Free shipping.'
        )
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
        )
        self.assertNotIn("<", result.description)
        self.assertIn("best", result.description)

    def test_default_currency_when_blank(self) -> None:
        result = normalize_bigcommerce_product(
            _sample_product(),
            store_domain="store.example.com",
            currency="",
        )
        self.assertEqual(result.currency, "USD")

    def test_brand_prepended_to_tags(self) -> None:
        product = _sample_product(search_keywords="")
        result = normalize_bigcommerce_product(
            product,
            store_domain="store.example.com",
            currency="USD",
            categories_map={},
            brands_map={5: "Acme"},
        )
        self.assertEqual(result.tags[0], "Acme")


if __name__ == "__main__":
    unittest.main()
