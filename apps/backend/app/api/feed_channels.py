from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user
from app.core.config import load_settings
from app.services.auth import AuthUser
from app.services.feed_management.channels.models import (
    ChannelFieldOverrideCreate,
    ChannelFieldOverrideResponse,
    FeedChannelCreate,
    FeedChannelResponse,
    FeedChannelUpdate,
)
from app.services.feed_management.channels.repository import (
    ChannelNotFoundError,
    feed_channel_repository,
)
from app.services.feed_management.channels.feed_generator import feed_generator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed-channels"])

_repo = feed_channel_repository


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ChannelListResponse(BaseModel):
    items: list[FeedChannelResponse]


class OverrideListResponse(BaseModel):
    items: list[ChannelFieldOverrideResponse]


class OverrideBulkRequest(BaseModel):
    overrides: list[ChannelFieldOverrideCreate]


# ---------------------------------------------------------------------------
# Channel CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/feed-sources/{source_id}/channels",
    response_model=ChannelListResponse,
)
def list_channels(
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ChannelListResponse:
    """List all channels for a feed source."""
    _enforce_feature_flag()
    items = _repo.list_by_source(source_id)
    return ChannelListResponse(items=items)


@router.post(
    "/feed-sources/{source_id}/channels",
    response_model=FeedChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    source_id: str,
    payload: FeedChannelCreate,
    user: AuthUser = Depends(get_current_user),
) -> FeedChannelResponse:
    """Create a new channel for a feed source."""
    _enforce_feature_flag()
    return _repo.create(source_id, payload)


@router.get("/channels/{channel_id}", response_model=FeedChannelResponse)
def get_channel(
    channel_id: str,
    user: AuthUser = Depends(get_current_user),
) -> FeedChannelResponse:
    """Get channel details."""
    _enforce_feature_flag()
    try:
        return _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.put("/channels/{channel_id}", response_model=FeedChannelResponse)
def update_channel(
    channel_id: str,
    payload: FeedChannelUpdate,
    user: AuthUser = Depends(get_current_user),
) -> FeedChannelResponse:
    """Update channel settings."""
    _enforce_feature_flag()
    try:
        return _repo.update(channel_id, payload)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.delete("/channels/{channel_id}")
def delete_channel(
    channel_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a channel."""
    _enforce_feature_flag()
    try:
        _repo.delete(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return {"status": "ok", "id": channel_id}


# ---------------------------------------------------------------------------
# Feed generation
# ---------------------------------------------------------------------------

@router.post(
    "/channels/{channel_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_feed(
    channel_id: str,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger feed generation in the background."""
    _enforce_feature_flag()
    try:
        _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    def _run() -> None:
        try:
            feed_generator.generate(channel_id)
        except Exception:
            logger.exception("Feed generation failed for channel %s", channel_id)

    background_tasks.add_task(_run)
    return {
        "status": "accepted",
        "channel_id": channel_id,
        "message": "Feed generation started",
    }


@router.get("/channels/{channel_id}/preview")
def preview_feed(
    channel_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Preview the first 5 transformed products (no S3 upload)."""
    _enforce_feature_flag()
    try:
        _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    results = feed_generator.preview(channel_id, limit=5)
    return {"channel_id": channel_id, "preview": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Channel overrides
# ---------------------------------------------------------------------------

@router.get(
    "/channels/{channel_id}/overrides",
    response_model=OverrideListResponse,
)
def list_overrides(
    channel_id: str,
    user: AuthUser = Depends(get_current_user),
) -> OverrideListResponse:
    """Get all field overrides for a channel."""
    _enforce_feature_flag()
    items = _repo.get_overrides(channel_id)
    return OverrideListResponse(items=items)


@router.post(
    "/channels/{channel_id}/overrides",
    response_model=OverrideListResponse,
)
def save_overrides(
    channel_id: str,
    payload: OverrideBulkRequest,
    user: AuthUser = Depends(get_current_user),
) -> OverrideListResponse:
    """Bulk save (upsert) field overrides for a channel."""
    _enforce_feature_flag()
    try:
        _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    items = _repo.save_overrides(
        channel_id,
        [o.model_dump() for o in payload.overrides],
    )
    return OverrideListResponse(items=items)
