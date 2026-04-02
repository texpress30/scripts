"""Feed refresh scheduler.

Identifies output feeds due for regeneration and enqueues them.
Designed to be called from a cron job or background worker.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FeedRefreshScheduler:
    """Determines which feeds need regeneration and triggers them."""

    def __init__(self, service=None) -> None:
        self._service = service

    @property
    def service(self):
        if self._service is None:
            from app.services.enriched_catalog.output_feed_service import output_feed_service
            self._service = output_feed_service
        return self._service

    def get_feeds_due_for_refresh(self) -> list[dict[str, Any]]:
        """Return feeds whose refresh interval has elapsed since last generation."""
        return self.service._repo.list_due_for_refresh()

    def enqueue_refresh(self, output_feed_id: str) -> dict[str, Any] | None:
        """Generate feed immediately. Returns the generation result or None on error."""
        try:
            result = self.service.generate_feed(output_feed_id)
            logger.info(
                "Feed %s refreshed: %d products, %d bytes",
                output_feed_id, result.products_count, result.file_size_bytes,
            )
            return {
                "output_feed_id": result.output_feed_id,
                "products_count": result.products_count,
                "file_size_bytes": result.file_size_bytes,
                "generated_at": result.generated_at,
            }
        except Exception:
            logger.exception("Failed to refresh feed %s", output_feed_id)
            return None

    def run_refresh_cycle(self) -> dict[str, Any]:
        """Run a full refresh cycle: find due feeds and regenerate them.

        Returns a summary of the cycle.
        """
        due = self.get_feeds_due_for_refresh()
        logger.info("Feed refresh cycle: %d feeds due", len(due))

        results: list[dict[str, Any]] = []
        errors = 0
        for feed in due:
            feed_id = feed["id"]
            result = self.enqueue_refresh(feed_id)
            if result is not None:
                results.append(result)
            else:
                errors += 1

        summary = {
            "feeds_checked": len(due),
            "feeds_refreshed": len(results),
            "errors": errors,
            "results": results,
        }
        logger.info(
            "Feed refresh cycle complete: %d refreshed, %d errors",
            len(results), errors,
        )
        return summary


feed_refresh_scheduler = FeedRefreshScheduler()
