from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.services.auth import AuthUser
from app.services.enriched_catalog.models import BrandPresetCreate, BrandPresetUpdate
from app.services.enriched_catalog.repository import brand_preset_repository

router = APIRouter(prefix="/creative/brand-presets", tags=["creative-brand-presets"])


@router.get("")
def list_brand_presets(subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict]]:
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=subaccount_id)
    return {"items": brand_preset_repository.get_by_subaccount(subaccount_id)}


@router.get("/{preset_id}")
def get_brand_preset(preset_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    preset = brand_preset_repository.get_by_id(preset_id)
    if preset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand preset not found")
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(preset.get("subaccount_id", 0)))
    return preset


@router.post("", status_code=status.HTTP_201_CREATED)
def create_brand_preset(payload: BrandPresetCreate, subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict:
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=subaccount_id)
    return brand_preset_repository.create(subaccount_id, payload.model_dump())


@router.put("/{preset_id}")
def update_brand_preset(preset_id: str, payload: BrandPresetUpdate, user: AuthUser = Depends(get_current_user)) -> dict:
    existing = brand_preset_repository.get_by_id(preset_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand preset not found")
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing.get("subaccount_id", 0)))
    updated = brand_preset_repository.update(preset_id, {k: v for k, v in payload.model_dump().items() if v is not None})
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand preset not found")
    return updated


@router.delete("/{preset_id}")
def delete_brand_preset(preset_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    existing = brand_preset_repository.get_by_id(preset_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand preset not found")
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing.get("subaccount_id", 0)))
    brand_preset_repository.delete(preset_id)
    return {"status": "ok", "id": preset_id}
