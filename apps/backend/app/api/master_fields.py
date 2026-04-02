from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.feed_management.master_fields.models import (
    MasterFieldMappingBulkRequest,
    MasterFieldMappingResponse,
)
from app.services.feed_management.master_fields.repository import (
    MasterFieldMappingNotFoundError,
    master_field_mapping_repository,
)
from app.services.feed_management.master_fields.service import (
    get_mappings_with_suggestions,
    get_source_fields,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["master-fields"])

_repo = master_field_mapping_repository


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class MasterFieldsListResponse(BaseModel):
    items: list[MasterFieldMappingResponse]


class BulkSaveResponse(BaseModel):
    items: list[MasterFieldMappingResponse]
    saved_count: int


class SourceFieldsResponse(BaseModel):
    source_id: str
    fields: list[dict[str, Any]]
    count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/feed-sources/{source_id}/master-fields")
def get_master_fields(
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return existing mappings + auto-suggestions for unmapped fields."""
    _enforce_feature_flag()
    return get_mappings_with_suggestions(source_id)


@router.post(
    "/feed-sources/{source_id}/master-fields",
    response_model=BulkSaveResponse,
    status_code=status.HTTP_200_OK,
)
def save_master_fields(
    source_id: str,
    payload: MasterFieldMappingBulkRequest,
    user: AuthUser = Depends(get_current_user),
) -> BulkSaveResponse:
    """Bulk save (upsert) all master field mappings for a source."""
    _enforce_feature_flag()
    items = _repo.bulk_save(source_id, payload.mappings)
    return BulkSaveResponse(items=items, saved_count=len(items))


@router.delete("/master-fields/{mapping_id}")
def delete_master_field(
    mapping_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a single master field mapping."""
    _enforce_feature_flag()
    try:
        _repo.delete(mapping_id)
    except MasterFieldMappingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return {"status": "ok", "id": mapping_id}


@router.get(
    "/feed-sources/{source_id}/source-fields",
    response_model=SourceFieldsResponse,
)
def list_source_fields(
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> SourceFieldsResponse:
    """Return available fields from the source data (first MongoDB product)."""
    _enforce_feature_flag()
    fields = get_source_fields(source_id)
    return SourceFieldsResponse(
        source_id=source_id,
        fields=fields,
        count=len(fields),
    )
