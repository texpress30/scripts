from __future__ import annotations

import io
import logging
import re
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_BINDING_RE = re.compile(r"\{\{(\w+)\}\}")

_MAX_CANVAS = 2000


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _parse_color(raw: str | None, default: str = "#FFFFFF") -> str:
    if not raw or not isinstance(raw, str):
        return default
    return raw.strip() or default


class ImageRenderer:
    """Renders a CreativeTemplate + product data into a PNG image using Pillow."""

    def __init__(self, template: dict[str, Any]) -> None:
        self._template = template
        self._width = _clamp(int(template.get("canvas_width") or 1080), 1, _MAX_CANVAS)
        self._height = _clamp(int(template.get("canvas_height") or 1080), 1, _MAX_CANVAS)
        self._bg_color = _parse_color(template.get("background_color"), "#FFFFFF")

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
            if element.get("dynamic_binding"):
                url = self._resolve_dynamic_value(element["dynamic_binding"], product_data)
            self._draw_image(canvas, element, url)

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

    def _draw_image(self, canvas: Image.Image, element: dict[str, Any], url: str) -> None:
        if not url:
            return
        x = int(element.get("position_x") or 0)
        y = int(element.get("position_y") or 0)
        w = int(element.get("width") or 0)
        h = int(element.get("height") or 0)

        try:
            import httpx

            timeout = 10.0
            try:
                from app.core.config import load_settings
                timeout = float(load_settings().storage_media_remote_fetch_timeout_seconds or 15)
            except Exception:
                pass

            resp = httpx.get(url, timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            if w > 0 and h > 0:
                img = img.resize((w, h), Image.LANCZOS)
            canvas.paste(img, (x, y), img)
        except Exception:
            logger.warning("Failed to fetch image from %s", url)

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
