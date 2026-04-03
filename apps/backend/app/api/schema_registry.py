"""API endpoints for Feed Schema Registry — template import and retrieval."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.feed_management.schema_registry.repository import (
    schema_registry_repository,
)
from app.services.feed_management.schema_registry.service import (
    parse_and_import,
    upload_file_to_s3,
    validate_catalog_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed-schema-registry"])

_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "application/xml",
    "text/xml",
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
    format_detected: str | None = None
    warnings: list[str] = []
    fields_parsed: int = 0


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
    template_format: str = Form(default="auto"),
    user: AuthUser = Depends(get_current_user),
) -> SchemaImportResponse:
    """Import a template file with field specifications for a channel + catalog type.

    Supports: Meta CSV templates, XML feed templates, and custom CSV format.
    Set ``template_format`` to ``auto`` (default), ``meta_csv``, ``xml``, or ``custom``.
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
    is_accepted = (
        content_type in _ALLOWED_CONTENT_TYPES
        or filename.lower().endswith((".csv", ".xml"))
    )
    if not is_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{content_type}'. Expected CSV or XML.",
        )

    # Read file
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # --- Parse & import ----------------------------------------------------
    try:
        result = parse_and_import(
            file_bytes=file_bytes,
            filename=filename,
            channel_slug=channel_slug,
            catalog_type=catalog_type,
            template_format=template_format.strip(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # --- S3 upload ---------------------------------------------------------
    s3_path = upload_file_to_s3(
        file_bytes=file_bytes,
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
        format_detected=result.get("format_detected"),
        warnings=result.get("warnings", []),
        fields_parsed=result.get("fields_parsed", 0),
    )


# ---------------------------------------------------------------------------
# Retrieval endpoints
# ---------------------------------------------------------------------------

@router.get("/feed-management/schemas/fields")
def list_schema_fields(
    catalog_type: str = Query(...),
    channel_slug: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return schema fields for a catalog type, optionally filtered by channel.

    When *channel_slug* is provided only fields linked to that channel are
    returned and ``is_required`` reflects that specific channel's requirement.
    Otherwise the full superset is returned with ``is_required`` derived from
    the MAX across all channels.
    """
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    fields = schema_registry_repository.list_fields(catalog_type, channel_slug)
    required_count = sum(1 for f in fields if f.get("is_required"))
    optional_count = len(fields) - required_count

    return {
        "catalog_type": catalog_type,
        "channel_slug": channel_slug,
        "total_fields": len(fields),
        "required_count": required_count,
        "optional_count": optional_count,
        "fields": fields,
    }


@router.get("/feed-management/schemas/channels")
def list_schema_channels(
    catalog_type: str = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return channels that have field definitions for a catalog type."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    channels = schema_registry_repository.list_channels(catalog_type)
    return {
        "catalog_type": catalog_type,
        "channels": channels,
    }


@router.get("/feed-management/schemas/imports")
def list_schema_imports(
    catalog_type: str | None = Query(default=None),
    channel_slug: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return import history, optionally filtered by catalog_type and/or channel."""
    _enforce_feature_flag()

    if catalog_type:
        try:
            validate_catalog_type(catalog_type)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
            ) from exc

    imports = schema_registry_repository.list_imports(
        catalog_type=catalog_type,
        channel_slug=channel_slug,
        limit=limit,
    )
    return {"imports": imports}
