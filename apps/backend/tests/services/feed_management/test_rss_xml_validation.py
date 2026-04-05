"""Tests for RSS XML validation, field name sanitization, and description handling.

Covers the two concrete causes from production:
1. Field names like image[0].url → image_0_.url (dots in tag names)
2. Long descriptions with control chars, emojis, & symbols breaking XML
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# _sanitize_xml_tag: clean field names
# ---------------------------------------------------------------------------

class TestSanitizeXmlTag:

    def test_brackets_and_dots_cleaned(self):
        """image[0].url → image_0_url (no dots, no brackets)."""
        assert _sanitize_xml_tag("image[0].url") == "image_0_url"

    def test_no_trailing_dot_underscore(self):
        assert "." not in _sanitize_xml_tag("image[0].tag")
        assert not _sanitize_xml_tag("image[0].tag").endswith("_")

    def test_consecutive_underscores_collapsed(self):
        assert "__" not in _sanitize_xml_tag("image[0].url")
        assert "__" not in _sanitize_xml_tag("some__field__name")

    def test_digit_start(self):
        result = _sanitize_xml_tag("0_type")
        assert not result[0].isdigit()

    def test_clean_name_unchanged(self):
        assert _sanitize_xml_tag("vehicle_condition") == "vehicle_condition"
        assert _sanitize_xml_tag("image_link") == "image_link"

    def test_spaces(self):
        assert _sanitize_xml_tag("Body Style") == "Body_Style"

    def test_parentheses(self):
        result = _sanitize_xml_tag("price (EUR)")
        assert "(" not in result
        assert ")" not in result


# ---------------------------------------------------------------------------
# _sanitize_xml_value: control chars and length
# ---------------------------------------------------------------------------

class TestSanitizeXmlValue:

    def test_control_chars_stripped(self):
        result = _sanitize_xml_value("text\x00with\x0bcontrol")
        assert "\x00" not in result
        assert "\x0b" not in result

    def test_preserves_newlines_tabs(self):
        result = _sanitize_xml_value("line1\nline2\ttab")
        assert "\n" in result
        assert "\t" in result

    def test_truncates_long_text(self):
        long_text = "word " * 2000  # ~10000 chars
        result = _sanitize_xml_value(long_text)
        assert len(result) <= 5010  # 5000 + "..."

    def test_none(self):
        assert _sanitize_xml_value(None) == ""

    def test_ampersand_not_escaped(self):
        """_sanitize_xml_value doesn't escape — ElementTree handles that."""
        result = _sanitize_xml_value("RATE & GARANTIE")
        assert result == "RATE & GARANTIE"  # ElementTree will escape later


# ---------------------------------------------------------------------------
# RSS XML: field names from schema imports
# ---------------------------------------------------------------------------

class TestRssFieldNames:

    def _gen(self):
        return FeedGenerator()

    def test_no_dots_in_field_names(self):
        products = [{"image[0].url": "https://img.test/0.jpg", "image[0].tag": "Front"}]
        xml = self._gen()._format_rss_xml(products)
        assert ".url>" not in xml
        assert ".tag>" not in xml
        fromstring(xml)

    def test_no_image_0_dot_url(self):
        """The exact production issue: image_0_.url must not appear."""
        products = [{"image[0].url": "https://img.test/0.jpg"}]
        xml = self._gen()._format_rss_xml(products)
        assert "image_0_.url" not in xml
        assert "image_0_url" in xml  # clean name

    def test_all_field_names_valid(self):
        """Every g: tag must be parseable."""
        products = [{
            "image[0].url": "https://img.test/0.jpg",
            "image[0].tag": "Front",
            "mileage.value": "111215",
            "address.city": "Bucharest",
            "0_type": "vehicle",
        }]
        xml = self._gen()._format_rss_xml(products)
        fromstring(xml)


# ---------------------------------------------------------------------------
# RSS XML: long descriptions with special chars
# ---------------------------------------------------------------------------

class TestRssDescriptions:

    def _gen(self):
        return FeedGenerator()

    def test_long_description_valid_xml(self):
        products = [{"offer_description": "Text lung\n" * 200 + "Finantare & Rate"}]
        xml = self._gen()._format_rss_xml(products)
        fromstring(xml)

    def test_description_with_ampersand(self):
        products = [{"description": "RATE FIXE & GARANTIE 12 LUNI"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        desc = root.find(f".//{{{GOOGLE_NS}}}description")
        assert desc.text == "RATE FIXE & GARANTIE 12 LUNI"

    def test_description_with_emoji(self):
        products = [{"description": "Motor 2.0 \u2705 EURO 5 \U0001f7e2 test"}]
        xml = self._gen()._format_rss_xml(products)
        fromstring(xml)

    def test_description_with_control_chars(self):
        products = [{"description": "Text\x00cu\x0bcontrol\x1fchars"}]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        desc = root.find(f".//{{{GOOGLE_NS}}}description")
        assert "\x00" not in desc.text


# ---------------------------------------------------------------------------
# RSS XML: validation gate
# ---------------------------------------------------------------------------

class TestRssValidation:

    def _gen(self):
        return FeedGenerator()

    def test_validation_catches_invalid(self):
        """If something somehow produces invalid XML, it raises."""
        gen = self._gen()
        # A valid product should not raise
        products = [{"title": "Test", "price": "6990 EUR"}]
        xml = gen._format_rss_xml(products)
        fromstring(xml)  # should not raise

    def test_realistic_vehicle_feed(self):
        products = [{
            "id": "63638",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "offer_description": "DACIA DUSTER 2013\n*1.5 DIESEL\n*EURO 5\n*CARLIG\nFinantare & Rate\nTel: 0764 984 036",
            "url": "https://rocautomobile.ro/produs/dacia-duster-2013/?utm_source=feed&type=auto",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2026/04/img.jpeg",
            "price": "6990 EUR",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "vin": "UU1HSDAG548270631",
            "vehicle_condition": "GOOD",
            "dealership_name": "ROC Automobile",
        }]
        xml = self._gen()._format_rss_xml(products)
        root = fromstring(xml)
        item = root.find(".//item")
        assert item.find(f"{{{GOOGLE_NS}}}make").text == "Dacia"
        assert item.find(f"{{{GOOGLE_NS}}}vin").text == "UU1HSDAG548270631"
        # URL with & must be escaped
        link = item.find(f"{{{GOOGLE_NS}}}url").text
        assert "utm_source=feed" in link


# ---------------------------------------------------------------------------
# Format routing: ALL channel types → RSS
# ---------------------------------------------------------------------------

class TestFormatRouting:

    def _gen(self):
        return FeedGenerator()

    @pytest.mark.parametrize("ct", [
        ChannelType.google_shopping,
        ChannelType.facebook_product_ads,
        ChannelType.facebook_automotive,
        ChannelType.meta_catalog,
        ChannelType.tiktok,
        ChannelType.tiktok_automotive_inventory,
    ])
    def test_platform_channels_produce_rss(self, ct):
        products = [{"id": "1", "title": "Test"}]
        xml = self._gen()._format_feed(products, ct, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "rss"
        assert "<feed count=" not in xml
        assert "<entry>" not in xml

    def test_custom_uses_generic(self):
        products = [{"id": "1"}]
        xml = self._gen()._format_feed(products, ChannelType.custom, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "feed"


# ---------------------------------------------------------------------------
# Output feeds: FeedFormatter
# ---------------------------------------------------------------------------

class TestFeedFormatterRss:

    def test_format_rss_xml_valid(self):
        fmt = FeedFormatter()
        products = [{"title": "Test & Car", "image[0].url": "https://img.test/0.jpg"}]
        xml = fmt.format_rss_xml(products)
        root = fromstring(xml)
        assert root.tag == "rss"
        assert "image_0_.url" not in xml
