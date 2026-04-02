from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.services.feed_management.master_fields.models import (
    MasterFieldMappingBulkItem,
    MasterFieldMappingResponse,
    MappingType,
)

logger = logging.getLogger(__name__)


def _connect():
    from app.db.pool import get_connection

    return get_connection()


def _parse_row(row: tuple) -> MasterFieldMappingResponse:
    return MasterFieldMappingResponse(
        id=str(row[0]),
        feed_source_id=str(row[1]),
        target_field=str(row[2]),
        source_field=str(row[3]) if row[3] else None,
        mapping_type=MappingType(str(row[4])),
        static_value=str(row[5]) if row[5] else None,
        template_value=str(row[6]) if row[6] else None,
        is_required=bool(row[7]),
        sort_order=int(row[8]),
        created_at=row[9],
        updated_at=row[10],
    )


_COLUMNS = (
    "id, feed_source_id, target_field, source_field, mapping_type, "
    "static_value, template_value, is_required, sort_order, created_at, updated_at"
)


class MasterFieldMappingRepository:

    def get_by_source(self, source_id: str) -> list[MasterFieldMappingResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {_COLUMNS} FROM master_field_mappings "
                    "WHERE feed_source_id = %s ORDER BY sort_order, target_field",
                    (source_id,),
                )
                rows = cur.fetchall()
        return [_parse_row(r) for r in rows]

    def upsert(
        self,
        source_id: str,
        target_field: str,
        data: MasterFieldMappingBulkItem,
    ) -> MasterFieldMappingResponse:
        mapping_id = str(uuid.uuid4())
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO master_field_mappings
                        (id, feed_source_id, target_field, source_field,
                         mapping_type, static_value, template_value,
                         is_required, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (feed_source_id, target_field)
                    DO UPDATE SET
                        source_field   = EXCLUDED.source_field,
                        mapping_type   = EXCLUDED.mapping_type,
                        static_value   = EXCLUDED.static_value,
                        template_value = EXCLUDED.template_value,
                        is_required    = EXCLUDED.is_required,
                        sort_order     = EXCLUDED.sort_order,
                        updated_at     = NOW()
                    RETURNING {_COLUMNS}
                    """,
                    (
                        mapping_id,
                        source_id,
                        target_field,
                        data.source_field,
                        data.mapping_type.value,
                        data.static_value,
                        data.template_value,
                        data.is_required,
                        data.sort_order,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            raise RuntimeError("Failed to upsert master field mapping")
        return _parse_row(row)

    def bulk_save(
        self,
        source_id: str,
        mappings: list[MasterFieldMappingBulkItem],
    ) -> list[MasterFieldMappingResponse]:
        results: list[MasterFieldMappingResponse] = []
        with _connect() as conn:
            with conn.cursor() as cur:
                # Remove existing mappings that are not in the new list
                target_fields = [m.target_field for m in mappings]
                if target_fields:
                    cur.execute(
                        "DELETE FROM master_field_mappings "
                        "WHERE feed_source_id = %s AND target_field != ALL(%s)",
                        (source_id, target_fields),
                    )
                else:
                    cur.execute(
                        "DELETE FROM master_field_mappings WHERE feed_source_id = %s",
                        (source_id,),
                    )

                for item in mappings:
                    mapping_id = str(uuid.uuid4())
                    cur.execute(
                        f"""
                        INSERT INTO master_field_mappings
                            (id, feed_source_id, target_field, source_field,
                             mapping_type, static_value, template_value,
                             is_required, sort_order)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (feed_source_id, target_field)
                        DO UPDATE SET
                            source_field   = EXCLUDED.source_field,
                            mapping_type   = EXCLUDED.mapping_type,
                            static_value   = EXCLUDED.static_value,
                            template_value = EXCLUDED.template_value,
                            is_required    = EXCLUDED.is_required,
                            sort_order     = EXCLUDED.sort_order,
                            updated_at     = NOW()
                        RETURNING {_COLUMNS}
                        """,
                        (
                            mapping_id,
                            source_id,
                            item.target_field,
                            item.source_field,
                            item.mapping_type.value,
                            item.static_value,
                            item.template_value,
                            item.is_required,
                            item.sort_order,
                        ),
                    )
                    row = cur.fetchone()
                    if row is not None:
                        results.append(_parse_row(row))
            conn.commit()
        return results

    def delete(self, mapping_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM master_field_mappings WHERE id = %s",
                    (mapping_id,),
                )
                if cur.rowcount == 0:
                    raise MasterFieldMappingNotFoundError(mapping_id)
            conn.commit()


class MasterFieldMappingNotFoundError(Exception):
    def __init__(self, mapping_id: str) -> None:
        super().__init__(f"Master field mapping {mapping_id} not found")
        self.mapping_id = mapping_id


master_field_mapping_repository = MasterFieldMappingRepository()
