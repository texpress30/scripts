from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET

import pytest

from app.services.enriched_catalog.feed_formatter import FeedFormatter


@pytest.fixture
def formatter():
    return FeedFormatter()


@pytest.fixture
def sample_products():
    return [
        {
            "id": "prod-1",
            "title": "Red Running Shoes",
            "description": "Lightweight & breathable",
            "price": "59.99 USD",
            "link": "https://shop.example.com/red-shoes",
            "image_link": "https://cdn.example.com/red-shoes.jpg",
            "availability": "in stock",
            "condition": "new",
            "brand": "RunFast",
            "category": "Shoes > Running",
        },
        {
            "id": "prod-2",
            "title": "Blue Sneakers",
            "description": "Classic style with <special> chars & more",
            "price": "79.99 USD",
            "link": "https://shop.example.com/blue-sneakers",
            "image_link": "https://cdn.example.com/blue-sneakers.jpg",
            "availability": "in stock",
            "condition": "new",
            "brand": "UrbanWalk",
            "category": "Shoes > Casual",
        },
    ]


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

class TestFormatAsJson:
    def test_valid_json(self, formatter, sample_products):
        result = formatter.format_as_json(sample_products)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_product_fields_preserved(self, formatter, sample_products):
        result = formatter.format_as_json(sample_products)
        parsed = json.loads(result)
        assert parsed[0]["id"] == "prod-1"
        assert parsed[1]["title"] == "Blue Sneakers"

    def test_empty_list(self, formatter):
        result = formatter.format_as_json([])
        assert json.loads(result) == []


# ---------------------------------------------------------------------------
# XML
# ---------------------------------------------------------------------------

class TestFormatAsXml:
    def test_valid_xml(self, formatter, sample_products):
        result = formatter.format_as_xml(sample_products)
        root = ET.fromstring(result)
        assert root.tag == "products"
        assert root.attrib["count"] == "2"

    def test_product_elements(self, formatter, sample_products):
        result = formatter.format_as_xml(sample_products)
        root = ET.fromstring(result)
        products = root.findall("product")
        assert len(products) == 2
        assert products[0].find("id").text == "prod-1"
        assert products[0].find("title").text == "Red Running Shoes"

    def test_special_chars_escaped(self, formatter, sample_products):
        result = formatter.format_as_xml(sample_products)
        # Should not crash on parsing despite special chars in description
        root = ET.fromstring(result)
        desc = root.findall("product")[1].find("description").text
        assert "<special>" in desc or "&lt;special&gt;" in result

    def test_catalog_type_attribute(self, formatter, sample_products):
        result = formatter.format_as_xml(sample_products, catalog_type="vehicle")
        root = ET.fromstring(result)
        assert root.attrib["catalog_type"] == "vehicle"

    def test_empty_list(self, formatter):
        result = formatter.format_as_xml([])
        root = ET.fromstring(result)
        assert len(root.findall("product")) == 0


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

class TestFormatAsCsv:
    def test_valid_csv_with_header(self, formatter, sample_products):
        result = formatter.format_as_csv(sample_products)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert "id" in reader.fieldnames
        assert "title" in reader.fieldnames

    def test_product_values(self, formatter, sample_products):
        result = formatter.format_as_csv(sample_products)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert rows[0]["id"] == "prod-1"
        assert rows[1]["brand"] == "UrbanWalk"

    def test_empty_list_returns_empty(self, formatter):
        result = formatter.format_as_csv([])
        assert result == ""

    def test_nested_dict_flattened(self, formatter):
        products = [{"id": "1", "address": {"city": "NYC", "zip": "10001"}}]
        result = formatter.format_as_csv(products)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert rows[0]["address.city"] == "NYC"
        assert rows[0]["address.zip"] == "10001"

    def test_list_values_joined(self, formatter):
        products = [{"id": "1", "tags": ["sale", "new", "featured"]}]
        result = formatter.format_as_csv(products)
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert rows[0]["tags"] == "sale,new,featured"


# ---------------------------------------------------------------------------
# Google Shopping XML
# ---------------------------------------------------------------------------

class TestFormatGoogleShoppingXml:
    def test_rss_structure(self, formatter, sample_products):
        result = formatter.format_google_shopping_xml(sample_products)
        assert '<?xml version="1.0" encoding="UTF-8"?>' in result
        assert '<rss version="2.0"' in result
        assert 'xmlns:g="http://base.google.com/ns/1.0"' in result
        assert "<channel>" in result

    def test_item_count(self, formatter, sample_products):
        result = formatter.format_google_shopping_xml(sample_products)
        assert result.count("<item>") == 2

    def test_g_namespace_tags(self, formatter, sample_products):
        result = formatter.format_google_shopping_xml(sample_products)
        assert "<g:id>prod-1</g:id>" in result
        assert "<g:title>Red Running Shoes</g:title>" in result
        assert "<g:price>59.99 USD</g:price>" in result

    def test_special_chars_escaped_in_xml(self, formatter):
        products = [{"id": "1", "title": 'Shoe & Boot <"special">'}]
        result = formatter.format_google_shopping_xml(products)
        assert "&amp;" in result
        assert "&lt;" in result

    def test_missing_fields_omitted(self, formatter):
        products = [{"id": "1", "title": "Minimal Product"}]
        result = formatter.format_google_shopping_xml(products)
        assert "<g:id>1</g:id>" in result
        assert "<g:title>Minimal Product</g:title>" in result
        # Fields not present should not appear
        assert "<g:brand>" not in result

    def test_empty_products(self, formatter):
        result = formatter.format_google_shopping_xml([])
        assert "<item>" not in result
        assert "</channel>" in result


# ---------------------------------------------------------------------------
# Meta Catalog CSV
# ---------------------------------------------------------------------------

class TestFormatMetaCatalogCsv:
    def test_product_catalog_header(self, formatter, sample_products):
        result = formatter.format_meta_catalog_csv(sample_products, catalog_type="product")
        reader = csv.DictReader(io.StringIO(result))
        assert "id" in reader.fieldnames
        assert "title" in reader.fieldnames
        assert "availability" in reader.fieldnames

    def test_product_rows(self, formatter, sample_products):
        result = formatter.format_meta_catalog_csv(sample_products, catalog_type="product")
        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["id"] == "prod-1"

    def test_vehicle_catalog_header(self, formatter):
        products = [{"vehicle_id": "v1", "title": "2024 BMW X5", "make": "BMW", "model": "X5", "year": "2024"}]
        result = formatter.format_meta_catalog_csv(products, catalog_type="vehicle")
        reader = csv.DictReader(io.StringIO(result))
        assert "vehicle_id" in reader.fieldnames
        assert "make" in reader.fieldnames

    def test_unknown_catalog_defaults_to_product(self, formatter, sample_products):
        result = formatter.format_meta_catalog_csv(sample_products, catalog_type="unknown_type")
        reader = csv.DictReader(io.StringIO(result))
        assert "id" in reader.fieldnames

    def test_empty_products(self, formatter):
        result = formatter.format_meta_catalog_csv([], catalog_type="product")
        # Should just be header row
        lines = result.strip().split("\n")
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestFlattenDict:
    def test_simple_dict(self, formatter):
        result = formatter._flatten_dict({"a": 1, "b": "two"})
        assert result == {"a": 1, "b": "two"}

    def test_nested_dict(self, formatter):
        result = formatter._flatten_dict({"a": {"b": {"c": 3}}})
        assert result == {"a.b.c": 3}

    def test_list_values(self, formatter):
        result = formatter._flatten_dict({"tags": ["a", "b"]})
        assert result == {"tags": "a,b"}
