from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Canvas element
# ---------------------------------------------------------------------------

class CanvasElement(BaseModel):
    type: Literal["text", "image", "shape", "dynamic_field"]
    position_x: float = 0.0
    position_y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    style: dict[str, object] = Field(default_factory=dict)
    dynamic_binding: str | None = None  # e.g. "{{product_title}}", "{{price}}"
    content: str = ""


# ---------------------------------------------------------------------------
# Creative template
# ---------------------------------------------------------------------------

class CreativeTemplate(BaseModel):
    id: str = ""
    subaccount_id: int = 0
    name: str = ""
    canvas_width: int = 1080
    canvas_height: int = 1080
    elements: list[CanvasElement] = Field(default_factory=list)
    background_color: str = "#FFFFFF"
    created_at: str = ""
    updated_at: str = ""


class CreativeTemplateCreate(BaseModel):
    name: str
    canvas_width: int = 1080
    canvas_height: int = 1080
    elements: list[CanvasElement] = Field(default_factory=list)
    background_color: str = "#FFFFFF"


class CreativeTemplateUpdate(BaseModel):
    name: str | None = None
    canvas_width: int | None = None
    canvas_height: int | None = None
    elements: list[CanvasElement] | None = None
    background_color: str | None = None


class CreativeTemplateResponse(BaseModel):
    id: str
    subaccount_id: int
    name: str
    canvas_width: int
    canvas_height: int
    elements: list[CanvasElement]
    background_color: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Treatment filter & treatment
# ---------------------------------------------------------------------------

class TreatmentFilter(BaseModel):
    field_name: str
    operator: Literal["equals", "contains", "in_list"]
    value: str | list[str]


class Treatment(BaseModel):
    id: str = ""
    output_feed_id: str = ""
    name: str = ""
    template_id: str = ""
    filters: list[TreatmentFilter] = Field(default_factory=list)
    priority: int = 0
    is_default: bool = False
    created_at: str = ""
    updated_at: str = ""


class TreatmentCreate(BaseModel):
    name: str
    template_id: str
    output_feed_id: str
    filters: list[TreatmentFilter] = Field(default_factory=list)
    priority: int = 0
    is_default: bool = False


class TreatmentUpdate(BaseModel):
    name: str | None = None
    template_id: str | None = None
    filters: list[TreatmentFilter] | None = None
    priority: int | None = None
    is_default: bool | None = None


class TreatmentResponse(BaseModel):
    id: str
    output_feed_id: str
    name: str
    template_id: str
    filters: list[TreatmentFilter]
    priority: int
    is_default: bool
    created_at: str
    updated_at: str
