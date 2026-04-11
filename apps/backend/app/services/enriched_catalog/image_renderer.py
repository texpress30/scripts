from __future__ import annotations

import hashlib
import io
import logging
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_BINDING_RE = re.compile(r"\{\{(\w+)\}\}")

_MAX_CANVAS = 2000

# Image bindings that we consider "product photos" and therefore want to
# resolve through the cutout pipeline. Any layer whose `dynamic_binding`
# references one of these fields will automatically get its cutout drawn
# in place of the raw source image (when available).
_CUTOUT_IMAGE_BINDINGS: frozenset[str] = frozenset(
    {"image_src", "image", "image_url", "main_image", "primary_image"}
)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _parse_color(raw: str | None, default: str = "#FFFFFF") -> str:
    if not raw or not isinstance(raw, str):
        return default
    return raw.strip() or default


def _fit_contain(source: Image.Image, *, box_w: int, box_h: int) -> Image.Image:
    """Scale ``source`` to fit inside (box_w, box_h) preserving aspect ratio.

    Returns an RGBA image of size (box_w, box_h) with the source centered and
    transparent padding around it. Used for cutouts where stretching the
    product to the raw layer size would distort it (a trimmed cutout has a
    very different aspect ratio from the original layer box).
    """
    if box_w <= 0 or box_h <= 0 or source.width <= 0 or source.height <= 0:
        return source
    ratio = min(box_w / float(source.width), box_h / float(source.height))
    new_w = max(1, int(source.width * ratio))
    new_h = max(1, int(source.height * ratio))
    scaled = source.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    offset = ((box_w - new_w) // 2, (box_h - new_h) // 2)
    canvas.paste(scaled, offset, scaled)
    return canvas


def _fit_cover(source: Image.Image, *, box_w: int, box_h: int) -> Image.Image:
    """Scale and crop ``source`` so it covers (box_w, box_h) fully."""
    if box_w <= 0 or box_h <= 0 or source.width <= 0 or source.height <= 0:
        return source
    ratio = max(box_w / float(source.width), box_h / float(source.height))
    new_w = max(1, int(source.width * ratio))
    new_h = max(1, int(source.height * ratio))
    scaled = source.resize((new_w, new_h), Image.LANCZOS)
    left = max(0, (new_w - box_w) // 2)
    top = max(0, (new_h - box_h) // 2)
    return scaled.crop((left, top, left + box_w, top + box_h))


class ImageRenderer:
    """Renders a CreativeTemplate + product data into a PNG image using Pillow."""

    def __init__(
        self,
        template: dict[str, Any],
        *,
        client_id: int | None = None,
    ) -> None:
        self._template = template
        self._width = _clamp(int(template.get("canvas_width") or 1080), 1, _MAX_CANVAS)
        self._height = _clamp(int(template.get("canvas_height") or 1080), 1, _MAX_CANVAS)
        self._bg_color = _parse_color(template.get("background_color"), "#FFFFFF")
        self._client_id = int(client_id) if client_id else None

    def render(self, product_data: dict[str, Any]) -> bytes:
        canvas = Image.new("RGBA", (self._width, self._height), self._bg_color)
        draw = ImageDraw.Draw(canvas)

        for element in list(self._template.get("elements") or []):
            if not isinstance(element, dict):
                continue
            try:
                self._draw_element(canvas, draw, element, product_data)
            except Exception:
                logger.exception("Failed to draw element %s", element.get("type"))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    # -- element dispatch -----------------------------------------------------

    def _draw_element(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        element: dict[str, Any],
        product_data: dict[str, Any],
    ) -> None:
        el_type = str(element.get("type") or "")

        if el_type == "text":
            text = str(element.get("content") or "")
            self._draw_text(draw, element, text)

        elif el_type == "dynamic_field":
            binding = element.get("dynamic_binding") or ""
            resolved = self._resolve_dynamic_value(binding, product_data)
            self._draw_text(draw, element, resolved)

        elif el_type == "image":
            url = str(element.get("content") or "")
            binding = str(element.get("dynamic_binding") or "")
            if binding:
                url = self._resolve_dynamic_value(binding, product_data)
            is_product_photo = self._is_product_photo_binding(binding)
            self._draw_image(canvas, element, url, is_product_photo=is_product_photo)

        elif el_type == "shape":
            self._draw_shape(draw, element)

    # -- dynamic binding ------------------------------------------------------

    @staticmethod
    def _resolve_dynamic_value(binding: str, product_data: dict[str, Any]) -> str:
        def _replacer(match: re.Match) -> str:
            field_name = match.group(1)
            return str(product_data.get(field_name) or "")

        return _BINDING_RE.sub(_replacer, str(binding))

    # -- drawing helpers ------------------------------------------------------

    def _draw_text(self, draw: ImageDraw.Draw, element: dict[str, Any], text: str) -> None:
        if not text:
            return
        x = float(element.get("position_x") or 0)
        y = float(element.get("position_y") or 0)
        style = element.get("style") or {}
        color = _parse_color(style.get("color"), "#000000")
        font_size = int(style.get("font_size") or 16)

        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        draw.text((x, y), text, fill=color, font=font)

    def _draw_image(
        self,
        canvas: Image.Image,
        element: dict[str, Any],
        url: str,
        *,
        is_product_photo: bool = False,
    ) -> None:
        if not url:
            return
        x = int(element.get("position_x") or 0)
        y = int(element.get("position_y") or 0)
        w = int(element.get("width") or 0)
        h = int(element.get("height") or 0)

        # `image_fit` controls how the source image is laid into the layer box.
        # Defaults to `contain` for product photos (so cutouts don't distort)
        # and `stretch` for static/decorative images to preserve legacy behavior.
        default_fit = "contain" if is_product_photo else "stretch"
        image_fit = str(element.get("image_fit") or default_fit).lower()

        # For product-photo bindings we prefer the background-removed cutout.
        # Fast path: look up by URL hash (no download needed) — populated
        # whenever the priming / sync-delta pipeline has processed this URL.
        # Slow path: download once, hash the bytes and check content hash.
        img: Image.Image
        try:
            cutout_url: str | None = None
            if is_product_photo and self._client_id:
                cutout_url = self._resolve_cutout_url_by_url(url)
                if cutout_url:
                    img = self._fetch_image(cutout_url)
                else:
                    raw_bytes = self._fetch_bytes(url)
                    cutout_url = self._resolve_cutout_url_from_bytes(raw_bytes)
                    if cutout_url:
                        img = self._fetch_image(cutout_url)
                    else:
                        img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
            else:
                img = self._fetch_image(url)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to fetch image from %s", url)
            return

        if w > 0 and h > 0:
            if image_fit == "cover":
                img = _fit_cover(img, box_w=w, box_h=h)
            elif image_fit == "stretch":
                img = img.resize((w, h), Image.LANCZOS)
            else:
                img = _fit_contain(img, box_w=w, box_h=h)

        canvas.paste(img, (x, y), img)

    def _fetch_image(self, url: str) -> Image.Image:
        return Image.open(io.BytesIO(self._fetch_bytes(url))).convert("RGBA")

    def _fetch_bytes(self, url: str) -> bytes:
        import httpx

        timeout = 10.0
        try:
            from app.core.config import load_settings

            timeout = float(load_settings().storage_media_remote_fetch_timeout_seconds or 15)
        except Exception:  # noqa: BLE001
            pass
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _is_product_photo_binding(binding: str) -> bool:
        if not binding:
            return False
        # Extract the first `{{field}}` token from the binding string.
        match = _BINDING_RE.search(binding)
        if match is None:
            return False
        return match.group(1).lower() in _CUTOUT_IMAGE_BINDINGS

    def _resolve_cutout_url_by_url(self, source_url: str) -> str | None:
        """Fast path: check the URL-hash index on ``image_cutouts``.

        Populated whenever ``cutout_service.ensure_cutout`` runs for this URL,
        so this is a cheap O(1) lookup that avoids downloading the source
        bytes at all when the renderer is called repeatedly for the same
        product.
        """
        if not source_url or not self._client_id:
            return None
        try:
            from app.services.enriched_catalog import cutout_service

            record = cutout_service.lookup_ready_cutout_by_url(
                int(self._client_id), source_url
            )
            if record and record.image_url:
                return record.image_url
        except Exception:  # noqa: BLE001
            logger.debug("cutout_url_lookup_failed", exc_info=True)
        return None

    def _resolve_cutout_url_from_bytes(self, raw_bytes: bytes) -> str | None:
        """Hash the downloaded bytes and look up a ready cutout record.

        This is purely opportunistic — if the dedup entry exists and is
        ``ready`` we return the cutout's S3 URL so the renderer can paste a
        transparent-background PNG instead of the raw photo. Otherwise we
        return ``None`` and the caller falls back to the original image.
        """
        if not raw_bytes or not self._client_id:
            return None
        try:
            from app.services.enriched_catalog import cutout_service

            source_hash = hashlib.sha256(raw_bytes).hexdigest()
            record = cutout_service.lookup_ready_cutout(int(self._client_id), source_hash)
            if record and record.image_url:
                return record.image_url
        except Exception:  # noqa: BLE001
            logger.debug("cutout_lookup_failed", exc_info=True)
        return None

    def _draw_shape(self, draw: ImageDraw.Draw, element: dict[str, Any]) -> None:
        x = float(element.get("position_x") or 0)
        y = float(element.get("position_y") or 0)
        w = float(element.get("width") or 0)
        h = float(element.get("height") or 0)
        style = element.get("style") or {}
        fill = _parse_color(style.get("fill_color") or style.get("color"), "#CCCCCC")
        shape_type = str(style.get("shape_type") or element.get("content") or "rectangle")

        if shape_type == "circle" or shape_type == "ellipse":
            draw.ellipse([x, y, x + w, y + h], fill=fill)
        else:
            draw.rectangle([x, y, x + w, y + h], fill=fill)
