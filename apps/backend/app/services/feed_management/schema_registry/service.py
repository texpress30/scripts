"""Service layer for schema import — supports multiple template formats."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.feed_management.schema_registry.adapters import (
    FieldSpec,
    parse_template,
)
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


def validate_catalog_type(catalog_type: str) -> None:
    if catalog_type not in _VALID_CATALOG_TYPES:
        raise ValueError(
            f"Invalid catalog_type '{catalog_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_CATALOG_TYPES))}"
        )


# ---------------------------------------------------------------------------
# Unified import (adapter-based)
# ---------------------------------------------------------------------------

def parse_and_import(
    *,
    file_bytes: bytes,
    filename: str,
    channel_slug: str,
    catalog_type: str,
    template_format: str = "auto",
) -> dict[str, Any]:
    """Parse a template file (any supported format), upsert fields, return summary."""

    # 1. Parse template via adapter
    fields, detected_format, warnings = parse_template(
        file_bytes, filename, template_format,
    )

    if not fields:
        raise ValueError("Template parsed successfully but contained no fields.")

    # 2. Upsert into DB
    result = _upsert_fields(
        fields=fields,
        channel_slug=channel_slug,
        catalog_type=catalog_type,
    )

    result["format_detected"] = detected_format
    result["warnings"] = warnings
    result["fields_parsed"] = len(fields)
    return result


def parse_and_import_csv(
    *,
    csv_bytes: bytes,
    channel_slug: str,
    catalog_type: str,
) -> dict[str, Any]:
    """Legacy entry point — delegates to parse_and_import with auto-detect."""
    return parse_and_import(
        file_bytes=csv_bytes,
        filename="upload.csv",
        channel_slug=channel_slug,
        catalog_type=catalog_type,
        template_format="auto",
    )


# ---------------------------------------------------------------------------
# DB upsert logic (shared by all adapters)
# ---------------------------------------------------------------------------

def _upsert_fields(
    *,
    fields: list[FieldSpec],
    channel_slug: str,
    catalog_type: str,
) -> dict[str, Any]:
    """Upsert a list of parsed field specs into the schema registry."""

    existing_keys = schema_registry_repository.count_existing_channel_fields(
        channel_slug, catalog_type,
    )

    fields_added = 0
    fields_updated = 0
    imported_keys: set[str] = set()

    for sort_idx, spec in enumerate(fields, start=1):
        field_key = spec["field_key"]
        display_name = spec["display_name"]

        if not field_key or not display_name:
            continue

        data_type = spec.get("data_type", "string") or "string"
        if data_type not in _VALID_DATA_TYPES:
            data_type = "string"

        allowed_values = spec.get("allowed_values")
        is_required = bool(spec.get("is_required", False))
        channel_field_name = spec.get("channel_field_name") or field_key

        # 1. Upsert into feed_schema_fields
        field_id, was_inserted = schema_registry_repository.upsert_field(
            catalog_type=catalog_type,
            field_key=field_key,
            display_name=display_name,
            description=spec.get("description"),
            data_type=data_type,
            allowed_values=allowed_values,
            format_pattern=spec.get("format_pattern"),
            example_value=spec.get("example_value"),
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
            default_value=spec.get("default_value"),
            sort_order=sort_idx,
        )

        imported_keys.add(field_key)

    # 3. Deprecation count
    deprecated_keys = existing_keys - imported_keys
    fields_deprecated = len(deprecated_keys)

    return {
        "fields_added": fields_added,
        "fields_updated": fields_updated,
        "fields_deprecated": fields_deprecated,
        "imported_keys": sorted(imported_keys),
    }


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------

def upload_file_to_s3(
    *,
    file_bytes: bytes,
    catalog_type: str,
    channel_slug: str,
    filename: str,
) -> str | None:
    """Upload the raw template file to S3 and return the S3 key."""
    try:
        from app.services.s3_provider import get_s3_client, get_s3_bucket_name

        bucket = get_s3_bucket_name()
        if not bucket:
            logger.warning("S3 bucket not configured — skipping file upload")
            return None

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"feed-schemas/{catalog_type}/{channel_slug}/{ts}_{filename}"

        content_type = "application/xml" if filename.lower().endswith(".xml") else "text/csv"

        s3 = get_s3_client()
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return s3_key
    except Exception:
        logger.exception("Failed to upload schema file to S3")
        return None


# Keep old name as alias for backward compat
upload_csv_to_s3 = upload_file_to_s3
