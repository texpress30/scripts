"""Dedicated CRUD router for Lightspeed eCom feed sources.

Lightspeed connections need Shop ID, Shop Language, and Shop Region —
not API credentials.  All fields are non-sensitive metadata persisted in
the ``feed_sources.config`` JSONB column.  There is no encrypted
credential storage for this platform.

The endpoint layout mirrors the generic-API-key and Magento routers so
the frontend wizard can call them uniformly:

* ``POST   /sources``                — create a new source
* ``GET    /sources``                — list sources for a subaccount
* ``GET    /sources/{source_id}``    — read one source
* ``PUT    /sources/{source_id}``    — update
* ``DELETE /sources/{source_id}``    — delete
* ``POST   /sources/{source_id}/test-connection`` — reachability probe
* ``POST   /test-connection``        — pre-save URL probe
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from app.api.dependencies import (
    enforce_action_scope,
    enforce_subaccount_action,
    get_current_user,
)
from app.core.config import load_settings
from app.integrations.generic_api_key.service import probe_store_url
from app.integrations.lightspeed.config import (
    LIGHTSPEED_REGIONS,
    validate_shop_id,
    validate_shop_region,
    validate_store_url,
)
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceResponse,
    FeedSourceType,
    FeedSourceUpdate,
)
from app.services.feed_management.repository import FeedSourceRepository


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integrations/lightspeed",
    tags=["lightspeed", "integrations"],
)

_source_repo = FeedSourceRepository()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class LightspeedSourceCreateRequest(BaseModel):
    source_name: str = Field(min_length=1, max_length=255)
    store_url: HttpUrl
    shop_id: str = Field(min_length=1, max_length=100)
    shop_language: str = Field(default="", max_length=10)
    shop_region: str = Field(min_length=1, max_length=10)
    catalog_type: str = Field(default="product", min_length=1, max_length=50)
    catalog_variant: str = Field(default="physical_products", min_length=1, max_length=50)


class LightspeedSourceUpdateRequest(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    store_url: HttpUrl | None = None
    shop_id: str | None = Field(default=None, min_length=1, max_length=100)
    shop_language: str | None = Field(default=None, max_length=10)
    shop_region: str | None = Field(default=None, min_length=1, max_length=10)
    catalog_type: str | None = Field(default=None, min_length=1, max_length=50)
    catalog_variant: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class LightspeedSourceResponse(BaseModel):
    source_id: str
    subaccount_id: int
    source_name: str
    platform: str = "lightspeed"
    store_url: str
    shop_id: str = ""
    shop_language: str = ""
    shop_region: str = ""
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    connection_status: str = "pending"
    last_connection_check: str | None = None
    last_error: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class LightspeedTestConnectionResponse(BaseModel):
    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isoformat_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


def _require_lightspeed_source(
    source_id: str, subaccount_id: int
) -> FeedSourceResponse:
    """Load a source that MUST belong to ``subaccount_id`` and be Lightspeed.

    Returns 404 (not 403) for cross-tenant lookups so we never leak the
    existence of sources owned by other clients.
    """
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lightspeed source not found",
        ) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lightspeed source not found",
        )
    if source.source_type != FeedSourceType.lightspeed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lightspeed source not found",
        )
    return source


def _source_to_response(source: FeedSourceResponse) -> LightspeedSourceResponse:
    config = source.config or {}
    # Lightspeed fields live under the ``extra`` JSONB sub-dict, since
    # ``FeedSourceConfig`` only has typed top-level fields for
    # ``store_url`` etc. and everything else goes into ``extra``.
    extra = config.get("extra") or {}
    return LightspeedSourceResponse(
        source_id=source.id,
        subaccount_id=source.subaccount_id,
        source_name=source.name,
        store_url=str(config.get("store_url") or ""),
        shop_id=str(extra.get("shop_id") or ""),
        shop_language=str(extra.get("shop_language") or ""),
        shop_region=str(extra.get("shop_region") or ""),
        catalog_type=source.catalog_type,
        catalog_variant=source.catalog_variant,
        connection_status=source.connection_status,
        last_connection_check=_isoformat_or_none(source.last_connection_check),
        last_error=source.last_error,
        is_active=source.is_active,
        created_at=_isoformat_or_none(source.created_at),
        updated_at=_isoformat_or_none(source.updated_at),
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/sources",
    response_model=LightspeedSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    payload: LightspeedSourceCreateRequest,
    subaccount_id: int = Query(
        ..., description="Subaccount that owns this Lightspeed source"
    ),
    user: AuthUser = Depends(get_current_user),
) -> LightspeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )

    try:
        store_url = validate_store_url(str(payload.store_url))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        shop_id = validate_shop_id(payload.shop_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        shop_region = validate_shop_region(payload.shop_region)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    shop_language = (payload.shop_language or "").strip()

    try:
        source = _source_repo.create(
            FeedSourceCreate(
                subaccount_id=subaccount_id,
                source_type=FeedSourceType.lightspeed,
                name=payload.source_name,
                config=FeedSourceConfig(
                    store_url=store_url,
                    extra={
                        "shop_id": shop_id,
                        "shop_language": shop_language,
                        "shop_region": shop_region,
                    },
                ),
                catalog_type=payload.catalog_type,
                catalog_variant=payload.catalog_variant,
            )
        )
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="lightspeed.source.created",
        resource=f"feed_source:{source.id}",
        details={
            "subaccount_id": subaccount_id,
            "store_url": store_url,
            "shop_id": shop_id,
            "shop_region": shop_region,
        },
    )
    return _source_to_response(source)


@router.get(
    "/sources",
    response_model=list[LightspeedSourceResponse],
)
def list_sources(
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> list[LightspeedSourceResponse]:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    sources = _source_repo.get_by_subaccount(subaccount_id)
    return [
        _source_to_response(src)
        for src in sources
        if src.source_type == FeedSourceType.lightspeed
    ]


@router.get(
    "/sources/{source_id}",
    response_model=LightspeedSourceResponse,
)
def get_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> LightspeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    source = _require_lightspeed_source(source_id, subaccount_id)
    return _source_to_response(source)


@router.put(
    "/sources/{source_id}",
    response_model=LightspeedSourceResponse,
)
def update_source(
    source_id: str,
    payload: LightspeedSourceUpdateRequest,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> LightspeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )
    source = _require_lightspeed_source(source_id, subaccount_id)

    store_url_update: str | None = None
    if payload.store_url is not None:
        try:
            store_url_update = validate_store_url(str(payload.store_url))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    shop_region_update: str | None = None
    if payload.shop_region is not None:
        try:
            shop_region_update = validate_shop_region(payload.shop_region)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    shop_id_update: str | None = None
    if payload.shop_id is not None:
        try:
            shop_id_update = validate_shop_id(payload.shop_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    # Merge config: start from existing config, overlay supplied fields.
    existing_config = dict(source.config or {})
    existing_extra = dict(existing_config.get("extra") or {})

    if store_url_update is not None:
        existing_config["store_url"] = store_url_update
    if shop_id_update is not None:
        existing_extra["shop_id"] = shop_id_update
    if payload.shop_language is not None:
        existing_extra["shop_language"] = payload.shop_language.strip()
    if shop_region_update is not None:
        existing_extra["shop_region"] = shop_region_update

    existing_config["extra"] = existing_extra
    config_update = FeedSourceConfig(**existing_config)

    has_any_update = any(
        value is not None
        for value in (
            payload.source_name,
            store_url_update,
            shop_id_update,
            payload.shop_language,
            shop_region_update,
            payload.catalog_type,
            payload.catalog_variant,
            payload.is_active,
        )
    )

    updated_source = source
    if has_any_update:
        try:
            updated_source = _source_repo.update(
                source_id,
                FeedSourceUpdate(
                    name=payload.source_name,
                    config=config_update,
                    catalog_type=payload.catalog_type,
                    catalog_variant=payload.catalog_variant,
                    is_active=payload.is_active,
                ),
            )
        except FeedSourceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lightspeed source not found",
            ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="lightspeed.source.updated",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id},
    )
    return _source_to_response(updated_source)


@router.delete("/sources/{source_id}")
def delete_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )
    source = _require_lightspeed_source(source_id, subaccount_id)

    try:
        _source_repo.delete(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lightspeed source not found",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="lightspeed.source.deleted",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "store_url": (source.config or {}).get("store_url"),
        },
    )
    return {"status": "ok", "id": source_id}


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/test-connection",
    response_model=LightspeedTestConnectionResponse,
)
def test_source_connection(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> LightspeedTestConnectionResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )
    source = _require_lightspeed_source(source_id, subaccount_id)
    store_url = str((source.config or {}).get("store_url") or "")
    result = probe_store_url(store_url)
    try:
        _source_repo.record_connection_check(
            source_id,
            success=bool(result.get("success")),
            error=None if result.get("success") else result.get("message"),
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "lightspeed_probe_persist_failed source_id=%s",
            source_id,
            exc_info=True,
        )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="lightspeed.source.test_connection",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "success": bool(result.get("success")),
        },
    )
    return LightspeedTestConnectionResponse(**result)


@router.post(
    "/test-connection",
    response_model=LightspeedTestConnectionResponse,
)
def test_connection_pre_save(
    store_url: str = Query(
        ..., min_length=1, description="Lightspeed store URL"
    ),
    user: AuthUser = Depends(get_current_user),
) -> LightspeedTestConnectionResponse:
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="data:write", scope="agency")

    try:
        cleaned = validate_store_url(store_url)
    except ValueError as exc:
        return LightspeedTestConnectionResponse(
            success=False, message=str(exc)
        )

    result = probe_store_url(cleaned)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="lightspeed.test_connection.before_save",
        resource="integration:lightspeed",
        details={
            "success": bool(result.get("success")),
            "store_url": cleaned,
        },
    )
    return LightspeedTestConnectionResponse(**result)
