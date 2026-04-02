"""Internal cron endpoints — called by the Railway cron worker.

Protected by X-Internal-Key header matching INTERNAL_CRON_KEY env var.
Accepts both GET and POST for flexibility with different cron runners.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import load_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


def _verify_cron_key(request: Request) -> None:
    """Verify the X-Internal-Key header matches the configured secret."""
    settings = load_settings()
    expected = settings.internal_cron_key
    if not expected:
        logger.warning("INTERNAL_CRON_KEY not configured — allowing request without auth")
        return
    provided = request.headers.get("X-Internal-Key", "")
    if provided != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid cron key")


@router.get("/run-scheduled-syncs")
@router.post("/run-scheduled-syncs")
async def run_scheduled_syncs(request: Request) -> dict:
    """Find all feed sources due for sync and trigger them."""
    _verify_cron_key(request)

    from app.db.pool import get_connection
    from app.services.feed_management.models import SyncSchedule, SCHEDULE_INTERVALS
    from app.services.feed_management.sync_service import feed_sync_service

    now = datetime.now(timezone.utc)
    triggered = 0
    errors = 0

    # First log all scheduled sources for debugging
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, sync_schedule, next_scheduled_sync, is_active, last_sync_at
                    FROM feed_sources
                    WHERE sync_schedule != 'manual'
                    """,
                )
                all_scheduled = cur.fetchall()
                for r in all_scheduled:
                    logger.info(
                        "Scheduled source: id=%s schedule=%s next=%s active=%s last_sync=%s",
                        r[0], r[1], r[2], r[3], r[4],
                    )

                cur.execute(
                    """
                    SELECT id, sync_schedule
                    FROM feed_sources
                    WHERE sync_schedule != 'manual'
                      AND is_active = TRUE
                      AND next_scheduled_sync IS NOT NULL
                      AND next_scheduled_sync <= %s
                    ORDER BY next_scheduled_sync ASC
                    LIMIT 10
                    """,
                    (now,),
                )
                rows = cur.fetchall()
    except Exception:
        logger.exception("Failed to query scheduled syncs")
        raise HTTPException(status_code=500, detail="Database error")

    logger.info("Scheduled sync cron: checked_at=%s, found %d sources due (of %d scheduled)", now.isoformat(), len(rows), len(all_scheduled))

    for row in rows:
        source_id = str(row[0])
        schedule_str = str(row[1])

        try:
            logger.info("Starting scheduled sync for source %s (schedule=%s)", source_id, schedule_str)
            result = await feed_sync_service.run_sync(source_id)
            logger.info("Scheduled sync completed for %s: %s (%d products)", source_id, result.status, result.imported_products)
            triggered += 1

            # Update last_sync_at, product_count, and next_scheduled_sync
            try:
                from app.services.feed_management.products_repository import feed_products_repository
                product_count = feed_products_repository.count_products(source_id)
            except Exception:
                product_count = result.imported_products

            try:
                schedule = SyncSchedule(schedule_str)
                interval = SCHEDULE_INTERVALS.get(schedule)
                next_sync = datetime.now(timezone.utc) + interval if interval else None
            except (ValueError, TypeError):
                next_sync = None

            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE feed_sources
                           SET last_sync_at = NOW(),
                               product_count = %s,
                               next_scheduled_sync = %s,
                               updated_at = NOW()
                           WHERE id = %s""",
                        (product_count, next_sync, source_id),
                    )
                conn.commit()
            logger.info("Updated source %s: product_count=%d, next_sync=%s", source_id, product_count, next_sync)

        except Exception:
            logger.exception("Scheduled sync failed for source %s", source_id)
            errors += 1

    return {
        "status": "ok",
        "checked_at": now.isoformat(),
        "sources_due": len(rows),
        "triggered": triggered,
        "errors": errors,
    }


@router.get("/health")
async def cron_health() -> dict:
    """Simple health check for the cron system."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
