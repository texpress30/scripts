"""Tests for XML feed generation — sanitization and escaping.

Verifies that:
- Ampersands, angle brackets, quotes are escaped
- Control characters are stripped
- Field names are sanitized to valid XML element names
- Generated XML is parseable by standard XML parsers
"""

from __future__ import annotations

from xml.etree.ElementTree import fromstring

from app.services.feed_management.channels.feed_generator import (
    FeedGenerator,
    _sanitize_xml_tag,
    _sanitize_xml_value,
)


# ---------------------------------------------------------------------------
# _sanitize_xml_value
# ---------------------------------------------------------------------------

class TestSanitizeXmlValue:

    def test_escapes_ampersand(self):
        assert _sanitize_xml_value("RATE FIXE & GARANTIE") == "RATE FIXE &amp; GARANTIE"

    def test_escapes_angle_brackets(self):
        result = _sanitize_xml_value("Preț < 5000 > concurență")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_strips_control_characters(self):
        result = _sanitize_xml_value("Text cu \x00 control \x0b chars")
        assert "\x00" not in result
        assert "\x0b" not in result
        assert "Text cu  control  chars" == result

    def test_preserves_valid_whitespace(self):
        result = _sanitize_xml_value("Line 1\nLine 2\tTabbed")
        assert "\n" in result
        assert "\t" in result

    def test_handles_none(self):
        assert _sanitize_xml_value(None) == ""

    def test_handles_number(self):
        assert _sanitize_xml_value(6990) == "6990"

    def test_handles_romanian_chars(self):
        result = _sanitize_xml_value("Mașină în stare bună — preț: 6.990€")
        assert "Mașină" in result
        assert "€" in result

    def test_handles_quotes(self):
        result = _sanitize_xml_value('Mașină "premium"')
        assert "premium" in result


# ---------------------------------------------------------------------------
# _sanitize_xml_tag
# ---------------------------------------------------------------------------

class TestSanitizeXmlTag:

    def test_basic_tag(self):
        assert _sanitize_xml_tag("title") == "title"

    def test_spaces_to_underscores(self):
        assert _sanitize_xml_tag("Body Style") == "Body_Style"

    def test_strips_brackets(self):
        assert _sanitize_xml_tag("features[0].type") == "features_0_.type"

    def test_prepends_underscore_for_digit_start(self):
        assert _sanitize_xml_tag("0_type") == "_0_type"

    def test_handles_special_chars(self):
        assert _sanitize_xml_tag("price (EUR)") == "price__EUR_"

    def test_preserves_hyphens_and_dots(self):
        assert _sanitize_xml_tag("g:image-link") == "g_image-link"
        # colon gets replaced but hyphen and dot preserved


# ---------------------------------------------------------------------------
# Full XML generation
# ---------------------------------------------------------------------------

class TestFormatXml:

    def _gen(self) -> FeedGenerator:
        return FeedGenerator()

    def test_xml_with_ampersand_is_valid(self):
        products = [{"title": "RATE FIXE & GARANTIE", "price": "6990"}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        entry = root.find("entry")
        assert entry is not None
        assert entry.findtext("title") == "RATE FIXE & GARANTIE"

    def test_xml_with_angle_brackets_is_valid(self):
        products = [{"description": "Preț < 5000 > concurență"}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        assert root.find("entry/description").text == "Preț < 5000 > concurență"

    def test_xml_with_newlines_is_valid(self):
        products = [{"description": "VW TOURAN\n*7 LOCURI\n*2.0 TDI"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)  # should not raise

    def test_xml_with_quotes_is_valid(self):
        products = [{"title": 'Mașină "premium"', "id": "123"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_xml_with_control_chars_is_valid(self):
        products = [{"description": "Text cu \x00 control \x0b chars"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_xml_with_romanian_chars_is_valid(self):
        products = [{"title": "DACIA DUSTER — preț: 6.990€", "description": "Mașină în stare bună"}]
        xml = self._gen()._format_xml(products)
        fromstring(xml)

    def test_xml_skips_none_values(self):
        products = [{"title": "Test", "description": None}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        assert root.find("entry/description") is None

    def test_xml_sanitizes_numeric_field_names(self):
        products = [{"0_type": "simple", "title": "Test"}]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        # Should be _0_type (prepended underscore)
        assert root.find("entry/_0_type") is not None

    def test_xml_multiple_products(self):
        products = [
            {"title": "BMW X1 & extras", "price": "7500"},
            {"title": "VW TOURAN <diesel>", "price": "5500"},
        ]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        entries = root.findall("entry")
        assert len(entries) == 2

    def test_xml_realistic_product(self):
        """Full product with fields that commonly cause XML issues."""
        products = [{
            "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
            "description": "*2.0 TDI *170 CP *NAVIGATIE *CLIMA\n*SENZORI PARCARE\n*RATE & GARANTIE",
            "price": "6990",
            "link": "https://rocautomobile.ro/produs/dacia-duster/?utm_source=feed&type=auto",
            "image_link": "https://rocautomobile.ro/wp-content/uploads/2025/07/img.jpg",
            "make": "Dacia",
            "model": "Duster",
            "year": "2013",
            "vin": "UU1HSDAG548270631",
            "dealership_name": "ROC Automobile",
        }]
        xml = self._gen()._format_xml(products)
        root = fromstring(xml)
        entry = root.find("entry")
        assert entry.findtext("make") == "Dacia"
        assert "&" in entry.findtext("description")


class TestFormatGoogleShoppingXml:

    def _gen(self) -> FeedGenerator:
        return FeedGenerator()

    def test_google_xml_with_ampersand_is_valid(self):
        products = [{"title": "RATE FIXE & GARANTIE"}]
        xml = self._gen()._format_google_shopping_xml(products)
        root = fromstring(xml)
        # RSS structure: rss > channel > item > g:title
        items = root.findall(".//{http://base.google.com/ns/1.0}title")
        assert len(items) == 1
        assert items[0].text == "RATE FIXE & GARANTIE"

    def test_google_xml_with_special_chars_is_valid(self):
        products = [{"description": "Motor < 2.0L > turbo & diesel\n170 CP"}]
        xml = self._gen()._format_google_shopping_xml(products)
        fromstring(xml)
