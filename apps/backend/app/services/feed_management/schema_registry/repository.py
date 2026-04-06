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
        source_description: str | None = None,
        subtype_slug: str | None = None,
    ) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feed_schema_channel_fields
                        (schema_field_id, channel_slug, is_required,
                         channel_field_name, default_value, sort_order,
                         source_description, subtype_slug, imported_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (schema_field_id, channel_slug) DO UPDATE SET
                        is_required        = EXCLUDED.is_required,
                        channel_field_name = EXCLUDED.channel_field_name,
                        default_value      = EXCLUDED.default_value,
                        sort_order         = EXCLUDED.sort_order,
                        source_description = CASE
                            WHEN EXCLUDED.source_description IS NOT NULL AND EXCLUDED.source_description != ''
                            THEN EXCLUDED.source_description
                            ELSE feed_schema_channel_fields.source_description
                        END,
                        subtype_slug       = COALESCE(EXCLUDED.subtype_slug, feed_schema_channel_fields.subtype_slug),
                        imported_at        = NOW()
                    """,
                    (schema_field_id, channel_slug, is_required,
                     channel_field_name, default_value, sort_order,
                     source_description, subtype_slug),
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

    def count_total_fields(self, catalog_type: str, canonical_only: bool = False) -> int:
        if canonical_only:
            sql = (
                "SELECT count(*) FROM feed_schema_fields WHERE catalog_type = %s "
                "AND (canonical_group = field_key OR canonical_group IS NULL)"
            )
        else:
            sql = "SELECT count(*) FROM feed_schema_fields WHERE catalog_type = %s"
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (catalog_type,))
                row = cur.fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Feed generation queries
    # ------------------------------------------------------------------

    def get_channel_field_specs(
        self,
        channel_slug: str,
        catalog_type: str,
    ) -> list[dict[str, Any]]:
        """Return field specs for feed generation: field_key, channel_field_name,
        data_type, allowed_values, format_pattern, is_required, default_value.

        Single query, ordered by sort_order.
        """
        sql = """
            SELECT
                f.field_key,
                COALESCE(cf.channel_field_name, f.field_key) AS channel_field_name,
                f.data_type,
                f.allowed_values,
                f.format_pattern,
                cf.is_required,
                cf.default_value
            FROM feed_schema_channel_fields cf
            JOIN feed_schema_fields f ON f.id = cf.schema_field_id
            WHERE cf.channel_slug = %s AND f.catalog_type = %s
            ORDER BY cf.sort_order
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (channel_slug, catalog_type))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            if isinstance(d.get("allowed_values"), str):
                d["allowed_values"] = json.loads(d["allowed_values"])
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Retrieval queries
    # ------------------------------------------------------------------

    def list_fields(
        self,
        catalog_type: str,
        channel_slug: str | None = None,
        canonical_only: bool = False,
        subtype_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return schema fields with aggregated channel info in a single query.

        When *channel_slug* is provided, only fields linked to that channel are
        returned and ``is_required`` reflects that channel's setting.  Otherwise
        all fields for the catalog type are returned with ``is_required`` set to
        the MAX across all channels.

        When *canonical_only* is True, only canonical fields are returned (where
        canonical_group = field_key OR canonical_group IS NULL).  Alias counts
        and all_channels (including channels via aliases) are aggregated.

        When *subtype_slug* is provided, only fields linked to channels with
        that subtype_slug are returned.
        """
        canonical_filter = ""
        if canonical_only:
            canonical_filter = " AND (f.canonical_group = f.field_key OR f.canonical_group IS NULL)"
        subtype_filter = ""
        if subtype_slug:
            subtype_filter = " AND cf.subtype_slug = %s"

        if channel_slug:
            sql = f"""
                SELECT
                    f.id, f.field_key, f.display_name, f.description,
                    f.data_type, f.allowed_values, f.format_pattern,
                    f.example_value, f.is_system,
                    f.canonical_group, f.canonical_status,
                    cf.is_required AS is_required,
                    cf.sort_order,
                    jsonb_build_array(
                        jsonb_build_object(
                            'channel_slug', cf.channel_slug,
                            'is_required', cf.is_required,
                            'channel_field_name', COALESCE(cf.channel_field_name, f.field_key),
                            'source_description', cf.source_description
                        )
                    ) AS channels
                FROM feed_schema_fields f
                JOIN feed_schema_channel_fields cf ON cf.schema_field_id = f.id
                WHERE f.catalog_type = %s AND cf.channel_slug = %s{canonical_filter}{subtype_filter}
                ORDER BY cf.is_required DESC, f.is_system DESC, cf.sort_order ASC
            """
            params_list: list[Any] = [catalog_type, channel_slug]
            if subtype_slug:
                params_list.append(subtype_slug)
            params: tuple[Any, ...] = tuple(params_list)
        else:
            # When subtype_slug is given without channel_slug, filter via a subquery
            subtype_join = ""
            if subtype_slug:
                subtype_join = (
                    " AND f.id IN ("
                    "   SELECT cf2.schema_field_id FROM feed_schema_channel_fields cf2"
                    "   WHERE cf2.subtype_slug = %s"
                    " )"
                )
            sql = f"""
                SELECT
                    f.id, f.field_key, f.display_name, f.description,
                    f.data_type, f.allowed_values, f.format_pattern,
                    f.example_value, f.is_system,
                    f.canonical_group, f.canonical_status,
                    COALESCE(bool_or(cf.is_required), false) AS is_required,
                    COALESCE(MIN(cf.sort_order), 0) AS sort_order,
                    COALESCE(
                        jsonb_agg(
                            jsonb_build_object(
                                'channel_slug', cf.channel_slug,
                                'is_required', cf.is_required,
                                'channel_field_name', COALESCE(cf.channel_field_name, f.field_key),
                                'source_description', cf.source_description
                            )
                        ) FILTER (WHERE cf.id IS NOT NULL),
                        '[]'::jsonb
                    ) AS channels
                FROM feed_schema_fields f
                LEFT JOIN feed_schema_channel_fields cf ON cf.schema_field_id = f.id
                WHERE f.catalog_type = %s{canonical_filter}{subtype_join}
                GROUP BY f.id, f.field_key, f.display_name, f.description,
                         f.data_type, f.allowed_values, f.format_pattern,
                         f.example_value, f.is_system,
                         f.canonical_group, f.canonical_status
                ORDER BY COALESCE(bool_or(cf.is_required), false) DESC,
                         f.is_system DESC,
                         COALESCE(MIN(cf.sort_order), 0) ASC
            """
            params_list2: list[Any] = [catalog_type]
            if subtype_slug:
                params_list2.append(subtype_slug)
            params = tuple(params_list2)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            d["id"] = str(d["id"])
            # allowed_values and channels may already be parsed by psycopg
            if isinstance(d.get("allowed_values"), str):
                d["allowed_values"] = json.loads(d["allowed_values"])
            if isinstance(d.get("channels"), str):
                d["channels"] = json.loads(d["channels"])
            results.append(d)

        # When canonical_only, enrich with alias counts and all_channels
        if canonical_only and results:
            alias_map = self.get_aliases_for_fields(catalog_type)
            # Also get all channel links for alias fields
            alias_channels = self._get_alias_channels(catalog_type)
            for d in results:
                fk = d["field_key"]
                aliases = alias_map.get(fk, [])
                d["aliases_count"] = len(aliases)
                d["aliases"] = aliases
                # Merge channels from direct + alias fields
                direct_channels = [ch["channel_slug"] for ch in (d.get("channels") or [])]
                alias_ch = alias_channels.get(fk, [])
                all_ch = list(dict.fromkeys(direct_channels + alias_ch))  # dedupe, preserve order
                d["all_channels"] = all_ch
                d["channels_count"] = len(all_ch)

        return results

    def _get_alias_channels(self, catalog_type: str) -> dict[str, list[str]]:
        """Return {canonical_key: [channel_slugs from alias fields]}."""
        sql = """
            SELECT a.canonical_key, cf.channel_slug
            FROM feed_field_aliases a
            JOIN feed_schema_fields f ON f.catalog_type = a.catalog_type AND f.field_key = a.alias_key
            JOIN feed_schema_channel_fields cf ON cf.schema_field_id = f.id
            WHERE a.catalog_type = %s
            ORDER BY a.canonical_key, cf.channel_slug
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (catalog_type,))
                rows = cur.fetchall()
        result: dict[str, list[str]] = {}
        for canonical_key, channel_slug in rows:
            result.setdefault(str(canonical_key), []).append(str(channel_slug))
        return result

    def get_channel_fields_with_mappings(
        self,
        channel_slug: str,
        catalog_type: str,
        source_id: str,
    ) -> list[dict[str, Any]]:
        """Return channel-specific fields with inherited master mappings.

        For each channel field, checks for a channel override first,
        then falls back to the master field mapping on the canonical key.
        """
        sql = """
            SELECT
                f.id AS schema_field_id,
                f.field_key AS canonical_key,
                f.display_name,
                f.data_type,
                cf.channel_field_name,
                cf.is_required,
                cf.sort_order,
                cf.source_description,
                -- Master mapping (inherited)
                mm.source_field AS master_source_field,
                mm.mapping_type AS master_mapping_type,
                mm.static_value AS master_static_value,
                mm.template_value AS master_template_value,
                -- Channel override
                co.source_field AS override_source_field,
                co.mapping_type AS override_mapping_type,
                co.static_value AS override_static_value,
                co.template_value AS override_template_value,
                co.id AS override_id
            FROM feed_schema_channel_fields cf
            JOIN feed_schema_fields f ON f.id = cf.schema_field_id
            LEFT JOIN master_field_mappings mm
                ON mm.feed_source_id = %s AND mm.target_field = f.field_key
            LEFT JOIN channel_field_overrides co
                ON co.channel_id = (
                    SELECT fc.id FROM feed_channels fc
                    WHERE fc.feed_source_id = %s AND fc.channel_type = %s
                    LIMIT 1
                )
                AND co.target_field = f.field_key
            WHERE cf.channel_slug = %s AND f.catalog_type = %s
            ORDER BY cf.is_required DESC, cf.sort_order ASC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (source_id, source_id, channel_slug, channel_slug, catalog_type))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            d["schema_field_id"] = str(d["schema_field_id"])

            # Determine effective mapping (override > master)
            if d.get("override_id"):
                mapping = {
                    "type": d["override_mapping_type"] or "direct",
                    "source_field": d["override_source_field"],
                    "static_value": d["override_static_value"],
                    "template_value": d["override_template_value"],
                    "inherited_from": "channel_override",
                }
            elif d.get("master_source_field") or d.get("master_static_value") or d.get("master_template_value"):
                mapping = {
                    "type": d["master_mapping_type"] or "direct",
                    "source_field": d["master_source_field"],
                    "static_value": d["master_static_value"],
                    "template_value": d["master_template_value"],
                    "inherited_from": "master_fields",
                }
            else:
                mapping = None

            results.append({
                "canonical_key": d["canonical_key"],
                "channel_field_name": d["channel_field_name"] or d["canonical_key"],
                "display_name": d["display_name"],
                "data_type": d["data_type"],
                "is_required": d["is_required"],
                "sort_order": d["sort_order"],
                "source_description": d["source_description"],
                "mapping": mapping,
            })
        return results

    def get_channel_fields_by_channel_id(
        self,
        channel_id: str,
        source_id: str,
        channel_type: str,
        catalog_type: str,
    ) -> list[dict[str, Any]]:
        """Return channel-specific fields using channel_id for override lookups."""
        sql = """
            SELECT
                f.id AS schema_field_id,
                f.field_key AS canonical_key,
                f.display_name,
                f.data_type,
                cf.channel_field_name,
                cf.is_required,
                cf.sort_order,
                cf.source_description,
                mm.source_field AS master_source_field,
                mm.mapping_type AS master_mapping_type,
                mm.static_value AS master_static_value,
                mm.template_value AS master_template_value,
                co.source_field AS override_source_field,
                co.mapping_type AS override_mapping_type,
                co.static_value AS override_static_value,
                co.template_value AS override_template_value,
                co.id AS override_id
            FROM feed_schema_channel_fields cf
            JOIN feed_schema_fields f ON f.id = cf.schema_field_id
            LEFT JOIN master_field_mappings mm
                ON mm.feed_source_id = %s AND mm.target_field = f.field_key
            LEFT JOIN channel_field_overrides co
                ON co.channel_id = %s AND co.target_field = f.field_key
            WHERE cf.channel_slug = %s AND f.catalog_type = %s
            ORDER BY cf.is_required DESC, cf.sort_order ASC
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (source_id, channel_id, channel_type, catalog_type))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            d["schema_field_id"] = str(d["schema_field_id"])

            if d.get("override_id"):
                mapping = {
                    "type": d["override_mapping_type"] or "direct",
                    "source_field": d["override_source_field"],
                    "static_value": d["override_static_value"],
                    "template_value": d["override_template_value"],
                    "inherited_from": "channel_override",
                }
            elif d.get("master_source_field") or d.get("master_static_value") or d.get("master_template_value"):
                mapping = {
                    "type": d["master_mapping_type"] or "direct",
                    "source_field": d["master_source_field"],
                    "static_value": d["master_static_value"],
                    "template_value": d["master_template_value"],
                    "inherited_from": "master_fields",
                }
            else:
                mapping = None

            results.append({
                "canonical_key": d["canonical_key"],
                "channel_field_name": d["channel_field_name"] or d["canonical_key"],
                "display_name": d["display_name"],
                "data_type": d["data_type"],
                "is_required": d["is_required"],
                "sort_order": d["sort_order"],
                "source_description": d["source_description"],
                "mapping": mapping,
            })
        return results

    def list_channels(self, catalog_type: str) -> list[dict[str, Any]]:
        """Return channel summary for a catalog type."""
        sql = """
            SELECT
                cf.channel_slug,
                count(*) AS fields_count,
                count(*) FILTER (WHERE cf.is_required) AS required_count,
                count(*) FILTER (WHERE NOT cf.is_required) AS optional_count,
                MAX(cf.imported_at) AS last_imported_at
            FROM feed_schema_channel_fields cf
            JOIN feed_schema_fields f ON f.id = cf.schema_field_id
            WHERE f.catalog_type = %s
            GROUP BY cf.channel_slug
            ORDER BY cf.channel_slug
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (catalog_type,))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    def list_imports(
        self,
        *,
        catalog_type: str | None = None,
        channel_slug: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return import history, optionally filtered."""
        conditions: list[str] = []
        params: list[Any] = []

        if catalog_type:
            conditions.append("catalog_type = %s")
            params.append(catalog_type)
        if channel_slug:
            conditions.append("channel_slug = %s")
            params.append(channel_slug)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(min(max(1, limit), 100))

        sql = f"""
            SELECT id, channel_slug, catalog_type, agency_id, filename,
                   s3_path, fields_added, fields_updated, fields_deprecated,
                   imported_by, imported_at
            FROM feed_schema_imports
            {where}
            ORDER BY imported_at DESC
            LIMIT %s
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            d["id"] = str(d["id"])
            results.append(d)
        return results

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


    # ------------------------------------------------------------------
    # feed_field_aliases
    # ------------------------------------------------------------------

    def get_aliases(self, catalog_type: str) -> dict[str, str]:
        """Return {alias_key: canonical_key} for a catalog type."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT alias_key, canonical_key FROM feed_field_aliases WHERE catalog_type = %s",
                    (catalog_type,),
                )
                rows = cur.fetchall()
        return {str(r[0]): str(r[1]) for r in rows}

    def list_aliases(self, catalog_type: str) -> list[dict[str, Any]]:
        """Return all aliases for a catalog type."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, catalog_type, canonical_key, alias_key,
                           platform_hint, platform_hints, created_at
                    FROM feed_field_aliases
                    WHERE catalog_type = %s
                    ORDER BY canonical_key, alias_key
                    """,
                    (catalog_type,),
                )
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
        results = []
        for r in rows:
            d = dict(zip(cols, r))
            d["id"] = str(d["id"])
            hints = d.get("platform_hints")
            d["platform_hints"] = list(hints) if hints else []
            results.append(d)
        return results

    def create_alias(
        self,
        *,
        catalog_type: str,
        canonical_key: str,
        alias_key: str,
        platform_hint: str | None,
    ) -> dict[str, Any]:
        """Create a new alias. Returns the created row."""
        with _connect() as conn:
            with conn.cursor() as cur:
                # Validate canonical_key exists
                cur.execute(
                    "SELECT 1 FROM feed_schema_fields WHERE catalog_type = %s AND field_key = %s",
                    (catalog_type, canonical_key),
                )
                if not cur.fetchone():
                    raise ValueError(
                        f"canonical_key '{canonical_key}' does not exist in "
                        f"feed_schema_fields for catalog_type '{catalog_type}'"
                    )

                # Validate alias_key isn't already a canonical key
                cur.execute(
                    "SELECT 1 FROM feed_field_aliases WHERE catalog_type = %s AND canonical_key = %s",
                    (catalog_type, alias_key),
                )
                if cur.fetchone():
                    raise ValueError(
                        f"alias_key '{alias_key}' is already used as a canonical_key — "
                        f"would create a cycle"
                    )

                cur.execute(
                    """
                    INSERT INTO feed_field_aliases
                        (catalog_type, canonical_key, alias_key, platform_hint, platform_hints)
                    VALUES (%s, %s, %s, %s,
                            CASE WHEN %s IS NOT NULL AND %s != '' THEN jsonb_build_array(%s) ELSE '[]'::jsonb END)
                    ON CONFLICT (catalog_type, alias_key) DO UPDATE SET
                        platform_hint = COALESCE(EXCLUDED.platform_hint, feed_field_aliases.platform_hint),
                        platform_hints = CASE
                            WHEN EXCLUDED.platform_hint IS NOT NULL
                                 AND EXCLUDED.platform_hint != ''
                                 AND NOT feed_field_aliases.platform_hints @> jsonb_build_array(EXCLUDED.platform_hint)
                            THEN feed_field_aliases.platform_hints || jsonb_build_array(EXCLUDED.platform_hint)
                            ELSE feed_field_aliases.platform_hints
                        END
                    RETURNING id, catalog_type, canonical_key, alias_key,
                              platform_hint, platform_hints, created_at
                    """,
                    (catalog_type, canonical_key, alias_key, platform_hint,
                     platform_hint, platform_hint, platform_hint),
                )
                cols = [desc[0] for desc in cur.description]
                row = cur.fetchone()
            conn.commit()
        d = dict(zip(cols, row))
        d["id"] = str(d["id"])
        # Ensure platform_hints is a plain list for JSON serialization
        if isinstance(d.get("platform_hints"), list):
            pass
        elif d.get("platform_hints"):
            d["platform_hints"] = list(d["platform_hints"])
        else:
            d["platform_hints"] = []
        return d

    def delete_alias(self, alias_id: str) -> None:
        """Delete an alias by ID."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM feed_field_aliases WHERE id = %s RETURNING id",
                    (alias_id,),
                )
                if not cur.fetchone():
                    raise ValueError(f"Alias {alias_id} not found")
            conn.commit()

    def get_aliases_for_fields(self, catalog_type: str) -> dict[str, list[dict[str, Any]]]:
        """Return {canonical_key: [{alias_key, platform_hint, platform_hints}, ...]} for display."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT canonical_key, alias_key, platform_hint, platform_hints
                    FROM feed_field_aliases
                    WHERE catalog_type = %s
                    ORDER BY canonical_key, alias_key
                    """,
                    (catalog_type,),
                )
                rows = cur.fetchall()
        result: dict[str, list[dict[str, Any]]] = {}
        for canonical, alias, hint, hints in rows:
            platform_hints = list(hints) if hints else []
            result.setdefault(str(canonical), []).append({
                "alias_key": str(alias),
                "platform_hint": str(hint) if hint else "",
                "platform_hints": platform_hints,
            })
        return result


    # ------------------------------------------------------------------
    # Canonical group updates
    # ------------------------------------------------------------------

    def set_canonical(self, field_id: str, canonical_group: str, status: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE feed_schema_fields SET canonical_group = %s, canonical_status = %s WHERE id = %s",
                    (canonical_group, status, field_id),
                )
            conn.commit()

    def bulk_set_canonical(self, updates: list[dict[str, str]]) -> int:
        count = 0
        with _connect() as conn:
            with conn.cursor() as cur:
                for u in updates:
                    cur.execute(
                        "UPDATE feed_schema_fields SET canonical_group = %s, canonical_status = %s WHERE id = %s",
                        (u["canonical_group"], u.get("status", "confirmed"), u["field_id"]),
                    )
                    count += cur.rowcount
            conn.commit()
        return count

    # ------------------------------------------------------------------
    # Merge duplicates
    # ------------------------------------------------------------------

    def merge_field_into_canonical(
        self,
        *,
        catalog_type: str,
        canonical_key: str,
        alias_key: str,
        platform_hint: str | None = None,
    ) -> bool:
        """Merge a duplicate field into a canonical one.

        Creates alias, moves channel links, deletes the duplicate field.
        Returns True if merge happened, False if fields didn't exist.
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                # Find both field IDs
                cur.execute(
                    "SELECT id FROM feed_schema_fields WHERE catalog_type = %s AND field_key = %s",
                    (catalog_type, canonical_key),
                )
                row = cur.fetchone()
                if not row:
                    return False
                canonical_id = row[0]

                cur.execute(
                    "SELECT id FROM feed_schema_fields WHERE catalog_type = %s AND field_key = %s",
                    (catalog_type, alias_key),
                )
                row = cur.fetchone()
                if not row:
                    return False
                alias_id = row[0]

                # Create alias (append platform_hint on conflict)
                cur.execute(
                    """
                    INSERT INTO feed_field_aliases
                        (catalog_type, canonical_key, alias_key, platform_hint, platform_hints)
                    VALUES (%s, %s, %s, %s,
                            CASE WHEN %s IS NOT NULL AND %s != '' THEN jsonb_build_array(%s) ELSE '[]'::jsonb END)
                    ON CONFLICT (catalog_type, alias_key) DO UPDATE SET
                        platform_hint = COALESCE(EXCLUDED.platform_hint, feed_field_aliases.platform_hint),
                        platform_hints = CASE
                            WHEN EXCLUDED.platform_hint IS NOT NULL
                                 AND EXCLUDED.platform_hint != ''
                                 AND NOT feed_field_aliases.platform_hints @> jsonb_build_array(EXCLUDED.platform_hint)
                            THEN feed_field_aliases.platform_hints || jsonb_build_array(EXCLUDED.platform_hint)
                            ELSE feed_field_aliases.platform_hints
                        END
                    """,
                    (catalog_type, canonical_key, alias_key, platform_hint,
                     platform_hint, platform_hint, platform_hint),
                )

                # Move channel links: set channel_field_name to preserve original name
                cur.execute(
                    """
                    UPDATE feed_schema_channel_fields
                    SET schema_field_id = %s,
                        channel_field_name = COALESCE(channel_field_name, %s)
                    WHERE schema_field_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM feed_schema_channel_fields cf2
                          WHERE cf2.schema_field_id = %s
                            AND cf2.channel_slug = feed_schema_channel_fields.channel_slug
                      )
                    """,
                    (canonical_id, alias_key, alias_id, canonical_id),
                )

                # Delete orphaned channel links
                cur.execute(
                    "DELETE FROM feed_schema_channel_fields WHERE schema_field_id = %s",
                    (alias_id,),
                )

                # Delete duplicate field
                cur.execute(
                    "DELETE FROM feed_schema_fields WHERE id = %s",
                    (alias_id,),
                )

            conn.commit()
        return True

    # ------------------------------------------------------------------
    # Catalog sub-types
    # ------------------------------------------------------------------

    def list_subtypes(
        self,
        catalog_type: str,
    ) -> list[dict[str, Any]]:
        """Return sub-types for a catalog type with channel and field counts."""
        sql = """
            SELECT
                st.id, st.catalog_type, st.subtype_slug, st.subtype_name,
                st.description, st.icon_hint, st.sort_order, st.created_at,
                COALESCE(ch_counts.channels_count, 0) AS channels_count,
                COALESCE(ch_counts.fields_count, 0) AS fields_count,
                COALESCE(ch_counts.channel_slugs, ARRAY[]::text[]) AS channels
            FROM feed_catalog_subtypes st
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(DISTINCT cf.channel_slug) AS channels_count,
                    COUNT(DISTINCT cf.schema_field_id) AS fields_count,
                    ARRAY_AGG(DISTINCT cf.channel_slug) AS channel_slugs
                FROM feed_schema_channel_fields cf
                WHERE cf.subtype_slug = st.subtype_slug
            ) ch_counts ON true
            WHERE st.catalog_type = %s
            ORDER BY st.sort_order, st.subtype_name
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (catalog_type,))
                cols = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            d = dict(zip(cols, row))
            d["id"] = str(d["id"])
            # Convert psycopg array to list
            if d.get("channels") and not isinstance(d["channels"], list):
                d["channels"] = list(d["channels"])
            results.append(d)
        return results

    def create_subtype(
        self,
        *,
        catalog_type: str,
        subtype_slug: str,
        subtype_name: str,
        description: str | None = None,
        icon_hint: str | None = None,
        sort_order: int = 0,
    ) -> dict[str, Any]:
        """Create a new catalog sub-type. Returns the created row."""
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feed_catalog_subtypes
                        (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, catalog_type, subtype_slug, subtype_name,
                              description, icon_hint, sort_order, created_at
                    """,
                    (catalog_type, subtype_slug, subtype_name, description, icon_hint, sort_order),
                )
                cols = [desc[0] for desc in cur.description]
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to create catalog subtype")
        d = dict(zip(cols, row))
        d["id"] = str(d["id"])
        return d

    def delete_subtype(self, subtype_id: str) -> None:
        """Delete a sub-type only if no channel fields reference it."""
        with _connect() as conn:
            with conn.cursor() as cur:
                # Check for linked channel fields
                cur.execute(
                    """
                    SELECT st.subtype_slug FROM feed_catalog_subtypes st
                    WHERE st.id = %s
                    """,
                    (subtype_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Subtype {subtype_id} not found")
                slug = row[0]

                cur.execute(
                    "SELECT count(*) FROM feed_schema_channel_fields WHERE subtype_slug = %s",
                    (slug,),
                )
                count = cur.fetchone()[0]
                if count > 0:
                    raise ValueError(
                        f"Cannot delete subtype '{slug}': {count} channel field(s) still reference it"
                    )

                cur.execute(
                    "DELETE FROM feed_catalog_subtypes WHERE id = %s",
                    (subtype_id,),
                )
            conn.commit()

    def get_channel_subtype_map(self, catalog_type: str) -> dict[str, dict[str, str]]:
        """Return {channel_slug: {subtype_slug, subtype_name}} for a catalog type."""
        sql = """
            SELECT DISTINCT cf.channel_slug, cf.subtype_slug, st.subtype_name
            FROM feed_schema_channel_fields cf
            LEFT JOIN feed_catalog_subtypes st
                ON st.catalog_type = %s AND st.subtype_slug = cf.subtype_slug
            JOIN feed_schema_fields f ON f.id = cf.schema_field_id
            WHERE f.catalog_type = %s AND cf.subtype_slug IS NOT NULL
        """
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (catalog_type, catalog_type))
                rows = cur.fetchall()
        result: dict[str, dict[str, str]] = {}
        for channel_slug, subtype_slug, subtype_name in rows:
            result[str(channel_slug)] = {
                "subtype_slug": str(subtype_slug),
                "subtype_name": str(subtype_name) if subtype_name else str(subtype_slug),
            }
        return result


schema_registry_repository = SchemaRegistryRepository()
