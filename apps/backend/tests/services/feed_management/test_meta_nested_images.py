"""Tests for Meta Vehicle Offers nested <image> elements.

Verifies that image_N_url/tag fields are converted to nested <image><url>+<tag>
and that flat image fields (image_link, image_count) are excluded.
"""

from __future__ import annotations

from xml.etree.ElementTree import fromstring

from app.services.feed_management.channels.feed_generator import FeedGenerator
from app.services.enriched_catalog.feed_formatter import FeedFormatter


def _gen():
    return FeedGenerator()


def _fmt():
    return FeedFormatter()


PRODUCT_WITH_IMAGES = {
    "vehicle_offer_id": "63638",
    "title": "DACIA DUSTER 2013",
    "image_0_url": "https://img.test/0.jpg",
    "image_0_tag": "Față",
    "image_1_url": "https://img.test/1.jpg",
    "image_1_tag": "Spate",
    "image_2_url": "https://img.test/2.jpg",
    "image_2_tag": "Lateral",
    "image_link": "https://img.test/0.jpg",
    "image_count": "3",
    "make": "Dacia",
    "price": "6990.00 EUR",
}


class TestNestedImages:

    def test_images_are_nested(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        root = fromstring(xml)
        listing = root.find("listing")
        images = listing.findall("image")
        assert len(images) == 3

    def test_image_has_url_and_tag(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        root = fromstring(xml)
        image = root.find("listing/image")
        assert image.find("url").text == "https://img.test/0.jpg"
        assert image.find("tag").text == "Față"

    def test_images_before_other_fields(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        root = fromstring(xml)
        listing = root.find("listing")
        children = list(listing)
        # First 3 elements must be <image>
        assert children[0].tag == "image"
        assert children[1].tag == "image"
        assert children[2].tag == "image"
        # After images, other fields
        assert children[3].tag != "image"


class TestNoFlatImageFields:

    def test_no_image_0_url(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        assert "<image_0_url>" not in xml

    def test_no_image_0_tag(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        assert "<image_0_tag>" not in xml

    def test_no_image_link(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        assert "<image_link>" not in xml

    def test_no_image_count(self):
        xml = _gen()._format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        assert "<image_count>" not in xml


class TestImageLinkFallback:

    def test_fallback_when_no_indexed_images(self):
        product = {"title": "Test", "image_link": "https://fallback.jpg"}
        xml = _gen()._format_meta_listings_xml([product])
        root = fromstring(xml)
        image = root.find("listing/image")
        assert image is not None
        assert image.find("url").text == "https://fallback.jpg"

    def test_no_fallback_when_indexed_images_exist(self):
        product = {
            "title": "Test",
            "image_0_url": "https://indexed.jpg",
            "image_0_tag": "Față",
            "image_link": "https://fallback.jpg",
        }
        xml = _gen()._format_meta_listings_xml([product])
        root = fromstring(xml)
        images = root.findall("listing/image")
        assert len(images) == 1
        assert images[0].find("url").text == "https://indexed.jpg"

    def test_no_image_at_all(self):
        product = {"title": "Test", "make": "Dacia"}
        xml = _gen()._format_meta_listings_xml([product])
        root = fromstring(xml)
        assert root.find("listing/image") is None


class TestRawChannelFieldNames:
    """Test with raw channel_field_names from schema registry (image[0].url)."""

    def test_bracket_notation_creates_nested_images(self):
        """After _apply_field_specs, keys may be image[0].url — must still nest."""
        product = {
            "image[0].url": "https://img.test/bracket0.jpg",
            "image[0].tag[0]": "Față",
            "image[1].url": "https://img.test/bracket1.jpg",
            "image[1].tag[0]": "Spate",
            "image_link": "https://img.test/link.jpg",
            "title": "Test Car",
        }
        xml = _gen()._format_meta_listings_xml([product])
        root = fromstring(xml)
        images = root.findall("listing/image")
        assert len(images) == 2
        assert images[0].find("url").text == "https://img.test/bracket0.jpg"
        assert images[0].find("tag").text == "Față"
        # No flat fields
        assert "image[0]" not in xml
        assert "<image_link>" not in xml

    def test_mixed_notation(self):
        """Product has both canonical and raw field names."""
        product = {
            "image_0_url": "https://img.test/canon.jpg",
            "image_0_tag": "Față",
            "image[1].url": "https://img.test/raw.jpg",
            "title": "Mixed",
        }
        xml = _gen()._format_meta_listings_xml([product])
        root = fromstring(xml)
        images = root.findall("listing/image")
        assert len(images) == 2


class TestFeedFormatterMetaImages:

    def test_nested_images(self):
        xml = _fmt().format_meta_listings_xml([PRODUCT_WITH_IMAGES])
        root = fromstring(xml)
        images = root.findall("listing/image")
        assert len(images) == 3
        assert "<image_link>" not in xml
        assert "<image_count>" not in xml

    def test_fallback(self):
        product = {"title": "Test", "image_link": "https://fb.jpg"}
        xml = _fmt().format_meta_listings_xml([product])
        root = fromstring(xml)
        assert root.find("listing/image/url").text == "https://fb.jpg"

    def test_bracket_notation(self):
        product = {
            "image[0].url": "https://img.test/0.jpg",
            "image[0].tag[0]": "Față",
            "title": "Test",
        }
        xml = _fmt().format_meta_listings_xml([product])
        root = fromstring(xml)
        images = root.findall("listing/image")
        assert len(images) == 1
        assert "<image[0]" not in xml
