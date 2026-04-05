"""Tests for image tag rendering and tag rule distribution.

Verifies that:
- image_*_tag columns are detected as string, not image
- image_*_url columns are detected as image
- Default tag rules produce realistic distribution
- All generated tags are in the valid TikTok list
- flatten_images always re-applies current tag rules
"""

from __future__ import annotations

from app.services.feed_management.connectors.base import (
    DEFAULT_IMAGE_TAG_RULES,
    VALID_IMAGE_TAGS,
    flatten_images,
)
from app.services.feed_management.channels.feed_generator import FeedGenerator


# ---------------------------------------------------------------------------
# Column type detection
# ---------------------------------------------------------------------------

def _detect_column_type(key: str) -> str:
    """Replicate the column type detection logic from get_channel_products."""
    col_type = "string"
    if "image" in key and "tag" not in key:
        col_type = "image"
    elif key in ("link", "url") or key.endswith("_url") or key.endswith("_link"):
        col_type = "url"
    elif "price" in key:
        col_type = "price"
    return col_type


class TestColumnTypeDetection:

    def test_image_tag_is_string(self):
        """image_*_tag columns must render as text, not image thumbnails."""
        assert _detect_column_type("image_0_tag") == "string"
        assert _detect_column_type("image_0_tag_0") == "string"
        assert _detect_column_type("image_1_tag") == "string"
        assert _detect_column_type("image_10_tag") == "string"

    def test_image_url_is_image(self):
        """image_*_url/link columns should render as image thumbnails."""
        assert _detect_column_type("image_link") == "image"
        assert _detect_column_type("image_0_url") == "image"
        assert _detect_column_type("additional_image_link") == "image"

    def test_url_columns(self):
        assert _detect_column_type("dealer_url") == "url"
        assert _detect_column_type("video_0_url") == "url"
        assert _detect_column_type("link") == "url"

    def test_price_columns(self):
        assert _detect_column_type("price") == "price"
        assert _detect_column_type("sale_price") == "price"

    def test_string_columns(self):
        assert _detect_column_type("title") == "string"
        assert _detect_column_type("vin") == "string"
        assert _detect_column_type("body_style") == "string"


# ---------------------------------------------------------------------------
# Tag rules distribution
# ---------------------------------------------------------------------------

def _apply_tag_rules(image_count: int) -> list[str]:
    """Generate tags for N images using flatten_images."""
    raw = {"images": [f"https://img.test/{i}.jpg" for i in range(image_count)]}
    flatten_images(raw)
    return [raw[f"image_{i}_tag"] for i in range(image_count)]


class TestTagRulesDistribution:

    def test_default_rules_10_images(self):
        tags = _apply_tag_rules(10)
        assert tags[0] == "Față"
        assert tags[1] == "Față"
        assert tags[2] == "Spate"
        assert tags[3] == "Lateral"
        assert tags[4] == "Lateral"
        assert tags[5] == "Interior"
        assert tags[6] == "Interior"
        assert tags[7] == "Bord"
        assert tags[8] == "Interior"
        assert tags[9] == "Portbagaj"

    def test_default_rules_16_images(self):
        tags = _apply_tag_rules(16)
        # Positions 10+ default to Interior
        assert tags[10] == "Interior"
        assert tags[15] == "Interior"

    def test_all_tags_valid(self):
        """All generated tags must be in the TikTok valid list."""
        tags = _apply_tag_rules(20)
        for tag in tags:
            assert tag in VALID_IMAGE_TAGS, f"Tag '{tag}' not in VALID_IMAGE_TAGS"

    def test_single_image(self):
        tags = _apply_tag_rules(1)
        assert tags[0] == "Față"

    def test_realistic_distribution(self):
        """Should not have excessive repetition of one tag."""
        tags = _apply_tag_rules(16)
        from collections import Counter
        counts = Counter(tags)
        # Interior should not dominate excessively (was 14 before, now more balanced)
        assert counts["Interior"] <= 10
        # Must have variety
        assert len(counts) >= 4


# ---------------------------------------------------------------------------
# flatten_images behavior
# ---------------------------------------------------------------------------

class TestFlattenImages:

    def test_basic_flatten(self):
        raw = {"images": ["https://img.test/0.jpg", "https://img.test/1.jpg"]}
        flatten_images(raw)
        assert raw["image_0_url"] == "https://img.test/0.jpg"
        assert raw["image_0_tag"] == "Față"
        assert raw["image_1_url"] == "https://img.test/1.jpg"
        assert raw["image_1_tag"] == "Față"
        assert raw["image_count"] == 2

    def test_re_applies_tags(self):
        """Always re-applies current rules, overwriting stale tags."""
        raw = {
            "images": ["https://img.test/0.jpg", "https://img.test/1.jpg"],
            "image_0_tag": "OLD_TAG",
            "image_1_tag": "OLD_TAG",
        }
        flatten_images(raw)
        assert raw["image_0_tag"] == "Față"
        assert raw["image_1_tag"] == "Față"

    def test_empty_images(self):
        raw = {"images": []}
        flatten_images(raw)
        assert "image_0_url" not in raw

    def test_no_images_key(self):
        raw = {"title": "test"}
        flatten_images(raw)
        assert "image_0_url" not in raw


# ---------------------------------------------------------------------------
# _merge_raw_data integration with flatten
# ---------------------------------------------------------------------------

class TestMergeRawDataWithFlatten:

    def test_merge_flattens_images(self):
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "raw_data": {
                "images": ["https://img.test/front.jpg", "https://img.test/back.jpg"],
                "attribute_vin": "ABC123",
            },
        }
        merged = gen._merge_raw_data(data)
        assert merged["image_0_url"] == "https://img.test/front.jpg"
        assert merged["image_0_tag"] == "Față"
        assert merged["image_1_url"] == "https://img.test/back.jpg"
        assert merged["image_1_tag"] == "Față"
        assert merged["attribute_vin"] == "ABC123"

    def test_merge_updates_stale_tags(self):
        """Re-flattening ensures stale tags in MongoDB get current rules."""
        gen = FeedGenerator()
        data = {
            "title": "Product",
            "raw_data": {
                "images": ["https://img.test/0.jpg"] * 10,
                "image_0_tag": "OLD",
                "image_5_tag": "OLD",
            },
        }
        merged = gen._merge_raw_data(data)
        # Tags should reflect current rules, not stale values
        assert merged["image_0_tag"] == "Față"
        assert merged["image_5_tag"] == "Interior"
        assert merged["image_7_tag"] == "Bord"
        assert merged["image_9_tag"] == "Portbagaj"
