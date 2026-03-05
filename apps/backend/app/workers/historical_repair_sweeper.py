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
    return sync_runs_store.sweep_stale_historical_runs(
        stale_after_minutes=effective_stale_after_minutes,
        limit=max(1, int(limit)),
        repair_source="sweeper",
    )


def main() -> None:
    stale_after_minutes_env = os.environ.get("HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES")
    stale_after_minutes = int(stale_after_minutes_env) if stale_after_minutes_env else None
    limit = int(os.environ.get("HISTORICAL_REPAIR_SWEEPER_LIMIT", "100") or 100)
    summary = sweep_stale_historical_runs(stale_after_minutes=stale_after_minutes, limit=limit)
    print(summary)


if __name__ == "__main__":
    main()
