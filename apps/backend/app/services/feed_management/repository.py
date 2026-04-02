from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.feed_management.exceptions import (
    FeedImportInProgressError,
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedImportCreate,
    FeedImportResponse,
    FeedImportStatus,
    FeedSourceCreate,
    FeedSourceResponse,
    FeedSourceType,
    FeedSourceUpdate,
)


def _connect():
    from app.db.pool import get_connection
    return get_connection()


def _parse_source_row(row: tuple) -> FeedSourceResponse:
    config_raw = row[4]
    config = json.loads(config_raw) if isinstance(config_raw, str) else (config_raw or {})
    return FeedSourceResponse(
        id=str(row[0]),
        subaccount_id=int(row[1]),
        source_type=FeedSourceType(str(row[2])),
        name=str(row[3]),
        config=config,
        credentials_secret_id=str(row[5]) if row[5] else None,
        is_active=bool(row[6]),
        catalog_type=str(row[7]) if row[7] else "product",
        sync_schedule=str(row[8]) if row[8] else "manual",
        next_scheduled_sync=row[9],
        created_at=row[10],
        updated_at=row[11],
    )


def _parse_import_row(row: tuple) -> FeedImportResponse:
    errors_raw = row[5]
    errors = json.loads(errors_raw) if isinstance(errors_raw, str) else (errors_raw or [])
    return FeedImportResponse(
        id=str(row[0]),
        feed_source_id=str(row[1]),
        status=FeedImportStatus(str(row[2])),
        total_products=int(row[3]),
        imported_products=int(row[4]),
        errors=errors,
        started_at=row[6],
        completed_at=row[7],
        created_at=row[8],
    )


class FeedSourceRepository:
    def create(self, payload: FeedSourceCreate) -> FeedSourceResponse:
        source_id = str(uuid.uuid4())
        config_json = payload.config.model_dump_json()

        with _connect() as conn:
            with conn.cursor() as cur:
                # Check for duplicate name within the same subaccount
                cur.execute(
                    "SELECT id FROM feed_sources WHERE subaccount_id = %s AND name = %s LIMIT 1",
                    (payload.subaccount_id, payload.name),
                )
                if cur.fetchone() is not None:
                    raise FeedSourceAlreadyExistsError(payload.name, payload.subaccount_id)

                cur.execute(
                    """
                    INSERT INTO feed_sources (id, subaccount_id, source_type, name, config, credentials_secret_id, catalog_type)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, created_at, updated_at
                    """,
                    (source_id, payload.subaccount_id, payload.source_type.value, payload.name, config_json, payload.credentials_secret_id, payload.catalog_type),
                )
                row = cur.fetchone()
            conn.commit()

        return _parse_source_row(row)

    def get_by_id(self, source_id: str) -> FeedSourceResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, created_at, updated_at
                    FROM feed_sources WHERE id = %s LIMIT 1
                    """,
                    (source_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise FeedSourceNotFoundError(source_id)
        return _parse_source_row(row)

    def get_by_subaccount(self, subaccount_id: int) -> list[FeedSourceResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, created_at, updated_at
                    FROM feed_sources WHERE subaccount_id = %s ORDER BY created_at DESC
                    """,
                    (subaccount_id,),
                )
                rows = cur.fetchall()

        return [_parse_source_row(row) for row in rows]

    def update(self, source_id: str, payload: FeedSourceUpdate) -> FeedSourceResponse:
        sets: list[str] = []
        params: list[Any] = []

        if payload.name is not None:
            sets.append("name = %s")
            params.append(payload.name)
        if payload.config is not None:
            sets.append("config = %s::jsonb")
            params.append(payload.config.model_dump_json())
        if payload.credentials_secret_id is not None:
            sets.append("credentials_secret_id = %s")
            params.append(payload.credentials_secret_id)
        if payload.is_active is not None:
            sets.append("is_active = %s")
            params.append(payload.is_active)

        if not sets:
            return self.get_by_id(source_id)

        sets.append("updated_at = NOW()")
        params.append(source_id)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE feed_sources SET {', '.join(sets)}
                    WHERE id = %s
                    RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, created_at, updated_at
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise FeedSourceNotFoundError(source_id)
        return _parse_source_row(row)

    def delete(self, source_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM feed_sources WHERE id = %s", (source_id,))
                if cur.rowcount == 0:
                    raise FeedSourceNotFoundError(source_id)
            conn.commit()

    def list_all(self, *, limit: int = 100, offset: int = 0) -> list[FeedSourceResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, created_at, updated_at
                    FROM feed_sources ORDER BY created_at DESC LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()

        return [_parse_source_row(row) for row in rows]


class FeedImportRepository:
    def create(self, payload: FeedImportCreate) -> FeedImportResponse:
        import_id = str(uuid.uuid4())

        with _connect() as conn:
            with conn.cursor() as cur:
                # Check for an already in-progress import for this source
                cur.execute(
                    "SELECT id FROM feed_imports WHERE feed_source_id = %s AND status IN ('pending', 'in_progress') LIMIT 1",
                    (payload.feed_source_id,),
                )
                if cur.fetchone() is not None:
                    raise FeedImportInProgressError(payload.feed_source_id)

                cur.execute(
                    """
                    INSERT INTO feed_imports (id, feed_source_id)
                    VALUES (%s, %s)
                    RETURNING id, feed_source_id, status, total_products, imported_products, errors, started_at, completed_at, created_at
                    """,
                    (import_id, payload.feed_source_id),
                )
                row = cur.fetchone()
            conn.commit()

        return _parse_import_row(row)

    def get_by_id(self, import_id: str) -> FeedImportResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feed_source_id, status, total_products, imported_products, errors, started_at, completed_at, created_at
                    FROM feed_imports WHERE id = %s LIMIT 1
                    """,
                    (import_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise FeedSourceNotFoundError(import_id)
        return _parse_import_row(row)

    def get_by_source(self, feed_source_id: str, *, limit: int = 50) -> list[FeedImportResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feed_source_id, status, total_products, imported_products, errors, started_at, completed_at, created_at
                    FROM feed_imports WHERE feed_source_id = %s ORDER BY created_at DESC LIMIT %s
                    """,
                    (feed_source_id, limit),
                )
                rows = cur.fetchall()

        return [_parse_import_row(row) for row in rows]

    def update_status(
        self,
        import_id: str,
        *,
        status: FeedImportStatus,
        total_products: int | None = None,
        imported_products: int | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> FeedImportResponse:
        sets = ["status = %s"]
        params: list[Any] = [status.value]

        if status == FeedImportStatus.in_progress:
            sets.append("started_at = COALESCE(started_at, NOW())")
        if status in (FeedImportStatus.completed, FeedImportStatus.failed):
            sets.append("completed_at = NOW()")

        if total_products is not None:
            sets.append("total_products = %s")
            params.append(total_products)
        if imported_products is not None:
            sets.append("imported_products = %s")
            params.append(imported_products)
        if errors is not None:
            sets.append("errors = %s::jsonb")
            params.append(json.dumps(errors))

        params.append(import_id)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE feed_imports SET {', '.join(sets)}
                    WHERE id = %s
                    RETURNING id, feed_source_id, status, total_products, imported_products, errors, started_at, completed_at, created_at
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
            conn.commit()

        if row is None:
            raise FeedSourceNotFoundError(import_id)
        return _parse_import_row(row)

    def get_latest_by_source(self, feed_source_id: str) -> FeedImportResponse | None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feed_source_id, status, total_products, imported_products, errors, started_at, completed_at, created_at
                    FROM feed_imports WHERE feed_source_id = %s ORDER BY created_at DESC LIMIT 1
                    """,
                    (feed_source_id,),
                )
                row = cur.fetchone()

        if row is None:
            return None
        return _parse_import_row(row)
