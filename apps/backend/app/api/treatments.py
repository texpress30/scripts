from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.services.auth import AuthUser
from app.services.enriched_catalog.models import TreatmentCreate, TreatmentUpdate
from app.services.enriched_catalog.repository import treatment_repository
from app.services.enriched_catalog.output_feed_service import OutputFeedNotFoundError, output_feed_service

router = APIRouter(prefix="/creative", tags=["creative-treatments"])


class ReorderTreatmentsRequest(BaseModel):
    treatment_ids: list[str] = Field(default_factory=list)


@router.get("/output-feeds/{output_feed_id}/treatments")
def list_treatments(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict]]:
    try:
        feed = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(feed["subaccount_id"]))
    return {"items": treatment_repository.get_by_output_feed(output_feed_id)}


@router.post("/output-feeds/{output_feed_id}/treatments", status_code=status.HTTP_201_CREATED)
def create_treatment(output_feed_id: str, payload: TreatmentCreate, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        feed = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(feed["subaccount_id"]))
    data = payload.model_dump()
    data["output_feed_id"] = output_feed_id
    data["filters"] = [f.model_dump() if hasattr(f, "model_dump") else f for f in (payload.filters or [])]
    return treatment_repository.create(data)


@router.put("/treatments/{treatment_id}")
def update_treatment(treatment_id: str, payload: TreatmentUpdate, user: AuthUser = Depends(get_current_user)) -> dict:
    existing = treatment_repository.get_by_id(treatment_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
    try:
        feed = output_feed_service.get_output_feed(existing["output_feed_id"])
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(feed["subaccount_id"]))
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "filters" in update_data:
        update_data["filters"] = [f.model_dump() if hasattr(f, "model_dump") else f for f in (payload.filters or [])]
    updated = treatment_repository.update(treatment_id, update_data)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
    return updated


@router.delete("/treatments/{treatment_id}")
def delete_treatment(treatment_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    existing = treatment_repository.get_by_id(treatment_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Treatment not found")
    try:
        feed = output_feed_service.get_output_feed(existing["output_feed_id"])
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(feed["subaccount_id"]))
    treatment_repository.delete(treatment_id)
    return {"status": "ok", "id": treatment_id}


@router.post("/output-feeds/{output_feed_id}/treatments/reorder")
def reorder_treatments(output_feed_id: str, payload: ReorderTreatmentsRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        feed = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(feed["subaccount_id"]))
    treatment_repository.reorder_priority(output_feed_id, payload.treatment_ids)
    return {"status": "ok", "items": treatment_repository.get_by_output_feed(output_feed_id)}
