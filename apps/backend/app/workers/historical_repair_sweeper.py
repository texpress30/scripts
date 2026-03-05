from __future__ import annotations

import os

from app.core.config import load_settings
from app.services.sync_runs_store import sync_runs_store


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
    summary = sweep_stale_historical_runs(stale_after_minutes=stale_after_minutes, limit=limit)
    print(summary)


if __name__ == "__main__":
    main()
