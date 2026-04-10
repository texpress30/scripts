"""Smart format adaptation — reposition/resize elements for different canvas dimensions.

Adapts elements from a source canvas size to a target canvas size while
preserving visual hierarchy and readability.

Strategy:
  1. Compute uniform scale = min(target_w / source_w, target_h / source_h)
  2. Scale all positions and sizes by this factor (preserves proportions)
  3. Center the scaled layout within the target canvas
  4. Scale font sizes proportionally (clamped to min 8px)
  5. Clamp all elements to canvas bounds
"""

from __future__ import annotations

import copy
import uuid
from typing import Any


_MIN_FONT_SIZE = 8
_MAX_FONT_SIZE = 200


def adapt_elements(
    *,
    source_elements: list[dict[str, Any]],
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
    background_color: str = "#FFFFFF",
) -> dict[str, Any]:
    """Adapt elements from source canvas to target canvas dimensions.

    Returns dict with adapted elements list and metadata.
    """
    if source_width <= 0 or source_height <= 0 or target_width <= 0 or target_height <= 0:
        return {
            "elements": source_elements,
            "target_width": target_width,
            "target_height": target_height,
            "scale_factor": 1.0,
        }

    scale_x = target_width / source_width
    scale_y = target_height / source_height
    uniform_scale = min(scale_x, scale_y)

    # Compute the bounding box of all scaled elements to center them
    scaled_content_width = source_width * uniform_scale
    scaled_content_height = source_height * uniform_scale
    offset_x = (target_width - scaled_content_width) / 2
    offset_y = (target_height - scaled_content_height) / 2

    adapted: list[dict[str, Any]] = []
    for src_el in source_elements:
        if not isinstance(src_el, dict):
            continue
        el = copy.deepcopy(src_el)

        # Generate new element_id to avoid conflicts, but keep a reference
        el["element_id"] = el.get("element_id") or str(uuid.uuid4())

        # Scale position
        el["position_x"] = round(float(el.get("position_x") or 0) * uniform_scale + offset_x, 1)
        el["position_y"] = round(float(el.get("position_y") or 0) * uniform_scale + offset_y, 1)

        # Scale size
        el["width"] = round(float(el.get("width") or 0) * uniform_scale, 1)
        el["height"] = round(float(el.get("height") or 0) * uniform_scale, 1)

        # Scale font size for text elements
        el_type = str(el.get("type") or "")
        if el_type in ("text", "dynamic_field"):
            style = dict(el.get("style") or {})
            font_size = float(style.get("font_size") or 16)
            scaled_font = round(font_size * uniform_scale)
            style["font_size"] = max(_MIN_FONT_SIZE, min(_MAX_FONT_SIZE, scaled_font))
            el["style"] = style

        # Clamp to canvas bounds
        el["position_x"] = max(0, min(float(el["position_x"]), target_width - max(1, float(el.get("width") or 1))))
        el["position_y"] = max(0, min(float(el["position_y"]), target_height - max(1, float(el.get("height") or 1))))

        adapted.append(el)

    return {
        "elements": adapted,
        "target_width": target_width,
        "target_height": target_height,
        "background_color": background_color,
        "scale_factor": round(uniform_scale, 4),
    }
