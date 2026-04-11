"""Periodic cleanup tasks run by Celery Beat.

Currently there is only one task: ``purge_orphan_cutouts`` — used weekly to
hard-delete cutouts for products that haven't been referenced in the
retention window (default 30 days). This keeps the bucket from growing
unboundedly as clients churn their catalogs, without punishing catalogs that
briefly drop a product and bring it back next sync.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.cleanup.purge_orphan_cutouts")
def purge_orphan_cutouts(retention_days: int | None = None) -> dict[str, Any]:
    """Delete cutouts and their Media Storage entries for sources that have
    been idle past the retention window.

    Safety: only rows whose ``last_referenced_at`` is older than the window
    AND whose status is ``ready`` are eligible. Failed / in-progress rows are
    left alone so debugging is possible.
    """
    try:
        from app.core.config import load_settings

        window = int(retention_days or load_settings().cutout_orphan_retention_days or 30)
    except Exception:  # noqa: BLE001
        window = int(retention_days or 30)

    from app.db.pool import get_connection

    deleted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, client_id, media_id
                FROM image_cutouts
                WHERE status = 'ready'
                  AND last_referenced_at < NOW() - (%s || ' days')::interval
                LIMIT 1000
                """,
                (str(window),),
            )
            rows = cur.fetchall() or []

        # Soft-delete the media_files rows first so the Stocare Media cleanup
        # job picks them up on the next sweep; then drop the Postgres cutout
        # rows so they don't reappear in listings.
        purged_media: list[str] = []
        for row_id, _client_id, media_id in rows:
            if media_id:
                try:
                    from app.services.media_metadata_repository import media_metadata_repository

                    media_metadata_repository.soft_delete(media_id=str(media_id))
                    purged_media.append(str(media_id))
                except Exception:  # noqa: BLE001
                    logger.debug("orphan_purge_media_soft_delete_failed media_id=%s", media_id, exc_info=True)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM image_cutouts WHERE id = %s",
                    (int(row_id),),
                )
                deleted += cur.rowcount or 0
        conn.commit()

    logger.info(
        "orphan_cutout_purge deleted=%s retention_days=%s",
        deleted,
        window,
    )
    return {"deleted": deleted, "retention_days": window}
