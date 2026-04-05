"""Tests for RSS 2.0 XML feed generation (Meta/Google compatible).

Verifies that:
- Feed has RSS 2.0 structure: <rss><channel><item> with g: namespace
- All product fields use g: prefix
- Channel header has title, link, description
- Special characters are escaped / control chars stripped
- Both feed_generator and feed_formatter paths produce valid RSS
"""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.etree.ElementTree import fromstring

import pytest

from app.services.feed_management.channels.feed_generator import (
    GOOGLE_NS,
    FeedGenerator,
)
from app.services.enriched_catalog.feed_formatter import FeedFormatter

NS = {"g": GOOGLE_NS}


# ---------------------------------------------------------------------------
# Channel feeds: FeedGenerator._format_rss_xml
# ---------------------------------------------------------------------------

class TestFeedGeneratorRssXml:

    def _gen(self):
        return FeedGenerator()

    def test_rss_root_structure(self):
        products = [{"id": "1", "title": "Test"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"

    def test_channel_header(self):
        xml = self._gen()._format_rss_xml([{"id": "1"}])
        root = fromstring(xml)
        channel = root.find("channel")
        assert channel is not None
        assert channel.find("title") is not None
        assert channel.find("link") is not None
        assert channel.find("description") is not None

    def test_google_namespace_on_fields(self):
        products = [{"id": "1", "title": "Test Car", "price": "6990 EUR"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        g_fields = [el for el in item if el.tag.startswith(f"{{{GOOGLE_NS}}}")]
        assert len(g_fields) == 3  # id, title, price

    def test_item_count(self):
        products = [{"id": str(i)} for i in range(5)]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        items = root.findall(".//item")
        assert len(items) == 5

    def test_special_chars_escaped(self):
        products = [{"title": "RATE & GARANTIE", "description": "price < 5000"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)  # Valid XML
        item = root.find(".//item")
        title = item.find(f"{{{GOOGLE_NS}}}title")
        assert title.text == "RATE & GARANTIE"

    def test_control_chars_stripped(self):
        products = [{"title": "Test\x00\x0bcar"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        title = root.find(f".//{{{GOOGLE_NS}}}title")
        assert "\x00" not in title.text

    def test_brackets_in_field_name(self):
        """Schema import field names like image[0].url are sanitized."""
        products = [{"image[0].url": "https://img.test/0.jpg"}]
        xml = self._gen()._format_rss_xml(products)
        fromstring(xml)  # Must not raise

    def test_skips_empty_values(self):
        products = [{"id": "1", "title": "", "price": "6990"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        fields = [el.tag.split("}")[-1] for el in item]
        assert "title" not in fields  # empty string skipped

    def test_channel_name_in_title(self):
        channel = MagicMock()
        channel.name = "ROC Automobile - Vehicle Offers"
        channel.feed_url = "/feeds/abc123.xml"
        xml = self._gen()._format_rss_xml([{"id": "1"}], channel=channel)
        root = fromstring(xml)
        assert root.find("channel/title").text == "ROC Automobile - Vehicle Offers"

    def test_realistic_vehicle_product(self):
        products = [{
            "id": "63638",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "description": "DACIA DUSTER 2013 *1.5 DIESEL *EURO 5\n*RATE & GARANTIE",
            "url": "https://rocautomobile.ro/produs/dacia-duster-2013/",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2026/04/img.jpeg",
            "price": "6990 EUR",
            "availability": "in stock",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "mileage": "111215 km",
            "body_style": "SUV",
            "exterior_color": "Negru",
            "vin": "UU1HSDAG548270631",
            "vehicle_condition": "GOOD",
            "drivetrain": "manual",
            "fuel_type": "Diesel",
            "engine": "1.5L",
            "dealership_name": "ROC Automobile",
        }]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        assert item.find(f"{{{GOOGLE_NS}}}make").text == "Dacia"
        assert item.find(f"{{{GOOGLE_NS}}}price").text == "6990 EUR"
        assert item.find(f"{{{GOOGLE_NS}}}vin").text == "UU1HSDAG548270631"


# ---------------------------------------------------------------------------
# Output feeds: FeedFormatter.format_rss_xml
# ---------------------------------------------------------------------------

class TestFeedFormatterRssXml:

    def _fmt(self):
        return FeedFormatter()

    def test_rss_structure(self):
        products = [{"id": "1", "title": "Test"}]
        xml = self._fmt().format_rss_xml(products, title="Test Feed")
        root = fromstring(xml)
        assert root.tag == "rss"
        assert root.get("version") == "2.0"
        assert root.find("channel/title").text == "Test Feed"

    def test_google_namespace(self):
        products = [{"title": "Test"}]
        xml = self._fmt().format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        title = item.find(f"{{{GOOGLE_NS}}}title")
        assert title is not None
        assert title.text == "Test"

    def test_backwards_compat_google_shopping(self):
        """format_google_shopping_xml now delegates to format_rss_xml."""
        products = [{"id": "1", "title": "Test"}]
        xml = self._fmt().format_google_shopping_xml(products)
        root = fromstring(xml)
        assert root.tag == "rss"

    def test_special_chars(self):
        products = [{"title": "RATE & GARANTIE", "description": "Test\x00"}]
        xml = self._fmt().format_rss_xml(products)
        fromstring(xml)

    def test_atom_self_link(self):
        url = "https://admin.omarosa.ro/api/feeds/abc.xml"
        xml = self._fmt().format_rss_xml([{"id": "1"}], feed_url=url)
        root = fromstring(xml)
        atom_ns = "http://www.w3.org/2005/Atom"
        link = root.find(f"channel/{{{atom_ns}}}link")
        assert link is not None
        assert link.get("href") == url


# ---------------------------------------------------------------------------
# _format_feed routing (channel feed generator)
# ---------------------------------------------------------------------------

class TestFormatFeedRouting:

    def _gen(self):
        return FeedGenerator()

    def test_facebook_uses_rss(self):
        from app.services.feed_management.channels.models import ChannelType, FeedFormat
        products = [{"id": "1", "title": "Test"}]
        xml = self._gen()._format_feed(
            products, ChannelType.facebook_product_ads, FeedFormat.xml,
        )
        root = fromstring(xml)
        assert root.tag == "rss"

    def test_google_shopping_uses_rss(self):
        from app.services.feed_management.channels.models import ChannelType, FeedFormat
        products = [{"id": "1", "title": "Test"}]
        xml = self._gen()._format_feed(
            products, ChannelType.google_shopping, FeedFormat.xml,
        )
        root = fromstring(xml)
        assert root.tag == "rss"

    def test_custom_channel_uses_generic_xml(self):
        from app.services.feed_management.channels.models import ChannelType, FeedFormat
        products = [{"id": "1", "title": "Test"}]
        xml = self._gen()._format_feed(
            products, ChannelType.custom, FeedFormat.xml,
        )
        root = fromstring(xml)
        assert root.tag == "feed"  # generic format
