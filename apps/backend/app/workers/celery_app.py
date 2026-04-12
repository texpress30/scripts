"""Celery application for async background removal, preview rendering, and
delta-sync hooks.

Queues
------
- ``bgremoval_interactive``  high priority: shuffle-pool misses, user actions
- ``bgremoval_prime``        medium priority: priming when a template editor opens
- ``bgremoval``              normal priority: sync-delta and on-demand cutouts
- ``bgremoval_bulk``         low priority: large backfills (10k+ products)
- ``render_hi``              high priority: editor + preview grid single renders
- ``render_bulk``            low priority: Publish / materialize full feed
- ``sync_hooks``              delta fan-out from FeedSyncService
- ``cleanup``                Beat-driven: purge orphan cutouts, retry failed

The broker and result backend both speak Redis (the Redis container is already
part of docker-compose). Broker DB 1 / result DB 2 keep them out of the cache
space used by the rate limiter.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

logger = logging.getLogger(__name__)

_APP_NAME = "mcc_workers"


def _build_app() -> Celery:
    # Resolve broker / result backend lazily from Settings, with env fallbacks so
    # `celery -A app.workers.celery_app worker` can start without importing app
    # config in unit tests.
    broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    result = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    app = Celery(_APP_NAME, broker=broker, backend=result)

    # Re-read the actual Settings if available; if config import fails at
    # worker-process start (missing DB env vars), fall back to the env-only
    # values captured above.
    try:
        from app.core.config import load_settings

        settings = load_settings()
        if settings.celery_broker_url:
            app.conf.broker_url = settings.celery_broker_url
        if settings.celery_result_backend:
            app.conf.result_backend = settings.celery_result_backend
        app.conf.task_always_eager = bool(settings.celery_task_always_eager)
    except Exception:  # noqa: BLE001
        logger.warning("celery_settings_load_failed_falling_back_to_env", exc_info=True)

    app.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,  # fair dispatch for heavy image tasks
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_default_queue="default",
        task_queues=_queue_definitions(),
        task_routes=_route_map(),
        broker_transport_options={
            "visibility_timeout": 3600,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        },
        broker_connection_retry_on_startup=True,  # future-proof for Celery 6.0 deprecation
        result_expires=60 * 60 * 24,  # 24h
        beat_schedule=_beat_schedule(),
    )

    # Register task modules. Importing for side-effects only — Celery autodiscovery
    # would require a Django-style app registry, so we list modules explicitly.
    app.autodiscover_tasks(
        packages=["app.workers.tasks"],
        related_name=None,
        force=True,
    )
    # Explicit imports guarantee task registration even when autodiscovery is
    # bypassed (tests, eager mode).
    try:
        from app.workers.tasks import bg_removal  # noqa: F401
        from app.workers.tasks import cleanup  # noqa: F401
        from app.workers.tasks import render as _render  # noqa: F401
        from app.workers.tasks import sync_hooks  # noqa: F401
    except Exception:  # noqa: BLE001
        # In unit tests the task modules may pull in optional ML deps that are
        # not installed; swallow and let individual tests import what they need.
        logger.debug("celery_task_module_import_skipped", exc_info=True)

    return app


def _queue_definitions() -> dict[str, dict[str, Any]]:
    from kombu import Queue

    return {
        q.name: {"exchange": q.name, "routing_key": q.name}
        for q in [
            Queue("default"),
            Queue("bgremoval_interactive"),
            Queue("bgremoval_prime"),
            Queue("bgremoval"),
            Queue("bgremoval_bulk"),
            Queue("render_hi"),
            Queue("render_bulk"),
            Queue("sync_hooks"),
            Queue("cleanup"),
        ]
    }


def _route_map() -> dict[str, dict[str, str]]:
    return {
        "app.workers.tasks.bg_removal.process_source_image": {"queue": "bgremoval"},
        "app.workers.tasks.bg_removal.process_source_image_interactive": {"queue": "bgremoval_interactive"},
        "app.workers.tasks.bg_removal.process_source_image_prime": {"queue": "bgremoval_prime"},
        "app.workers.tasks.bg_removal.process_source_image_bulk": {"queue": "bgremoval_bulk"},
        "app.workers.tasks.bg_removal.retry_failed": {"queue": "cleanup"},
        "app.workers.tasks.render.render_one": {"queue": "render_hi"},
        "app.workers.tasks.render.render_batch": {"queue": "render_bulk"},
        "app.workers.tasks.render.invalidate_and_rerender": {"queue": "render_hi"},
        "app.workers.tasks.sync_hooks.handle_sync_delta": {"queue": "sync_hooks"},
        "app.workers.tasks.cleanup.purge_orphan_cutouts": {"queue": "cleanup"},
    }


def _beat_schedule() -> dict[str, dict[str, Any]]:
    return {
        "purge-orphan-cutouts": {
            "task": "app.workers.tasks.cleanup.purge_orphan_cutouts",
            "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00 UTC
        },
        "retry-failed-cutouts": {
            "task": "app.workers.tasks.bg_removal.retry_failed",
            "schedule": crontab(minute=0),  # top of every hour
        },
    }


celery_app = _build_app()


@worker_process_init.connect
def _warm_rembg_session(**_: Any) -> None:
    """Preload the ONNX model in each worker process so the first task doesn't
    pay the cold-start cost (~2-3 s for u2net).

    Safe no-op if rembg isn't installed (e.g. render_hi workers that never touch
    the background-removal pipeline)."""
    try:
        from app.services.enriched_catalog.cutout_service import warm_rembg_session

        warm_rembg_session()
    except Exception:  # noqa: BLE001
        logger.debug("rembg_warmup_skipped", exc_info=True)
