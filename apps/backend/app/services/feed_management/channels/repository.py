from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.services.feed_management.channels.models import (
    ChannelFieldOverrideResponse,
    ChannelStatus,
    ChannelType,
    FeedChannelCreate,
    FeedChannelResponse,
    FeedChannelUpdate,
    FeedFormat,
    OverrideMappingType,
)

logger = logging.getLogger(__name__)


def _connect():
    from app.db.pool import get_connection

    return get_connection()


# ---------------------------------------------------------------------------
# Row parsers
# ---------------------------------------------------------------------------

_CHANNEL_COLUMNS = (
    "id, feed_source_id, name, channel_type, status, feed_format, "
    "public_token, feed_url, s3_key, included_products, excluded_products, "
    "last_generated_at, error_message, settings, created_at, updated_at"
)


def _parse_channel_row(row: tuple) -> FeedChannelResponse:
    settings_raw = row[13]
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else (settings_raw or {})
    return FeedChannelResponse(
        id=str(row[0]),
        feed_source_id=str(row[1]),
        name=str(row[2]),
        channel_type=ChannelType(str(row[3])),
        status=ChannelStatus(str(row[4])),
        feed_format=FeedFormat(str(row[5])),
        public_token=str(row[6]),
        feed_url=str(row[7]) if row[7] else None,
        s3_key=str(row[8]) if row[8] else None,
        included_products=int(row[9]) if row[9] is not None else 0,
        excluded_products=int(row[10]) if row[10] is not None else 0,
        last_generated_at=row[11],
        error_message=str(row[12]) if row[12] else None,
        settings=settings,
        created_at=row[14],
        updated_at=row[15],
    )


_OVERRIDE_COLUMNS = (
    "id, channel_id, target_field, source_field, mapping_type, "
    "static_value, template_value, created_at, updated_at"
)


def _parse_override_row(row: tuple) -> ChannelFieldOverrideResponse:
    return ChannelFieldOverrideResponse(
        id=str(row[0]),
        channel_id=str(row[1]),
        target_field=str(row[2]),
        source_field=str(row[3]) if row[3] else None,
        mapping_type=OverrideMappingType(str(row[4])),
        static_value=str(row[5]) if row[5] else None,
        template_value=str(row[6]) if row[6] else None,
        created_at=row[7],
        updated_at=row[8],
    )


# ---------------------------------------------------------------------------
# Channel repository
# ---------------------------------------------------------------------------

class FeedChannelRepository:

    # -- Channel CRUD ------------------------------------------------------

    def create(self, source_id: str, payload: FeedChannelCreate) -> FeedChannelResponse:
        channel_id = str(uuid.uuid4())
        settings_json = json.dumps(payload.settings) if payload.settings else "{}"
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO feed_channels
                        (id, feed_source_id, name, channel_type, feed_format, settings)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    RETURNING {_CHANNEL_COLUMNS}
                    """,
                    (
                        channel_id,
                        source_id,
                        payload.name,
                        payload.channel_type.value,
                        payload.feed_format.value,
                        settings_json,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create feed channel")
        return _parse_channel_row(row)

    def get_by_id(self, channel_id: str) -> FeedChannelResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_CHANNEL_COLUMNS} FROM feed_channels WHERE id = %s",
                    (channel_id,),
                )
                row = cur.fetchone()
        if row is None:
            raise ChannelNotFoundError(channel_id)
        return _parse_channel_row(row)

    def get_by_token(self, token: str) -> FeedChannelResponse | None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_CHANNEL_COLUMNS} FROM feed_channels WHERE public_token = %s",
                    (token,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return _parse_channel_row(row)

    def list_by_source(self, source_id: str) -> list[FeedChannelResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_CHANNEL_COLUMNS} FROM feed_channels "
                    "WHERE feed_source_id = %s ORDER BY created_at DESC",
                    (source_id,),
                )
                rows = cur.fetchall()
        return [_parse_channel_row(r) for r in rows]

    def list_active_by_source(self, source_id: str) -> list[FeedChannelResponse]:
        """Return only channels with status='active' for a source.

        Used by the sync pipeline to decide which channels to auto-regenerate
        after a successful sync. Draft / paused / error channels are skipped
        on purpose so we don't revive them silently.
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_CHANNEL_COLUMNS} FROM feed_channels "
                    "WHERE feed_source_id = %s AND status = 'active' "
                    "ORDER BY created_at DESC",
                    (source_id,),
                )
                rows = cur.fetchall()
        return [_parse_channel_row(r) for r in rows]

    def update(self, channel_id: str, payload: FeedChannelUpdate) -> FeedChannelResponse:
        sets: list[str] = []
        params: list[Any] = []

        if payload.name is not None:
            sets.append("name = %s")
            params.append(payload.name)
        if payload.channel_type is not None:
            sets.append("channel_type = %s")
            params.append(payload.channel_type.value)
        if payload.status is not None:
            sets.append("status = %s")
            params.append(payload.status.value)
        if payload.feed_format is not None:
            sets.append("feed_format = %s")
            params.append(payload.feed_format.value)
        if payload.settings is not None:
            sets.append("settings = %s::jsonb")
            params.append(json.dumps(payload.settings))

        if not sets:
            return self.get_by_id(channel_id)

        sets.append("updated_at = NOW()")
        params.append(channel_id)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE feed_channels SET {', '.join(sets)} "
                    f"WHERE id = %s RETURNING {_CHANNEL_COLUMNS}",
                    tuple(params),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise ChannelNotFoundError(channel_id)
        return _parse_channel_row(row)

    def update_metadata(self, channel_id: str, data: dict[str, Any]) -> None:
        """Update generation metadata (s3_key, counts, status, etc.)."""
        sets: list[str] = []
        params: list[Any] = []
        for key, value in data.items():
            if key == "settings":
                sets.append("settings = %s::jsonb")
                params.append(json.dumps(value))
            else:
                sets.append(f"{key} = %s")
                params.append(value)
        if not sets:
            return
        sets.append("updated_at = NOW()")
        params.append(channel_id)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE feed_channels SET {', '.join(sets)} WHERE id = %s",
                    tuple(params),
                )
            conn.commit()

    def delete(self, channel_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM feed_channels WHERE id = %s", (channel_id,))
                if cur.rowcount == 0:
                    raise ChannelNotFoundError(channel_id)
            conn.commit()

    # -- Overrides ---------------------------------------------------------

    def get_overrides(self, channel_id: str) -> list[ChannelFieldOverrideResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_OVERRIDE_COLUMNS} FROM channel_field_overrides "
                    "WHERE channel_id = %s ORDER BY target_field",
                    (channel_id,),
                )
                rows = cur.fetchall()
        return [_parse_override_row(r) for r in rows]

    def save_overrides(
        self,
        channel_id: str,
        overrides: list[dict[str, Any]],
    ) -> list[ChannelFieldOverrideResponse]:
        results: list[ChannelFieldOverrideResponse] = []
        with _connect() as conn:
            with conn.cursor() as cur:
                # Remove overrides not in the new list
                target_fields = [o["target_field"] for o in overrides]
                if target_fields:
                    cur.execute(
                        "DELETE FROM channel_field_overrides "
                        "WHERE channel_id = %s AND target_field != ALL(%s)",
                        (channel_id, target_fields),
                    )
                else:
                    cur.execute(
                        "DELETE FROM channel_field_overrides WHERE channel_id = %s",
                        (channel_id,),
                    )

                for o in overrides:
                    override_id = str(uuid.uuid4())
                    cur.execute(
                        f"""
                        INSERT INTO channel_field_overrides
                            (id, channel_id, target_field, source_field,
                             mapping_type, static_value, template_value)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (channel_id, target_field)
                        DO UPDATE SET
                            source_field   = EXCLUDED.source_field,
                            mapping_type   = EXCLUDED.mapping_type,
                            static_value   = EXCLUDED.static_value,
                            template_value = EXCLUDED.template_value,
                            updated_at     = NOW()
                        RETURNING {_OVERRIDE_COLUMNS}
                        """,
                        (
                            override_id,
                            channel_id,
                            o["target_field"],
                            o.get("source_field"),
                            o.get("mapping_type", "direct"),
                            o.get("static_value"),
                            o.get("template_value"),
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        results.append(_parse_override_row(row))
            conn.commit()
        return results


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ChannelNotFoundError(Exception):
    def __init__(self, channel_id: str) -> None:
        super().__init__(f"Feed channel {channel_id} not found")
        self.channel_id = channel_id


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

feed_channel_repository = FeedChannelRepository()
