from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.core.config import load_settings
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.feed_management.catalog_schemas import (
    CatalogType,
    get_all_fields,
    get_catalog_schema,
    validate_mapping_completeness,
)
from app.services.feed_management.exceptions import FeedSourceNotFoundError
from app.services.feed_management.field_mapping.models import (
    CatalogFieldInfo,
    CatalogSchemaResponse,
    CatalogTypeInfo,
    FieldMappingCreate,
    FieldMappingDetailResponse,
    FieldMappingResponse,
    FieldMappingRuleCreate,
    FieldMappingRuleResponse,
    FieldMappingRuleUpdate,
    FieldMappingUpdate,
    MappingValidationResponse,
    TargetChannel,
    TransformPreviewRequest,
)
from app.services.feed_management.field_mapping.presets import (
    get_preset,
    list_available_presets,
)
from app.services.feed_management.field_mapping.repository import (
    FieldMappingNotFoundError,
    FieldMappingRepository,
    FieldMappingRuleNotFoundError,
)
from app.services.feed_management.field_mapping.transformer import field_transformer
from app.services.feed_management.products_repository import feed_products_repository
from app.services.feed_management.repository import FeedSourceRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["field-mappings"])

_source_repo = FeedSourceRepository()
_mapping_repo = FieldMappingRepository()


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed management is not enabled")


# ---------------------------------------------------------------------------
# Catalog schema endpoints (no subaccount scope needed)
# ---------------------------------------------------------------------------

class CatalogTypeListResponse(BaseModel):
    items: list[CatalogTypeInfo]


class CatalogPresetListResponse(BaseModel):
    items: list[dict[str, str]]


@router.get("/catalog-schemas", response_model=CatalogTypeListResponse)
def list_catalog_types(
    user: AuthUser = Depends(get_current_user),
) -> CatalogTypeListResponse:
    _enforce_feature_flag()
    items: list[CatalogTypeInfo] = []
    for ct in CatalogType:
        schema = get_catalog_schema(ct)
        items.append(CatalogTypeInfo(
            value=ct.value,
            label=ct.value.replace("_", " ").title(),
            required_count=len(schema.get("required", [])),
            optional_count=len(schema.get("optional", [])),
        ))
    return CatalogTypeListResponse(items=items)


@router.get("/catalog-schemas/{catalog_type}", response_model=CatalogSchemaResponse)
def get_catalog_schema_detail(
    catalog_type: CatalogType,
    user: AuthUser = Depends(get_current_user),
) -> CatalogSchemaResponse:
    _enforce_feature_flag()
    schema = get_catalog_schema(catalog_type)
    return CatalogSchemaResponse(
        catalog_type=catalog_type.value,
        required=[CatalogFieldInfo(**f) for f in schema.get("required", [])],
        optional=[CatalogFieldInfo(**f) for f in schema.get("optional", [])],
    )


@router.get("/field-mappings/presets", response_model=CatalogPresetListResponse)
def list_presets(
    user: AuthUser = Depends(get_current_user),
) -> CatalogPresetListResponse:
    _enforce_feature_flag()
    return CatalogPresetListResponse(items=list_available_presets())


@router.get("/field-mappings/presets/{catalog_type}/{channel}")
def get_preset_rules(
    catalog_type: CatalogType,
    channel: TargetChannel,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    _enforce_feature_flag()
    rules = get_preset(catalog_type, channel)
    return {"catalog_type": catalog_type.value, "channel": channel.value, "rules": [r.model_dump() for r in rules]}


# ---------------------------------------------------------------------------
# Field mapping CRUD (scoped to subaccount via feed_source)
# ---------------------------------------------------------------------------

class FieldMappingListResponse(BaseModel):
    items: list[FieldMappingResponse]


@router.get(
    "/subaccount/{subaccount_id}/feed-sources/{source_id}/field-mappings",
    response_model=FieldMappingListResponse,
)
def list_field_mappings(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingListResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    _resolve_source(subaccount_id, source_id)
    mappings = _mapping_repo.get_by_source(source_id)
    return FieldMappingListResponse(items=mappings)


@router.post(
    "/subaccount/{subaccount_id}/feed-sources/{source_id}/field-mappings",
    response_model=FieldMappingDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_field_mapping(
    subaccount_id: int,
    source_id: str,
    payload: FieldMappingCreate,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingDetailResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    source = _resolve_source(subaccount_id, source_id)

    if payload.from_preset and not payload.rules:
        ct = CatalogType(source.config.get("catalog_type", "product")) if isinstance(source.config, dict) else CatalogType.product
        preset_rules = get_preset(ct, payload.target_channel)
        payload = payload.model_copy(update={"rules": preset_rules})

    mapping = _mapping_repo.create(source_id, payload)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="field_mapping.created",
        resource=f"field_mapping:{mapping.id}",
        details={"subaccount_id": subaccount_id, "source_id": source_id, "name": payload.name},
    )
    return mapping


@router.get("/field-mappings/{mapping_id}", response_model=FieldMappingDetailResponse)
def get_field_mapping(
    mapping_id: str,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingDetailResponse:
    _enforce_feature_flag()
    try:
        return _mapping_repo.get_by_id(mapping_id)
    except FieldMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.put("/field-mappings/{mapping_id}", response_model=FieldMappingDetailResponse)
def update_field_mapping(
    mapping_id: str,
    payload: FieldMappingUpdate,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingDetailResponse:
    _enforce_feature_flag()
    try:
        return _mapping_repo.update(mapping_id, payload)
    except FieldMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/field-mappings/{mapping_id}")
def delete_field_mapping(
    mapping_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    _enforce_feature_flag()
    _mapping_repo.delete(mapping_id)
    return {"status": "ok", "id": mapping_id}


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/field-mappings/{mapping_id}/rules",
    response_model=FieldMappingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_rule(
    mapping_id: str,
    payload: FieldMappingRuleCreate,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingRuleResponse:
    _enforce_feature_flag()
    try:
        _mapping_repo.get_by_id(mapping_id)
    except FieldMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _mapping_repo.add_rule(mapping_id, payload)


@router.put("/field-mappings/rules/{rule_id}", response_model=FieldMappingRuleResponse)
def update_rule(
    rule_id: str,
    payload: FieldMappingRuleUpdate,
    user: AuthUser = Depends(get_current_user),
) -> FieldMappingRuleResponse:
    _enforce_feature_flag()
    try:
        return _mapping_repo.update_rule(rule_id, payload)
    except FieldMappingRuleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/field-mappings/rules/{rule_id}")
def delete_rule(
    rule_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    _enforce_feature_flag()
    _mapping_repo.delete_rule(rule_id)
    return {"status": "ok", "id": rule_id}


class ReorderRulesRequest(BaseModel):
    rule_ids: list[str]


@router.post("/field-mappings/{mapping_id}/rules/reorder")
def reorder_rules(
    mapping_id: str,
    payload: ReorderRulesRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    _enforce_feature_flag()
    rules = _mapping_repo.reorder_rules(mapping_id, payload.rule_ids)
    return {"rules": [r.model_dump() for r in rules]}


# ---------------------------------------------------------------------------
# Preview & validate
# ---------------------------------------------------------------------------

@router.post("/field-mappings/{mapping_id}/preview")
def preview_mapping(
    mapping_id: str,
    payload: TransformPreviewRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    _enforce_feature_flag()
    try:
        mapping = _mapping_repo.get_by_id(mapping_id)
    except FieldMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    products = feed_products_repository.list_products(
        mapping.feed_source_id, limit=payload.limit,
    )

    if payload.product_ids:
        products = [p for p in products if p.get("product_id") in payload.product_ids]

    results: list[dict[str, Any]] = []
    for prod in products[:payload.limit]:
        transformed = field_transformer.apply_mapping(prod, mapping.rules)
        results.append({"original": prod, "transformed": transformed})

    return {"mapping_id": mapping_id, "results": results}


@router.post("/field-mappings/{mapping_id}/validate", response_model=MappingValidationResponse)
def validate_mapping(
    mapping_id: str,
    user: AuthUser = Depends(get_current_user),
) -> MappingValidationResponse:
    _enforce_feature_flag()
    try:
        mapping = _mapping_repo.get_by_id(mapping_id)
    except FieldMappingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    source = _source_repo.get_by_id(mapping.feed_source_id)
    ct_str = source.config.get("catalog_type", "product") if isinstance(source.config, dict) else "product"
    ct = CatalogType(ct_str)

    mapped_fields = [r.target_field for r in mapping.rules]
    result = validate_mapping_completeness(ct, mapped_fields)
    return MappingValidationResponse(**result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_source(subaccount_id: int, source_id: str):
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    return source
