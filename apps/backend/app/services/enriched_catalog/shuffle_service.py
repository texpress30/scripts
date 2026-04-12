"""Shuffle-pool service.

The template editor has a Shuffle button that swaps the displayed sample
product with another random product from the feed. We want three properties:

1. Shuffle must be fast — preferably "show the new product instantly". That
   means the cutouts for the candidate products must already be ready in
   Stocare Media before the button is clicked.
2. Shuffle must respect the treatment filters of the template being edited.
   A template that only renders SUVs shouldn't show a sedan when the user
   clicks Shuffle — that product will never match the treatment at render
   time.
3. Shuffle must be cheap even for catalogs with hundreds of thousands of
   products — we can't pre-process everything.

The pool is built by joining products from the feed's source to
``image_cutouts`` (status=ready) so only products with a ready cutout appear.
A separate priming task enqueues a bounded number of products per template
open so the pool grows in the background.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


DEFAULT_POOL_LIMIT = 50
DEFAULT_PRIMING_LIMIT = 200


# ---------------------------------------------------------------------------
# Treatment matching
# ---------------------------------------------------------------------------


def _treatment_accepts_product(treatment: dict[str, Any] | None, product: dict[str, Any]) -> bool:
    """Return True when ``product`` would render with the given template.

    Mirrors ``TreatmentRepository._matches_filters`` so shuffle stays
    consistent with what the render pipeline eventually produces.
    """
    if not treatment:
        return True
    filters = list(treatment.get("filters") or [])
    if not filters:
        return True
    for f in filters:
        field_name = str(f.get("field_name") or "")
        operator = str(f.get("operator") or "")
        filter_value = f.get("value")
        product_value = str(product.get(field_name) or "")
        if operator == "equals":
            if product_value != str(filter_value or ""):
                return False
        elif operator == "contains":
            if str(filter_value or "") not in product_value:
                return False
        elif operator == "in_list":
            values_list = (
                filter_value if isinstance(filter_value, list) else [str(filter_value or "")]
            )
            if product_value not in values_list:
                return False
        else:
            return False
    return True


# ---------------------------------------------------------------------------
# Shuffle pool
# ---------------------------------------------------------------------------


def _find_output_feed_for_template(template_id: str) -> dict[str, Any] | None:
    """Locate an output feed that references ``template_id`` via a treatment.

    Needed because templates on their own don't know which feeds host them —
    the relationship is via ``treatments(template_id, output_feed_id)``. We
    pick the most recent feed so the editor always sees fresh data.
    """
    from app.db.pool import get_connection
    from app.services.enriched_catalog.repository import treatment_repository

    # Scan treatments in Mongo for one that references this template.
    collection = treatment_repository._collection()  # noqa: SLF001
    treatment_doc = collection.find_one(
        {"template_id": str(template_id)},
        {"output_feed_id": 1, "_id": 0},
    )
    if not treatment_doc or not treatment_doc.get("output_feed_id"):
        return None
    output_feed_id = str(treatment_doc.get("output_feed_id"))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, subaccount_id, feed_source_id::text, name
                FROM output_feeds
                WHERE id = %s::uuid
                """,
                (output_feed_id,),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return {
        "output_feed_id": row[0],
        "subaccount_id": int(row[1]),
        "feed_source_id": row[2],
        "name": str(row[3] or ""),
    }


def _fetch_ready_cutout_media_by_hash(client_id: int) -> dict[str, str]:
    """Return ``{source_url_hash: media_id}`` for every ready cutout of a client.

    Used to pre-filter the shuffle pool (URL-hash prefilter) AND to resolve the
    cutout's media_id in a single SQL query. Callers then translate media_id
    to an S3 URL via ``cutout_service._lookup_media_storage`` so the shuffle
    pool response can include ``cutout_url`` per product without an N+1 fan-out.
    """
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT source_url_hash, media_id FROM image_cutouts
                WHERE client_id = %s
                  AND status = 'ready'
                  AND source_url_hash IS NOT NULL
                  AND media_id IS NOT NULL
                """,
                (int(client_id),),
            )
            rows = cur.fetchall() or []
    return {str(r[0]): str(r[1]) for r in rows if r[0] and r[1]}


def get_shuffle_pool(
    *,
    template_id: str,
    limit: int = DEFAULT_POOL_LIMIT,
    fallback_feed_source_id: str | None = None,
    fallback_client_id: int | None = None,
) -> dict[str, Any]:
    """Return a randomized slice of products whose cutouts are ready and who
    match the template's treatment filters.

    Shape::

        {
            "template_id": str,
            "output_feed_id": str | None,
            "pool": [product_data...],       # size <= limit
            "pool_ready_count": int,         # how many distinct products are ready
            "total_products": int,           # total products in the source feed
        }

    The pool is a simple random sample; the front-end shuffle button picks one
    element at a time from this list. When the pool is smaller than expected
    the caller should enqueue priming (see ``prime_cutouts_for_template``).
    """
    from app.services.enriched_catalog.repository import (
        creative_template_repository,
        treatment_repository,
    )
    from app.services.feed_management.products_repository import feed_products_repository

    template = creative_template_repository.get_by_id(template_id)
    if template is None:
        return {
            "template_id": template_id,
            "output_feed_id": None,
            "pool": [],
            "pool_ready_count": 0,
            "total_products": 0,
        }

    feed_info = _find_output_feed_for_template(template_id)
    if feed_info is None and fallback_feed_source_id and (fallback_client_id or 0) > 0:
        feed_info = {
            "output_feed_id": None,
            "subaccount_id": fallback_client_id,
            "feed_source_id": fallback_feed_source_id,
            "name": "",
        }
    if feed_info is None:
        return {
            "template_id": template_id,
            "output_feed_id": None,
            "pool": [],
            "pool_ready_count": 0,
            "total_products": 0,
        }

    feed_source_id = feed_info.get("feed_source_id")
    client_id = int(feed_info.get("subaccount_id") or 0)
    if not feed_source_id or client_id <= 0:
        return {
            "template_id": template_id,
            "output_feed_id": feed_info.get("output_feed_id"),
            "pool": [],
            "pool_ready_count": 0,
            "total_products": 0,
        }

    # Resolve the treatment gating this template (so shuffle mirrors render).
    # For standalone templates (no output feed), skip treatment filtering —
    # all products in the feed source are eligible.
    matching_treatment = None
    if feed_info.get("output_feed_id"):
        treatments = treatment_repository.get_by_output_feed(feed_info["output_feed_id"])
        for tr in treatments:
            if str(tr.get("template_id") or "") == str(template_id):
                matching_treatment = tr
                break

    ready_media_by_hash = _fetch_ready_cutout_media_by_hash(client_id)

    # Pull a bounded slice of products. We pick more than `limit` so we can
    # filter out those without ready cutouts without starving the pool.
    oversample = max(limit * 6, 200)
    raw_products = feed_products_repository.list_products(
        str(feed_source_id),
        skip=0,
        limit=min(oversample, 500),
    )
    total_products = feed_products_repository.count_products(str(feed_source_id))

    import hashlib

    from app.services.enriched_catalog import cutout_service

    pool: list[dict[str, Any]] = []
    for doc in raw_products:
        data = doc.get("data", doc)
        if not isinstance(data, dict):
            continue
        if not _treatment_accepts_product(matching_treatment, data):
            continue
        image_src = _first_image_url(data)
        if not image_src:
            continue
        # Use the URL-hash index on ``image_cutouts`` so the shuffle pool
        # only contains products with a ready cutout. Products whose URL
        # hasn't been primed yet are skipped until the next refresh.
        url_hash = hashlib.sha256(image_src.encode("utf-8")).hexdigest()
        media_id = ready_media_by_hash.get(url_hash)
        if not media_id:
            continue
        # Resolve the cutout's media URL (S3 key → presigned/public URL) so
        # the canvas editor can render the background-removed PNG instead of
        # the raw product image. ``_lookup_media_storage`` is a Mongo point
        # read per media_id; bounded by ``limit`` (typically 50).
        _s3_key, cutout_url = cutout_service._lookup_media_storage(media_id)
        if cutout_url:
            data["cutout_url"] = cutout_url
        pool.append(data)
        if len(pool) >= limit:
            break

    # Shuffle in-place so repeated calls don't always return the same order.
    random.shuffle(pool)

    return {
        "template_id": template_id,
        "output_feed_id": feed_info.get("output_feed_id"),
        "pool": pool[:limit],
        "pool_ready_count": len(pool),
        "total_products": int(total_products),
    }


def prime_cutouts_for_template(
    *,
    template_id: str,
    limit: int = DEFAULT_PRIMING_LIMIT,
    fallback_feed_source_id: str | None = None,
    fallback_client_id: int | None = None,
) -> dict[str, Any]:
    """Enqueue background removal for the top-N products of the feed that
    backs ``template_id``.

    Called when the template editor opens — the goal is to have a healthy
    shuffle pool ready by the time the user first clicks Shuffle. The task
    is idempotent (``image_cutouts`` unique on ``(client_id, source_hash)``)
    so repeated opens don't trigger re-processing.
    """
    from app.services.feed_management.products_repository import feed_products_repository

    feed_info = _find_output_feed_for_template(template_id)
    if feed_info is None and fallback_feed_source_id and (fallback_client_id or 0) > 0:
        feed_info = {
            "output_feed_id": None,
            "subaccount_id": fallback_client_id,
            "feed_source_id": fallback_feed_source_id,
            "name": "",
        }
    if feed_info is None:
        return {"enqueued": 0, "reason": "no_feed"}
    feed_source_id = feed_info.get("feed_source_id")
    client_id = int(feed_info.get("subaccount_id") or 0)
    if not feed_source_id or client_id <= 0:
        return {"enqueued": 0, "reason": "missing_ids"}

    products = feed_products_repository.list_products(
        str(feed_source_id),
        skip=0,
        limit=int(limit),
    )

    try:
        from app.workers.tasks.bg_removal import process_source_image_prime
    except Exception:  # noqa: BLE001
        logger.exception("prime_cutouts_task_unavailable")
        return {"enqueued": 0, "reason": "celery_unavailable"}

    enqueued = 0
    for doc in products:
        data = doc.get("data", doc) if isinstance(doc, dict) else {}
        image_src = _first_image_url(data)
        if not image_src:
            continue
        try:
            process_source_image_prime.apply_async(
                kwargs={
                    "client_id": client_id,
                    "subaccount_id": client_id,
                    "source_url": image_src,
                    "feed_source_name": feed_info.get("name"),
                },
                queue="bgremoval_prime",
                retry=False,
            )
            enqueued += 1
        except Exception:  # noqa: BLE001
            logger.warning("prime_enqueue_failed broker_url=%s", image_src, exc_info=True)
            break  # broker is down — no point trying remaining products

    return {"enqueued": enqueued, "feed_source_id": str(feed_source_id)}


def _first_image_url(data: dict[str, Any]) -> str:
    """Pick the first product image URL from the document shape written by
    connectors. Different connectors use ``images[]`` (ProductData),
    ``image_src`` (legacy) or both.
    """
    images = data.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            for key in ("url", "src", "image"):
                if first.get(key):
                    return str(first[key]).strip()
        elif isinstance(first, str):
            return first.strip()
    image_src = data.get("image_src") or data.get("image") or data.get("image_url")
    if isinstance(image_src, str):
        return image_src.strip()
    return ""
