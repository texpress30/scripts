from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.services.auth import AuthUser
from app.services.enriched_catalog.output_feed_service import OutputFeedNotFoundError, output_feed_service
from app.services.enriched_catalog.repository import treatment_repository

router = APIRouter(prefix="/creative/output-feeds", tags=["creative-output-feeds"])


class CreateOutputFeedRequest(BaseModel):
    name: str
    feed_source_id: str | None = None


class UpdateOutputFeedRequest(BaseModel):
    name: str | None = None
    feed_source_id: str | None = None


class StartRenderRequest(BaseModel):
    template_id: str
    products: list[dict] = Field(default_factory=list)


@router.get("")
def list_output_feeds(subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict]]:
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=subaccount_id)
    return {"items": output_feed_service.list_output_feeds(subaccount_id)}


@router.get("/{output_feed_id}")
def get_output_feed(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        feed = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(feed["subaccount_id"]))
    feed["treatments"] = treatment_repository.get_by_output_feed(output_feed_id)
    return feed


@router.post("", status_code=status.HTTP_201_CREATED)
def create_output_feed(payload: CreateOutputFeedRequest, subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict:
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=subaccount_id)
    return output_feed_service.create_output_feed(subaccount_id=subaccount_id, name=payload.name, feed_source_id=payload.feed_source_id)


@router.put("/{output_feed_id}")
def update_output_feed(output_feed_id: str, payload: UpdateOutputFeedRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing["subaccount_id"]))
    return output_feed_service.update_output_feed(output_feed_id, {k: v for k, v in payload.model_dump().items() if v is not None})


@router.delete("/{output_feed_id}")
def delete_output_feed(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing["subaccount_id"]))
    output_feed_service.delete_output_feed(output_feed_id)
    return {"status": "ok", "id": output_feed_id}


@router.post("/{output_feed_id}/render", status_code=status.HTTP_202_ACCEPTED)
def start_render(
    output_feed_id: str,
    payload: StartRenderRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:write", subaccount_id=int(existing["subaccount_id"]))

    job = output_feed_service.start_render_job(
        output_feed_id=output_feed_id,
        template_id=payload.template_id,
        total_products=len(payload.products),
    )

    from app.services.enriched_catalog.render_job_service import render_job_service
    background_tasks.add_task(render_job_service.run_render_background, output_feed_id, payload.products)

    return job


@router.get("/{output_feed_id}/render-status")
def get_render_status(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(existing["subaccount_id"]))
    job = output_feed_service.get_render_status(output_feed_id)
    if job is None:
        return {"status": "no_jobs", "message": "No render jobs found for this output feed"}
    return job


@router.get("/{output_feed_id}/url")
def get_enriched_feed_url(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="campaigns:read", subaccount_id=int(existing["subaccount_id"]))
    url = output_feed_service.get_enriched_feed_url(output_feed_id)
    if url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed is not published yet or URL is not available")
    return {"url": url, "output_feed_id": output_feed_id}
