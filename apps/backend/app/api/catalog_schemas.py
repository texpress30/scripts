from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.feed_management.catalog_field_schemas import (
    CatalogField,
    FieldType,
    get_catalog_fields,
    get_required_fields as get_required_fields_svc,
    CATALOG_FIELD_SCHEMAS,
)
from app.services.feed_management.catalog_schemas import CatalogType

logger = logging.getLogger(__name__)

# Map data_type strings back to FieldType enum values
_FIELD_TYPE_MAP: dict[str, FieldType] = {ft.value: ft for ft in FieldType}


def _resolve_catalog_fields(catalog_type_value: str) -> list[CatalogField]:
    """Return fields from schema registry DB, falling back to hardcoded."""
    try:
        from app.services.feed_management.schema_registry.repository import (
            schema_registry_repository,
        )
        db_fields = schema_registry_repository.list_fields(catalog_type_value)
    except Exception:
        db_fields = []

    if not db_fields:
        return get_catalog_fields(catalog_type_value)

    result: list[CatalogField] = []
    for d in db_fields:
        ft = _FIELD_TYPE_MAP.get(d.get("data_type", "string"), FieldType.STRING)
        result.append(CatalogField(
            name=d["field_key"],
            display_name=d["display_name"],
            description=d.get("description") or "",
            field_type=ft,
            required=bool(d.get("is_required", False)),
            category=d.get("category", ""),
            enum_values=d.get("allowed_values"),
            google_attribute=d.get("google_attribute"),
            facebook_attribute=d.get("facebook_attribute"),
            example=d.get("example_value"),
        ))
    return result

router = APIRouter(prefix="/catalog-schemas", tags=["catalog-schemas"])


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CatalogFieldResponse(BaseModel):
    name: str
    display_name: str
    description: str
    field_type: str
    required: bool
    category: str
    enum_values: list[str] | None = None
    google_attribute: str | None = None
    facebook_attribute: str | None = None
    example: str | None = None


class CatalogTypeListItem(BaseModel):
    value: str
    label: str
    required_count: int
    optional_count: int
    total_count: int


class CatalogTypeListResponse(BaseModel):
    items: list[CatalogTypeListItem]


class CatalogSchemaDetailResponse(BaseModel):
    catalog_type: str
    fields: list[CatalogFieldResponse]
    total_count: int
    required_count: int
    optional_count: int


class CatalogRequiredFieldsResponse(BaseModel):
    catalog_type: str
    fields: list[CatalogFieldResponse]
    count: int


class CategoryGroup(BaseModel):
    category: str
    fields: list[CatalogFieldResponse]


class CatalogCategoriesResponse(BaseModel):
    catalog_type: str
    categories: list[CategoryGroup]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _field_to_response(f: CatalogField) -> CatalogFieldResponse:
    return CatalogFieldResponse(
        name=f.name,
        display_name=f.display_name,
        description=f.description,
        field_type=f.field_type.value,
        required=f.required,
        category=f.category,
        enum_values=f.enum_values,
        google_attribute=f.google_attribute,
        facebook_attribute=f.facebook_attribute,
        example=f.example,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=CatalogTypeListResponse)
def list_catalog_types(
    user: AuthUser = Depends(get_current_user),
) -> CatalogTypeListResponse:
    """List all available catalog types with field counts."""
    _enforce_feature_flag()
    items: list[CatalogTypeListItem] = []
    for ct in CatalogType:
        fields = _resolve_catalog_fields(ct.value)
        req = [f for f in fields if f.required]
        opt = [f for f in fields if not f.required]
        items.append(
            CatalogTypeListItem(
                value=ct.value,
                label=ct.value.replace("_", " ").title(),
                required_count=len(req),
                optional_count=len(opt),
                total_count=len(fields),
            )
        )
    return CatalogTypeListResponse(items=items)


@router.get("/{catalog_type}", response_model=CatalogSchemaDetailResponse)
def get_catalog_schema_detail(
    catalog_type: CatalogType,
    user: AuthUser = Depends(get_current_user),
) -> CatalogSchemaDetailResponse:
    """Return all fields for a catalog type."""
    _enforce_feature_flag()
    fields = _resolve_catalog_fields(catalog_type.value)
    req = [f for f in fields if f.required]
    opt = [f for f in fields if not f.required]
    return CatalogSchemaDetailResponse(
        catalog_type=catalog_type.value,
        fields=[_field_to_response(f) for f in fields],
        total_count=len(fields),
        required_count=len(req),
        optional_count=len(opt),
    )


@router.get("/{catalog_type}/required", response_model=CatalogRequiredFieldsResponse)
def get_required_fields_endpoint(
    catalog_type: CatalogType,
    user: AuthUser = Depends(get_current_user),
) -> CatalogRequiredFieldsResponse:
    """Return only the required fields for a catalog type."""
    _enforce_feature_flag()
    fields = [f for f in _resolve_catalog_fields(catalog_type.value) if f.required]
    return CatalogRequiredFieldsResponse(
        catalog_type=catalog_type.value,
        fields=[_field_to_response(f) for f in fields],
        count=len(fields),
    )


@router.get("/{catalog_type}/categories", response_model=CatalogCategoriesResponse)
def get_fields_by_categories(
    catalog_type: CatalogType,
    user: AuthUser = Depends(get_current_user),
) -> CatalogCategoriesResponse:
    """Return fields grouped by category for a catalog type."""
    _enforce_feature_flag()
    fields = _resolve_catalog_fields(catalog_type.value)
    groups: dict[str, list[CatalogFieldResponse]] = defaultdict(list)
    for f in fields:
        groups[f.category].append(_field_to_response(f))
    return CatalogCategoriesResponse(
        catalog_type=catalog_type.value,
        categories=[
            CategoryGroup(category=cat, fields=flds) for cat, flds in groups.items()
        ],
    )
