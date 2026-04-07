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
        last_sync_at=row[10],
        product_count=int(row[11] or 0),
        created_at=row[12],
        updated_at=row[13],
        catalog_variant=str(row[14]) if row[14] else "physical_products",
        shop_domain=str(row[15]) if row[15] else None,
        connection_status=str(row[16]) if row[16] else "pending",
        last_connection_check=row[17],
        last_error=str(row[18]) if row[18] else None,
        has_token=bool(row[19]),
        token_scopes=str(row[20]) if row[20] else None,
        last_import_at=row[21],
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

                # Check for duplicate Shopify shop within the same subaccount
                if payload.shop_domain:
                    cur.execute(
                        """
                        SELECT id FROM feed_sources
                        WHERE subaccount_id = %s AND source_type = %s AND shop_domain = %s
                        LIMIT 1
                        """,
                        (payload.subaccount_id, payload.source_type.value, payload.shop_domain),
                    )
                    if cur.fetchone() is not None:
                        raise FeedSourceAlreadyExistsError(payload.shop_domain, payload.subaccount_id)

                cur.execute(
                    """
                    INSERT INTO feed_sources (
                        id, subaccount_id, source_type, name, config,
                        credentials_secret_id, catalog_type, catalog_variant, shop_domain
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
                    """,
                    (
                        source_id,
                        payload.subaccount_id,
                        payload.source_type.value,
                        payload.name,
                        config_json,
                        payload.credentials_secret_id,
                        payload.catalog_type,
                        payload.catalog_variant,
                        payload.shop_domain,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        return _parse_source_row(row)

    def mark_oauth_connected(
        self,
        source_id: str,
        *,
        scopes: str | None,
    ) -> FeedSourceResponse:
        """Flip a feed source to ``connected`` after a successful OAuth exchange."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE feed_sources
                    SET connection_status = 'connected',
                        has_token = TRUE,
                        token_scopes = %s,
                        last_connection_check = NOW(),
                        last_error = NULL,
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
                    """,
                    (scopes, source_id),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise FeedSourceNotFoundError(source_id)
        return _parse_source_row(row)

    def record_connection_check(
        self,
        source_id: str,
        *,
        success: bool,
        error: str | None = None,
    ) -> FeedSourceResponse:
        """Persist the outcome of a live connection probe."""
        with _connect() as conn:
            with conn.cursor() as cur:
                if success:
                    cur.execute(
                        """
                        UPDATE feed_sources
                        SET last_connection_check = NOW(),
                            connection_status = 'connected',
                            last_error = NULL,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
                        """,
                        (source_id,),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE feed_sources
                        SET last_connection_check = NOW(),
                            connection_status = 'error',
                            last_error = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
                        """,
                        (error or "Unknown error", source_id),
                    )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise FeedSourceNotFoundError(source_id)
        return _parse_source_row(row)

    def clear_token(self, source_id: str) -> None:
        """Clear stored-token flags on the row (token row in integration_secrets is deleted separately)."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE feed_sources
                    SET has_token = FALSE,
                        token_scopes = NULL,
                        connection_status = 'disconnected',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (source_id,),
                )
            conn.commit()

    def get_by_id(self, source_id: str) -> FeedSourceResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
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
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
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
        if payload.catalog_type is not None:
            sets.append("catalog_type = %s")
            params.append(payload.catalog_type)
        if payload.catalog_variant is not None:
            sets.append("catalog_variant = %s")
            params.append(payload.catalog_variant)

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
                    RETURNING id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
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
                    SELECT id, subaccount_id, source_type, name, config, credentials_secret_id, is_active, catalog_type, sync_schedule, next_scheduled_sync, last_sync_at, product_count, created_at, updated_at, catalog_variant, shop_domain, connection_status, last_connection_check, last_error, has_token, token_scopes, last_import_at
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
