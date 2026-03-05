from __future__ import annotations

import logging
import os
import time

from app.core.config import load_settings
from app.services.sync_runs_store import sync_runs_store

logger = logging.getLogger(__name__)


def _parse_bool_env(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    normalized = str(raw).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _parse_positive_int_env(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return max(1, int(default))
    try:
        parsed = int(str(raw).strip())
    except Exception:  # noqa: BLE001
        return max(1, int(default))
    return max(1, parsed)


def run_single_iteration(*, stale_after_minutes: int | None = None, limit: int = 100) -> dict[str, object]:
    started_at = time.monotonic()
    logger.info(
        "historical_repair_sweeper_loop.iteration_started stale_after_minutes=%s limit=%s",
        stale_after_minutes,
        max(1, int(limit)),
    )

    settings = load_settings()
    effective_stale_after = int(settings.sync_run_repair_stale_minutes) if stale_after_minutes is None else max(1, int(stale_after_minutes))
    effective_limit = max(1, int(limit))

    historical_summary = sync_runs_store.sweep_stale_historical_runs(
        stale_after_minutes=effective_stale_after,
        limit=effective_limit,
        repair_source="sweeper",
    )
    rolling_summary = sync_runs_store.sweep_stale_rolling_runs(
        stale_after_minutes=effective_stale_after,
        limit=effective_limit,
        repair_source="sweeper",
    )
    summary = {
        "historical": historical_summary,
        "rolling": rolling_summary,
        "total_processed_count": int(historical_summary.get("processed_count") or 0) + int(rolling_summary.get("processed_count") or 0),
        "total_repaired_count": int(historical_summary.get("repaired_count") or 0) + int(rolling_summary.get("repaired_count") or 0),
        "total_error_count": int(historical_summary.get("error_count") or 0) + int(rolling_summary.get("error_count") or 0),
    }

    duration_ms = int((time.monotonic() - started_at) * 1000)
    logger.info(
        "historical_repair_sweeper_loop.iteration_finished duration_ms=%s summary=%s",
        duration_ms,
        summary,
    )
    return summary


def run_periodic_loop(
    *,
    enabled: bool,
    interval_seconds: int,
    stale_after_minutes: int | None,
    limit: int,
    max_iterations: int | None = None,
) -> dict[str, object]:
    if not bool(enabled):
        logger.info("historical_repair_sweeper_loop.disabled")
        return {"status": "disabled"}

    interval_value = max(1, int(interval_seconds))
    iteration = 0
    while True:
        iteration += 1
        try:
            run_single_iteration(stale_after_minutes=stale_after_minutes, limit=limit)
        except Exception:  # noqa: BLE001
            logger.exception("historical_repair_sweeper_loop.iteration_failed iteration=%s", iteration)

        if max_iterations is not None and iteration >= max(1, int(max_iterations)):
            return {"status": "stopped", "iterations": iteration}

        time.sleep(interval_value)


def main() -> None:
    enabled = _parse_bool_env("HISTORICAL_REPAIR_SWEEPER_ENABLED", default=True)
    interval_seconds = _parse_positive_int_env("HISTORICAL_REPAIR_SWEEPER_INTERVAL_SECONDS", default=300)

    stale_after_minutes_env = os.environ.get("HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES")
    stale_after_minutes = int(stale_after_minutes_env) if stale_after_minutes_env else None
    limit = _parse_positive_int_env("HISTORICAL_REPAIR_SWEEPER_LIMIT", default=100)

    run_periodic_loop(
        enabled=enabled,
        interval_seconds=interval_seconds,
        stale_after_minutes=stale_after_minutes,
        limit=limit,
    )


if __name__ == "__main__":
    main()
