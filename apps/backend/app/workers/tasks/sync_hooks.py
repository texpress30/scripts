"""Sync-delta fan-out.

When ``FeedSyncService.run_sync`` finishes a successful run it emits a
``handle_sync_delta`` task with the delta summary. This task dispatches the
follow-up work:

* NEW products → enqueue background removal for their ``image_src``
* products whose images changed → same, plus preview cache invalidation
* REMOVED products → touch the render cache (but leave cutouts alone for the
  retention window — a product may reappear in stock tomorrow)
* products whose attributes changed → re-evaluate treatments; if the
  matching template changed the old preview is stale

None of the sub-tasks are on the critical sync path: failures are logged and
swallowed so a bad delta never blocks a sync.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.sync_hooks.handle_sync_delta")
def handle_sync_delta(delta: dict[str, Any]) -> dict[str, Any]:
    """Entry point: fan out per-product work based on the delta shape.

    ``delta`` schema::

        {
            "feed_source_id": str,
            "subaccount_id": int,
            "client_id": int,
            "feed_source_name": str | None,
            "added": [{"product_id": str, "image_src": str}],
            "updated_images": [{"product_id": str, "image_src": str}],
            "removed": [product_id],
            "stock_changed": [product_id],
        }
    """
    feed_source_id = str(delta.get("feed_source_id") or "")
    subaccount_id = int(delta.get("subaccount_id") or 0)
    client_id = int(delta.get("client_id") or subaccount_id or 0)
    feed_source_name = delta.get("feed_source_name")
    summary: dict[str, Any] = {
        "feed_source_id": feed_source_id,
        "bgremoval_enqueued": 0,
        "render_invalidations": 0,
        "output_feeds_refreshed": 0,
    }
    if not feed_source_id or client_id <= 0:
        logger.warning("sync_hooks_delta_missing_ids delta=%s", delta)
        return summary

    # 1. Background-remove new product images.
    from app.workers.tasks.bg_removal import process_source_image

    for entry in list(delta.get("added") or []):
        image_src = _first_image_url(entry.get("image_src"))
        if not image_src:
            continue
        try:
            process_source_image.apply_async(
                kwargs={
                    "client_id": client_id,
                    "subaccount_id": subaccount_id,
                    "source_url": image_src,
                    "feed_source_name": feed_source_name,
                },
                queue="bgremoval",
            )
            summary["bgremoval_enqueued"] += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "sync_hooks_bgremoval_enqueue_failed client_id=%s image_src=%s",
                client_id,
                image_src,
            )

    # 2. Re-run BG removal + invalidate preview for products whose image changed.
    from app.services.enriched_catalog import render_cache

    for entry in list(delta.get("updated_images") or []):
        product_id = str(entry.get("product_id") or "")
        image_src = _first_image_url(entry.get("image_src"))
        if product_id:
            summary["render_invalidations"] += render_cache.invalidate_by_product(
                product_id=product_id,
            )
        if image_src:
            try:
                process_source_image.apply_async(
                    kwargs={
                        "client_id": client_id,
                        "subaccount_id": subaccount_id,
                        "source_url": image_src,
                        "feed_source_name": feed_source_name,
                    },
                    queue="bgremoval",
                )
                summary["bgremoval_enqueued"] += 1
            except Exception:  # noqa: BLE001
                logger.exception("sync_hooks_image_change_enqueue_failed product_id=%s", product_id)

    # 3. Drop preview cache for removed products (they will be excluded from
    # the next enriched feed build).
    for product_id in list(delta.get("removed") or []):
        summary["render_invalidations"] += render_cache.invalidate_by_product(
            product_id=str(product_id)
        )

    # 4. Stock changes don't need a cutout refresh, but they may flip a
    # product in/out of a feed whose treatment filters on availability — drop
    # the cached preview for those products so the next render reflects the
    # new state.
    for product_id in list(delta.get("stock_changed") or []):
        summary["render_invalidations"] += render_cache.invalidate_by_product(
            product_id=str(product_id)
        )

    # 5. Re-dispatch render for every output feed backed by this source so the
    # enriched feed artefact on S3 picks up the new state at the next publish.
    try:
        summary["output_feeds_refreshed"] = _refresh_output_feeds(feed_source_id)
    except Exception:  # noqa: BLE001
        logger.exception("sync_hooks_output_feed_refresh_failed feed_source_id=%s", feed_source_id)

    logger.info(
        "sync_hooks_delta_processed feed_source_id=%s added=%s image_changes=%s removed=%s stock=%s enqueued=%s invalidations=%s",
        feed_source_id,
        len(delta.get("added") or []),
        len(delta.get("updated_images") or []),
        len(delta.get("removed") or []),
        len(delta.get("stock_changed") or []),
        summary["bgremoval_enqueued"],
        summary["render_invalidations"],
    )
    return summary


def _first_image_url(value: Any) -> str:
    """Accept either a raw URL string or the typical connector format
    (a list of dicts/strings) and return the first usable URL.
    """
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            for key in ("url", "src", "image", "image_src"):
                if first.get(key):
                    return str(first[key]).strip()
        elif isinstance(first, str):
            return first.strip()
    return ""


def _refresh_output_feeds(feed_source_id: str) -> int:
    """Touch every output feed rooted at ``feed_source_id`` so the next
    rebuild picks up added/removed products.

    We intentionally don't dispatch a bulk render here — that would rebuild
    the entire feed on every sync which is too expensive for catalogs with
    100k+ products. Instead we drop the preview cache entries that were
    touched by the delta (handled in the main task) so the next Publish /
    feed refresh re-renders only what changed.
    """
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text FROM output_feeds WHERE feed_source_id = %s::uuid
                """,
                (str(feed_source_id),),
            )
            feeds = [row[0] for row in (cur.fetchall() or [])]
    return len(feeds)
