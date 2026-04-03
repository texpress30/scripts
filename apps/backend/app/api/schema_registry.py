"""API endpoints for Feed Schema Registry — CSV import of field specifications."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.feed_management.schema_registry.repository import (
    schema_registry_repository,
)
from app.services.feed_management.schema_registry.service import (
    parse_and_import_csv,
    upload_csv_to_s3,
    validate_catalog_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed-schema-registry"])

_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ImportSummary(BaseModel):
    fields_added: int
    fields_updated: int
    fields_deprecated: int
    total_fields_in_superset: int


class SchemaImportResponse(BaseModel):
    status: str
    channel_slug: str
    catalog_type: str
    summary: ImportSummary
    s3_path: str | None
    import_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/feed-management/schemas/import",
    response_model=SchemaImportResponse,
    status_code=status.HTTP_200_OK,
)
async def import_schema_csv(
    channel_slug: str = Form(...),
    catalog_type: str = Form(...),
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
) -> SchemaImportResponse:
    """Import a CSV file with field specifications for a channel + catalog type.

    The CSV must have at least ``field_key`` and ``display_name`` columns.
    Optional columns: ``description``, ``data_type``, ``is_required``,
    ``allowed_values``, ``format_pattern``, ``example_value``,
    ``channel_field_name``, ``default_value``.
    """
    _enforce_feature_flag()

    # --- Validate inputs ---------------------------------------------------
    channel_slug = channel_slug.strip()
    catalog_type = catalog_type.strip()

    if not channel_slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="channel_slug is required",
        )

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Validate file type
    content_type = (file.content_type or "").lower()
    filename = file.filename or "upload.csv"
    if content_type not in _ALLOWED_CONTENT_TYPES and not filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{content_type}'. Expected a CSV file.",
        )

    # Read file
    csv_bytes = await file.read()
    if not csv_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # --- Parse & import ----------------------------------------------------
    try:
        result = parse_and_import_csv(
            csv_bytes=csv_bytes,
            channel_slug=channel_slug,
            catalog_type=catalog_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # --- S3 upload ---------------------------------------------------------
    s3_path = upload_csv_to_s3(
        csv_bytes=csv_bytes,
        catalog_type=catalog_type,
        channel_slug=channel_slug,
        filename=filename,
    )

    # --- Audit log ---------------------------------------------------------
    total_fields = schema_registry_repository.count_total_fields(catalog_type)

    import_id = schema_registry_repository.create_import_log(
        channel_slug=channel_slug,
        catalog_type=catalog_type,
        agency_id=None,
        filename=filename,
        s3_path=s3_path,
        fields_added=result["fields_added"],
        fields_updated=result["fields_updated"],
        fields_deprecated=result["fields_deprecated"],
        imported_by=user.user_id,
    )

    return SchemaImportResponse(
        status="success",
        channel_slug=channel_slug,
        catalog_type=catalog_type,
        summary=ImportSummary(
            fields_added=result["fields_added"],
            fields_updated=result["fields_updated"],
            fields_deprecated=result["fields_deprecated"],
            total_fields_in_superset=total_fields,
        ),
        s3_path=s3_path,
        import_id=import_id,
    )
