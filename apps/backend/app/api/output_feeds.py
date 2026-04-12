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
    channel_id: str | None = None
    treatment_mode: str = "single"


class UpdateOutputFeedRequest(BaseModel):
    name: str | None = None
    feed_source_id: str | None = None
    feed_format: str | None = None
    field_mapping_id: str | None = None
    channel_id: str | None = None
    treatment_mode: str | None = None


class StartRenderRequest(BaseModel):
    template_id: str
    products: list[dict] = Field(default_factory=list)


class RenderPageRequest(BaseModel):
    """Lazy render dispatch for the preview grid.

    The grid emits the list of product_ids currently visible (plus one page
    of prefetch). We look up the full product documents in Mongo, resolve
    each product's matching template via treatments, and enqueue the render
    on the render_hi queue. Only the requested products get rendered, so a
    100k-product feed never costs more than the ~40 products the user is
    actually looking at.
    """

    product_ids: list[str] = Field(default_factory=list)
    priority: str = "hi"  # "hi" for editor/grid, "bulk" for Publish


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
        channel_id=payload.channel_id,
        treatment_mode=payload.treatment_mode,
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


@router.post("/{output_feed_id}/render/page", status_code=status.HTTP_202_ACCEPTED)
def render_visible_page(
    output_feed_id: str,
    payload: RenderPageRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Enqueue async renders for a bounded slice of products.

    Called by the preview grid whenever the visible page changes. We look up
    each product_id in Mongo, hand the rows to
    ``render_job_service.dispatch_render_job`` which checks the
    template_render_results cache and only enqueues tasks for stale entries.

    Returns a summary: how many tasks were dispatched vs cache-hit vs
    skipped because no treatment matched.
    """
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(
        user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"])
    )

    if not payload.product_ids:
        return {"dispatched": 0, "cache_hits": 0, "chunks": 0, "priority": payload.priority}

    # Resolve the product documents from Mongo. The feed_source_id is on the
    # output feed record; we look up each product_id individually so large
    # batches don't bloat the query.
    from app.services.feed_management.products_repository import feed_products_repository
    from app.services.enriched_catalog.render_job_service import render_job_service

    feed_source_id = existing.get("feed_source_id")
    if not feed_source_id:
        return {"dispatched": 0, "cache_hits": 0, "chunks": 0, "priority": payload.priority}

    products: list[dict] = []
    for product_id in payload.product_ids:
        doc = feed_products_repository.get_product(str(feed_source_id), str(product_id))
        if not doc:
            continue
        data = doc.get("data", doc) if isinstance(doc, dict) else {}
        if isinstance(data, dict):
            # Ensure the product id is always present in the dict so the
            # renderer can address the cache row later.
            data.setdefault("id", str(product_id))
            products.append(data)

    return render_job_service.dispatch_render_job(
        output_feed_id,
        products,
        priority=payload.priority,
    )


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


# ---------------------------------------------------------------------------
# Multi-format bulk generation
# ---------------------------------------------------------------------------

class MultiFormatRenderRequest(BaseModel):
    template_ids: list[str] = Field(min_length=1, max_length=20)
    products: list[dict] = Field(default_factory=list)
    webhook_url: str | None = None


@router.post("/{output_feed_id}/render-multi-format", status_code=status.HTTP_202_ACCEPTED)
def start_multi_format_render(
    output_feed_id: str,
    payload: MultiFormatRenderRequest,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Render products across multiple templates (format group) in one batch."""
    try:
        existing = output_feed_service.get_output_feed(output_feed_id)
    except OutputFeedNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    enforce_subaccount_action(user=user, action="creative:write", subaccount_id=int(existing["subaccount_id"]))

    job = output_feed_service.start_render_job(
        output_feed_id=output_feed_id,
        template_id=payload.template_ids[0],
        total_products=len(payload.products) * len(payload.template_ids),
    )

    def _run():
        from app.services.enriched_catalog.multi_format_renderer import multi_format_render_service
        try:
            multi_format_render_service.render_multi_format(
                output_feed_id=output_feed_id,
                template_ids=payload.template_ids,
                products=payload.products,
                webhook_url=payload.webhook_url,
            )
            output_feed_service.update_output_feed(output_feed_id, {"status": "published"})
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Multi-format render failed for feed %s", output_feed_id)
            try:
                output_feed_service.update_output_feed(output_feed_id, {"status": "failed"})
            except Exception:
                pass

    background_tasks.add_task(_run)
    return {
        "status": "accepted",
        "output_feed_id": output_feed_id,
        "template_count": len(payload.template_ids),
        "product_count": len(payload.products),
        "total_renders": len(payload.products) * len(payload.template_ids),
        "webhook_url": payload.webhook_url,
        "job": job,
    }
