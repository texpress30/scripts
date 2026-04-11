from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.services.enriched_catalog import render_cache
from app.services.enriched_catalog.image_renderer import ImageRenderer
from app.services.enriched_catalog.multi_format_renderer import _bridge_render_to_media_library
from app.services.enriched_catalog.output_feed_service import output_feed_service
from app.services.enriched_catalog.repository import creative_template_repository, treatment_repository

logger = logging.getLogger(__name__)

RENDER_BATCH_CHUNK_SIZE = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _upload_to_s3(key: str, body: bytes, content_type: str) -> str:
    """Upload bytes to S3 using the existing s3_provider and return the object URL."""
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


class RenderJobService:
    """Orchestrates rendering all products in an output feed and uploading to S3."""

    def __init__(
        self,
        feed_service=None,
        template_repo=None,
        treatment_repo=None,
        upload_fn=None,
    ) -> None:
        self._feed_service = feed_service or output_feed_service
        self._template_repo = template_repo or creative_template_repository
        self._treatment_repo = treatment_repo or treatment_repository
        self._upload = upload_fn or _upload_to_s3

    def process_render_job(self, output_feed_id: str, products: list[dict[str, Any]]) -> dict[str, Any]:
        """Render all products, upload PNGs to S3, return enriched entries."""
        feed = self._feed_service.get_output_feed(output_feed_id)
        total = len(products)
        rendered_count = 0
        errors: list[dict[str, str]] = []
        entries: list[dict[str, Any]] = []

        feed_subaccount_id: int | None = None
        feed_name = ""
        try:
            feed_subaccount_id = int(feed.get("subaccount_id")) if feed and feed.get("subaccount_id") else None
            feed_name = str((feed or {}).get("name") or "").strip()
        except Exception:  # noqa: BLE001
            feed_subaccount_id = None

        # Cache templates by id to avoid repeated lookups
        template_cache: dict[str, dict[str, Any] | None] = {}

        for idx, product in enumerate(products):
            product_id = str(product.get("id") or product.get("product_id") or f"product_{idx}")
            try:
                treatment = self._treatment_repo.get_matching_treatment(output_feed_id, product)
                if treatment is None:
                    entries.append({
                        "product_id": product_id,
                        "product_data": product,
                        "template_id": None,
                        "treatment_id": None,
                        "enriched_image_url": None,
                    })
                    continue

                template_id = treatment.get("template_id") or ""
                if template_id not in template_cache:
                    template_cache[template_id] = self._template_repo.get_by_id(template_id)
                template = template_cache[template_id]

                if template is None:
                    entries.append({
                        "product_id": product_id,
                        "product_data": product,
                        "template_id": template_id,
                        "treatment_id": treatment.get("id"),
                        "enriched_image_url": None,
                    })
                    errors.append({"product_id": product_id, "error": f"Template {template_id} not found"})
                    continue

                renderer = ImageRenderer(template, client_id=feed_subaccount_id)
                png_bytes = renderer.render(product)
                s3_key = f"enriched-catalog/{output_feed_id}/{product_id}.png"
                image_url = self._upload(s3_key, png_bytes, "image/png")
                rendered_count += 1

                format_label = (
                    (template or {}).get("format_label")
                    or f"{(template or {}).get('canvas_width')}x{(template or {}).get('canvas_height')}"
                )
                _bridge_render_to_media_library(
                    subaccount_id=feed_subaccount_id,
                    feed_name=feed_name,
                    output_feed_id=str(output_feed_id),
                    template_id=str(template_id),
                    product_id=product_id,
                    format_label=str(format_label or ""),
                    s3_key=s3_key,
                    image_url=image_url,
                )

                entries.append({
                    "product_id": product_id,
                    "product_data": product,
                    "template_id": template_id,
                    "treatment_id": treatment.get("id"),
                    "enriched_image_url": image_url,
                })
            except Exception as exc:
                logger.exception("Failed to render product %s", product_id)
                errors.append({"product_id": product_id, "error": str(exc)})
                entries.append({
                    "product_id": product_id,
                    "product_data": product,
                    "template_id": None,
                    "treatment_id": None,
                    "enriched_image_url": None,
                })

        return {
            "output_feed_id": output_feed_id,
            "total_products": total,
            "rendered_products": rendered_count,
            "errors": errors,
            "entries": entries,
        }

    def run_render_background(self, output_feed_id: str, products: list[dict[str, Any]]) -> None:
        """Background wrapper — logs result/exception, never re-raises."""
        try:
            result = self.process_render_job(output_feed_id, products)
            logger.info(
                "Render job completed for feed %s: rendered=%d/%d errors=%d",
                output_feed_id,
                result["rendered_products"],
                result["total_products"],
                len(result["errors"]),
            )
            # Build and upload the enriched feed JSON
            enriched_feed_builder.build_and_upload(output_feed_id, result["entries"])

            # Update output feed status
            self._feed_service.update_output_feed(output_feed_id, {"status": "published"})
        except Exception:
            logger.exception("Render job crashed for feed %s", output_feed_id)
            try:
                self._feed_service.update_output_feed(output_feed_id, {"status": "failed"})
            except Exception:
                logger.exception("Failed to update feed status after crash")

    # ------------------------------------------------------------------
    # Async dispatch
    # ------------------------------------------------------------------

    def dispatch_render_job(
        self,
        output_feed_id: str,
        products: list[dict[str, Any]],
        *,
        priority: str = "bulk",
    ) -> dict[str, Any]:
        """Enqueue a render job on the Celery workers instead of running it
        inline.

        The request thread returns immediately with a summary of what was
        dispatched. For ``priority="hi"`` (editor / grid on-demand) each
        product becomes a ``render_one`` task on the ``render_hi`` queue. For
        ``priority="bulk"`` (Publish) products are chunked into
        ``render_batch`` tasks on ``render_bulk``.

        This path consults the template_render_results cache and only
        enqueues tasks for products whose preview is stale. A 100k-product
        feed therefore triggers ~0 tasks on a re-publish if nothing changed.
        """
        if not products:
            return {
                "output_feed_id": output_feed_id,
                "dispatched": 0,
                "cache_hits": 0,
                "chunks": 0,
                "priority": priority,
            }

        # Resolve which template each product maps to via treatments.
        template_cache: dict[str, dict[str, Any] | None] = {}
        buckets: dict[str, list[dict[str, Any]]] = {}
        skipped_no_match = 0
        for product in products:
            treatment = self._treatment_repo.get_matching_treatment(output_feed_id, product)
            if treatment is None:
                skipped_no_match += 1
                continue
            template_id = str(treatment.get("template_id") or "")
            if not template_id:
                skipped_no_match += 1
                continue
            if template_id not in template_cache:
                template_cache[template_id] = self._template_repo.get_by_id(template_id)
            if template_cache[template_id] is None:
                skipped_no_match += 1
                continue
            buckets.setdefault(template_id, []).append(product)

        dispatched = 0
        cache_hits = 0
        chunks = 0

        # Celery is imported lazily so unit tests can exercise the planning
        # logic without pulling in the full worker stack.
        try:
            from app.workers.tasks.render import render_batch, render_one
        except Exception:  # noqa: BLE001
            logger.exception("render_tasks_unavailable")
            render_batch = None
            render_one = None

        for template_id, bucket_products in buckets.items():
            template = template_cache[template_id] or {}
            template_version = int(template.get("version") or 1)
            product_ids = [
                str(p.get("id") or p.get("product_id") or "")
                for p in bucket_products
            ]
            cached = render_cache.get_many(
                template_id=template_id,
                template_version=template_version,
                output_feed_id=output_feed_id,
                product_ids=product_ids,
            )
            stale = [
                p
                for p, pid in zip(bucket_products, product_ids)
                if pid and pid not in cached
            ]
            cache_hits += len(cached)

            if priority == "hi" and render_one is not None:
                for product in stale:
                    render_one.apply_async(
                        kwargs={
                            "template_id": template_id,
                            "output_feed_id": str(output_feed_id),
                            "product": product,
                        },
                        queue="render_hi",
                    )
                    dispatched += 1
            elif render_batch is not None:
                for chunk in _chunked(stale, RENDER_BATCH_CHUNK_SIZE):
                    render_batch.apply_async(
                        kwargs={
                            "template_id": template_id,
                            "output_feed_id": str(output_feed_id),
                            "products": list(chunk),
                        },
                        queue="render_bulk",
                    )
                    chunks += 1
                    dispatched += len(chunk)

        logger.info(
            "render_dispatch output_feed_id=%s priority=%s dispatched=%s cache_hits=%s skipped=%s",
            output_feed_id,
            priority,
            dispatched,
            cache_hits,
            skipped_no_match,
        )
        return {
            "output_feed_id": output_feed_id,
            "priority": priority,
            "dispatched": int(dispatched),
            "cache_hits": int(cache_hits),
            "skipped_no_match": int(skipped_no_match),
            "chunks": int(chunks),
        }


def _chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


render_job_service = RenderJobService()

# Late import to avoid circular dependency
from app.services.enriched_catalog.enriched_feed_builder import enriched_feed_builder  # noqa: E402
