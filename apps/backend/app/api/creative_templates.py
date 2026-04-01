from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.services.auth import AuthUser
from app.services.enriched_catalog.exceptions import TemplateNotFoundError
from app.services.enriched_catalog.models import CreativeTemplateCreate, CreativeTemplateUpdate
from app.services.enriched_catalog.repository import creative_template_repository
from app.services.enriched_catalog.template_service import template_service

router = APIRouter(prefix="/creative/templates", tags=["creative-templates"])


class DuplicateTemplateRequest(BaseModel):
    new_name: str


class PreviewTemplateRequest(BaseModel):
    product_data: dict[str, object] = Field(default_factory=dict)


class ValidateBindingsRequest(BaseModel):
    available_fields: list[str] = Field(default_factory=list)


@router.get("")
def list_templates(subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict]]:
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=subaccount_id)
    items = creative_template_repository.get_by_subaccount(subaccount_id)
    return {"items": items}


@router.get("/{template_id}")
def get_template(template_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        template = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(template.get("subaccount_id", 0)))
    return template


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(payload: CreativeTemplateCreate, subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict:
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=subaccount_id)
    return template_service.create_template(subaccount_id, payload.model_dump())


@router.put("/{template_id}")
def update_template(template_id: str, payload: CreativeTemplateUpdate, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing.get("subaccount_id", 0)))
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "elements" in update_data:
        update_data["elements"] = [el.model_dump() if hasattr(el, "model_dump") else el for el in (payload.elements or [])]
    updated = creative_template_repository.update(template_id, update_data)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return updated


@router.delete("/{template_id}")
def delete_template(template_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing.get("subaccount_id", 0)))
    creative_template_repository.delete(template_id)
    return {"status": "ok", "id": template_id}


@router.post("/{template_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_template(template_id: str, payload: DuplicateTemplateRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing.get("subaccount_id", 0)))
    try:
        return template_service.duplicate_template(template_id, payload.new_name)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{template_id}/preview")
def preview_template(template_id: str, payload: PreviewTemplateRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(existing.get("subaccount_id", 0)))
    return template_service.preview_template(template_id, payload.product_data)


@router.post("/{template_id}/validate-bindings")
def validate_bindings(template_id: str, payload: ValidateBindingsRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = template_service.get_template(template_id)
    except TemplateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(existing.get("subaccount_id", 0)))
    errors = template_service.validate_dynamic_bindings(template_id, payload.available_fields)
    return {"valid": len(errors) == 0, "errors": errors}
