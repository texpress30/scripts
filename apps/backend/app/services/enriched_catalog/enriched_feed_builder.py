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


class EnrichedFeedBuilder:
    """Builds the final enriched feed JSON and uploads it to S3."""

    def __init__(self, upload_fn=None) -> None:
        self._upload = upload_fn or _upload_to_s3

    def build_and_upload(self, output_feed_id: str, entries: list[dict[str, Any]]) -> str:
        """Build feed JSON from rendered entries and upload to S3. Returns the feed URL."""
        feed_data = {
            "feed_id": output_feed_id,
            "generated_at": _utcnow().isoformat(),
            "total": len(entries),
            "products": [
                {
                    "id": entry.get("product_id") or "",
                    "title": str((entry.get("product_data") or {}).get("title") or (entry.get("product_data") or {}).get("name") or ""),
                    "enriched_image_url": entry.get("enriched_image_url"),
                    "template_id": entry.get("template_id"),
                    "treatment_id": entry.get("treatment_id"),
                    "original_data": entry.get("product_data") or {},
                }
                for entry in entries
            ],
        }

        json_bytes = json.dumps(feed_data, ensure_ascii=False, indent=2).encode("utf-8")
        s3_key = f"enriched-catalog/{output_feed_id}/feed.json"
        url = self._upload(s3_key, json_bytes, "application/json")

        logger.info("Uploaded enriched feed JSON to %s (%d products)", s3_key, len(entries))

        # Update the output feed with the enriched_feed_url
        try:
            from app.services.enriched_catalog.output_feed_service import output_feed_service
            output_feed_service.update_output_feed(output_feed_id, {"enriched_feed_url": url})
        except Exception:
            logger.exception("Failed to update enriched_feed_url for %s", output_feed_id)

        return url


enriched_feed_builder = EnrichedFeedBuilder()
