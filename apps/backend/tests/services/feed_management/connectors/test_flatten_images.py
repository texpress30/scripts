"""Tests for flatten_images utility."""

from app.services.feed_management.connectors.base import flatten_images, MAX_FEED_IMAGES


class TestFlattenImages:
    def test_basic(self):
        raw = {"images": ["https://img1.jpg", "https://img2.jpg"]}
        flatten_images(raw)
        assert raw["image_0_url"] == "https://img1.jpg"
        assert raw["image_1_url"] == "https://img2.jpg"
        assert raw["image_count"] == 2

    def test_tags_assigned(self):
        raw = {"images": [f"https://img{i}.jpg" for i in range(7)]}
        flatten_images(raw)
        assert raw["image_0_tag"] == "Față"
        assert raw["image_3_tag"] == "Față"
        assert raw["image_4_tag"] == "Spate"
        assert raw["image_5_tag"] == "Spate"
        assert raw["image_6_tag"] == "Lateral"

    def test_default_tag_for_high_index(self):
        raw = {"images": [f"https://img{i}.jpg" for i in range(12)]}
        flatten_images(raw)
        assert raw["image_9_tag"] == "Spate"  # default
        assert raw["image_11_tag"] == "Spate"

    def test_empty_images(self):
        raw = {"images": []}
        flatten_images(raw)
        assert "image_0_url" not in raw
        assert "image_count" not in raw

    def test_no_images_key(self):
        raw = {"title": "Test"}
        flatten_images(raw)
        assert "image_0_url" not in raw

    def test_max_limit(self):
        raw = {"images": [f"https://img{i}.jpg" for i in range(30)]}
        flatten_images(raw)
        assert raw["image_count"] == MAX_FEED_IMAGES
        assert f"image_{MAX_FEED_IMAGES - 1}_url" in raw
        assert f"image_{MAX_FEED_IMAGES}_url" not in raw

    def test_preserves_original_array(self):
        imgs = ["https://img1.jpg", "https://img2.jpg"]
        raw = {"images": imgs, "title": "Test"}
        flatten_images(raw)
        assert raw["images"] == imgs  # original preserved
        assert raw["title"] == "Test"  # other fields untouched

    def test_skips_none_urls(self):
        raw = {"images": ["https://img1.jpg", None, "", "https://img3.jpg"]}
        flatten_images(raw)
        assert raw["image_0_url"] == "https://img1.jpg"
        assert "image_1_url" not in raw
        assert "image_2_url" not in raw
        assert raw["image_3_url"] == "https://img3.jpg"

    def test_idempotent(self):
        raw = {"images": ["https://img1.jpg", "https://img2.jpg"]}
        flatten_images(raw)
        first_count = raw["image_count"]
        flatten_images(raw)  # second call
        assert raw["image_count"] == first_count
        assert raw["image_0_url"] == "https://img1.jpg"

    def test_woocommerce_integration(self):
        """Test with real WooCommerce _flatten_raw output structure."""
        from app.services.feed_management.connectors.woocommerce_connector import _flatten_raw

        woo = {
            "id": 60837,
            "name": "VW TOURAN",
            "type": "simple",
            "status": "publish",
            "price": "7500",
            "regular_price": "7500",
            "description": "test",
            "short_description": "",
            "sku": "",
            "slug": "vw",
            "permalink": "https://example.com/p",
            "on_sale": False,
            "manage_stock": False,
            "stock_quantity": None,
            "stock_status": "instock",
            "weight": "",
            "purchase_note": "",
            "menu_order": 0,
            "featured": False,
            "categories": [],
            "tags": [],
            "images": [
                {"src": "https://img.test/1.jpg"},
                {"src": "https://img.test/2.jpg"},
                {"src": "https://img.test/3.jpg"},
            ],
            "attributes": [],
            "dimensions": {},
            "meta_data": [],
        }
        raw = _flatten_raw(woo)
        assert raw["image_0_url"] == "https://img.test/1.jpg"
        assert raw["image_1_url"] == "https://img.test/2.jpg"
        assert raw["image_2_url"] == "https://img.test/3.jpg"
        assert raw["image_0_tag"] == "Față"
        assert raw["image_count"] == 3
        assert raw["image_src"] == "https://img.test/1.jpg"  # original still there
        assert len(raw["images"]) == 3  # array preserved
