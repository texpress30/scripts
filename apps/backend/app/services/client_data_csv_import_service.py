"""CSV import service for client data daily inputs.

Parses and validates a CSV file, maps columns to DB fields,
returns a preview, and imports confirmed rows via transactional upsert.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROWS = 500

# CSV header → DB column mapping (case-insensitive, stripped).
# Multiple header variants map to the same DB column.
_HEADER_MAP: dict[str, str] = {
    "saptamana": "week",
    "săptămâna": "week",
    "saptamina": "week",
    "week": "week",
    "data vanzare": "metric_date",
    "data vânzare": "metric_date",
    "sale_date": "metric_date",
    "metric_date": "metric_date",
    "lead-uri": "leads",
    "leaduri": "leads",
    "leads": "leads",
    "telefoane": "phones",
    "phones": "phones",
    "custom value 1": "custom_value_1_count",
    "custom_value_1": "custom_value_1_count",
    "custom_value_1_count": "custom_value_1_count",
    "custom value 2": "custom_value_2_count",
    "custom_value_2": "custom_value_2_count",
    "custom_value_2_count": "custom_value_2_count",
    "custom value 3": "custom_value_3_amount",
    "custom_value_3": "custom_value_3_amount",
    "custom_value_3_amount": "custom_value_3_amount",
    "custom value 4": "custom_value_4_amount",
    "custom_value_4": "custom_value_4_amount",
    "custom_value_4_amount": "custom_value_4_amount",
    "custom value 5": "custom_value_5_amount",
    "custom_value_5": "custom_value_5_amount",
    "custom_value_5_amount": "custom_value_5_amount",
    "vanzari": "sales_count",
    "vânzări": "sales_count",
    "sales": "sales_count",
    "sales_count": "sales_count",
    "pret vanzare": "sale_price_amount",
    "preț vânzare": "sale_price_amount",
    "pret vanzare": "sale_price_amount",
    "sale_price": "sale_price_amount",
    "sale_price_amount": "sale_price_amount",
    "pret actual": "actual_price_amount",
    "preț actual": "actual_price_amount",
    "current_price": "actual_price_amount",
    "actual_price_amount": "actual_price_amount",
    "profit brut": "gross_profit_amount",
    "gross_profit": "gross_profit_amount",
    "gross_profit_amount": "gross_profit_amount",
    "sursa": "source",
    "source": "source",
}

# Fields that are integers in the DB.
_INTEGER_FIELDS: set[str] = {"week", "leads", "phones", "custom_value_1_count", "custom_value_2_count", "sales_count"}

# Fields that are decimals in the DB.
_DECIMAL_FIELDS: set[str] = {
    "custom_value_3_amount",
    "custom_value_4_amount",
    "custom_value_5_amount",
    "sale_price_amount",
    "actual_price_amount",
    "gross_profit_amount",
}


def _normalize_header(header: str) -> str:
    """Lowercase, strip whitespace, collapse internal whitespace."""
    return re.sub(r"\s+", " ", header.strip().lower())


def _detect_delimiter(sample: str) -> str:
    """Detect CSV delimiter: semicolon or comma."""
    semicolons = sample.count(";")
    commas = sample.count(",")
    return ";" if semicolons > commas else ","


def _parse_date(value: str) -> str | None:
    """Try to parse common date formats and return ISO format (YYYY-MM-DD)."""
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except (ValueError, OverflowError):
        return None


def _parse_decimal(value: str) -> str | None:
    value = value.strip().replace(",", ".")
    if not value:
        return None
    try:
        return str(Decimal(value))
    except InvalidOperation:
        return None


def parse_csv_for_preview(file_content: bytes) -> dict:
    """Parse CSV bytes and return preview data.

    Returns dict with keys: total, valid, errors, columns_detected, rows.
    Raises ValueError for file-level errors (too large, bad format, etc.).
    """
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"Fișierul depășește limita de {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.")

    # Decode content (try utf-8-sig first for BOM, then latin-1 as fallback).
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_content.decode("latin-1")
        except UnicodeDecodeError:
            raise ValueError("Fișierul nu poate fi decodat. Asigurați-vă că este un CSV valid în format UTF-8 sau Latin-1.")

    text = text.strip()
    if not text:
        raise ValueError("Fișierul CSV este gol.")

    # Detect delimiter from first few lines.
    sample = "\n".join(text.split("\n")[:5])
    delimiter = _detect_delimiter(sample)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        raw_headers = next(reader)
    except StopIteration:
        raise ValueError("Fișierul CSV nu conține header.")

    # Map headers to DB columns.
    columns_detected: list[str] = []
    column_mapping: list[str | None] = []  # index → DB column or None if unrecognized
    for raw_h in raw_headers:
        original = raw_h.strip()
        columns_detected.append(original)
        normalized = _normalize_header(raw_h)
        column_mapping.append(_HEADER_MAP.get(normalized))

    mapped_columns = [c for c in column_mapping if c is not None]
    if not mapped_columns:
        raise ValueError(
            "Nicio coloană din CSV nu a putut fi mapată la câmpurile cunoscute. "
            "Verificați că header-ele CSV corespund: Săptămâna, Data vânzare, Lead-uri, Telefoane, etc."
        )

    rows: list[dict] = []
    for row_idx, csv_row in enumerate(reader, start=1):
        if row_idx > MAX_ROWS:
            raise ValueError(f"Fișierul depășește limita de {MAX_ROWS} rânduri.")

        row_data: dict[str, object] = {}
        errors: list[str] = []

        for col_idx, cell_value in enumerate(csv_row):
            if col_idx >= len(column_mapping):
                break
            db_col = column_mapping[col_idx]
            if db_col is None:
                continue

            cell_value = cell_value.strip()
            if not cell_value:
                continue

            if db_col == "metric_date":
                parsed = _parse_date(cell_value)
                if parsed is None:
                    errors.append(f"Format dată invalid: '{cell_value}'")
                else:
                    row_data[db_col] = parsed
            elif db_col in _INTEGER_FIELDS:
                parsed = _parse_int(cell_value)
                if parsed is None:
                    errors.append(f"Valoare numerică invalidă pentru {db_col}: '{cell_value}'")
                else:
                    row_data[db_col] = parsed
            elif db_col in _DECIMAL_FIELDS:
                parsed = _parse_decimal(cell_value)
                if parsed is None:
                    errors.append(f"Valoare decimală invalidă pentru {db_col}: '{cell_value}'")
                else:
                    row_data[db_col] = parsed
            elif db_col == "source":
                row_data[db_col] = _normalize_source_for_import(cell_value)
            else:
                row_data[db_col] = cell_value

        # Validate required fields: at least metric_date or week must exist.
        has_date = "metric_date" in row_data
        has_week = "week" in row_data
        if not has_date and not has_week:
            errors.append("Lipsește Data vânzare sau Săptămâna")

        if errors:
            rows.append({
                "row_index": row_idx,
                "status": "error",
                "error_message": "; ".join(errors),
                "data": row_data,
            })
        else:
            rows.append({
                "row_index": row_idx,
                "status": "valid",
                "data": row_data,
            })

    if not rows:
        raise ValueError("Fișierul CSV nu conține rânduri de date (doar header).")

    valid_count = sum(1 for r in rows if r["status"] == "valid")
    error_count = sum(1 for r in rows if r["status"] == "error")

    return {
        "total": len(rows),
        "valid": valid_count,
        "errors": error_count,
        "columns_detected": columns_detected,
        "columns_mapping": column_mapping,
        "rows": rows,
    }


# ── Fields that live in client_data_daily_inputs ──
_DAILY_INPUT_INT_FIELDS = {"leads", "phones", "custom_value_1_count", "custom_value_2_count", "sales_count"}
_DAILY_INPUT_DECIMAL_FIELDS = {"custom_value_3_amount", "custom_value_4_amount", "custom_value_5_amount"}
_DAILY_INPUT_ALL_FIELDS = _DAILY_INPUT_INT_FIELDS | _DAILY_INPUT_DECIMAL_FIELDS

# ── Fields that map to sale_entries ──
_SALE_ENTRY_FIELDS = {"sale_price_amount", "actual_price_amount"}

# ── Source alias map: friendly CSV names → canonical DB source keys ──
_SOURCE_ALIAS_MAP: dict[str, str] = {
    "meta": "meta_ads",
    "google": "google_ads",
    "tiktok": "tiktok_ads",
    "linkedin": "linkedin_ads",
    "pinterest": "pinterest_ads",
    "snapchat": "snapchat_ads",
    "reddit": "reddit_ads",
    "quora": "quora_ads",
    "taboola": "taboola_ads",
}


def _normalize_source_for_import(raw_source: str) -> str:
    """Normalize a CSV source value to a canonical DB source key."""
    cleaned = raw_source.strip().lower()
    if not cleaned:
        return "unknown"
    return _SOURCE_ALIAS_MAP.get(cleaned, cleaned)

_RETURNING_COLS = (
    "id, client_id, metric_date, source, leads, phones, "
    "custom_value_1_count, custom_value_2_count, custom_value_3_amount, "
    "custom_value_4_amount, custom_value_5_amount, sales_count, notes"
)


def import_csv_rows(*, client_id: int, rows: list[dict]) -> dict:
    """Import validated CSV rows into DB using a single atomic transaction.

    Each row is identified by (client_id, metric_date, source).
    Existing rows are updated (only non-null CSV fields overwrite);
    missing rows are inserted with CSV values (others default to 0).
    Sale entries (sale_price, actual_price) are created as new entries
    linked to the daily input.

    Returns dict with imported, inserted, updated, errors, message.
    Raises ValueError on total failure.
    """
    from app.db.pool import get_connection

    if not rows:
        raise ValueError("Nu există rânduri de importat.")

    inserted = 0
    updated = 0
    errors: list[dict] = []

    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                for row in rows:
                    row_data = row.get("data", {})
                    row_index = row.get("row_index", 0)

                    metric_date = row_data.get("metric_date")
                    source = _normalize_source_for_import(str(row_data.get("source", "") or ""))

                    if not metric_date:
                        errors.append({"row_index": row_index, "error_message": "Lipsește metric_date"})
                        continue

                    # Check if row exists
                    cur.execute(
                        "SELECT id, leads, phones, custom_value_1_count, custom_value_2_count, "
                        "custom_value_3_amount, custom_value_4_amount, custom_value_5_amount, sales_count "
                        "FROM client_data_daily_inputs "
                        "WHERE client_id = %s AND metric_date = %s AND source = %s LIMIT 1",
                        (int(client_id), str(metric_date), source),
                    )
                    existing = cur.fetchone()

                    # Build field updates from CSV data (only non-null values)
                    field_updates: dict[str, object] = {}
                    for field in _DAILY_INPUT_INT_FIELDS:
                        val = row_data.get(field)
                        if val is not None:
                            field_updates[field] = int(val)
                    for field in _DAILY_INPUT_DECIMAL_FIELDS:
                        val = row_data.get(field)
                        if val is not None:
                            field_updates[field] = Decimal(str(val))

                    # Recompute custom_value_5_amount = cv4 - cv3
                    if existing:
                        # existing order: leads(0), phones(1), cv1(2), cv2(3), cv3(4), cv4(5), cv5(6), sales(7)
                        effective_cv3 = Decimal(str(field_updates.get("custom_value_3_amount", existing[4] or 0)))
                        effective_cv4 = Decimal(str(field_updates.get("custom_value_4_amount", existing[5] or 0)))
                    else:
                        effective_cv3 = Decimal(str(field_updates.get("custom_value_3_amount", 0)))
                        effective_cv4 = Decimal(str(field_updates.get("custom_value_4_amount", 0)))
                    field_updates["custom_value_5_amount"] = effective_cv4 - effective_cv3

                    if existing:
                        # UPDATE existing row
                        daily_input_id = int(existing[0])
                        if field_updates:
                            set_clauses = [f"{col} = %s" for col in field_updates]
                            set_clauses.append("updated_at = NOW()")
                            params = list(field_updates.values()) + [daily_input_id]
                            cur.execute(
                                f"UPDATE client_data_daily_inputs SET {', '.join(set_clauses)} WHERE id = %s",
                                tuple(params),
                            )
                        updated += 1
                    else:
                        # INSERT new row
                        cur.execute(
                            f"""
                            INSERT INTO client_data_daily_inputs (
                                client_id, metric_date, source,
                                leads, phones, custom_value_1_count, custom_value_2_count,
                                custom_value_3_amount, custom_value_4_amount, custom_value_5_amount,
                                sales_count, notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                            RETURNING id
                            """,
                            (
                                int(client_id),
                                str(metric_date),
                                source,
                                int(field_updates.get("leads", 0)),
                                int(field_updates.get("phones", 0)),
                                int(field_updates.get("custom_value_1_count", 0)),
                                int(field_updates.get("custom_value_2_count", 0)),
                                field_updates.get("custom_value_3_amount", Decimal("0")),
                                field_updates.get("custom_value_4_amount", Decimal("0")),
                                field_updates.get("custom_value_5_amount", Decimal("0")),
                                int(field_updates.get("sales_count", 0)),
                            ),
                        )
                        new_row = cur.fetchone()
                        daily_input_id = int(new_row[0])
                        inserted += 1

                    # Create/replace sale entry if sale price fields are present
                    sale_price = row_data.get("sale_price_amount")
                    actual_price = row_data.get("actual_price_amount")
                    if sale_price is not None or actual_price is not None:
                        sp = Decimal(str(sale_price)) if sale_price is not None else Decimal("0")
                        ap = Decimal(str(actual_price)) if actual_price is not None else Decimal("0")
                        # Remove existing sale entries for this daily input before inserting
                        cur.execute(
                            "DELETE FROM client_data_sale_entries WHERE daily_input_id = %s",
                            (daily_input_id,),
                        )
                        cur.execute(
                            """
                            INSERT INTO client_data_sale_entries (
                                daily_input_id, sale_price_amount, actual_price_amount, sort_order
                            ) VALUES (%s, %s, %s, 0)
                            """,
                            (daily_input_id, sp, ap),
                        )

            if errors:
                conn.rollback()
                raise ValueError(f"{len(errors)} rânduri au eșuat la import.")

            conn.commit()
        except ValueError:
            raise
        except Exception as exc:
            conn.rollback()
            raise ValueError(f"Eroare la import: {exc}") from exc

    total_imported = inserted + updated
    parts = []
    if inserted > 0:
        parts.append(f"{inserted} {'rând nou' if inserted == 1 else 'rânduri noi'}")
    if updated > 0:
        parts.append(f"{updated} {'actualizat' if updated == 1 else 'actualizate'}")
    message = f"Import finalizat: {', '.join(parts)}." if parts else "Niciun rând importat."

    return {
        "imported": total_imported,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "message": message,
    }
