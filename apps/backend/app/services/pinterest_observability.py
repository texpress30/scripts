from __future__ import annotations

from threading import Lock


class PinterestSyncMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {
            "sync_started": 0,
            "sync_succeeded": 0,
            "sync_failed": 0,
        }

    def increment(self, name: str) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def reset(self) -> None:
        with self._lock:
            for key in list(self._counters.keys()):
                self._counters[key] = 0


pinterest_sync_metrics = PinterestSyncMetrics()
