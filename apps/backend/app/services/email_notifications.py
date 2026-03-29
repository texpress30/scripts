from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


AGENCY_DEFAULT_SCOPE_KEY = "agency_default"


@dataclass(frozen=True)
class EmailNotificationCatalogItem:
    key: str
    label: str
    description: str
    channel: str
    scope: str
    template_key: str
    default_enabled: bool


@dataclass(frozen=True)
class EffectiveEmailNotification:
    key: str
    label: str
    description: str
    channel: str
    scope: str
    template_key: str
    enabled: bool
    default_enabled: bool
    is_overridden: bool
    updated_at: datetime | None


@dataclass(frozen=True)
class RuntimeEmailNotification:
    key: str
    template_key: str
    enabled: bool
    default_enabled: bool
    is_overridden: bool
    updated_at: datetime | None


@dataclass(frozen=True)
class EmailNotificationOverrideInput:
    enabled: bool


_CANONICAL_EMAIL_NOTIFICATIONS: tuple[EmailNotificationCatalogItem, ...] = (
    EmailNotificationCatalogItem(
        key="auth_forgot_password",
        label="Auth · Forgot Password",
        description="Control pentru trimiterea notificării email la resetarea parolei.",
        channel="email",
        scope="agency",
        template_key="auth_forgot_password",
        default_enabled=True,
    ),
    EmailNotificationCatalogItem(
        key="team_invite_user",
        label="Team · Invite User",
        description="Control pentru invitațiile Team: fără parolă => set-password, cu parolă => account-ready/login.",
        channel="email",
        scope="agency",
        template_key="team_invite_user",
        default_enabled=True,
    ),
)


class EmailNotificationsService:
    def _connect(self):
        from app.db.pool import get_connection
        return get_connection()

    def initialize_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agency_email_notifications (
                        id BIGSERIAL PRIMARY KEY,
                        notification_key TEXT NOT NULL,
                        scope_key TEXT NOT NULL DEFAULT 'agency_default',
                        enabled_override BOOLEAN NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        CONSTRAINT agency_email_notifications_unique_scope_key UNIQUE (notification_key, scope_key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agency_email_notifications_notification_key
                    ON agency_email_notifications(notification_key)
                    """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_agency_email_notifications_scope_key
                    ON agency_email_notifications(scope_key)
                    """
                )
            conn.commit()

    def list_notifications(self) -> list[EmailNotificationCatalogItem]:
        return list(_CANONICAL_EMAIL_NOTIFICATIONS)

    def get_notification(self, notification_key: str) -> EmailNotificationCatalogItem | None:
        key = str(notification_key or "").strip().lower()
        if key == "":
            return None
        for item in _CANONICAL_EMAIL_NOTIFICATIONS:
            if item.key == key:
                return item
        return None

    def list_effective_notifications(self) -> list[EffectiveEmailNotification]:
        overrides_by_key = {row["notification_key"]: row for row in self._list_override_rows(scope_key=AGENCY_DEFAULT_SCOPE_KEY)}
        items: list[EffectiveEmailNotification] = []
        for item in _CANONICAL_EMAIL_NOTIFICATIONS:
            items.append(self._build_effective_notification(item=item, override_row=overrides_by_key.get(item.key)))
        return items

    def get_effective_notification(self, notification_key: str) -> EffectiveEmailNotification | None:
        item = self.get_notification(notification_key)
        if item is None:
            return None
        override = self._fetch_override_row(notification_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_notification(item=item, override_row=override)

    def resolve_runtime_notification(self, *, notification_key: str) -> RuntimeEmailNotification | None:
        effective = self.get_effective_notification(notification_key=notification_key)
        if effective is None:
            return None
        return RuntimeEmailNotification(
            key=effective.key,
            template_key=effective.template_key,
            enabled=effective.enabled,
            default_enabled=effective.default_enabled,
            is_overridden=effective.is_overridden,
            updated_at=effective.updated_at,
        )

    def save_override(self, *, notification_key: str, enabled: bool | None) -> EffectiveEmailNotification | None:
        item = self.get_notification(notification_key)
        if item is None:
            return None

        normalized = self._normalize_override_input(enabled=enabled)
        self._upsert_override_row(notification_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY, payload=normalized)
        override = self._fetch_override_row(notification_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_notification(item=item, override_row=override)

    def reset_override(self, *, notification_key: str) -> EffectiveEmailNotification | None:
        item = self.get_notification(notification_key)
        if item is None:
            return None

        self._delete_override_row(notification_key=item.key, scope_key=AGENCY_DEFAULT_SCOPE_KEY)
        return self._build_effective_notification(item=item, override_row=None)

    def _normalize_override_input(self, *, enabled: bool | None) -> EmailNotificationOverrideInput:
        if enabled is None:
            raise ValueError("enabled este obligatoriu")
        return EmailNotificationOverrideInput(enabled=bool(enabled))

    def _build_effective_notification(
        self,
        *,
        item: EmailNotificationCatalogItem,
        override_row: dict[str, object] | None,
    ) -> EffectiveEmailNotification:
        if not override_row:
            return EffectiveEmailNotification(
                key=item.key,
                label=item.label,
                description=item.description,
                channel=item.channel,
                scope=item.scope,
                template_key=item.template_key,
                enabled=item.default_enabled,
                default_enabled=item.default_enabled,
                is_overridden=False,
                updated_at=None,
            )

        override_enabled = bool(override_row.get("enabled_override", item.default_enabled))
        updated_at = override_row.get("updated_at")
        return EffectiveEmailNotification(
            key=item.key,
            label=item.label,
            description=item.description,
            channel=item.channel,
            scope=item.scope,
            template_key=item.template_key,
            enabled=override_enabled,
            default_enabled=item.default_enabled,
            is_overridden=True,
            updated_at=updated_at if isinstance(updated_at, datetime) else None,
        )

    def _list_override_rows(self, *, scope_key: str) -> list[dict[str, object]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT notification_key, scope_key, enabled_override, updated_at
                    FROM agency_email_notifications
                    WHERE scope_key = %s
                    """,
                    (scope_key,),
                )
                rows = cur.fetchall()

        payload: list[dict[str, object]] = []
        for row in rows:
            payload.append(
                {
                    "notification_key": str(row[0]),
                    "scope_key": str(row[1]),
                    "enabled_override": bool(row[2]),
                    "updated_at": row[3],
                }
            )
        return payload

    def _fetch_override_row(self, *, notification_key: str, scope_key: str) -> dict[str, object] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT notification_key, scope_key, enabled_override, updated_at
                    FROM agency_email_notifications
                    WHERE notification_key = %s AND scope_key = %s
                    LIMIT 1
                    """,
                    (notification_key, scope_key),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return {
            "notification_key": str(row[0]),
            "scope_key": str(row[1]),
            "enabled_override": bool(row[2]),
            "updated_at": row[3],
        }

    def _upsert_override_row(
        self,
        *,
        notification_key: str,
        scope_key: str,
        payload: EmailNotificationOverrideInput,
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agency_email_notifications(notification_key, scope_key, enabled_override)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(notification_key, scope_key)
                    DO UPDATE SET enabled_override = EXCLUDED.enabled_override, updated_at = NOW()
                    """,
                    (notification_key, scope_key, payload.enabled),
                )
            conn.commit()

    def _delete_override_row(self, *, notification_key: str, scope_key: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM agency_email_notifications
                    WHERE notification_key = %s AND scope_key = %s
                    """,
                    (notification_key, scope_key),
                )
            conn.commit()


email_notifications_service = EmailNotificationsService()
