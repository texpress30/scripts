from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TransformationType(str, enum.Enum):
    direct = "direct"
    template = "template"
    static = "static"
    conditional = "conditional"
    concatenate = "concatenate"
    uppercase = "uppercase"
    lowercase = "lowercase"
    prefix = "prefix"
    suffix = "suffix"
    replace = "replace"
    truncate = "truncate"


class TargetChannel(str, enum.Enum):
    google_shopping = "google_shopping"
    meta_catalog = "meta_catalog"
    tiktok_catalog = "tiktok_catalog"
    custom = "custom"


# ---------------------------------------------------------------------------
# Rule models
# ---------------------------------------------------------------------------

class FieldMappingRuleBase(BaseModel):
    target_field: str
    source_field: str | None = None
    transformation_type: TransformationType = TransformationType.direct
    transformation_config: dict[str, Any] = Field(default_factory=dict)
    is_required: bool = False
    sort_order: int = 0


class FieldMappingRuleCreate(FieldMappingRuleBase):
    pass


class FieldMappingRuleUpdate(BaseModel):
    target_field: str | None = None
    source_field: str | None = None
    transformation_type: TransformationType | None = None
    transformation_config: dict[str, Any] | None = None
    is_required: bool | None = None
    sort_order: int | None = None


class FieldMappingRuleResponse(FieldMappingRuleBase):
    id: str
    field_mapping_id: str


# ---------------------------------------------------------------------------
# Mapping models
# ---------------------------------------------------------------------------

class FieldMappingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    target_channel: TargetChannel
    is_active: bool = True
    rules: list[FieldMappingRuleCreate] = Field(default_factory=list)
    from_preset: bool = False


class FieldMappingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    target_channel: TargetChannel | None = None
    is_active: bool | None = None


class FieldMappingResponse(BaseModel):
    id: str
    feed_source_id: str
    name: str
    target_channel: TargetChannel
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FieldMappingDetailResponse(FieldMappingResponse):
    rules: list[FieldMappingRuleResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Catalog schema response models
# ---------------------------------------------------------------------------

class CatalogFieldInfo(BaseModel):
    field: str
    type: str
    description: str = ""
    max_length: int | None = None
    values: list[str] | None = None


class CatalogSchemaResponse(BaseModel):
    catalog_type: str
    required: list[CatalogFieldInfo]
    optional: list[CatalogFieldInfo]


class CatalogTypeInfo(BaseModel):
    value: str
    label: str
    required_count: int
    optional_count: int


# ---------------------------------------------------------------------------
# Preview / validation
# ---------------------------------------------------------------------------

class TransformPreviewRequest(BaseModel):
    product_ids: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=5, ge=1, le=10)


class MappingValidationResponse(BaseModel):
    is_complete: bool
    missing_required: list[str]
    mapped_count: int
    required_count: int
