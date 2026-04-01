from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.enriched_catalog.image_renderer import ImageRenderer


def _make_template(*, width=200, height=100, bg="#FFFFFF", elements=None):
    return {
        "id": "tpl-1",
        "subaccount_id": 1,
        "name": "Test",
        "canvas_width": width,
        "canvas_height": height,
        "background_color": bg,
        "elements": elements or [],
    }


def _png_to_image(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


class TestBasicRender:
    def test_empty_template_produces_png(self):
        renderer = ImageRenderer(_make_template())
        result = renderer.render({})
        img = _png_to_image(result)
        assert img.size == (200, 100)
        assert img.mode == "RGBA"

    def test_background_color(self):
        renderer = ImageRenderer(_make_template(bg="#FF0000"))
        result = renderer.render({})
        img = _png_to_image(result)
        r, g, b, a = img.getpixel((10, 10))
        assert r == 255 and g == 0 and b == 0

    def test_canvas_clamped_to_max(self):
        renderer = ImageRenderer(_make_template(width=5000, height=3000))
        result = renderer.render({})
        img = _png_to_image(result)
        assert img.size == (2000, 2000)


class TestTextRendering:
    def test_static_text_element(self):
        elements = [
            {
                "type": "text",
                "position_x": 10,
                "position_y": 10,
                "content": "Hello World",
                "style": {"color": "#000000", "font_size": 16},
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({})
        img = _png_to_image(result)
        assert img.size == (200, 100)
        # The text changes some pixels from the white background
        assert result != ImageRenderer(_make_template()).render({})


class TestDynamicBinding:
    def test_dynamic_field_resolved(self):
        elements = [
            {
                "type": "dynamic_field",
                "position_x": 10,
                "position_y": 10,
                "dynamic_binding": "{{product_title}}",
                "style": {"color": "#000000", "font_size": 16},
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({"product_title": "Cool Shoes"})
        # Should produce different output than rendering with empty data
        result_empty = renderer.render({})
        assert result != result_empty

    def test_missing_binding_renders_empty(self):
        elements = [
            {
                "type": "dynamic_field",
                "position_x": 10,
                "position_y": 10,
                "dynamic_binding": "{{nonexistent_field}}",
                "style": {"color": "#000000"},
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({"other_field": "value"})
        # Should still produce a valid PNG without crashing
        img = _png_to_image(result)
        assert img.size == (200, 100)

    def test_multiple_bindings_in_one_field(self):
        renderer = ImageRenderer(_make_template())
        resolved = renderer._resolve_dynamic_value("{{brand}} - {{name}}", {"brand": "Nike", "name": "Air"})
        assert resolved == "Nike - Air"


class TestImageElement:
    def test_image_element_with_failed_fetch(self):
        """Image fetch failures are handled gracefully."""
        elements = [
            {
                "type": "image",
                "position_x": 0,
                "position_y": 0,
                "width": 50,
                "height": 50,
                "content": "https://invalid-url.test/image.png",
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({})
        img = _png_to_image(result)
        assert img.size == (200, 100)

    def test_image_element_with_mock_fetch(self):
        """Simulate a successful image fetch via mock."""
        elements = [
            {
                "type": "image",
                "position_x": 0,
                "position_y": 0,
                "width": 50,
                "height": 50,
                "content": "https://example.com/photo.png",
            }
        ]
        # Create a small red test image
        test_img = Image.new("RGBA", (50, 50), "#FF0000")
        buf = io.BytesIO()
        test_img.save(buf, format="PNG")
        test_img_bytes = buf.getvalue()

        mock_resp = MagicMock()
        mock_resp.content = test_img_bytes
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.get", return_value=mock_resp) as mock_get:
            renderer = ImageRenderer(_make_template(elements=elements))
            result = renderer.render({})

        img = _png_to_image(result)
        r, g, b, a = img.getpixel((25, 25))
        assert r == 255 and g == 0 and b == 0


class TestShapeRendering:
    def test_rectangle_shape(self):
        elements = [
            {
                "type": "shape",
                "position_x": 10,
                "position_y": 10,
                "width": 80,
                "height": 40,
                "content": "rectangle",
                "style": {"fill_color": "#0000FF"},
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({})
        img = _png_to_image(result)
        r, g, b, a = img.getpixel((50, 30))
        assert r == 0 and g == 0 and b == 255

    def test_circle_shape(self):
        elements = [
            {
                "type": "shape",
                "position_x": 0,
                "position_y": 0,
                "width": 100,
                "height": 100,
                "style": {"shape_type": "circle", "fill_color": "#00FF00"},
            }
        ]
        renderer = ImageRenderer(_make_template(elements=elements))
        result = renderer.render({})
        img = _png_to_image(result)
        # Center of circle should be green
        r, g, b, a = img.getpixel((50, 50))
        assert g == 255


class TestRenderJobService:
    def test_process_render_job_with_matching_treatment(self):
        from app.services.enriched_catalog.render_job_service import RenderJobService

        uploaded: list[tuple[str, str]] = []

        def fake_upload(key, body, content_type):
            uploaded.append((key, content_type))
            return f"https://bucket.s3.amazonaws.com/{key}"

        fake_feed_service = MagicMock()
        fake_feed_service.get_output_feed.return_value = {"id": "feed-1", "subaccount_id": 1}

        fake_template_repo = MagicMock()
        fake_template_repo.get_by_id.return_value = _make_template()

        fake_treatment_repo = MagicMock()
        fake_treatment_repo.get_matching_treatment.return_value = {"id": "treat-1", "template_id": "tpl-1"}

        service = RenderJobService(
            feed_service=fake_feed_service,
            template_repo=fake_template_repo,
            treatment_repo=fake_treatment_repo,
            upload_fn=fake_upload,
        )

        products = [{"id": "prod-1", "title": "Shoes"}, {"id": "prod-2", "title": "Boots"}]
        result = service.process_render_job("feed-1", products)

        assert result["total_products"] == 2
        assert result["rendered_products"] == 2
        assert len(result["errors"]) == 0
        assert len(uploaded) == 2
        assert uploaded[0] == ("enriched-catalog/feed-1/prod-1.png", "image/png")
        assert result["entries"][0]["enriched_image_url"] == "https://bucket.s3.amazonaws.com/enriched-catalog/feed-1/prod-1.png"

    def test_process_render_job_no_treatment(self):
        from app.services.enriched_catalog.render_job_service import RenderJobService

        fake_feed_service = MagicMock()
        fake_feed_service.get_output_feed.return_value = {"id": "feed-1", "subaccount_id": 1}

        fake_treatment_repo = MagicMock()
        fake_treatment_repo.get_matching_treatment.return_value = None

        service = RenderJobService(
            feed_service=fake_feed_service,
            template_repo=MagicMock(),
            treatment_repo=fake_treatment_repo,
            upload_fn=lambda *a: "",
        )

        result = service.process_render_job("feed-1", [{"id": "p1"}])
        assert result["rendered_products"] == 0
        assert result["entries"][0]["enriched_image_url"] is None


class TestEnrichedFeedBuilder:
    def test_build_and_upload(self):
        from app.services.enriched_catalog.enriched_feed_builder import EnrichedFeedBuilder

        uploaded_data: list[tuple[str, bytes, str]] = []

        def fake_upload(key, body, content_type):
            uploaded_data.append((key, body, content_type))
            return f"https://bucket.s3.amazonaws.com/{key}"

        builder = EnrichedFeedBuilder(upload_fn=fake_upload)
        entries = [
            {"product_id": "p1", "product_data": {"title": "Shoes"}, "enriched_image_url": "https://img/p1.png", "template_id": "t1", "treatment_id": "tr1"},
        ]

        with patch("app.services.enriched_catalog.output_feed_service.output_feed_service") as mock_svc:
            url = builder.build_and_upload("feed-1", entries)

        assert url == "https://bucket.s3.amazonaws.com/enriched-catalog/feed-1/feed.json"
        assert len(uploaded_data) == 1
        key, body, ct = uploaded_data[0]
        assert key == "enriched-catalog/feed-1/feed.json"
        assert ct == "application/json"
        parsed = json.loads(body)
        assert parsed["feed_id"] == "feed-1"
        assert len(parsed["products"]) == 1
        assert parsed["products"][0]["id"] == "p1"
