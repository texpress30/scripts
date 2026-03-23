from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping

from app.core.config import load_settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None

_SUPPORTED_SOURCES: tuple[tuple[str, str], ...] = (
    ("call_center", "Call Center"),
    ("direct", "Direct"),
    ("google_ads", "Google"),
    ("linkedin_ads", "LinkedIn"),
    ("meta_ads", "Meta"),
    ("organic", "Organic"),
    ("pinterest_ads", "Pinterest"),
    ("quora_ads", "Quora"),
    ("reddit_ads", "Reddit"),
    ("referral", "Referral"),
    ("snapchat_ads", "Snapchat"),
    ("taboola_ads", "Taboola"),
    ("tiktok_ads", "TikTok"),
    ("unknown", "Unknown"),
)

_SOURCE_LABEL_BY_KEY = {key: label for key, label in _SUPPORTED_SOURCES}
_ALLOWED_VALUE_KINDS = {"count", "amount"}


def _connect():
    settings = load_settings()
    if psycopg is None:
        raise RuntimeError("psycopg is required for client_data_store persistence")
    return psycopg.connect(settings.database_url)


def _normalize_source_key(source_key: str | None) -> str:
    return (source_key or "").strip().lower()


def _normalize_label(label: str) -> str:
    cleaned = " ".join((label or "").split()).strip()
    if not cleaned:
        raise ValueError("label is required")
    return cleaned


def _normalize_value_kind(value_kind: str) -> str:
    normalized = (value_kind or "").strip().lower()
    if normalized not in _ALLOWED_VALUE_KINDS:
        raise ValueError("value_kind must be one of: count, amount")
    return normalized


def _slugify_field_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return normalized


def _normalize_field_key(field_key: str | None, *, fallback: str = "custom_field") -> str:
    candidate = _slugify_field_key(field_key or "")
    if candidate:
        return candidate

    fallback_key = _slugify_field_key(fallback)
    return fallback_key or "custom_field"


def _row_to_custom_field_payload(row: tuple[object, ...] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "client_id": int(row[1]),
        "field_key": str(row[2]),
        "label": str(row[3]),
        "value_kind": str(row[4]),
        "sort_order": int(row[5]),
        "is_active": bool(row[6]),
        "archived_at": str(row[7]) if row[7] is not None else None,
    }


def _field_key_exists(*, conn, client_id: int, field_key: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM client_data_custom_fields
            WHERE client_id = %s AND field_key = %s
            LIMIT 1
            """,
            (int(client_id), str(field_key)),
        )
        return cur.fetchone() is not None


def _generate_unique_field_key(*, conn, client_id: int, base_key: str) -> str:
    if not _field_key_exists(conn=conn, client_id=client_id, field_key=base_key):
        return base_key

    suffix = 2
    while True:
        candidate = f"{base_key}_{suffix}"
        if not _field_key_exists(conn=conn, client_id=client_id, field_key=candidate):
            return candidate
        suffix += 1


def _resolve_sort_order(*, conn, client_id: int, sort_order: int | None) -> int:
    if sort_order is not None:
        return int(sort_order)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1
            FROM client_data_custom_fields
            WHERE client_id = %s
            """,
            (int(client_id),),
        )
        row = cur.fetchone() or (0,)
    return int(row[0])


def list_supported_sources() -> list[dict[str, str]]:
    return [{"key": key, "label": label} for key, label in _SUPPORTED_SOURCES]


def is_supported_source(source_key: str | None) -> bool:
    normalized = _normalize_source_key(source_key)
    return normalized in _SOURCE_LABEL_BY_KEY


def get_source_label(source_key: str | None) -> str | None:
    normalized = _normalize_source_key(source_key)
    if not normalized:
        return None
    return _SOURCE_LABEL_BY_KEY.get(normalized)


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _sum_decimal_values(sale_entries: list[Mapping[str, Any]], key: str) -> Decimal:
    total = Decimal("0")
    for entry in sale_entries:
        total += _to_decimal(entry.get(key))
    return total


def compute_sales_count(sale_entries: list[Mapping[str, Any]]) -> int:
    return len(sale_entries)


def compute_revenue(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return _sum_decimal_values(sale_entries, "sale_price_amount")


def compute_cogs(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return _sum_decimal_values(sale_entries, "actual_price_amount")


def compute_custom_value_4(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return compute_revenue(sale_entries)


def compute_gross_profit(sale_entries: list[Mapping[str, Any]]) -> Decimal:
    return compute_revenue(sale_entries) - compute_cogs(sale_entries)


def list_custom_fields(*, client_id: int, include_inactive: bool = False) -> list[dict[str, object]]:
    where_clause = "client_id = %s"
    params: list[object] = [int(client_id)]
    if not include_inactive:
        where_clause += " AND is_active = TRUE"

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    client_id,
                    field_key,
                    label,
                    value_kind,
                    sort_order,
                    is_active,
                    archived_at
                FROM client_data_custom_fields
                WHERE {where_clause}
                ORDER BY sort_order ASC, id ASC
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
    return [payload for payload in (_row_to_custom_field_payload(row) for row in rows) if payload is not None]


def validate_custom_field_belongs_to_client(*, custom_field_id: int, client_id: int) -> dict[str, object]:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    client_id,
                    field_key,
                    label,
                    value_kind,
                    sort_order,
                    is_active,
                    archived_at
                FROM client_data_custom_fields
                WHERE id = %s AND client_id = %s
                LIMIT 1
                """,
                (int(custom_field_id), int(client_id)),
            )
            row = cur.fetchone()

    payload = _row_to_custom_field_payload(row)
    if payload is None:
        raise LookupError(f"Custom field {custom_field_id} not found for client {client_id}")
    return payload


def create_custom_field(
    *,
    client_id: int,
    label: str,
    value_kind: str,
    field_key: str | None = None,
    sort_order: int | None = None,
) -> dict[str, object]:
    normalized_label = _normalize_label(label)
    normalized_value_kind = _normalize_value_kind(value_kind)
    normalized_field_key = _normalize_field_key(field_key or normalized_label, fallback="custom_field")

    with _connect() as conn:
        unique_field_key = _generate_unique_field_key(conn=conn, client_id=int(client_id), base_key=normalized_field_key)
        resolved_sort_order = _resolve_sort_order(conn=conn, client_id=int(client_id), sort_order=sort_order)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_data_custom_fields (
                    client_id,
                    field_key,
                    label,
                    value_kind,
                    sort_order,
                    is_active,
                    archived_at
                ) VALUES (%s, %s, %s, %s, %s, TRUE, NULL)
                RETURNING
                    id,
                    client_id,
                    field_key,
                    label,
                    value_kind,
                    sort_order,
                    is_active,
                    archived_at
                """,
                (
                    int(client_id),
                    unique_field_key,
                    normalized_label,
                    normalized_value_kind,
                    resolved_sort_order,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_custom_field_payload(row)
    if payload is None:
        raise RuntimeError("Failed to create custom field")
    return payload
