"""Smoke tests for the cutout service.

Focus on the pure image-processing primitives — alpha detection, tight
cropping and resize. The DB / S3 / rembg integration paths are tested by
the Celery task module separately (see ``test_bg_removal_task``).
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.services.enriched_catalog import cutout_service


def _make_rgba(size: tuple[int, int], border_alpha: int, center_alpha: int) -> Image.Image:
    """Build a test image where the outer ring has ``border_alpha`` and the
    interior has ``center_alpha`` so the alpha-detector can be exercised.
    """
    img = Image.new("RGBA", size, (255, 0, 0, center_alpha))
    # Paint the outermost pixel ring with the border alpha.
    pixels = img.load()
    w, h = size
    for x in range(w):
        pixels[x, 0] = (255, 0, 0, border_alpha)
        pixels[x, h - 1] = (255, 0, 0, border_alpha)
    for y in range(h):
        pixels[0, y] = (255, 0, 0, border_alpha)
        pixels[w - 1, y] = (255, 0, 0, border_alpha)
    return img


class TestHasUsableAlpha:
    def test_rgb_image_rejected(self):
        img = Image.new("RGB", (40, 40), (255, 0, 0))
        assert cutout_service.has_usable_alpha(img) is False

    def test_fully_opaque_rgba_rejected(self):
        img = Image.new("RGBA", (40, 40), (255, 0, 0, 255))
        assert cutout_service.has_usable_alpha(img) is False

    def test_transparent_border_accepted(self):
        img = _make_rgba((40, 40), border_alpha=0, center_alpha=255)
        assert cutout_service.has_usable_alpha(img) is True

    def test_mostly_opaque_border_rejected(self):
        # Only one pixel on the border is transparent — below the 2% threshold.
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        img.putpixel((0, 0), (0, 0, 0, 0))
        assert cutout_service.has_usable_alpha(img) is False


class TestTightCropAlpha:
    def test_crop_returns_bbox_of_opaque_region(self):
        # Build a 200x200 canvas with a 20x30 opaque patch at (50, 60).
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        patch = Image.new("RGBA", (20, 30), (255, 255, 255, 255))
        img.paste(patch, (50, 60))

        cropped, bbox = cutout_service.tight_crop_alpha(img, padding=0)
        assert bbox == (50, 60, 70, 90)
        assert cropped.size == (20, 30)

    def test_crop_adds_padding(self):
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        patch = Image.new("RGBA", (40, 40), (255, 255, 255, 255))
        img.paste(patch, (80, 80))
        cropped, bbox = cutout_service.tight_crop_alpha(img, padding=4)
        # Padded bounds stay inside the canvas.
        assert bbox == (76, 76, 124, 124)
        assert cropped.size == (48, 48)

    def test_fully_transparent_returns_unmodified(self):
        img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        cropped, bbox = cutout_service.tight_crop_alpha(img, padding=0)
        assert bbox is None
        assert cropped.size == (50, 50)


class TestResizeToMax:
    def test_resize_scales_down_preserving_ratio(self):
        img = Image.new("RGBA", (4000, 2000), (0, 0, 0, 255))
        out = cutout_service.resize_to_max(img, max_edge=2048)
        assert out.size == (2048, 1024)

    def test_resize_noop_for_small_image(self):
        img = Image.new("RGBA", (300, 400), (0, 0, 0, 255))
        out = cutout_service.resize_to_max(img, max_edge=2048)
        assert out.size == (300, 400)


class TestUrlHash:
    def test_url_hash_is_stable(self):
        a = cutout_service._url_hash("https://example.com/image.png")
        b = cutout_service._url_hash("https://example.com/image.png")
        assert a == b
        assert len(a) == 64  # hex SHA-256

    def test_different_urls_hash_differently(self):
        assert cutout_service._url_hash("https://a") != cutout_service._url_hash("https://b")
