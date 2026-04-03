"""Service layer for CSV schema import."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any

from app.services.feed_management.schema_registry.repository import (
    schema_registry_repository,
)

logger = logging.getLogger(__name__)

_VALID_CATALOG_TYPES = frozenset({
    "product", "vehicle", "vehicle_offer", "home_listing",
    "hotel", "hotel_room", "flight", "trip", "media",
})

_VALID_DATA_TYPES = frozenset({
    "string", "number", "url", "price", "boolean", "enum", "date", "html",
    "image_url",
})

_REQUIRED_CSV_COLUMNS = {"field_key", "display_name"}


def validate_catalog_type(catalog_type: str) -> None:
    if catalog_type not in _VALID_CATALOG_TYPES:
        raise ValueError(
            f"Invalid catalog_type '{catalog_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_CATALOG_TYPES))}"
        )


def parse_and_import_csv(
    *,
    csv_bytes: bytes,
    channel_slug: str,
    catalog_type: str,
) -> dict[str, Any]:
    """Parse CSV content and upsert fields into the schema registry.

    Returns a summary dict with fields_added, fields_updated,
    fields_deprecated counts and the list of processed field_keys.
    """
    text = csv_bytes.decode("utf-8-sig")  # handles BOM
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row")

    # Normalise header names (strip whitespace, lowercase)
    normalised = {h.strip().lower(): h for h in reader.fieldnames}
    missing = _REQUIRED_CSV_COLUMNS - set(normalised.keys())
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {', '.join(sorted(missing))}. "
            f"Found columns: {', '.join(reader.fieldnames)}"
        )

    # Existing field_keys for deprecation check
    existing_keys = schema_registry_repository.count_existing_channel_fields(
        channel_slug, catalog_type,
    )

    fields_added = 0
    fields_updated = 0
    imported_keys: set[str] = set()

    for sort_idx, row in enumerate(reader, start=1):
        # Normalise row keys
        norm_row = {k.strip().lower(): (v or "").strip() for k, v in row.items()}

        field_key = norm_row.get("field_key", "").strip()
        display_name = norm_row.get("display_name", "").strip()

        if not field_key or not display_name:
            continue  # skip blank rows

        data_type = norm_row.get("data_type", "string").strip() or "string"
        if data_type not in _VALID_DATA_TYPES:
            data_type = "string"

        # Parse allowed_values from comma-separated string
        allowed_raw = norm_row.get("allowed_values", "").strip()
        allowed_values: list[str] | None = None
        if allowed_raw:
            allowed_values = [v.strip() for v in allowed_raw.split(",") if v.strip()]

        is_required_raw = norm_row.get("is_required", "false").strip().lower()
        is_required = is_required_raw in ("true", "1", "yes")

        channel_field_name = norm_row.get("channel_field_name", "").strip() or field_key
        default_value = norm_row.get("default_value", "").strip() or None

        # 1. Upsert into feed_schema_fields
        field_id, was_inserted = schema_registry_repository.upsert_field(
            catalog_type=catalog_type,
            field_key=field_key,
            display_name=display_name,
            description=norm_row.get("description", "").strip() or None,
            data_type=data_type,
            allowed_values=allowed_values,
            format_pattern=norm_row.get("format_pattern", "").strip() or None,
            example_value=norm_row.get("example_value", "").strip() or None,
        )

        if was_inserted:
            fields_added += 1
        else:
            fields_updated += 1

        # 2. Upsert into feed_schema_channel_fields
        schema_registry_repository.upsert_channel_field(
            schema_field_id=field_id,
            channel_slug=channel_slug,
            is_required=is_required,
            channel_field_name=channel_field_name,
            default_value=default_value,
            sort_order=sort_idx,
        )

        imported_keys.add(field_key)

    # 3. Deprecation count: existing keys not present in this CSV
    deprecated_keys = existing_keys - imported_keys
    fields_deprecated = len(deprecated_keys)

    return {
        "fields_added": fields_added,
        "fields_updated": fields_updated,
        "fields_deprecated": fields_deprecated,
        "imported_keys": sorted(imported_keys),
    }


def upload_csv_to_s3(
    *,
    csv_bytes: bytes,
    catalog_type: str,
    channel_slug: str,
    filename: str,
) -> str | None:
    """Upload the raw CSV to S3 and return the S3 key, or None on failure."""
    try:
        from app.services.s3_provider import get_s3_client, get_s3_bucket_name

        bucket = get_s3_bucket_name()
        if not bucket:
            logger.warning("S3 bucket not configured — skipping CSV upload")
            return None

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"feed-schemas/{catalog_type}/{channel_slug}/{ts}_{filename}"

        s3 = get_s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=csv_bytes,
            ContentType="text/csv",
        )
        return s3_key
    except Exception:
        logger.exception("Failed to upload schema CSV to S3")
        return None
