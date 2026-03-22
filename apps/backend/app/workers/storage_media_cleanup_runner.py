from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

from app.core.config import load_settings
from app.services.storage_media_cleanup import StorageMediaCleanupError, storage_media_cleanup_service


def _resolve_batch_limit(*, cli_limit: int | None) -> int:
    if cli_limit is not None:
        return max(1, int(cli_limit))
    settings = load_settings()
    return max(1, int(settings.storage_media_cleanup_batch_limit))


def run_cleanup_batch(
    *,
    limit: int | None = None,
    emit: Callable[[str], None] = print,
) -> int:
    resolved_limit = _resolve_batch_limit(cli_limit=limit)
    try:
        summary = storage_media_cleanup_service.run_batch(limit=resolved_limit)
    except StorageMediaCleanupError as exc:
        emit(
            json.dumps(
                {
                    "status": "error",
                    "limit": resolved_limit,
                    "error": str(exc),
                    "status_code": exc.status_code,
                }
            )
        )
        return 1
    except Exception as exc:  # noqa: BLE001
        emit(
            json.dumps(
                {
                    "status": "error",
                    "limit": resolved_limit,
                    "error": str(exc),
                }
            )
        )
        return 1

    emit(
        json.dumps(
            {
                "status": "ok",
                "limit": resolved_limit,
                "processed": int(summary.get("processed", 0)),
                "purged": int(summary.get("purged", 0)),
                "skipped": int(summary.get("skipped", 0)),
                "failed": int(summary.get("failed", 0)),
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one storage media cleanup batch")
    parser.add_argument("--limit", type=int, default=None, help="Optional batch limit override")
    args = parser.parse_args(argv)
    return run_cleanup_batch(limit=args.limit)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
