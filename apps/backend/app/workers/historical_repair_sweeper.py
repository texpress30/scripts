from __future__ import annotations

import logging
import os

from app.core.config import load_settings
from app.services.sync_runs_store import is_db_connection_error, sync_runs_store

logger = logging.getLogger(__name__)


def sweep_stale_historical_runs(*, stale_after_minutes: int | None = None, limit: int = 100) -> dict[str, object]:
    settings = load_settings()
    effective_stale_after_minutes = (
        int(stale_after_minutes)
        if stale_after_minutes is not None
        else int(settings.sync_run_repair_stale_minutes)
    )
    effective_limit = max(1, int(limit))

    historical_summary = sync_runs_store.sweep_stale_historical_runs(
        stale_after_minutes=effective_stale_after_minutes,
        limit=effective_limit,
        repair_source="sweeper",
    )
    rolling_summary = sync_runs_store.sweep_stale_rolling_runs(
        stale_after_minutes=effective_stale_after_minutes,
        limit=effective_limit,
        repair_source="sweeper",
    )

    return {
        "historical": historical_summary,
        "rolling": rolling_summary,
        "total_processed_count": int(historical_summary.get("processed_count", 0))
        + int(rolling_summary.get("processed_count", 0)),
        "total_repaired_count": int(historical_summary.get("repaired_count", 0))
        + int(rolling_summary.get("repaired_count", 0)),
        "total_error_count": int(historical_summary.get("error_count", 0))
        + int(rolling_summary.get("error_count", 0)),
    }


def main() -> None:
    stale_after_minutes_env = os.environ.get("HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES")
    stale_after_minutes = int(stale_after_minutes_env) if stale_after_minutes_env else None
    limit = int(os.environ.get("HISTORICAL_REPAIR_SWEEPER_LIMIT", "100") or 100)
    try:
        summary = sweep_stale_historical_runs(stale_after_minutes=stale_after_minutes, limit=limit)
    except Exception as exc:  # noqa: BLE001
        if not is_db_connection_error(exc):
            raise
        logger.warning(
            "historical_repair_sweeper.db_unavailable stale_after_minutes=%s limit=%s error=%s",
            stale_after_minutes,
            limit,
            exc.__class__.__name__,
        )
        summary = {
            "status": "db_unavailable",
            "error": "database_connection_unavailable",
            "total_processed_count": 0,
            "total_repaired_count": 0,
            "total_error_count": 1,
        }
    print(summary)


if __name__ == "__main__":
    main()
