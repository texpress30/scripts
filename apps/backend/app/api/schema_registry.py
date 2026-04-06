"""API endpoints for Feed Schema Registry — template import and retrieval."""

from __future__ import annotations

import json
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
    normalize_slug,
    parse_and_import,
    upload_file_to_s3,
    validate_catalog_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed-schema-registry"])


def _channel_slug_to_platform(slug: str) -> str:
    """Map a channel_slug to a short platform name for alias platform_hints."""
    slug_lower = slug.lower()
    if slug_lower.startswith(("facebook_", "meta_")):
        return "meta"
    if slug_lower.startswith("tiktok"):
        return "tiktok"
    if slug_lower.startswith("google"):
        return "google"
    return slug_lower

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
    channel_slug_original: str | None = None
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
    confirmed_aliases: str = Form(default=""),
    subtype_slug: str = Form(default=""),
    user: AuthUser = Depends(get_current_user),
) -> SchemaImportResponse:
    """Import a template file with field specifications for a channel + catalog type.

    Supports: Meta CSV templates, XML feed templates, and custom CSV format.
    Set ``template_format`` to ``auto`` (default), ``meta_csv``, ``xml``, or ``custom``.
    """
    _enforce_feature_flag()

    # --- Validate inputs ---------------------------------------------------
    channel_slug_original = channel_slug.strip()
    channel_slug = normalize_slug(channel_slug_original)
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

    # --- Create confirmed aliases (if provided) ----------------------------
    if confirmed_aliases:
        try:
            alias_list = json.loads(confirmed_aliases)
            if isinstance(alias_list, list):
                for a in alias_list:
                    if isinstance(a, dict) and a.get("new_field_key") and a.get("canonical_key"):
                        try:
                            schema_registry_repository.create_alias(
                                catalog_type=catalog_type,
                                canonical_key=a["canonical_key"],
                                alias_key=a["new_field_key"],
                                platform_hint=_channel_slug_to_platform(channel_slug),
                            )
                        except (ValueError, Exception):
                            pass  # alias may already exist
        except (json.JSONDecodeError, TypeError):
            pass  # invalid JSON — skip, don't block import

    # --- Parse & import ----------------------------------------------------
    try:
        result = parse_and_import(
            file_bytes=file_bytes,
            filename=filename,
            channel_slug=channel_slug,
            catalog_type=catalog_type,
            template_format=template_format.strip(),
            subtype_slug=subtype_slug.strip() or None,
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
        channel_slug_original=channel_slug_original if channel_slug_original != channel_slug else None,
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
# Preview endpoint (with AI alias suggestions)
# ---------------------------------------------------------------------------

@router.post("/feed-management/schemas/import/preview")
async def preview_schema_import(
    channel_slug: str = Form(...),
    catalog_type: str = Form(...),
    file: UploadFile = File(...),
    template_format: str = Form(default="auto"),
    model: str = Form(default=""),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Parse a template and return categorized fields with AI alias suggestions."""
    _enforce_feature_flag()

    channel_slug_original = channel_slug.strip()
    channel_slug = normalize_slug(channel_slug_original)
    catalog_type = catalog_type.strip()

    if not channel_slug:
        raise HTTPException(status_code=422, detail="channel_slug is required")
    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # 1. Parse template
    from app.services.feed_management.schema_registry.adapters import parse_template
    try:
        fields, detected_format, warnings = parse_template(
            file_bytes, file.filename or "upload.csv", template_format.strip(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 2. Load existing canonical fields
    existing = schema_registry_repository.list_fields(catalog_type)
    existing_keys = {f["field_key"] for f in existing}

    # 3. Categorize
    exact_match = []
    new_fields = []
    for f in fields:
        if f["field_key"] in existing_keys:
            exact_match.append({"field_key": f["field_key"], "status": "exists_in_superset"})
        else:
            new_fields.append(f)

    # 4. AI suggestions (if enabled)
    ai_suggestions: list[dict] = []
    ai_available = False
    if new_fields:
        from app.services.feed_management.schema_registry.ai_suggestions import (
            is_ai_enabled, suggest_aliases,
        )
        if is_ai_enabled():
            ai_available = True
            ai_suggestions = suggest_aliases(new_fields, existing, catalog_type, model=model or None)

    return {
        "format_detected": detected_format,
        "fields_parsed": len(fields),
        "warnings": warnings,
        "categories": {
            "exact_match": exact_match,
            "ai_suggested_aliases": [
                {**s, "action": "pending"} for s in ai_suggestions
            ],
            "new_fields": [
                {"field_key": f["field_key"], "display_name": f.get("display_name", ""),
                 "data_type": f.get("data_type", "string")}
                for f in new_fields
                if f["field_key"] not in {s["new_field_key"] for s in ai_suggestions}
            ],
        },
        "ai_suggestions_available": ai_available,
    }


# ---------------------------------------------------------------------------
# Catalog sub-types endpoints
# ---------------------------------------------------------------------------

class CreateSubtypeRequest(BaseModel):
    catalog_type: str
    subtype_slug: str
    subtype_name: str
    description: str | None = None
    icon_hint: str | None = None
    sort_order: int = 0


@router.get("/feed-management/schemas/subtypes")
def list_subtypes(
    catalog_type: str = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return catalog sub-types with channel and field counts."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    subtypes = schema_registry_repository.list_subtypes(catalog_type)
    return {
        "catalog_type": catalog_type,
        "subtypes": subtypes,
    }


@router.post(
    "/feed-management/schemas/subtypes",
    status_code=status.HTTP_201_CREATED,
)
def create_subtype(
    payload: CreateSubtypeRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Create a new catalog sub-type."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(payload.catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    try:
        subtype = schema_registry_repository.create_subtype(
            catalog_type=payload.catalog_type,
            subtype_slug=payload.subtype_slug,
            subtype_name=payload.subtype_name,
            description=payload.description,
            icon_hint=payload.icon_hint,
            sort_order=payload.sort_order,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    return subtype


@router.delete(
    "/feed-management/schemas/subtypes/{subtype_id}",
    status_code=status.HTTP_200_OK,
)
def delete_subtype(
    subtype_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Delete a catalog sub-type (only if no channel fields reference it)."""
    _enforce_feature_flag()

    try:
        schema_registry_repository.delete_subtype(subtype_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return {"status": "ok", "id": subtype_id}


# ---------------------------------------------------------------------------
# Retrieval endpoints
# ---------------------------------------------------------------------------

@router.get("/feed-management/schemas/fields")
def list_schema_fields(
    catalog_type: str = Query(...),
    channel_slug: str | None = Query(default=None),
    subtype_slug: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return schema fields for a catalog type, optionally filtered by channel or subtype.

    When *channel_slug* is provided only fields linked to that channel are
    returned and ``is_required`` reflects that specific channel's requirement.
    When *subtype_slug* is provided, only fields belonging to channels with that
    subtype are returned.
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

    if channel_slug:
        channel_slug = normalize_slug(channel_slug)
    fields = schema_registry_repository.list_fields(
        catalog_type, channel_slug, subtype_slug=subtype_slug,
    )
    required_count = sum(1 for f in fields if f.get("is_required"))
    optional_count = len(fields) - required_count

    return {
        "catalog_type": catalog_type,
        "channel_slug": channel_slug,
        "subtype_slug": subtype_slug,
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
    """Return channels that have field definitions for a catalog type, with subtype info."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    channels = schema_registry_repository.list_channels(catalog_type)

    # Enrich with subtype info
    subtype_map = schema_registry_repository.get_channel_subtype_map(catalog_type)
    for ch in channels:
        slug = str(ch.get("channel_slug", ""))
        st = subtype_map.get(slug)
        ch["subtype_slug"] = st["subtype_slug"] if st else None
        ch["subtype_name"] = st["subtype_name"] if st else None

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
        channel_slug=normalize_slug(channel_slug) if channel_slug else None,
        limit=limit,
    )
    return {"imports": imports}


# ---------------------------------------------------------------------------
# AI analysis endpoints
# ---------------------------------------------------------------------------

@router.get("/feed-management/schemas/ai-status")
def ai_status(user: AuthUser = Depends(get_current_user)) -> dict:
    """Return AI availability and model info."""
    _enforce_feature_flag()
    from app.services.feed_management.schema_registry.ai_suggestions import get_ai_status
    return get_ai_status()


@router.post("/feed-management/schemas/analyze")
def analyze_fields(
    catalog_type: str = Form(...),
    model: str = Form(default=""),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Suggest canonical groups for each field using AI with template descriptions."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from app.services.feed_management.schema_registry.ai_suggestions import (
        suggest_canonical_groups, is_ai_enabled, _resolve_model,
    )

    if not is_ai_enabled():
        return {
            "catalog_type": catalog_type,
            "ai_available": False,
            "suggestions": [],
            "total_fields": 0,
        }

    all_fields = schema_registry_repository.list_fields(catalog_type)
    aliases = schema_registry_repository.get_aliases_for_fields(catalog_type)
    resolved_model = _resolve_model(model or None)

    suggestions = suggest_canonical_groups(all_fields, catalog_type, model=resolved_model)

    # Build groups summary from AI + existing aliases
    groups: dict[str, list[str]] = {}
    for s in suggestions:
        cg = s.get("canonical_group", s.get("field_key", ""))
        groups.setdefault(cg, []).append(s.get("field_key", ""))

    # Build confirmed groups from existing aliases
    confirmed_groups: list[dict] = []
    for canonical_key, alias_list in aliases.items():
        confirmed_groups.append({
            "canonical_group": canonical_key,
            "aliases": [a["alias_key"] for a in alias_list],
            "status": "confirmed",
        })

    # Self-canonical count (fields with no aliases)
    fields_with_aliases = set(aliases.keys())
    self_canonical = sum(1 for f in all_fields if f["field_key"] not in fields_with_aliases)

    return {
        "catalog_type": catalog_type,
        "model_used": resolved_model,
        "total_fields": len(all_fields),
        "suggestions": suggestions,
        "confirmed_groups": confirmed_groups,
        "self_canonical_count": self_canonical,
        "groups_summary": [
            {"canonical_group": k, "members": v}
            for k, v in groups.items() if len(v) > 1
        ],
        "ai_available": True,
    }


@router.post("/feed-management/schemas/fields/{field_id}/canonical")
def set_field_canonical(
    field_id: str,
    payload: dict,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Set canonical_group for a single field."""
    _enforce_feature_flag()
    canonical_group = payload.get("canonical_group", "")
    status = payload.get("status", "confirmed")
    if not canonical_group:
        raise HTTPException(status_code=422, detail="canonical_group is required")
    schema_registry_repository.set_canonical(field_id, canonical_group, status)
    return {"status": "ok", "field_id": field_id, "canonical_group": canonical_group}


@router.post("/feed-management/schemas/fields/bulk-canonical")
def bulk_set_canonical(
    payload: dict,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Bulk update canonical_group for multiple fields."""
    _enforce_feature_flag()
    updates = payload.get("updates", [])
    if not updates:
        raise HTTPException(status_code=422, detail="updates array is required")
    count = schema_registry_repository.bulk_set_canonical(updates)
    return {"status": "ok", "updated_count": count}


@router.post("/feed-management/schemas/analyze/confirm")
def confirm_analysis(
    payload: dict,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Confirm and execute field merges from AI analysis."""
    _enforce_feature_flag()

    catalog_type = payload.get("catalog_type", "")
    confirmed_groups = payload.get("confirmed_groups", [])

    if not catalog_type or not confirmed_groups:
        raise HTTPException(status_code=422, detail="catalog_type and confirmed_groups required")

    aliases_created = 0
    fields_merged = 0

    for group in confirmed_groups:
        canonical = group.get("canonical_key", "")
        alias_keys = group.get("aliases", [])
        hints = group.get("platform_hints", {})

        for alias_key in alias_keys:
            if alias_key == canonical:
                continue
            merged = schema_registry_repository.merge_field_into_canonical(
                catalog_type=catalog_type,
                canonical_key=canonical,
                alias_key=alias_key,
                platform_hint=hints.get(alias_key, "ai_analysis"),
            )
            if merged:
                aliases_created += 1
                fields_merged += 1

    return {
        "status": "ok",
        "aliases_created": aliases_created,
        "fields_merged": fields_merged,
    }


# ---------------------------------------------------------------------------
# Alias endpoints
# ---------------------------------------------------------------------------

class CreateAliasRequest(BaseModel):
    catalog_type: str
    canonical_key: str
    alias_key: str
    platform_hint: str | None = None


@router.get("/feed-management/schemas/aliases")
def list_aliases(
    catalog_type: str = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Return field aliases for a catalog type."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    aliases = schema_registry_repository.list_aliases(catalog_type)
    return {"catalog_type": catalog_type, "aliases": aliases}


@router.post(
    "/feed-management/schemas/aliases",
    status_code=status.HTTP_201_CREATED,
)
def create_alias(
    payload: CreateAliasRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Create a new field alias."""
    _enforce_feature_flag()

    try:
        validate_catalog_type(payload.catalog_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    try:
        alias = schema_registry_repository.create_alias(
            catalog_type=payload.catalog_type,
            canonical_key=payload.canonical_key,
            alias_key=payload.alias_key,
            platform_hint=payload.platform_hint,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
        ) from exc

    return alias


@router.delete(
    "/feed-management/schemas/aliases/{alias_id}",
    status_code=status.HTTP_200_OK,
)
def delete_alias(
    alias_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Delete a field alias."""
    _enforce_feature_flag()

    try:
        schema_registry_repository.delete_alias(alias_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc),
        ) from exc

    return {"status": "ok", "id": alias_id}
