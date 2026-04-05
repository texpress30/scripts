"""Tests for XML feed generation — element name and value sanitization.

Root cause of "error parsing attribute name" at line 5 column 11:
Schema registry adapters store channel_field_name as the RAW template name
(e.g., "image[0].url"). When _apply_field_specs renames keys, the output
has "image[0].url" as field name. The XML formatter then produces:
    <image[0].url>https://...</image[0].url>
The parser sees <image, then [ which is invalid → "error parsing attribute name".

Both formatters (feed_generator.py for channels, feed_formatter.py for
output feeds) need to sanitize element names AND values.
"""

from __future__ import annotations

from xml.etree.ElementTree import fromstring

import pytest

from app.services.feed_management.channels.feed_generator import (
    FeedGenerator,
    _sanitize_xml_tag,
    _sanitize_xml_value,
)
from app.services.enriched_catalog.feed_formatter import FeedFormatter


# ---------------------------------------------------------------------------
# _sanitize_xml_tag
# ---------------------------------------------------------------------------

class TestSanitizeXmlTag:

    def test_brackets_replaced(self):
        """image[0].url → image_0_.url — the actual root cause."""
        assert _sanitize_xml_tag("image[0].url") == "image_0_.url"

    def test_digit_start(self):
        assert _sanitize_xml_tag("0_type") == "_0_type"

    def test_spaces(self):
        assert _sanitize_xml_tag("Body Style") == "Body_Style"

    def test_parentheses(self):
        assert _sanitize_xml_tag("price (EUR)") == "price__EUR_"

    def test_colon_replaced(self):
        # Colons are valid in XML names (namespaces) but we strip them
        # because the g: prefix is added separately in Google Shopping format
        assert _sanitize_xml_tag("g:title") == "g_title"

    def test_clean_name_unchanged(self):
        assert _sanitize_xml_tag("vehicle_condition") == "vehicle_condition"

    def test_hyphen_and_dot_preserved(self):
        assert _sanitize_xml_tag("fuel-type") == "fuel-type"
        assert _sanitize_xml_tag("mileage.value") == "mileage.value"


# ---------------------------------------------------------------------------
# _sanitize_xml_value
# ---------------------------------------------------------------------------

class TestSanitizeXmlValue:

    def test_ampersand(self):
        assert _sanitize_xml_value("RATE & GARANTIE") == "RATE &amp; GARANTIE"

    def test_angle_brackets(self):
        result = _sanitize_xml_value("price < 5000")
        assert "&lt;" in result

    def test_control_chars(self):
        result = _sanitize_xml_value("text\x00with\x0bcontrol")
        assert "\x00" not in result
        assert "\x0b" not in result

    def test_none(self):
        assert _sanitize_xml_value(None) == ""

    def test_number(self):
        assert _sanitize_xml_value(6990) == "6990"


# ---------------------------------------------------------------------------
# Channel feed: _format_xml with problematic field names
# ---------------------------------------------------------------------------

class TestChannelFeedXml:

    def _gen(self):
        return FeedGenerator()

    def test_brackets_in_field_name_produces_valid_xml(self):
        """THE ROOT CAUSE TEST: image[0].url as field name must not break XML."""
        products = [{"image[0].url": "https://example.com/img.jpg", "title": "Test"}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)  # Must not raise
        entry = root.find("entry")
        assert entry is not None

    def test_digit_starting_field_name(self):
        products = [{"0_type": "simple"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_ampersand_in_value(self):
        products = [{"title": "RATE FIXE & GARANTIE 12 LUNI"}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        assert root.find("entry/title").text == "RATE FIXE & GARANTIE 12 LUNI"

    def test_control_chars_in_description(self):
        products = [{"description": "VW TOURAN\x00 *2.0 TDI\x0b *170 CP"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_newlines_in_description(self):
        products = [{"description": "VW TOURAN\n*7 LOCURI\n*2.0 TDI"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_realistic_vehicle_product(self):
        """Full realistic product — must produce valid XML."""
        products = [{
            "id": "60837",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "description": "*2.0 TDI *170 CP *NAVIGATIE *CLIMA\n*RATE & GARANTIE",
            "link": "https://rocautomobile.ro/produs/dacia-duster/?utm_source=feed&type=auto",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2025/07/img.jpg",
            "price": "6990 RON",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "vin": "UU1HSDAG548270631",
            "mileage": "125000 km",
            "vehicle_condition": "used",
        }]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        assert root.find("entry/make").text == "Dacia"
        # URL with & must be escaped
        link = root.find("entry/link").text
        assert "utm_source=feed" in link
        assert "type=auto" in link

    def test_multiple_products_with_special_chars(self):
        products = [
            {"title": "BMW X1 & extras", "price": "7500"},
            {"title": 'VW TOURAN "diesel"', "price": "5500"},
            {"title": "DACIA < best price >", "price": "4000"},
        ]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        assert len(root.findall("entry")) == 3

    def test_google_shopping_xml_with_brackets(self):
        products = [{"image[0].url": "https://img.test/0.jpg", "title": "Test"}]
        xml = self._gen()._format_google_shopping_xml(products)
        fromstring(xml)


# ---------------------------------------------------------------------------
# Output feed: feed_formatter with problematic field names
# ---------------------------------------------------------------------------

class TestOutputFeedXml:

    def _fmt(self):
        return FeedFormatter()

    def test_format_as_xml_with_brackets(self):
        """Output feed path: ElementTree + sanitized tag names."""
        products = [{"image[0].url": "https://example.com/img.jpg", "title": "Test"}]
        xml = self._fmt().format_as_xml(products)
        fromstring(xml)

    def test_format_as_xml_with_control_chars(self):
        products = [{"description": "Text\x00with\x0bcontrol chars"}]
        xml = self._fmt().format_as_xml(products)
        fromstring(xml)

    def test_format_as_xml_with_ampersand(self):
        products = [{"title": "RATE & GARANTIE"}]
        xml = self._fmt().format_as_xml(products)
        root = fromstring(xml)
        assert root.find("product/title").text == "RATE & GARANTIE"

    def test_format_as_xml_realistic(self):
        products = [{
            "id": "60837",
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "description": "*2.0 TDI\n*RATE & GARANTIE",
            "price": "6990 RON",
            "link": "https://example.com/produs?utm_source=feed&type=auto",
        }]
        xml = self._fmt().format_as_xml(products)
        fromstring(xml)

    def test_google_shopping_xml_with_special_chars(self):
        products = [{"title": "RATE & GARANTIE", "price": "6990 RON", "description": "Test\x00"}]
        xml = self._fmt().format_google_shopping_xml(products)
        fromstring(xml)

    def test_format_as_xml_digit_field_name(self):
        products = [{"0_type": "simple"}]
        xml = self._fmt().format_as_xml(products)
        fromstring(xml)
