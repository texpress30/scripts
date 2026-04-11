"""Celery tasks for rendering creative previews.

Two kinds of tasks:

* ``render_one`` — synchronous single-product render used by the editor and
  preview grid. Runs on the ``render_hi`` queue. Checks the
  ``template_render_results`` cache first; only does the real Pillow work on
  a miss.
* ``render_batch`` — bulk renderer used when publishing a full feed. Runs on
  ``render_bulk`` and is enqueued as a Celery chord so the caller can wait on
  all results and then trigger ``enriched_feed_builder.build_and_upload``.

Both tasks share the same inner primitive (``_render_and_store``) so the cache
write, media-library bridge and Postgres upsert stay consistent across paths.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inner primitive
# ---------------------------------------------------------------------------


def _render_and_store(
    *,
    template_id: str,
    output_feed_id: str,
    product: dict[str, Any],
) -> dict[str, Any]:
    from app.services.enriched_catalog import render_cache
    from app.services.enriched_catalog.image_renderer import ImageRenderer
    from app.services.enriched_catalog.multi_format_renderer import _bridge_render_to_media_library
    from app.services.enriched_catalog.output_feed_service import output_feed_service
    from app.services.enriched_catalog.repository import creative_template_repository
    from app.services.s3_provider import get_s3_bucket_name, get_s3_client

    template = creative_template_repository.get_by_id(template_id)
    if template is None:
        raise RuntimeError(f"template not found: {template_id}")

    template_version = int(template.get("version") or 1)
    product_id = str(product.get("id") or product.get("product_id") or "unknown")

    # Cache hit short-circuit.
    cached = render_cache.get_result(
        template_id=template_id,
        template_version=template_version,
        output_feed_id=output_feed_id,
        product_id=product_id,
    )
    if cached is not None and cached.status == "ready":
        return cached.to_dict()

    # Resolve sub-account context for the media bridge.
    feed = output_feed_service.get_output_feed(output_feed_id)
    feed_subaccount_id: int | None = None
    feed_name = ""
    try:
        feed_subaccount_id = int(feed.get("subaccount_id")) if feed and feed.get("subaccount_id") else None
        feed_name = str((feed or {}).get("name") or "").strip()
    except Exception:  # noqa: BLE001
        feed_subaccount_id = None

    renderer = ImageRenderer(template, client_id=feed_subaccount_id)
    png_bytes = renderer.render(product)

    s3_key = (
        f"enriched-catalog/{output_feed_id}/previews/"
        f"{template_id}/{template_version}/{product_id}.png"
    )
    bucket = get_s3_bucket_name()
    s3 = get_s3_client()
    s3.put_object(Bucket=bucket, Key=s3_key, Body=png_bytes, ContentType="image/png")

    # Build a stable URL using either the CDN or the bucket origin.
    image_url = _build_public_url(bucket, s3_key)

    # Best-effort bridge into Stocare Media so the preview also shows up in
    # the client's media library.
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

    render_cache.upsert_result(
        template_id=template_id,
        template_version=template_version,
        output_feed_id=output_feed_id,
        product_id=product_id,
        s3_key=s3_key,
        image_url=image_url,
    )

    return {
        "template_id": template_id,
        "template_version": template_version,
        "output_feed_id": output_feed_id,
        "product_id": product_id,
        "s3_key": s3_key,
        "image_url": image_url,
        "status": "ready",
    }


def _build_public_url(bucket: str, key: str) -> str:
    try:
        from app.core.config import load_settings

        settings = load_settings()
        cdn = str(settings.storage_cdn_base_url or "").strip()
        region = str(settings.storage_s3_region or "").strip()
    except Exception:  # noqa: BLE001
        cdn = ""
        region = ""
    if cdn:
        return f"{cdn.rstrip('/')}/{key}"
    if region:
        return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return f"https://{bucket}.s3.amazonaws.com/{key}"


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    name="app.workers.tasks.render.render_one",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def render_one(
    self,
    *,
    template_id: str,
    output_feed_id: str,
    product: dict[str, Any],
) -> dict[str, Any]:
    logger.info(
        "render_one_start template_id=%s product=%s task_id=%s",
        template_id,
        product.get("id") or product.get("product_id"),
        getattr(self.request, "id", None),
    )
    return _render_and_store(
        template_id=template_id,
        output_feed_id=output_feed_id,
        product=product,
    )


@celery_app.task(
    name="app.workers.tasks.render.render_batch",
    bind=True,
)
def render_batch(
    self,
    *,
    template_id: str,
    output_feed_id: str,
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    """Render a chunk of products in one worker.

    We intentionally render sequentially inside the task to keep a single
    rembg session warm. Parallelism is achieved by dispatching many
    ``render_batch`` tasks (one per chunk) in a Celery chord from
    ``render_job_service.process_render_job``.
    """
    rendered = 0
    failed: list[dict[str, str]] = []
    entries: list[dict[str, Any]] = []
    for product in products:
        try:
            entry = _render_and_store(
                template_id=template_id,
                output_feed_id=output_feed_id,
                product=product,
            )
            entries.append(entry)
            rendered += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "render_batch_item_failed template_id=%s product_id=%s",
                template_id,
                product.get("id") or product.get("product_id"),
            )
            failed.append(
                {
                    "product_id": str(product.get("id") or product.get("product_id") or ""),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "template_id": template_id,
        "output_feed_id": output_feed_id,
        "rendered": rendered,
        "failed": failed,
        "entries": entries,
    }


@celery_app.task(
    name="app.workers.tasks.render.invalidate_and_rerender",
    bind=True,
)
def invalidate_and_rerender(
    self,
    *,
    template_id: str,
    output_feed_id: str,
    product: dict[str, Any],
) -> dict[str, Any]:
    """Fan-out task emitted by the BG removal pipeline.

    After a cutout becomes ``ready`` any cached preview for that product is
    stale (it was rendered with the raw image). Drop the entry and re-render
    on the high-priority queue so the grid shows the cutout version next time.
    """
    from app.services.enriched_catalog import render_cache

    product_id = str(product.get("id") or product.get("product_id") or "unknown")
    render_cache.invalidate_by_product(output_feed_id=output_feed_id, product_id=product_id)
    return _render_and_store(
        template_id=template_id,
        output_feed_id=output_feed_id,
        product=product,
    )
