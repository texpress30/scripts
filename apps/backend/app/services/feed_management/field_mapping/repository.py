from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from app.services.feed_management.field_mapping.models import (
    FieldMappingCreate,
    FieldMappingDetailResponse,
    FieldMappingResponse,
    FieldMappingRuleCreate,
    FieldMappingRuleResponse,
    FieldMappingRuleUpdate,
    FieldMappingUpdate,
    TargetChannel,
    TransformationType,
)

logger = logging.getLogger(__name__)


def _connect():
    from app.db.pool import get_connection
    return get_connection()


# ---------------------------------------------------------------------------
# Row parsers
# ---------------------------------------------------------------------------

def _parse_mapping_row(row: tuple) -> FieldMappingResponse:
    return FieldMappingResponse(
        id=str(row[0]),
        feed_source_id=str(row[1]),
        name=str(row[2]),
        target_channel=TargetChannel(str(row[3])),
        is_active=bool(row[4]),
        created_at=row[5],
        updated_at=row[6],
    )


def _parse_rule_row(row: tuple) -> FieldMappingRuleResponse:
    config_raw = row[5]
    config = json.loads(config_raw) if isinstance(config_raw, str) else (config_raw or {})
    return FieldMappingRuleResponse(
        id=str(row[0]),
        field_mapping_id=str(row[1]),
        target_field=str(row[2]),
        source_field=str(row[3]) if row[3] else None,
        transformation_type=TransformationType(str(row[4])),
        transformation_config=config,
        is_required=bool(row[6]),
        sort_order=int(row[7]),
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class FieldMappingRepository:

    # -- Mappings CRUD -----------------------------------------------------

    def create(
        self,
        feed_source_id: str,
        payload: FieldMappingCreate,
    ) -> FieldMappingDetailResponse:
        mapping_id = str(uuid.uuid4())
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO field_mappings (id, feed_source_id, name, target_channel, is_active)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, feed_source_id, name, target_channel, is_active, created_at, updated_at
                    """,
                    (mapping_id, feed_source_id, payload.name, payload.target_channel.value, payload.is_active),
                )
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError("Failed to create field mapping")
                mapping = _parse_mapping_row(row)

                rules: list[FieldMappingRuleResponse] = []
                for rule in payload.rules:
                    rule_resp = self._insert_rule(cur, mapping_id, rule)
                    rules.append(rule_resp)

            conn.commit()

        return FieldMappingDetailResponse(**mapping.model_dump(), rules=rules)

    def get_by_id(self, mapping_id: str) -> FieldMappingDetailResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feed_source_id, name, target_channel, is_active, created_at, updated_at
                    FROM field_mappings WHERE id = %s
                    """,
                    (mapping_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise FieldMappingNotFoundError(mapping_id)
                mapping = _parse_mapping_row(row)
                rules = self._list_rules(cur, mapping_id)
        return FieldMappingDetailResponse(**mapping.model_dump(), rules=rules)

    def get_by_source(self, feed_source_id: str) -> list[FieldMappingResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, feed_source_id, name, target_channel, is_active, created_at, updated_at
                    FROM field_mappings
                    WHERE feed_source_id = %s
                    ORDER BY created_at
                    """,
                    (feed_source_id,),
                )
                return [_parse_mapping_row(r) for r in cur.fetchall()]

    def update(self, mapping_id: str, payload: FieldMappingUpdate) -> FieldMappingDetailResponse:
        sets: list[str] = []
        vals: list[Any] = []
        if payload.name is not None:
            sets.append("name = %s")
            vals.append(payload.name)
        if payload.target_channel is not None:
            sets.append("target_channel = %s")
            vals.append(payload.target_channel.value)
        if payload.is_active is not None:
            sets.append("is_active = %s")
            vals.append(payload.is_active)
        if not sets:
            return self.get_by_id(mapping_id)

        sets.append("updated_at = NOW()")
        vals.append(mapping_id)

        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE field_mappings SET {', '.join(sets)} WHERE id = %s "
                    "RETURNING id, feed_source_id, name, target_channel, is_active, created_at, updated_at",
                    vals,
                )
                row = cur.fetchone()
                if row is None:
                    raise FieldMappingNotFoundError(mapping_id)
                mapping = _parse_mapping_row(row)
                rules = self._list_rules(cur, mapping_id)
            conn.commit()
        return FieldMappingDetailResponse(**mapping.model_dump(), rules=rules)

    def delete(self, mapping_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM field_mappings WHERE id = %s", (mapping_id,))
            conn.commit()

    # -- Rules CRUD --------------------------------------------------------

    def add_rule(self, mapping_id: str, payload: FieldMappingRuleCreate) -> FieldMappingRuleResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                rule = self._insert_rule(cur, mapping_id, payload)
            conn.commit()
        return rule

    def update_rule(self, rule_id: str, payload: FieldMappingRuleUpdate) -> FieldMappingRuleResponse:
        sets: list[str] = []
        vals: list[Any] = []
        if payload.target_field is not None:
            sets.append("target_field = %s")
            vals.append(payload.target_field)
        if payload.source_field is not None:
            sets.append("source_field = %s")
            vals.append(payload.source_field)
        if payload.transformation_type is not None:
            sets.append("transformation_type = %s")
            vals.append(payload.transformation_type.value)
        if payload.transformation_config is not None:
            sets.append("transformation_config = %s::jsonb")
            vals.append(json.dumps(payload.transformation_config))
        if payload.is_required is not None:
            sets.append("is_required = %s")
            vals.append(payload.is_required)
        if payload.sort_order is not None:
            sets.append("sort_order = %s")
            vals.append(payload.sort_order)
        if not sets:
            return self._get_rule(rule_id)

        vals.append(rule_id)
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE field_mapping_rules SET {', '.join(sets)} WHERE id = %s "
                    "RETURNING id, field_mapping_id, target_field, source_field, "
                    "transformation_type, transformation_config, is_required, sort_order",
                    vals,
                )
                row = cur.fetchone()
                if row is None:
                    raise FieldMappingRuleNotFoundError(rule_id)
                rule = _parse_rule_row(row)
            conn.commit()
        return rule

    def delete_rule(self, rule_id: str) -> None:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM field_mapping_rules WHERE id = %s", (rule_id,))
            conn.commit()

    def list_rules(self, mapping_id: str) -> list[FieldMappingRuleResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                return self._list_rules(cur, mapping_id)

    def reorder_rules(self, mapping_id: str, rule_ids: list[str]) -> list[FieldMappingRuleResponse]:
        with _connect() as conn:
            with conn.cursor() as cur:
                for idx, rid in enumerate(rule_ids):
                    cur.execute(
                        "UPDATE field_mapping_rules SET sort_order = %s WHERE id = %s AND field_mapping_id = %s",
                        (idx, rid, mapping_id),
                    )
                rules = self._list_rules(cur, mapping_id)
            conn.commit()
        return rules

    # -- Internal helpers --------------------------------------------------

    def _insert_rule(self, cur, mapping_id: str, payload: FieldMappingRuleCreate) -> FieldMappingRuleResponse:
        rule_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO field_mapping_rules
                (id, field_mapping_id, target_field, source_field,
                 transformation_type, transformation_config, is_required, sort_order)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            RETURNING id, field_mapping_id, target_field, source_field,
                      transformation_type, transformation_config, is_required, sort_order
            """,
            (
                rule_id,
                mapping_id,
                payload.target_field,
                payload.source_field,
                payload.transformation_type.value,
                json.dumps(payload.transformation_config),
                payload.is_required,
                payload.sort_order,
            ),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert rule")
        return _parse_rule_row(row)

    def _list_rules(self, cur, mapping_id: str) -> list[FieldMappingRuleResponse]:
        cur.execute(
            """
            SELECT id, field_mapping_id, target_field, source_field,
                   transformation_type, transformation_config, is_required, sort_order
            FROM field_mapping_rules
            WHERE field_mapping_id = %s
            ORDER BY sort_order, target_field
            """,
            (mapping_id,),
        )
        return [_parse_rule_row(r) for r in cur.fetchall()]

    def _get_rule(self, rule_id: str) -> FieldMappingRuleResponse:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, field_mapping_id, target_field, source_field,
                           transformation_type, transformation_config, is_required, sort_order
                    FROM field_mapping_rules WHERE id = %s
                    """,
                    (rule_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise FieldMappingRuleNotFoundError(rule_id)
                return _parse_rule_row(row)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FieldMappingNotFoundError(Exception):
    def __init__(self, mapping_id: str) -> None:
        super().__init__(f"Field mapping not found: {mapping_id}")
        self.mapping_id = mapping_id


class FieldMappingRuleNotFoundError(Exception):
    def __init__(self, rule_id: str) -> None:
        super().__init__(f"Field mapping rule not found: {rule_id}")
        self.rule_id = rule_id
