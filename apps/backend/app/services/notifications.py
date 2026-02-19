from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock


class NotificationService:
    def __init__(self) -> None:
        self._events: list[dict[str, str]] = []
        self._lock = Lock()

    def send_email_mock(self, to_email: str, subject: str, message: str) -> dict[str, str]:
        payload = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "channel": "email_mock",
            "to": to_email,
            "subject": subject,
            "message": message,
        }
        # mock email output for local development
        print(f"[EMAIL_MOCK] to={to_email} subject={subject} message={message}")
        with self._lock:
            self._events.append(payload)
        return payload

    def list_events(self) -> list[dict[str, str]]:
        with self._lock:
            return list(self._events)


notification_service = NotificationService()
