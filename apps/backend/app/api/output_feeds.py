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
    feed_format: str = "xml"
    field_mapping_id: str | None = None


class UpdateOutputFeedRequest(BaseModel):
    name: str | None = None
    feed_source_id: str | None = None
    feed_format: str | None = None
    field_mapping_id: str | None = None


class StartRenderRequest(BaseModel):
    template_id: str
    products: list[dict] = Field(default_factory=list)


class ScheduleRefreshRequest(BaseModel):
    interval_hours: int = Field(ge=1, le=168)


@router.get("")
def list_output_feeds(subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict[str, list[dict]]:
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=subaccount_id)
    return {"items": output_feed_service.list_output_feeds(subaccount_id)}


@router.get("/{output_feed_id}")
def get_output_feed(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        feed = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(feed["subaccount_id"]))
    feed["treatments"] = treatment_repository.get_by_output_feed(output_feed_id)
    return feed


@router.post("", status_code=status.HTTP_201_CREATED)
def create_output_feed(payload: CreateOutputFeedRequest, subaccount_id: int = Query(...), user: AuthUser = Depends(get_current_user)) -> dict:
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=subaccount_id)
    return output_feed_service.create_output_feed(
        subaccount_id=subaccount_id,
        name=payload.name,
        feed_source_id=payload.feed_source_id,
        feed_format=payload.feed_format,
        field_mapping_id=payload.field_mapping_id,
    )


@router.put("/{output_feed_id}")
def update_output_feed(output_feed_id: str, payload: UpdateOutputFeedRequest, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))
    return output_feed_service.update_output_feed(output_feed_id, {k: v for k, v in payload.model_dump().items() if v is not None})


@router.delete("/{output_feed_id}")
def delete_output_feed(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))
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
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))

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
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(existing["subaccount_id"]))
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
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(existing["subaccount_id"]))
    url = output_feed_service.get_enriched_feed_url(output_feed_id)
    if url is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed is not published yet or URL is not available")
    return {"url": url, "output_feed_id": output_feed_id}


# ---------------------------------------------------------------------------
# New endpoints for feed generation workflow
# ---------------------------------------------------------------------------

@router.post("/{output_feed_id}/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_feed(
    output_feed_id: str,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Trigger feed generation: fetch products, apply mapping, format, upload to S3."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))

    def _run_generation():
        try:
            output_feed_service.generate_feed(output_feed_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Feed generation failed for %s", output_feed_id)

    background_tasks.add_task(_run_generation)
    return {"status": "accepted", "output_feed_id": output_feed_id, "message": "Feed generation started"}


@router.get("/{output_feed_id}/public-url")
def get_public_url(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    """Return the full public URL for crawler access."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(existing["subaccount_id"]))
    url = output_feed_service.get_public_url(output_feed_id)
    return {"public_url": url, "output_feed_id": output_feed_id}


@router.post("/{output_feed_id}/regenerate-token")
def regenerate_token(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    """Generate a new public token, invalidating the previous public URL."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))
    new_token = output_feed_service.regenerate_token(output_feed_id)
    new_url = output_feed_service.get_public_url(output_feed_id)
    return {"token": new_token, "public_url": new_url, "output_feed_id": output_feed_id}


@router.put("/{output_feed_id}/schedule")
def set_refresh_schedule(
    output_feed_id: str,
    payload: ScheduleRefreshRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Set the automatic refresh interval for this feed."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))
    updated = output_feed_service.schedule_refresh(output_feed_id, payload.interval_hours)
    return {"output_feed_id": output_feed_id, "refresh_interval_hours": updated.get("refresh_interval_hours")}


@router.get("/{output_feed_id}/stats")
def get_feed_stats(output_feed_id: str, user: AuthUser = Depends(get_current_user)) -> dict:
    """Return generation statistics for this feed."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:list", subaccount_id=int(existing["subaccount_id"]))
    return output_feed_service.get_feed_stats(output_feed_id)
