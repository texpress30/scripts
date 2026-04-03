"""Repository for feed_schema_fields, feed_schema_channel_fields, feed_schema_imports."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _connect():
    from app.db.pool import get_connection
    return get_connection()


class SchemaRegistryRepository:

    # ------------------------------------------------------------------
    # feed_schema_fields
    # ------------------------------------------------------------------

    def upsert_field(
        self,
        *,
        catalog_type: str,
        field_key: str,
        display_name: str,
        description: str | None,
        data_type: str,
        allowed_values: list[str] | None,
        format_pattern: str | None,
        example_value: str | None,
    ) -> tuple[str, bool]:
        """Upsert a schema field.  Returns (field_id, was_inserted).

        For allowed_values, merges with existing values (union) instead of
        replacing them so no previously defined options are lost.
        """
        allowed_json = json.dumps(allowed_values) if allowed_values else None

        with _connect() as conn:
            with conn.cursor() as cur:
                # Try insert first
                cur.execute(
                    """
                    INSERT INTO feed_schema_fields
                        (catalog_type, field_key, display_name, description,
                         data_type, allowed_values, format_pattern, example_value)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (catalog_type, field_key) DO UPDATE SET
                        display_name    = CASE WHEN EXCLUDED.display_name    != '' THEN EXCLUDED.display_name    ELSE feed_schema_fields.display_name END,
                        description     = CASE WHEN EXCLUDED.description     IS NOT NULL AND EXCLUDED.description != '' THEN EXCLUDED.description ELSE feed_schema_fields.description END,
                        data_type       = CASE WHEN EXCLUDED.data_type       != 'string' THEN EXCLUDED.data_type ELSE feed_schema_fields.data_type END,
                        allowed_values  = CASE
                                            WHEN EXCLUDED.allowed_values IS NOT NULL AND feed_schema_fields.allowed_values IS NOT NULL
                                            THEN (
                                                SELECT jsonb_agg(DISTINCT val)
                                                FROM (
                                                    SELECT jsonb_array_elements(feed_schema_fields.allowed_values) AS val
                                                    UNION
                                                    SELECT jsonb_array_elements(EXCLUDED.allowed_values) AS val
                                                ) merged
                                            )
                                            WHEN EXCLUDED.allowed_values IS NOT NULL THEN EXCLUDED.allowed_values
                                            ELSE feed_schema_fields.allowed_values
                                          END,
                        format_pattern  = CASE WHEN EXCLUDED.format_pattern  IS NOT NULL AND EXCLUDED.format_pattern  != '' THEN EXCLUDED.format_pattern  ELSE feed_schema_fields.format_pattern  END,
                        example_value   = CASE WHEN EXCLUDED.example_value   IS NOT NULL AND EXCLUDED.example_value   != '' THEN EXCLUDED.example_value   ELSE feed_schema_fields.example_value   END,
                        updated_at      = NOW()
                    RETURNING id, (xmax = 0) AS inserted
                    """,
                    (
                        catalog_type, field_key, display_name, description or "",
                        data_type, allowed_json, format_pattern or None, example_value or None,
                    ),
                )
                row = cur.fetchone()
            conn.commit()

        field_id = str(row[0])
        was_inserted = bool(row[1])
        return field_id, was_inserted

    # ------------------------------------------------------------------
    # feed_schema_channel_fields
    # ------------------------------------------------------------------

    def upsert_channel_field(
        self,
        *,
        schema_field_id: str,
        channel_slug: str,
        is_required: bool,
        channel_field_name: str | None,
        default_value: str | None,
        sort_order: int,
    ) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feed_schema_channel_fields
                        (schema_field_id, channel_slug, is_required,
                         channel_field_name, default_value, sort_order, imported_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (schema_field_id, channel_slug) DO UPDATE SET
                        is_required        = EXCLUDED.is_required,
                        channel_field_name = EXCLUDED.channel_field_name,
                        default_value      = EXCLUDED.default_value,
                        sort_order         = EXCLUDED.sort_order,
                        imported_at        = NOW()
                    """,
                    (schema_field_id, channel_slug, is_required,
                     channel_field_name, default_value, sort_order),
                )
            conn.commit()

    def count_existing_channel_fields(
        self,
        channel_slug: str,
        catalog_type: str,
    ) -> set[str]:
        """Return field_keys that already exist for this channel+catalog combo."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT f.field_key
                    FROM feed_schema_channel_fields cf
                    JOIN feed_schema_fields f ON f.id = cf.schema_field_id
                    WHERE cf.channel_slug = %s AND f.catalog_type = %s
                    """,
                    (channel_slug, catalog_type),
                )
                rows = cur.fetchall()
        return {str(r[0]) for r in rows}

    def count_total_fields(self, catalog_type: str) -> int:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM feed_schema_fields WHERE catalog_type = %s",
                    (catalog_type,),
                )
                row = cur.fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # feed_schema_imports
    # ------------------------------------------------------------------

    def create_import_log(
        self,
        *,
        channel_slug: str,
        catalog_type: str,
        agency_id: int | None,
        filename: str,
        s3_path: str | None,
        fields_added: int,
        fields_updated: int,
        fields_deprecated: int,
        imported_by: int | None,
    ) -> str:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feed_schema_imports
                        (channel_slug, catalog_type, agency_id, filename,
                         s3_path, fields_added, fields_updated,
                         fields_deprecated, imported_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (channel_slug, catalog_type, agency_id, filename,
                     s3_path, fields_added, fields_updated,
                     fields_deprecated, imported_by),
                )
                row = cur.fetchone()
            conn.commit()
        return str(row[0])


schema_registry_repository = SchemaRegistryRepository()
