from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: datetime


class ResponseCache:
    def __init__(self) -> None:
        self._lock = Lock()
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> Any | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            entry = self._entries.get(str(key))
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._entries.pop(str(key), None)
                return None
            return entry.value

    def set(self, key: str, value: Any, *, ttl_seconds: int) -> Any:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, int(ttl_seconds)))
        with self._lock:
            self._entries[str(key)] = _CacheEntry(value=value, expires_at=expires_at)
        return value


response_cache = ResponseCache()
