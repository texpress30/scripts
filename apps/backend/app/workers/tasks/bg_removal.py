"""Celery tasks for background removal.

The same underlying pipeline (``cutout_service.ensure_cutout``) is exposed via
four Celery tasks that differ only in the queue they run on and therefore in
their scheduling priority:

* ``process_source_image_interactive`` — shuffle-pool misses and other user
  actions that block the UI; lives on its own worker pool so it can't be
  starved by bulk imports.
* ``process_source_image_prime`` — opportunistic priming when the template
  editor opens (top N products of the feed).
* ``process_source_image`` — default path for sync delta hooks and API batch
  requests.
* ``process_source_image_bulk`` — large backfills (activating the feature for
  an existing feed with tens of thousands of products).

Retries are configured with exponential backoff because the most common
failures (network hiccups downloading the source image) are transient.
"""

from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


RETRY_KW = {
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 300,
    "retry_jitter": True,
    "max_retries": 3,
}


def _run_pipeline(
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None,
    model_name: str | None,
) -> dict[str, Any]:
    from app.services.enriched_catalog import cutout_service

    record = cutout_service.ensure_cutout(
        client_id=int(client_id),
        subaccount_id=int(subaccount_id),
        source_url=source_url,
        feed_source_name=feed_source_name,
        model_name=model_name,
    )
    return record.to_dict()


@celery_app.task(
    name="app.workers.tasks.bg_removal.process_source_image",
    bind=True,
    **RETRY_KW,
)
def process_source_image(
    self,
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Default lane — normal priority."""
    logger.info(
        "bgremoval_task_start client_id=%s task_id=%s lane=default",
        client_id,
        getattr(self.request, "id", None),
    )
    return _run_pipeline(
        client_id=client_id,
        subaccount_id=subaccount_id,
        source_url=source_url,
        feed_source_name=feed_source_name,
        model_name=model_name,
    )


@celery_app.task(
    name="app.workers.tasks.bg_removal.process_source_image_interactive",
    bind=True,
    **RETRY_KW,
)
def process_source_image_interactive(
    self,
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """High-priority lane for UI-blocking actions (shuffle-cold, retry now)."""
    logger.info(
        "bgremoval_task_start client_id=%s task_id=%s lane=interactive",
        client_id,
        getattr(self.request, "id", None),
    )
    return _run_pipeline(
        client_id=client_id,
        subaccount_id=subaccount_id,
        source_url=source_url,
        feed_source_name=feed_source_name,
        model_name=model_name,
    )


@celery_app.task(
    name="app.workers.tasks.bg_removal.process_source_image_prime",
    bind=True,
    **RETRY_KW,
)
def process_source_image_prime(
    self,
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Medium-priority lane for priming the shuffle pool when an editor opens."""
    logger.info(
        "bgremoval_task_start client_id=%s task_id=%s lane=prime",
        client_id,
        getattr(self.request, "id", None),
    )
    return _run_pipeline(
        client_id=client_id,
        subaccount_id=subaccount_id,
        source_url=source_url,
        feed_source_name=feed_source_name,
        model_name=model_name,
    )


@celery_app.task(
    name="app.workers.tasks.bg_removal.process_source_image_bulk",
    bind=True,
    **RETRY_KW,
)
def process_source_image_bulk(
    self,
    *,
    client_id: int,
    subaccount_id: int,
    source_url: str,
    feed_source_name: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Low-priority lane for full-catalog backfills."""
    logger.info(
        "bgremoval_task_start client_id=%s task_id=%s lane=bulk",
        client_id,
        getattr(self.request, "id", None),
    )
    return _run_pipeline(
        client_id=client_id,
        subaccount_id=subaccount_id,
        source_url=source_url,
        feed_source_name=feed_source_name,
        model_name=model_name,
    )


@celery_app.task(name="app.workers.tasks.bg_removal.retry_failed")
def retry_failed(limit: int = 200) -> dict[str, Any]:
    """Beat-driven hourly retry of cutouts stuck in ``failed`` status.

    Grabs the oldest failed rows, resets them to ``pending``, and re-enqueues
    on the default lane. This is safer than configuring infinite retries at
    the task level because it includes a cooldown between attempts.
    """
    from app.db.pool import get_connection

    reset: list[tuple[int, int, str]] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, subaccount_id, client_id, source_url
                FROM image_cutouts
                WHERE status = 'failed'
                  AND updated_at < NOW() - INTERVAL '15 minutes'
                ORDER BY updated_at ASC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall() or []
            for row in rows:
                row_id, subaccount_id, client_id, source_url = row
                cur.execute(
                    """
                    UPDATE image_cutouts
                    SET status = 'pending', error = NULL, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(row_id),),
                )
                reset.append((int(subaccount_id), int(client_id), str(source_url)))
        conn.commit()

    for subaccount_id, client_id, source_url in reset:
        process_source_image.apply_async(
            kwargs={
                "client_id": client_id,
                "subaccount_id": subaccount_id,
                "source_url": source_url,
            },
        )

    return {"retried": len(reset)}
