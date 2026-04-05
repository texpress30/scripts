from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class MappingType(str, enum.Enum):
    direct = "direct"
    static = "static"
    template = "template"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class MasterFieldMappingCreate(BaseModel):
    target_field: str = Field(min_length=1, max_length=100)
    source_field: str | None = None
    mapping_type: MappingType = MappingType.direct
    static_value: str | None = None
    template_value: str | None = None
    is_required: bool = False
    sort_order: int = 0
    manually_edited: bool = False


class MasterFieldMappingUpdate(BaseModel):
    source_field: str | None = None
    mapping_type: MappingType | None = None
    static_value: str | None = None
    template_value: str | None = None
    is_required: bool | None = None
    sort_order: int | None = None
    manually_edited: bool | None = None


class MasterFieldMappingBulkItem(BaseModel):
    target_field: str = Field(min_length=1, max_length=100)
    source_field: str | None = None
    mapping_type: MappingType = MappingType.direct
    static_value: str | None = None
    template_value: str | None = None
    is_required: bool = False
    sort_order: int = 0
    manually_edited: bool = False


class MasterFieldMappingBulkRequest(BaseModel):
    mappings: list[MasterFieldMappingBulkItem]


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class MasterFieldMappingResponse(BaseModel):
    id: str
    feed_source_id: str
    target_field: str
    source_field: str | None = None
    mapping_type: MappingType
    static_value: str | None = None
    template_value: str | None = None
    is_required: bool
    sort_order: int
    manually_edited: bool = False
    created_at: datetime
    updated_at: datetime
