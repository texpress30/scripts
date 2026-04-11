"""Render cache — Postgres-backed memoization of rendered preview PNGs.

Cache key is ``(template_id, template_version, output_feed_id, product_id)``.
Any mutation to a creative template bumps ``template.version`` (see
``repository.CreativeTemplateRepository.update``) which atomically invalidates
the cache for that template without a separate signal.

Public surface:

* :func:`get_result` — lookup a cached render
* :func:`upsert_result` — record a fresh render
* :func:`invalidate_by_output_feed` — drop all cached renders for a feed
  (used when treatments change)
* :func:`invalidate_by_product` — drop all cached renders for one product
  (used by sync delta when a product's image or attributes change)
* :func:`invalidate_by_template` — drop all cached renders for a template
  version (rarely needed — the version bump normally handles this)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderResult:
    template_id: str
    template_version: int
    output_feed_id: str
    product_id: str
    s3_key: str
    image_url: str | None
    media_id: str | None
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "output_feed_id": self.output_feed_id,
            "product_id": self.product_id,
            "s3_key": self.s3_key,
            "image_url": self.image_url,
            "media_id": self.media_id,
            "status": self.status,
        }


def get_result(
    *,
    template_id: str,
    template_version: int,
    output_feed_id: str,
    product_id: str,
) -> RenderResult | None:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT template_id, template_version, output_feed_id::text, product_id,
                       s3_key, image_url, media_id, status
                FROM template_render_results
                WHERE template_id = %s
                  AND template_version = %s
                  AND output_feed_id = %s::uuid
                  AND product_id = %s
                """,
                (
                    str(template_id),
                    int(template_version),
                    str(output_feed_id),
                    str(product_id),
                ),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return RenderResult(
        template_id=row[0],
        template_version=int(row[1]),
        output_feed_id=row[2],
        product_id=row[3],
        s3_key=row[4],
        image_url=row[5],
        media_id=row[6],
        status=row[7],
    )


def get_many(
    *,
    template_id: str,
    template_version: int,
    output_feed_id: str,
    product_ids: list[str],
) -> dict[str, RenderResult]:
    """Batched lookup — returns ``{product_id: RenderResult}`` for cache hits."""
    if not product_ids:
        return {}
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT template_id, template_version, output_feed_id::text, product_id,
                       s3_key, image_url, media_id, status
                FROM template_render_results
                WHERE template_id = %s
                  AND template_version = %s
                  AND output_feed_id = %s::uuid
                  AND product_id = ANY(%s)
                """,
                (
                    str(template_id),
                    int(template_version),
                    str(output_feed_id),
                    [str(pid) for pid in product_ids],
                ),
            )
            rows = cur.fetchall() or []

    out: dict[str, RenderResult] = {}
    for row in rows:
        if row[7] != "ready":
            continue
        out[row[3]] = RenderResult(
            template_id=row[0],
            template_version=int(row[1]),
            output_feed_id=row[2],
            product_id=row[3],
            s3_key=row[4],
            image_url=row[5],
            media_id=row[6],
            status=row[7],
        )
    return out


def upsert_result(
    *,
    template_id: str,
    template_version: int,
    output_feed_id: str,
    product_id: str,
    s3_key: str,
    image_url: str | None,
    media_id: str | None = None,
    status: str = "ready",
    error: str | None = None,
) -> None:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO template_render_results
                    (template_id, template_version, output_feed_id, product_id,
                     s3_key, image_url, media_id, status, error, rendered_at)
                VALUES
                    (%s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (template_id, template_version, output_feed_id, product_id)
                DO UPDATE SET
                    s3_key = EXCLUDED.s3_key,
                    image_url = EXCLUDED.image_url,
                    media_id = EXCLUDED.media_id,
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    rendered_at = NOW()
                """,
                (
                    str(template_id),
                    int(template_version),
                    str(output_feed_id),
                    str(product_id),
                    str(s3_key),
                    image_url,
                    media_id,
                    status,
                    error,
                ),
            )
        conn.commit()


def invalidate_by_output_feed(output_feed_id: str) -> int:
    """Drop every cached render for ``output_feed_id``.

    Called whenever treatments change on a feed, since a product might now
    match a different template and therefore need a fresh render.
    """
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM template_render_results WHERE output_feed_id = %s::uuid",
                (str(output_feed_id),),
            )
            deleted = cur.rowcount or 0
        conn.commit()
    if deleted:
        logger.info(
            "render_cache_invalidated_by_feed output_feed_id=%s deleted=%s",
            output_feed_id,
            deleted,
        )
    return int(deleted)


def invalidate_by_product(
    *,
    output_feed_id: str | None = None,
    product_id: str,
) -> int:
    """Drop cached renders for a specific product.

    If ``output_feed_id`` is omitted, drops the product from every feed (used
    when a product's image changes and we don't know which feeds referenced
    it).
    """
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            if output_feed_id:
                cur.execute(
                    """
                    DELETE FROM template_render_results
                    WHERE output_feed_id = %s::uuid AND product_id = %s
                    """,
                    (str(output_feed_id), str(product_id)),
                )
            else:
                cur.execute(
                    "DELETE FROM template_render_results WHERE product_id = %s",
                    (str(product_id),),
                )
            deleted = cur.rowcount or 0
        conn.commit()
    return int(deleted)


def invalidate_by_template(*, template_id: str, template_version: int | None = None) -> int:
    from app.db.pool import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            if template_version is None:
                cur.execute(
                    "DELETE FROM template_render_results WHERE template_id = %s",
                    (str(template_id),),
                )
            else:
                cur.execute(
                    """
                    DELETE FROM template_render_results
                    WHERE template_id = %s AND template_version = %s
                    """,
                    (str(template_id), int(template_version)),
                )
            deleted = cur.rowcount or 0
        conn.commit()
    return int(deleted)
