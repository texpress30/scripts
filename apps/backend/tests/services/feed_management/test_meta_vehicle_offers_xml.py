"""Tests for Meta Vehicle Offers XML format: <listings><listing>.

Validates against the official Meta Commerce Manager template.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from xml.etree.ElementTree import fromstring

import pytest

from app.services.feed_management.channels.feed_generator import FeedGenerator
from app.services.feed_management.channels.models import ChannelType, FeedFormat
from app.services.enriched_catalog.feed_formatter import FeedFormatter


def _gen():
    return FeedGenerator()


def _fmt():
    return FeedFormatter()


SAMPLE_PRODUCT = {
    "vehicle_offer_id": "63638",
    "title": "DACIA DUSTER 2013-RATE FIXE, GARANTIE 12 LUNI",
    "offer_description": "RATE FIXE, 0 % AVANS, 12 LUNI GARANTIE",
    "url": "https://rocautomobile.ro/produs/dacia-duster-2013/",
    "image_link": "https://rocautomobile.ro/img.jpeg",
    "image_0_url": "https://rocautomobile.ro/img0.jpeg",
    "image_0_tag": "Față",
    "image_1_url": "https://rocautomobile.ro/img1.jpeg",
    "image_1_tag": "Spate",
    "price": "6990.00 EUR",
    "make": "Dacia",
    "model": "Duster",
    "year": "2013",
    "body_style": "SUV",
    "vin": "UU1HSDAG548270631",
    "mileage": "111215",
    "vehicle_condition": "GOOD",
    "dealership_name": "ROC Automobile",
}


# ---------------------------------------------------------------------------
# Meta <listings><listing> structure
# ---------------------------------------------------------------------------

class TestMetaListingsStructure:

    def test_root_is_listings(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        assert root.tag == "listings"

    def test_has_xml_declaration(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        assert xml.startswith('<?xml version="1.0" encoding="utf-8"?>')

    def test_has_title(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        assert root.find("title") is not None

    def test_listing_not_item(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        assert root.find("listing") is not None
        assert root.find("item") is None
        assert root.find("entry") is None

    def test_no_namespace_prefix(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        assert "xmlns:" not in xml
        assert "<g:" not in xml

    def test_listing_count(self):
        products = [{"title": f"Car {i}"} for i in range(3)]
        xml = _gen()._format_meta_listings_xml(products)
        root = fromstring(xml)
        assert len(root.findall("listing")) == 3

    def test_fields_are_plain(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        listing = root.find("listing")
        assert listing.find("make").text == "Dacia"
        assert listing.find("model").text == "Duster"
        assert listing.find("year").text == "2013"
        assert listing.find("vin").text == "UU1HSDAG548270631"
        assert listing.find("vehicle_offer_id").text == "63638"


# ---------------------------------------------------------------------------
# Nested <image> elements
# ---------------------------------------------------------------------------

class TestNestedImages:

    def test_images_nested(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        listing = root.find("listing")
        images = listing.findall("image")
        assert len(images) == 2  # image_0 and image_1

    def test_image_has_url_and_tag(self):
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        image = root.find("listing/image")
        assert image.find("url").text == "https://rocautomobile.ro/img0.jpeg"
        assert image.find("tag").text == "Față"

    def test_image_fields_not_duplicated(self):
        """image_N_url/tag should not also appear as plain fields."""
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        assert "<image_0_url>" not in xml
        assert "<image_0_tag>" not in xml
        assert "<image_1_url>" not in xml

    def test_image_link_separate(self):
        """image_link is a plain field (not nested image)."""
        xml = _gen()._format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        listing = root.find("listing")
        assert listing.find("image_link") is not None


# ---------------------------------------------------------------------------
# Format routing
# ---------------------------------------------------------------------------

class TestFormatRouting:

    @pytest.mark.parametrize("ct", [
        ChannelType.facebook_product_ads,
        ChannelType.facebook_automotive,
        ChannelType.meta_catalog,
        ChannelType.facebook_marketplace,
    ])
    def test_meta_channels_produce_listings(self, ct):
        products = [{"title": "Test"}]
        xml = _gen()._format_feed(products, ct, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "listings", f"{ct.value} → <{root.tag}>, expected <listings>"

    @pytest.mark.parametrize("ct", [
        ChannelType.google_shopping,
        ChannelType.google_vehicle_ads_v3,
        ChannelType.tiktok,
    ])
    def test_google_tiktok_produce_rss(self, ct):
        products = [{"title": "Test"}]
        xml = _gen()._format_feed(products, ct, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "rss", f"{ct.value} → <{root.tag}>, expected <rss>"

    def test_custom_produces_generic(self):
        products = [{"title": "Test"}]
        xml = _gen()._format_feed(products, ChannelType.custom, FeedFormat.xml)
        root = fromstring(xml)
        assert root.tag == "feed"


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

class TestSanitization:

    def test_control_chars_stripped(self):
        products = [{"description": "text\x00\x0bhere"}]
        xml = _gen()._format_meta_listings_xml(products)
        fromstring(xml)

    def test_ampersand_escaped(self):
        products = [{"description": "RATE & GARANTIE"}]
        xml = _gen()._format_meta_listings_xml(products)
        root = fromstring(xml)
        assert root.find("listing/description").text == "RATE & GARANTIE"

    def test_brackets_in_field_name(self):
        products = [{"image[0].url": "https://img.test/0.jpg"}]
        xml = _gen()._format_meta_listings_xml(products)
        assert "image_0_.url" not in xml
        fromstring(xml)


# ---------------------------------------------------------------------------
# FeedFormatter (output feeds path)
# ---------------------------------------------------------------------------

class TestFeedFormatterMetaListings:

    def test_format_meta_listings_xml(self):
        xml = _fmt().format_meta_listings_xml([SAMPLE_PRODUCT])
        root = fromstring(xml)
        assert root.tag == "listings"
        listing = root.find("listing")
        assert listing.find("make").text == "Dacia"
        images = listing.findall("image")
        assert len(images) == 2

    def test_format_rss_xml_still_works(self):
        xml = _fmt().format_rss_xml([{"title": "Test"}])
        root = fromstring(xml)
        assert root.tag == "rss"

    def test_format_google_shopping_delegates(self):
        xml = _fmt().format_google_shopping_xml([{"title": "Test"}])
        root = fromstring(xml)
        assert root.tag == "rss"


# ---------------------------------------------------------------------------
# Extra fields overwrite fix
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
        data = gen._merge_raw_data({"title": "T", "description": "RAW"})
        mappings = [
            self._make_mapping("description", None, "static", "STATIC"),
            self._make_mapping("offer_description", "description"),
        ]
        row = gen._transform_product(data, mappings, {})
        specs = [
            {"field_key": "description", "channel_field_name": "offer_description",
             "data_type": "string", "is_required": True, "default_value": None,
             "allowed_values": None, "format_pattern": None},
        ]
        result = gen._apply_field_specs(row, specs, "p1")
        assert result["offer_description"] == "STATIC"
