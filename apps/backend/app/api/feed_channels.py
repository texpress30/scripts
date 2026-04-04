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


@router.get("/channels/{channel_id}/products")
def get_channel_products(
    channel_id: str,
    page: int = 1,
    per_page: int = 10,
    search: str | None = None,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return paginated transformed products for a channel."""
    _enforce_feature_flag()
    try:
        channel = _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    from app.services.feed_management.master_fields.repository import (
        master_field_mapping_repository,
    )
    from app.services.feed_management.products_repository import (
        feed_products_repository,
    )

    # Load mappings + overrides
    master_mappings = master_field_mapping_repository.get_by_source(
        channel.feed_source_id,
    )
    overrides = _repo.get_overrides(channel_id)
    override_map = {o.target_field: o for o in overrides}

    # Build columns list from master mappings
    columns = [
        {"key": m.target_field, "label": m.target_field.replace("_", " ").title(), "type": "string"}
        for m in master_mappings
    ]
    # Mark image/url/price types
    for col in columns:
        key = col["key"]
        if "image" in key:
            col["type"] = "image"
        elif key in ("link", "url"):
            col["type"] = "url"
        elif key == "price" or key == "sale_price":
            col["type"] = "price"

    # Count + fetch products
    total = feed_products_repository.count_products(
        channel.feed_source_id, search=search,
    )
    safe_page = max(1, page)
    safe_per_page = min(max(1, per_page), 100)
    skip = (safe_page - 1) * safe_per_page

    raw_products = feed_products_repository.list_products(
        channel.feed_source_id, skip=skip, limit=safe_per_page, search=search,
    )

    # Transform
    from app.services.feed_management.connectors.base import flatten_images, strip_html

    transformed: list[dict[str, Any]] = []
    for product in raw_products:
        data = product.get("data", {})
        if not isinstance(data, dict):
            continue
        # Safety nets for stale data: strip HTML + flatten images
        for _dk in ("description", "short_description"):
            if _dk in data and isinstance(data[_dk], str) and "<" in data[_dk]:
                data[_dk] = strip_html(data[_dk])
            raw = data.get("raw_data")
            if isinstance(raw, dict) and _dk in raw and isinstance(raw[_dk], str) and "<" in raw[_dk]:
                raw[_dk] = strip_html(raw[_dk])
        raw = data.get("raw_data")
        if isinstance(raw, dict) and "images" in raw and "image_0_url" not in raw:
            flatten_images(raw)
        row = feed_generator._transform_product(data, master_mappings, override_map)
        transformed.append(row)

    return {
        "channel_id": channel_id,
        "products": transformed,
        "columns": columns,
        "total": total,
        "page": safe_page,
        "per_page": safe_per_page,
    }


# ---------------------------------------------------------------------------
# Channel schema fields (with inheritance)
# ---------------------------------------------------------------------------

@router.get("/channels/{channel_id}/schema-fields")
def get_channel_schema_fields(
    channel_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return channel-specific schema fields with inherited master mappings."""
    _enforce_feature_flag()
    try:
        channel = _repo.get_by_id(channel_id)
    except ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    from app.services.feed_management.repository import FeedSourceRepository
    from app.services.feed_management.schema_registry.repository import (
        schema_registry_repository,
    )

    source_repo = FeedSourceRepository()
    source = source_repo.get_by_id(channel.feed_source_id)
    catalog_type = source.catalog_type if hasattr(source, "catalog_type") else "product"

    fields = schema_registry_repository.get_channel_fields_by_channel_id(
        channel_id=channel_id,
        source_id=channel.feed_source_id,
        channel_type=channel.channel_type.value,
        catalog_type=catalog_type,
    )

    total = len(fields)
    required_count = sum(1 for f in fields if f["is_required"])
    optional_count = total - required_count
    mapped_count = sum(1 for f in fields if f["mapping"] is not None)

    return {
        "channel_id": channel_id,
        "channel_type": channel.channel_type.value,
        "channel_name": channel.name,
        "catalog_type": catalog_type,
        "source_id": channel.feed_source_id,
        "fields": fields,
        "total": total,
        "required_count": required_count,
        "optional_count": optional_count,
        "mapped_count": mapped_count,
    }


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
