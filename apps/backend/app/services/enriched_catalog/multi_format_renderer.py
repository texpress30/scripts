"""Multi-format bulk generation service.

Renders products across multiple template formats in a single batch job,
uploads results to S3, and optionally notifies a webhook URL on completion.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _upload_to_s3(key: str, body: bytes, content_type: str) -> str:
    from app.services.s3_provider import get_s3_client, get_s3_bucket_name

    bucket = get_s3_bucket_name()
    s3 = get_s3_client()
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    region = ""
    try:
        from app.core.config import load_settings
        region = load_settings().storage_s3_region or ""
    except Exception:
        pass
    if region:
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return f"https://{bucket}.s3.amazonaws.com/{key}"


def _send_webhook(url: str, payload: dict[str, Any]) -> None:
    """POST webhook notification. Best-effort, never raises."""
    try:
        import httpx
        httpx.post(url, json=payload, timeout=15.0)
        logger.info("Webhook sent to %s", url)
    except Exception:
        logger.warning("Webhook delivery failed for %s", url, exc_info=True)


class MultiFormatRenderService:
    """Renders products across multiple templates (format group) in one batch."""

    def __init__(self, upload_fn=None) -> None:
        self._upload = upload_fn or _upload_to_s3

    def render_multi_format(
        self,
        *,
        output_feed_id: str,
        template_ids: list[str],
        products: list[dict[str, Any]],
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """Render all products x all templates, upload PNGs, return summary."""
        from app.services.enriched_catalog.image_renderer import ImageRenderer
        from app.services.enriched_catalog.repository import creative_template_repository

        started_at = _utcnow()
        format_results: list[dict[str, Any]] = []
        total_rendered = 0
        total_errors: list[dict[str, str]] = []

        for template_id in template_ids:
            template = creative_template_repository.get_by_id(template_id)
            if template is None:
                total_errors.append({"template_id": template_id, "error": "Template not found"})
                continue

            format_label = template.get("format_label") or f"{template.get('canvas_width')}x{template.get('canvas_height')}"
            renderer = ImageRenderer(template)
            format_rendered = 0
            format_entries: list[dict[str, Any]] = []

            for idx, product in enumerate(products):
                product_id = str(product.get("id") or product.get("product_id") or f"product_{idx}")
                try:
                    png_bytes = renderer.render(product)
                    s3_key = f"enriched-catalog/{output_feed_id}/{template_id}/{product_id}.png"
                    image_url = self._upload(s3_key, png_bytes, "image/png")
                    format_rendered += 1
                    format_entries.append({
                        "product_id": product_id,
                        "template_id": template_id,
                        "format_label": format_label,
                        "enriched_image_url": image_url,
                    })
                except Exception as exc:
                    logger.warning("Failed to render product %s with template %s: %s", product_id, template_id, exc)
                    total_errors.append({
                        "product_id": product_id,
                        "template_id": template_id,
                        "error": str(exc),
                    })

            total_rendered += format_rendered
            format_results.append({
                "template_id": template_id,
                "format_label": format_label,
                "canvas_width": template.get("canvas_width"),
                "canvas_height": template.get("canvas_height"),
                "rendered_count": format_rendered,
                "entries": format_entries,
            })

        completed_at = _utcnow()
        summary = {
            "output_feed_id": output_feed_id,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round((completed_at - started_at).total_seconds(), 1),
            "total_templates": len(template_ids),
            "total_products": len(products),
            "total_rendered": total_rendered,
            "total_errors": len(total_errors),
            "formats": format_results,
            "errors": total_errors[:50],  # cap error list
        }

        # Upload summary JSON to S3
        summary_key = f"enriched-catalog/{output_feed_id}/multi-format-summary.json"
        self._upload(summary_key, json.dumps(summary, default=str).encode("utf-8"), "application/json")

        # Send webhook if configured
        if webhook_url:
            _send_webhook(webhook_url, {
                "event": "multi_format_render_complete",
                "output_feed_id": output_feed_id,
                "total_rendered": total_rendered,
                "total_errors": len(total_errors),
                "total_templates": len(template_ids),
                "total_products": len(products),
                "duration_seconds": summary["duration_seconds"],
                "completed_at": completed_at.isoformat(),
            })

        return summary


multi_format_render_service = MultiFormatRenderService()
