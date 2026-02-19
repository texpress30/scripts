from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class AuditEvent:
    timestamp: str
    actor_email: str
    actor_role: str
    action: str
    resource: str
    details: dict[str, Any]


class AuditLogService:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def log(
        self,
        *,
        actor_email: str,
        actor_role: str,
        action: str,
        resource: str,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            resource=resource,
            details=details or {},
        )
        with self._lock:
            self._events.append(event)
        return event

    def list_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(e) for e in self._events]


audit_log_service = AuditLogService()
