"""Tests for Meta-compatible RSS XML feed — no xml declaration, no atom namespace.

Validated against DataFeedWatch working feed format that Meta accepts.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.etree.ElementTree import fromstring

import pytest

from app.services.feed_management.channels.feed_generator import (
    GOOGLE_NS,
    FeedGenerator,
    _sanitize_xml_tag,
    _sanitize_xml_value,
)
from app.services.feed_management.channels.models import ChannelType, FeedFormat
from app.services.enriched_catalog.feed_formatter import FeedFormatter


def _gen():
    return FeedGenerator()


def _fmt():
    return FeedFormatter()


# ---------------------------------------------------------------------------
# No XML declaration, no atom namespace
# ---------------------------------------------------------------------------

class TestNoXmlDeclaration:

    def test_starts_with_rss_tag(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        assert xml.startswith("<rss"), f"Expected <rss, got: {xml[:50]}"

    def test_no_xml_version(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        assert "<?xml" not in xml

    def test_no_atom_namespace(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        assert "xmlns:atom" not in xml
        assert "atom:link" not in xml

    def test_has_google_namespace(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        assert 'xmlns:g="http://base.google.com/ns/1.0"' in xml

    def test_formatter_starts_with_rss(self):
        xml = _fmt().format_rss_xml([{"id": "1"}])
        assert xml.startswith("<rss")
        assert "<?xml" not in xml
        assert "xmlns:atom" not in xml


# ---------------------------------------------------------------------------
# RSS structure matches DataFeedWatch format
# ---------------------------------------------------------------------------

class TestRssStructure:

    def test_root_is_rss(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        root = fromstring(xml)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"

    def test_channel_header(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        root = fromstring(xml)
        ch = root.find("channel")
        assert ch is not None
        assert ch.find("title") is not None
        assert ch.find("link") is not None

    def test_items_with_g_namespace(self):
        products = [{"id": "ROC123", "title": "BMW X1", "price": "9990 EUR"}]
        xml = _gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        assert item.find(f"{{{GOOGLE_NS}}}id").text == "ROC123"
        assert item.find(f"{{{GOOGLE_NS}}}title").text == "BMW X1"
        assert item.find(f"{{{GOOGLE_NS}}}price").text == "9990 EUR"

    def test_no_feed_entry_tags(self):
        xml = _gen()._format_rss_xml([{"id": "1"}])
        assert "<feed" not in xml
        assert "<entry>" not in xml


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

class TestSanitization:

    def test_tag_no_dots(self):
        assert "." not in _sanitize_xml_tag("image[0].url")
        assert _sanitize_xml_tag("image[0].url") == "image_0_url"

    def test_tag_no_consecutive_underscores(self):
        assert "__" not in _sanitize_xml_tag("image[0].url")

    def test_value_strips_control_chars(self):
        result = _sanitize_xml_value("text\x00\x0bhere")
        assert "\x00" not in result

    def test_value_truncates(self):
        long = "x " * 5000
        result = _sanitize_xml_value(long)
        assert len(result) <= 5010

    def test_ampersand_handled(self):
        """ElementTree handles & escaping — just verify the XML is valid."""
        products = [{"description": "RATE & GARANTIE"}]
        xml = _gen()._format_rss_xml(products)
        root = fromstring(xml)
        desc = root.find(f".//{{{GOOGLE_NS}}}description")
        assert desc.text == "RATE & GARANTIE"

    def test_brackets_in_field_name(self):
        products = [{"image[0].url": "https://img.test/0.jpg"}]
        xml = _gen()._format_rss_xml(products)
        assert "image_0_.url" not in xml
        fromstring(xml)


# ---------------------------------------------------------------------------
# Format routing
# ---------------------------------------------------------------------------

class TestFormatRouting:

    @pytest.mark.parametrize("ct", [
        ChannelType.google_shopping,
        ChannelType.facebook_product_ads,
        ChannelType.facebook_automotive,
        ChannelType.meta_catalog,
        ChannelType.tiktok,
    ])
    def test_platform_channels_produce_rss(self, ct):
        products = [{"id": "1", "title": "Test"}]
        xml = _gen()._format_feed(products, ct, FeedFormat.xml)
        assert xml.startswith("<rss")
        assert "<?xml" not in xml
        fromstring(xml)

    def test_custom_uses_generic(self):
        products = [{"id": "1"}]
        xml = _gen()._format_feed(products, ChannelType.custom, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "feed"


# ---------------------------------------------------------------------------
# Extra fields overwrite fix (from PR #903)
# ---------------------------------------------------------------------------

class TestExtraFieldsOverwrite:

    def _make_mapping(self, target, source=None, mtype="direct", static=None):
        m = MagicMock()
        m.target_field = target
        m.source_field = source
        m.mapping_type = MagicMock()
        m.mapping_type.value = mtype
        m.static_value = static
        m.template_value = None
        return m

    def test_static_not_overwritten(self):
        gen = _gen()
        data = {"title": "Test", "description": "RAW DESC"}
        data = gen._merge_raw_data(data)
        mappings = [
            self._make_mapping("title", "title"),
            self._make_mapping("description", None, "static", "STATIC VALUE"),
            self._make_mapping("offer_description", "description"),
        ]
        row = gen._transform_product(data, mappings, {})
        specs = [
            {"field_key": "description", "channel_field_name": "offer_description",
             "data_type": "string", "is_required": True, "default_value": None,
             "allowed_values": None, "format_pattern": None},
        ]
        result = gen._apply_field_specs(row, specs, "p1")
        assert result["offer_description"] == "STATIC VALUE"


# ---------------------------------------------------------------------------
# Realistic full feed
# ---------------------------------------------------------------------------

class TestRealisticFeed:

    def test_vehicle_feed(self):
        products = [{
            "id": "63638",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "offer_description": "RATE FIXE, 0 % AVANS, 12 LUNI GARANTIE, LIVRARE LA DOMICILIU",
            "url": "https://rocautomobile.ro/produs/dacia-duster-2013/",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2026/04/img.jpeg",
            "price": "6990 EUR",
            "availability": "in stock",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "mileage": "111215 km",
            "vin": "UU1HSDAG548270631",
            "vehicle_condition": "GOOD",
            "dealership_name": "ROC Automobile",
        }]
        xml = _gen()._format_rss_xml(products)
        assert xml.startswith("<rss")
        assert "<?xml" not in xml
        assert "xmlns:atom" not in xml
        root = fromstring(xml)
        item = root.find(".//item")
        assert item.find(f"{{{GOOGLE_NS}}}make").text == "Dacia"
        assert item.find(f"{{{GOOGLE_NS}}}offer_description").text.startswith("RATE FIXE")
