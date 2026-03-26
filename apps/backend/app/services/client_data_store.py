from __future__ import annotations

from datetime import date
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


def _validate_sort_order(sort_order: int) -> int:
    try:
        normalized = int(sort_order)
    except (TypeError, ValueError):
        raise ValueError("sort_order must be an integer >= 0") from None
    if normalized < 0:
        raise ValueError("sort_order must be an integer >= 0")
    return normalized


def _get_custom_field_by_id(*, conn, custom_field_id: int) -> dict[str, object] | None:
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
            WHERE id = %s
            LIMIT 1
            """,
            (int(custom_field_id),),
        )
        row = cur.fetchone()
    return _row_to_custom_field_payload(row)


def update_custom_field(
    *,
    custom_field_id: int,
    label: str | None = None,
    value_kind: str | None = None,
    sort_order: int | None = None,
) -> dict[str, object]:
    updates: dict[str, object] = {}
    if label is not None:
        updates["label"] = _normalize_label(label)
    if value_kind is not None:
        updates["value_kind"] = _normalize_value_kind(value_kind)
    if sort_order is not None:
        updates["sort_order"] = _validate_sort_order(sort_order)

    if len(updates) <= 0:
        raise ValueError("At least one update field is required")

    with _connect() as conn:
        existing = _get_custom_field_by_id(conn=conn, custom_field_id=int(custom_field_id))
        if existing is None:
            raise LookupError(f"Custom field {custom_field_id} not found")

        set_clauses: list[str] = []
        params: list[object] = []
        for column in ("label", "value_kind", "sort_order"):
            if column in updates:
                set_clauses.append(f"{column} = %s")
                params.append(updates[column])

        set_clauses.append("updated_at = NOW()")
        params.append(int(custom_field_id))

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE client_data_custom_fields
                SET {', '.join(set_clauses)}
                WHERE id = %s
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
                tuple(params),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_custom_field_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to update custom field {custom_field_id}")
    return payload


def archive_custom_field(*, custom_field_id: int) -> dict[str, object]:
    with _connect() as conn:
        existing = _get_custom_field_by_id(conn=conn, custom_field_id=int(custom_field_id))
        if existing is None:
            raise LookupError(f"Custom field {custom_field_id} not found")

        if not bool(existing.get("is_active", True)):
            return existing

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_data_custom_fields
                SET
                    is_active = FALSE,
                    archived_at = COALESCE(archived_at, NOW()),
                    updated_at = NOW()
                WHERE id = %s
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
                (int(custom_field_id),),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_custom_field_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to archive custom field {custom_field_id}")
    return payload


def _normalize_client_id(client_id: int) -> int:
    try:
        normalized = int(client_id)
    except (TypeError, ValueError):
        raise ValueError("client_id must be a positive integer") from None
    if normalized <= 0:
        raise ValueError("client_id must be a positive integer")
    return normalized


def _normalize_metric_date(metric_date: date | str) -> date:
    if isinstance(metric_date, date):
        return metric_date

    if isinstance(metric_date, str):
        value = metric_date.strip()
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise ValueError("metric_date must be a valid ISO date (YYYY-MM-DD)") from None

    raise ValueError("metric_date must be a date or ISO string")


def _normalize_supported_source(source: str) -> str:
    normalized = _normalize_source_key(source)
    if not is_supported_source(normalized):
        raise ValueError(f"Unsupported source: {source}")
    return normalized


def _row_to_daily_input_payload(row: tuple[object, ...] | None) -> dict[str, object] | None:
    if row is None:
        return None
    has_extended_daily_columns = len(row) >= 13
    return {
        "id": int(row[0]),
        "client_id": int(row[1]),
        "metric_date": str(row[2]),
        "source": str(row[3]),
        "leads": int(row[4]),
        "phones": int(row[5]),
        "custom_value_1_count": int(row[6]),
        "custom_value_2_count": int(row[7]),
        "custom_value_3_amount": _to_decimal(row[8]),
        "custom_value_4_amount": _to_decimal(row[9] if has_extended_daily_columns else 0),
        "custom_value_5_amount": _to_decimal(row[10] if has_extended_daily_columns else row[9]),
        "sales_count": int(row[11] if has_extended_daily_columns else 0),
        "notes": str(row[12] if has_extended_daily_columns else row[10]) if (row[12] if has_extended_daily_columns else row[10]) is not None else None,
    }


def get_or_create_daily_input(*, client_id: int, metric_date: date | str, source: str) -> dict[str, object]:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_metric_date = _normalize_metric_date(metric_date)
    normalized_source = _normalize_supported_source(source)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                FROM client_data_daily_inputs
                WHERE client_id = %s AND metric_date = %s AND source = %s
                LIMIT 1
                """,
                (normalized_client_id, normalized_metric_date, normalized_source),
            )
            existing_row = cur.fetchone()
            if existing_row is not None:
                payload = _row_to_daily_input_payload(existing_row)
                if payload is None:
                    raise RuntimeError("Failed to load existing daily input")
                return payload

            cur.execute(
                """
                INSERT INTO client_data_daily_inputs (
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                ) VALUES (%s, %s, %s, 0, 0, 0, 0, 0, 0, 0, 0, NULL)
                RETURNING
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                """,
                (normalized_client_id, normalized_metric_date, normalized_source),
            )
            created_row = cur.fetchone()
        conn.commit()

    payload = _row_to_daily_input_payload(created_row)
    if payload is None:
        raise RuntimeError("Failed to create daily input")
    return payload


def _parse_decimal_strict(value: object, *, field_name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{field_name} must be numeric") from None


def _validate_non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer >= 0")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer >= 0") from None
    if normalized < 0:
        raise ValueError(f"{field_name} must be an integer >= 0")
    return normalized


def _validate_decimal_amount(value: object, *, field_name: str, allow_negative: bool) -> Decimal:
    amount = _parse_decimal_strict(value, field_name=field_name)
    if not allow_negative and amount < Decimal("0"):
        raise ValueError(f"{field_name} must be >= 0")
    return amount


def upsert_daily_input(
    *,
    client_id: int,
    metric_date: date | str,
    source: str,
    leads: int | None = None,
    phones: int | None = None,
    custom_value_1_count: int | None = None,
    custom_value_2_count: int | None = None,
    custom_value_3_amount: object | None = None,
    custom_value_4_amount: object | None = None,
    custom_value_5_amount: object | None = None,
    sales_count: int | None = None,
    recompute_custom_value_5: bool = True,
) -> dict[str, object]:
    updates: dict[str, object] = {}
    if leads is not None:
        updates["leads"] = _validate_non_negative_int(leads, field_name="leads")
    if phones is not None:
        updates["phones"] = _validate_non_negative_int(phones, field_name="phones")
    if custom_value_1_count is not None:
        updates["custom_value_1_count"] = _validate_non_negative_int(custom_value_1_count, field_name="custom_value_1_count")
    if custom_value_2_count is not None:
        updates["custom_value_2_count"] = _validate_non_negative_int(custom_value_2_count, field_name="custom_value_2_count")
    if custom_value_3_amount is not None:
        updates["custom_value_3_amount"] = _validate_decimal_amount(
            custom_value_3_amount,
            field_name="custom_value_3_amount",
            allow_negative=False,
        )
    if custom_value_4_amount is not None:
        updates["custom_value_4_amount"] = _validate_decimal_amount(
            custom_value_4_amount,
            field_name="custom_value_4_amount",
            allow_negative=False,
        )
    if sales_count is not None:
        updates["sales_count"] = _validate_non_negative_int(sales_count, field_name="sales_count")
    if custom_value_5_amount is not None:  # accepted for backward compatibility, then overwritten by formula
        updates["custom_value_5_amount"] = _validate_decimal_amount(
            custom_value_5_amount,
            field_name="custom_value_5_amount",
            allow_negative=True,
        )

    if len(updates) <= 0:
        raise ValueError("At least one daily input field must be provided")

    base_row = get_or_create_daily_input(client_id=client_id, metric_date=metric_date, source=source)
    if recompute_custom_value_5:
        effective_custom_value_3 = _to_decimal(updates.get("custom_value_3_amount", base_row.get("custom_value_3_amount")))
        effective_custom_value_4 = _to_decimal(updates.get("custom_value_4_amount", base_row.get("custom_value_4_amount")))
        updates["custom_value_5_amount"] = effective_custom_value_4 - effective_custom_value_3

    set_clauses: list[str] = []
    params: list[object] = []
    for column in (
        "leads",
        "phones",
        "custom_value_1_count",
        "custom_value_2_count",
        "custom_value_3_amount",
        "custom_value_4_amount",
        "custom_value_5_amount",
        "sales_count",
    ):
        if column in updates:
            set_clauses.append(f"{column} = %s")
            params.append(updates[column])

    set_clauses.append("updated_at = NOW()")
    params.append(int(base_row["id"]))

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE client_data_daily_inputs
                SET {', '.join(set_clauses)}
                WHERE id = %s
                RETURNING
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                """,
                tuple(params),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_daily_input_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to upsert daily input {base_row['id']}")
    return payload


def create_daily_input(
    *,
    client_id: int,
    metric_date: date | str,
    source: str,
    leads: int = 0,
    phones: int = 0,
    custom_value_1_count: int = 0,
    custom_value_2_count: int = 0,
    custom_value_3_amount: object = 0,
    custom_value_4_amount: object = 0,
    sales_count: int = 0,
) -> dict[str, object]:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_metric_date = _normalize_metric_date(metric_date)
    normalized_source = _normalize_supported_source(source)

    parsed_leads = _validate_non_negative_int(leads, field_name="leads")
    parsed_phones = _validate_non_negative_int(phones, field_name="phones")
    parsed_cv1 = _validate_non_negative_int(custom_value_1_count, field_name="custom_value_1_count")
    parsed_cv2 = _validate_non_negative_int(custom_value_2_count, field_name="custom_value_2_count")
    parsed_cv3 = _validate_decimal_amount(custom_value_3_amount, field_name="custom_value_3_amount", allow_negative=False)
    parsed_cv4 = _validate_decimal_amount(custom_value_4_amount, field_name="custom_value_4_amount", allow_negative=False)
    parsed_sales = _validate_non_negative_int(sales_count, field_name="sales_count")
    parsed_cv5 = parsed_cv4 - parsed_cv3

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_data_daily_inputs (
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                RETURNING
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                """,
                (
                    normalized_client_id,
                    normalized_metric_date,
                    normalized_source,
                    parsed_leads,
                    parsed_phones,
                    parsed_cv1,
                    parsed_cv2,
                    parsed_cv3,
                    parsed_cv4,
                    parsed_cv5,
                    parsed_sales,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    payload = _row_to_daily_input_payload(row)
    if payload is None:
        raise RuntimeError("Failed to create daily input row")
    return payload


def update_daily_input_by_id(
    *,
    daily_input_id: int,
    leads: int | None = None,
    phones: int | None = None,
    custom_value_1_count: int | None = None,
    custom_value_2_count: int | None = None,
    custom_value_3_amount: object | None = None,
    custom_value_4_amount: object | None = None,
    sales_count: int | None = None,
) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    with _connect() as conn:
        base_row = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if base_row is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        updates: dict[str, object] = {}
        if leads is not None:
            updates["leads"] = _validate_non_negative_int(leads, field_name="leads")
        if phones is not None:
            updates["phones"] = _validate_non_negative_int(phones, field_name="phones")
        if custom_value_1_count is not None:
            updates["custom_value_1_count"] = _validate_non_negative_int(custom_value_1_count, field_name="custom_value_1_count")
        if custom_value_2_count is not None:
            updates["custom_value_2_count"] = _validate_non_negative_int(custom_value_2_count, field_name="custom_value_2_count")
        if custom_value_3_amount is not None:
            updates["custom_value_3_amount"] = _validate_decimal_amount(custom_value_3_amount, field_name="custom_value_3_amount", allow_negative=False)
        if custom_value_4_amount is not None:
            updates["custom_value_4_amount"] = _validate_decimal_amount(custom_value_4_amount, field_name="custom_value_4_amount", allow_negative=False)
        if sales_count is not None:
            updates["sales_count"] = _validate_non_negative_int(sales_count, field_name="sales_count")
        if not updates:
            raise ValueError("At least one daily input field must be provided")

        effective_custom_value_3 = _to_decimal(updates.get("custom_value_3_amount", base_row.get("custom_value_3_amount")))
        effective_custom_value_4 = _to_decimal(updates.get("custom_value_4_amount", base_row.get("custom_value_4_amount")))
        updates["custom_value_5_amount"] = effective_custom_value_4 - effective_custom_value_3

        set_clauses: list[str] = []
        params: list[object] = []
        for column in (
            "leads",
            "phones",
            "custom_value_1_count",
            "custom_value_2_count",
            "custom_value_3_amount",
            "custom_value_4_amount",
            "custom_value_5_amount",
            "sales_count",
        ):
            if column in updates:
                set_clauses.append(f"{column} = %s")
                params.append(updates[column])
        set_clauses.append("updated_at = NOW()")
        params.append(normalized_daily_input_id)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE client_data_daily_inputs
                SET {', '.join(set_clauses)}
                WHERE id = %s
                RETURNING
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                """,
                tuple(params),
            )
            row = cur.fetchone()
        conn.commit()
    payload = _row_to_daily_input_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to update daily input {daily_input_id}")
    return payload


def _normalize_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    if not isinstance(notes, str):
        raise ValueError("notes must be a string or None")
    cleaned = notes.strip()
    return cleaned if cleaned else None


def set_daily_input_notes(
    *,
    client_id: int,
    metric_date: date | str,
    source: str,
    notes: str | None,
) -> dict[str, object]:
    normalized_notes = _normalize_notes(notes)
    base_row = get_or_create_daily_input(client_id=client_id, metric_date=metric_date, source=source)

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE client_data_daily_inputs
                SET
                    notes = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                """,
                (normalized_notes, int(base_row["id"])),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_daily_input_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to set notes for daily input {base_row['id']}")
    return payload


def list_daily_inputs(
    *,
    client_id: int,
    date_from: date | str,
    date_to: date | str,
) -> list[dict[str, object]]:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_date_from = _normalize_metric_date(date_from)
    normalized_date_to = _normalize_metric_date(date_to)
    if normalized_date_from > normalized_date_to:
        raise ValueError("date_from must be <= date_to")

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    client_id,
                    metric_date,
                    source,
                    leads,
                    phones,
                    custom_value_1_count,
                    custom_value_2_count,
                    custom_value_3_amount,
                    custom_value_4_amount,
                    custom_value_5_amount,
                    sales_count,
                    notes
                FROM client_data_daily_inputs
                WHERE client_id = %s
                  AND metric_date >= %s
                  AND metric_date <= %s
                ORDER BY metric_date DESC, id DESC
                """,
                (normalized_client_id, normalized_date_from, normalized_date_to),
            )
            rows = cur.fetchall() or []

    return [payload for payload in (_row_to_daily_input_payload(row) for row in rows) if payload is not None]


def get_daily_input_map(
    *,
    client_id: int,
    date_from: date | str,
    date_to: date | str,
) -> dict[tuple[str, str], dict[str, object]]:
    rows = list_daily_inputs(client_id=client_id, date_from=date_from, date_to=date_to)
    mapped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["metric_date"]), str(row["source"]))
        mapped[key] = row
    return mapped


def _normalize_positive_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer") from None
    if normalized <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return normalized


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")
    cleaned = value.strip()
    return cleaned if cleaned else None


def _get_daily_input_row_by_id(*, conn, daily_input_id: int) -> dict[str, object] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                client_id,
                metric_date,
                source,
                leads,
                phones,
                custom_value_1_count,
                custom_value_2_count,
                custom_value_3_amount,
                custom_value_4_amount,
                custom_value_5_amount,
                sales_count,
                notes
            FROM client_data_daily_inputs
            WHERE id = %s
            LIMIT 1
            """,
            (int(daily_input_id),),
        )
        row = cur.fetchone()
    return _row_to_daily_input_payload(row)


def validate_daily_input_belongs_to_client(*, daily_input_id: int, client_id: int) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    normalized_client_id = _normalize_client_id(client_id)

    with _connect() as conn:
        payload = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)

    if payload is None or int(payload["client_id"]) != normalized_client_id:
        raise LookupError(f"Daily input {daily_input_id} not found for client {client_id}")
    return payload


def delete_daily_input_with_dependencies(*, daily_input_id: int) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM client_data_daily_custom_values
                WHERE daily_input_id = %s
                """,
                (normalized_daily_input_id,),
            )
            cur.execute(
                """
                DELETE FROM client_data_sale_entries
                WHERE daily_input_id = %s
                """,
                (normalized_daily_input_id,),
            )
            cur.execute(
                """
                DELETE FROM client_data_daily_inputs
                WHERE id = %s
                """,
                (normalized_daily_input_id,),
            )
        conn.commit()

    return daily_input


def _resolve_sale_entry_sort_order(*, conn, daily_input_id: int, sort_order: int | None) -> int:
    if sort_order is not None:
        return _validate_non_negative_int(sort_order, field_name="sort_order")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1
            FROM client_data_sale_entries
            WHERE daily_input_id = %s
            """,
            (int(daily_input_id),),
        )
        row = cur.fetchone() or (0,)
    return int(row[0])


def _row_to_sale_entry_payload(row: tuple[object, ...] | None) -> dict[str, object] | None:
    if row is None:
        return None

    sale_price = _to_decimal(row[4])
    actual_price = _to_decimal(row[5])
    return {
        "id": int(row[0]),
        "daily_input_id": int(row[1]),
        "brand": str(row[2]) if row[2] is not None else None,
        "model": str(row[3]) if row[3] is not None else None,
        "sale_price_amount": sale_price,
        "actual_price_amount": actual_price,
        "notes": str(row[6]) if row[6] is not None else None,
        "sort_order": int(row[7]),
        "gross_profit_amount": sale_price - actual_price,
    }


def list_sale_entries_for_daily_input(*, daily_input_id: int) -> list[dict[str, object]]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    daily_input_id,
                    brand,
                    model,
                    sale_price_amount,
                    actual_price_amount,
                    notes,
                    sort_order
                FROM client_data_sale_entries
                WHERE daily_input_id = %s
                ORDER BY sort_order ASC, id ASC
                """,
                (normalized_daily_input_id,),
            )
            rows = cur.fetchall() or []

    return [payload for payload in (_row_to_sale_entry_payload(row) for row in rows) if payload is not None]


def replace_sale_entries_for_daily_input(
    *,
    daily_input_id: int,
    sale_entries: list[Mapping[str, Any]],
) -> list[dict[str, object]]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    if not isinstance(sale_entries, list):
        raise ValueError("sale_entries must be a list")

    normalized_entries: list[dict[str, object]] = []
    for idx, raw_entry in enumerate(sale_entries):
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f"sale_entries[{idx}] must be an object")

        sale_price_amount = _validate_decimal_amount(
            raw_entry.get("sale_price_amount"),
            field_name=f"sale_entries[{idx}].sale_price_amount",
            allow_negative=False,
        )
        actual_price_amount = _validate_decimal_amount(
            raw_entry.get("actual_price_amount"),
            field_name=f"sale_entries[{idx}].actual_price_amount",
            allow_negative=False,
        )
        normalized_entries.append(
            {
                "brand": _normalize_optional_text(raw_entry.get("brand"), field_name=f"sale_entries[{idx}].brand"),
                "model": _normalize_optional_text(raw_entry.get("model"), field_name=f"sale_entries[{idx}].model"),
                "sale_price_amount": sale_price_amount,
                "actual_price_amount": actual_price_amount,
                "notes": _normalize_optional_text(raw_entry.get("notes"), field_name=f"sale_entries[{idx}].notes"),
                "sort_order": _validate_non_negative_int(
                    raw_entry.get("sort_order", idx),
                    field_name=f"sale_entries[{idx}].sort_order",
                ),
            }
        )

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM client_data_sale_entries
                WHERE daily_input_id = %s
                """,
                (normalized_daily_input_id,),
            )

            for entry in normalized_entries:
                cur.execute(
                    """
                    INSERT INTO client_data_sale_entries (
                        daily_input_id,
                        brand,
                        model,
                        sale_price_amount,
                        actual_price_amount,
                        notes,
                        sort_order
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        normalized_daily_input_id,
                        entry["brand"],
                        entry["model"],
                        entry["sale_price_amount"],
                        entry["actual_price_amount"],
                        entry["notes"],
                        entry["sort_order"],
                    ),
                )
        conn.commit()

    return list_sale_entries_for_daily_input(daily_input_id=normalized_daily_input_id)


def create_sale_entry(
    *,
    daily_input_id: int,
    sale_price_amount: object,
    actual_price_amount: object,
    brand: str | None = None,
    model: str | None = None,
    notes: str | None = None,
    sort_order: int | None = None,
) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    normalized_sale_price = _validate_decimal_amount(sale_price_amount, field_name="sale_price_amount", allow_negative=False)
    normalized_actual_price = _validate_decimal_amount(actual_price_amount, field_name="actual_price_amount", allow_negative=False)
    normalized_brand = _normalize_optional_text(brand, field_name="brand")
    normalized_model = _normalize_optional_text(model, field_name="model")
    normalized_notes = _normalize_optional_text(notes, field_name="notes")

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        resolved_sort_order = _resolve_sale_entry_sort_order(
            conn=conn,
            daily_input_id=normalized_daily_input_id,
            sort_order=sort_order,
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_data_sale_entries (
                    daily_input_id,
                    brand,
                    model,
                    sale_price_amount,
                    actual_price_amount,
                    notes,
                    sort_order
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING
                    id,
                    daily_input_id,
                    brand,
                    model,
                    sale_price_amount,
                    actual_price_amount,
                    notes,
                    sort_order
                """,
                (
                    normalized_daily_input_id,
                    normalized_brand,
                    normalized_model,
                    normalized_sale_price,
                    normalized_actual_price,
                    normalized_notes,
                    resolved_sort_order,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_sale_entry_payload(row)
    if payload is None:
        raise RuntimeError("Failed to create sale entry")
    return payload


def _get_sale_entry_row_by_id(*, conn, sale_entry_id: int) -> dict[str, object] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                daily_input_id,
                brand,
                model,
                sale_price_amount,
                actual_price_amount,
                notes,
                sort_order
            FROM client_data_sale_entries
            WHERE id = %s
            LIMIT 1
            """,
            (int(sale_entry_id),),
        )
        row = cur.fetchone()
    return _row_to_sale_entry_payload(row)


def validate_sale_entry_belongs_to_client(*, sale_entry_id: int, client_id: int) -> dict[str, object]:
    normalized_sale_entry_id = _normalize_positive_int(sale_entry_id, field_name="sale_entry_id")
    normalized_client_id = _normalize_client_id(client_id)

    with _connect() as conn:
        sale_entry_payload = _get_sale_entry_row_by_id(conn=conn, sale_entry_id=normalized_sale_entry_id)
        if sale_entry_payload is None:
            raise LookupError(f"Sale entry {sale_entry_id} not found for client {client_id}")

        daily_input_payload = _get_daily_input_row_by_id(conn=conn, daily_input_id=int(sale_entry_payload["daily_input_id"]))
        if daily_input_payload is None or int(daily_input_payload["client_id"]) != normalized_client_id:
            raise LookupError(f"Sale entry {sale_entry_id} not found for client {client_id}")

    return sale_entry_payload


def update_sale_entry(
    *,
    sale_entry_id: int,
    sale_price_amount: object | None = None,
    actual_price_amount: object | None = None,
    brand: str | None = None,
    model: str | None = None,
    notes: str | None = None,
    sort_order: int | None = None,
) -> dict[str, object]:
    normalized_sale_entry_id = _normalize_positive_int(sale_entry_id, field_name="sale_entry_id")

    updates: dict[str, object] = {}
    if sale_price_amount is not None:
        updates["sale_price_amount"] = _validate_decimal_amount(
            sale_price_amount,
            field_name="sale_price_amount",
            allow_negative=False,
        )
    if actual_price_amount is not None:
        updates["actual_price_amount"] = _validate_decimal_amount(
            actual_price_amount,
            field_name="actual_price_amount",
            allow_negative=False,
        )
    if brand is not None:
        updates["brand"] = _normalize_optional_text(brand, field_name="brand")
    if model is not None:
        updates["model"] = _normalize_optional_text(model, field_name="model")
    if notes is not None:
        updates["notes"] = _normalize_optional_text(notes, field_name="notes")
    if sort_order is not None:
        updates["sort_order"] = _validate_non_negative_int(sort_order, field_name="sort_order")

    if len(updates) <= 0:
        raise ValueError("At least one sale entry update field must be provided")

    with _connect() as conn:
        existing = _get_sale_entry_row_by_id(conn=conn, sale_entry_id=normalized_sale_entry_id)
        if existing is None:
            raise LookupError(f"Sale entry {sale_entry_id} not found")

        set_clauses: list[str] = []
        params: list[object] = []
        for column in ("sale_price_amount", "actual_price_amount", "brand", "model", "notes", "sort_order"):
            if column in updates:
                set_clauses.append(f"{column} = %s")
                params.append(updates[column])
        set_clauses.append("updated_at = NOW()")
        params.append(normalized_sale_entry_id)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE client_data_sale_entries
                SET {', '.join(set_clauses)}
                WHERE id = %s
                RETURNING
                    id,
                    daily_input_id,
                    brand,
                    model,
                    sale_price_amount,
                    actual_price_amount,
                    notes,
                    sort_order
                """,
                tuple(params),
            )
            row = cur.fetchone()
        conn.commit()

    payload = _row_to_sale_entry_payload(row)
    if payload is None:
        raise RuntimeError(f"Failed to update sale entry {sale_entry_id}")
    return payload


def delete_sale_entry(*, sale_entry_id: int) -> dict[str, object]:
    normalized_sale_entry_id = _normalize_positive_int(sale_entry_id, field_name="sale_entry_id")

    with _connect() as conn:
        existing = _get_sale_entry_row_by_id(conn=conn, sale_entry_id=normalized_sale_entry_id)
        if existing is None:
            raise LookupError(f"Sale entry {sale_entry_id} not found")

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM client_data_sale_entries
                WHERE id = %s
                """,
                (normalized_sale_entry_id,),
            )
        conn.commit()

    return existing


def _row_to_daily_custom_value_payload(row: tuple[object, ...] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "id": int(row[0]),
        "daily_input_id": int(row[1]),
        "metric_date": str(row[2]),
        "source": str(row[3]),
        "custom_field_id": int(row[4]),
        "field_key": str(row[5]),
        "label": str(row[6]),
        "value_kind": str(row[7]),
        "sort_order": int(row[8]),
        "is_active": bool(row[9]),
        "numeric_value": _to_decimal(row[10]),
    }


def _normalize_custom_value_by_kind(numeric_value: object, *, value_kind: str) -> Decimal:
    if value_kind == "count":
        if isinstance(numeric_value, bool):
            raise ValueError("numeric_value must be an integer >= 0 for count fields")
        try:
            parsed = Decimal(str(numeric_value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError("numeric_value must be an integer >= 0 for count fields") from None
        if parsed < 0 or parsed != parsed.to_integral_value():
            raise ValueError("numeric_value must be an integer >= 0 for count fields")
        return parsed

    if value_kind == "amount":
        return _parse_decimal_strict(numeric_value, field_name="numeric_value")

    raise ValueError(f"Unsupported custom field value_kind: {value_kind}")


def list_daily_custom_values(
    *,
    client_id: int,
    date_from: date | str,
    date_to: date | str,
) -> list[dict[str, object]]:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_date_from = _normalize_metric_date(date_from)
    normalized_date_to = _normalize_metric_date(date_to)
    if normalized_date_from > normalized_date_to:
        raise ValueError("date_from must be <= date_to")

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    dcv.id,
                    dcv.daily_input_id,
                    di.metric_date,
                    di.source,
                    dcv.custom_field_id,
                    cf.field_key,
                    cf.label,
                    cf.value_kind,
                    cf.sort_order,
                    cf.is_active,
                    dcv.numeric_value
                FROM client_data_daily_custom_values dcv
                JOIN client_data_daily_inputs di ON di.id = dcv.daily_input_id
                JOIN client_data_custom_fields cf ON cf.id = dcv.custom_field_id
                WHERE di.client_id = %s
                  AND di.metric_date >= %s
                  AND di.metric_date <= %s
                ORDER BY di.metric_date DESC, di.source ASC, cf.sort_order ASC, dcv.custom_field_id ASC, dcv.id ASC
                """,
                (normalized_client_id, normalized_date_from, normalized_date_to),
            )
            rows = cur.fetchall() or []

    return [payload for payload in (_row_to_daily_custom_value_payload(row) for row in rows) if payload is not None]


def list_daily_custom_values_for_daily_input(*, daily_input_id: int) -> list[dict[str, object]]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    dcv.id,
                    dcv.daily_input_id,
                    di.metric_date,
                    di.source,
                    dcv.custom_field_id,
                    cf.field_key,
                    cf.label,
                    cf.value_kind,
                    cf.sort_order,
                    cf.is_active,
                    dcv.numeric_value
                FROM client_data_daily_custom_values dcv
                JOIN client_data_daily_inputs di ON di.id = dcv.daily_input_id
                JOIN client_data_custom_fields cf ON cf.id = dcv.custom_field_id
                WHERE dcv.daily_input_id = %s
                ORDER BY cf.sort_order ASC, cf.id ASC
                """,
                (normalized_daily_input_id,),
            )
            rows = cur.fetchall() or []

    return [payload for payload in (_row_to_daily_custom_value_payload(row) for row in rows) if payload is not None]


def replace_daily_custom_values_for_daily_input(
    *,
    client_id: int,
    daily_input_id: int,
    dynamic_custom_values: list[Mapping[str, Any]],
) -> list[dict[str, object]]:
    normalized_client_id = _normalize_client_id(client_id)
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    if not isinstance(dynamic_custom_values, list):
        raise ValueError("dynamic_custom_values must be a list")

    seen_field_ids: set[int] = set()
    normalized_items: list[dict[str, object]] = []
    for idx, item in enumerate(dynamic_custom_values):
        if not isinstance(item, Mapping):
            raise ValueError(f"dynamic_custom_values[{idx}] must be an object")
        if "custom_field_id" not in item:
            raise ValueError(f"dynamic_custom_values[{idx}].custom_field_id is required")
        if "numeric_value" not in item:
            raise ValueError(f"dynamic_custom_values[{idx}].numeric_value is required")

        custom_field_id = _normalize_positive_int(item.get("custom_field_id"), field_name=f"dynamic_custom_values[{idx}].custom_field_id")
        if custom_field_id in seen_field_ids:
            raise ValueError(f"Duplicate custom_field_id in dynamic_custom_values: {custom_field_id}")
        seen_field_ids.add(custom_field_id)

        custom_field = validate_custom_field_belongs_to_client(custom_field_id=custom_field_id, client_id=normalized_client_id)
        if not bool(custom_field.get("is_active")):
            raise ValueError(f"Custom field {custom_field_id} is archived and cannot be written")

        numeric_value = _normalize_custom_value_by_kind(item.get("numeric_value"), value_kind=str(custom_field["value_kind"]))
        normalized_items.append(
            {
                "custom_field_id": custom_field_id,
                "numeric_value": numeric_value,
            }
        )

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")
        if int(daily_input["client_id"]) != normalized_client_id:
            raise LookupError(f"Daily input {daily_input_id} not found for client {client_id}")

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM client_data_daily_custom_values
                WHERE daily_input_id = %s
                """,
                (normalized_daily_input_id,),
            )

            for item in normalized_items:
                cur.execute(
                    """
                    INSERT INTO client_data_daily_custom_values (
                        daily_input_id,
                        custom_field_id,
                        numeric_value
                    ) VALUES (%s, %s, %s)
                    """,
                    (normalized_daily_input_id, item["custom_field_id"], item["numeric_value"]),
                )
        conn.commit()

    return list_daily_custom_values_for_daily_input(daily_input_id=normalized_daily_input_id)


def upsert_daily_custom_value(
    *,
    daily_input_id: int,
    custom_field_id: int,
    numeric_value: object,
) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    normalized_custom_field_id = _normalize_positive_int(custom_field_id, field_name="custom_field_id")

    with _connect() as conn:
        daily_input = _get_daily_input_row_by_id(conn=conn, daily_input_id=normalized_daily_input_id)
        if daily_input is None:
            raise LookupError(f"Daily input {daily_input_id} not found")

        custom_field = _get_custom_field_by_id(conn=conn, custom_field_id=normalized_custom_field_id)
        if custom_field is None:
            raise LookupError(f"Custom field {custom_field_id} not found")

        if int(daily_input["client_id"]) != int(custom_field["client_id"]):
            raise LookupError(
                f"Custom field {custom_field_id} does not belong to client {daily_input['client_id']}"
            )

        normalized_numeric_value = _normalize_custom_value_by_kind(
            numeric_value,
            value_kind=str(custom_field["value_kind"]),
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO client_data_daily_custom_values (
                    daily_input_id,
                    custom_field_id,
                    numeric_value
                ) VALUES (%s, %s, %s)
                ON CONFLICT (daily_input_id, custom_field_id)
                DO UPDATE SET
                    numeric_value = EXCLUDED.numeric_value,
                    updated_at = NOW()
                RETURNING id
                """,
                (normalized_daily_input_id, normalized_custom_field_id, normalized_numeric_value),
            )
            row = cur.fetchone() or (None,)
            custom_value_id = row[0]

            cur.execute(
                """
                SELECT
                    dcv.id,
                    dcv.daily_input_id,
                    di.metric_date,
                    di.source,
                    dcv.custom_field_id,
                    cf.field_key,
                    cf.label,
                    cf.value_kind,
                    cf.sort_order,
                    cf.is_active,
                    dcv.numeric_value
                FROM client_data_daily_custom_values dcv
                JOIN client_data_daily_inputs di ON di.id = dcv.daily_input_id
                JOIN client_data_custom_fields cf ON cf.id = dcv.custom_field_id
                WHERE dcv.id = %s
                LIMIT 1
                """,
                (custom_value_id,),
            )
            full_row = cur.fetchone()
        conn.commit()

    payload = _row_to_daily_custom_value_payload(full_row)
    if payload is None:
        raise RuntimeError("Failed to upsert daily custom value")
    return payload


def _fetch_daily_custom_value_join_by_pair(*, conn, daily_input_id: int, custom_field_id: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                dcv.id,
                dcv.daily_input_id,
                di.metric_date,
                di.source,
                dcv.custom_field_id,
                cf.field_key,
                cf.label,
                cf.value_kind,
                cf.sort_order,
                cf.is_active,
                dcv.numeric_value
            FROM client_data_daily_custom_values dcv
            JOIN client_data_daily_inputs di ON di.id = dcv.daily_input_id
            JOIN client_data_custom_fields cf ON cf.id = dcv.custom_field_id
            WHERE dcv.daily_input_id = %s AND dcv.custom_field_id = %s
            LIMIT 1
            """,
            (int(daily_input_id), int(custom_field_id)),
        )
        return cur.fetchone()


def delete_daily_custom_value(*, daily_input_id: int, custom_field_id: int) -> dict[str, object]:
    normalized_daily_input_id = _normalize_positive_int(daily_input_id, field_name="daily_input_id")
    normalized_custom_field_id = _normalize_positive_int(custom_field_id, field_name="custom_field_id")

    with _connect() as conn:
        row = _fetch_daily_custom_value_join_by_pair(
            conn=conn,
            daily_input_id=normalized_daily_input_id,
            custom_field_id=normalized_custom_field_id,
        )
        payload = _row_to_daily_custom_value_payload(row)
        if payload is None:
            raise LookupError(
                f"Daily custom value not found for daily_input_id={daily_input_id}, custom_field_id={custom_field_id}"
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM client_data_daily_custom_values
                WHERE daily_input_id = %s AND custom_field_id = %s
                """,
                (normalized_daily_input_id, normalized_custom_field_id),
            )
        conn.commit()

    return payload
