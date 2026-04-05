"""Tests verifying that ALL non-custom channel types produce RSS 2.0 XML.

The previous implementation only routed google_shopping to RSS; all other
channels (facebook_product_ads, facebook_automotive, meta_catalog, tiktok,
etc.) fell through to the generic <feed><entry> format which Meta rejects.

Fix: RSS 2.0 with g: namespace is now the DEFAULT for all XML feeds.
Only ChannelType.custom uses the generic format.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.etree.ElementTree import fromstring

import pytest

from app.services.feed_management.channels.feed_generator import (
    GOOGLE_NS,
    FeedGenerator,
)
from app.services.feed_management.channels.models import ChannelType, FeedFormat


NS = {"g": GOOGLE_NS}


def _gen():
    return FeedGenerator()


def _format(channel_type: ChannelType) -> str:
    products = [{"id": "1", "title": "Test Car", "price": "6990 EUR"}]
    return _gen()._format_feed(products, channel_type, FeedFormat.xml)


# ---------------------------------------------------------------------------
# Every platform channel type must produce RSS 2.0
# ---------------------------------------------------------------------------

class TestAllChannelTypesProduceRss:
    """Verify that EVERY non-custom ChannelType routes to RSS."""

    @pytest.mark.parametrize("ct", [
        ChannelType.google_shopping,
        ChannelType.google_vehicle_ads_v3,
        ChannelType.google_vehicle_listings,
        ChannelType.facebook_product_ads,
        ChannelType.facebook_automotive,
        ChannelType.facebook_country,
        ChannelType.meta_catalog,
        ChannelType.tiktok,
        ChannelType.tiktok_catalog,
        ChannelType.tiktok_automotive_inventory,
    ])
    def test_channel_type_produces_rss(self, ct: ChannelType):
        xml = _format(ct)
        root = fromstring(xml)
        assert root.tag == "rss", f"{ct.value} produced <{root.tag}> instead of <rss>"
        assert root.get("version") == "2.0"
        # Must have g: namespaced fields
        item = root.find(".//item")
        assert item is not None, f"{ct.value} has no <item>"
        g_fields = [el for el in item if el.tag.startswith(f"{{{GOOGLE_NS}}}")]
        assert len(g_fields) > 0, f"{ct.value} has no g: fields"

    def test_custom_uses_generic_format(self):
        xml = _format(ChannelType.custom)
        root = fromstring(xml)
        assert root.tag == "feed"
        assert root.find("entry") is not None


# ---------------------------------------------------------------------------
# RSS structure validation
# ---------------------------------------------------------------------------

class TestRssStructure:

    def test_rss_root_and_channel(self):
        xml = _format(ChannelType.facebook_product_ads)
        root = fromstring(xml)
        assert root.tag == "rss"
        channel = root.find("channel")
        assert channel is not None
        assert channel.find("title") is not None
        assert channel.find("link") is not None
        assert channel.find("description") is not None

    def test_items_with_g_namespace(self):
        xml = _format(ChannelType.facebook_automotive)
        root = fromstring(xml)
        items = root.findall(".//item")
        assert len(items) == 1
        item = items[0]
        assert item.find(f"{{{GOOGLE_NS}}}title").text == "Test Car"
        assert item.find(f"{{{GOOGLE_NS}}}price").text == "6990 EUR"

    def test_no_feed_entry_tags(self):
        """Old format tags must not appear."""
        xml = _format(ChannelType.facebook_product_ads)
        assert "<feed count=" not in xml
        assert "<entry>" not in xml
        assert "</entry>" not in xml

    def test_channel_name_from_channel_object(self):
        channel = MagicMock()
        channel.name = "ROC Automobile - Vehicle Offers"
        channel.feed_url = None
        products = [{"id": "1"}]
        xml = _gen()._format_rss_xml(products, channel=channel)
        root = fromstring(xml)
        assert root.find("channel/title").text == "ROC Automobile - Vehicle Offers"


# ---------------------------------------------------------------------------
# Sanitization in RSS output
# ---------------------------------------------------------------------------

class TestRssSanitization:

    def test_ampersand_escaped(self):
        products = [{"title": "RATE & GARANTIE"}]
        xml = _gen()._format_rss_xml(products)
        root = fromstring(xml)
        assert root.find(f".//{{{GOOGLE_NS}}}title").text == "RATE & GARANTIE"

    def test_brackets_in_field_name(self):
        products = [{"image[0].url": "https://img.test/0.jpg"}]
        xml = _gen()._format_rss_xml(products)
        fromstring(xml)  # Must not raise

    def test_control_chars_stripped(self):
        products = [{"title": "Test\x00\x0bcar"}]
        xml = _gen()._format_rss_xml(products)
        root = fromstring(xml)
        title = root.find(f".//{{{GOOGLE_NS}}}title")
        assert "\x00" not in title.text

    def test_realistic_vehicle(self):
        products = [{
            "id": "63638",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "description": "*1.5 DIESEL *EURO 5\n*RATE & GARANTIE",
            "url": "https://rocautomobile.ro/produs/dacia-duster/?utm_source=feed&type=auto",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2026/04/img.jpeg",
            "price": "6990 EUR",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "vin": "UU1HSDAG548270631",
        }]
        xml = _gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        assert item.find(f"{{{GOOGLE_NS}}}make").text == "Dacia"
        assert item.find(f"{{{GOOGLE_NS}}}vin").text == "UU1HSDAG548270631"


# ---------------------------------------------------------------------------
# Output feed service path
# ---------------------------------------------------------------------------

class TestOutputFeedRss:

    def test_format_rss_xml(self):
        from app.services.enriched_catalog.feed_formatter import FeedFormatter
        fmt = FeedFormatter()
        products = [{"id": "1", "title": "Test"}]
        xml = fmt.format_rss_xml(products, title="Test Feed")
        root = fromstring(xml)
        assert root.tag == "rss"
        assert root.find("channel/title").text == "Test Feed"

    def test_google_shopping_delegates_to_rss(self):
        from app.services.enriched_catalog.feed_formatter import FeedFormatter
        fmt = FeedFormatter()
        products = [{"id": "1"}]
        xml = fmt.format_google_shopping_xml(products)
        root = fromstring(xml)
        assert root.tag == "rss"
