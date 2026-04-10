"""Dedicated CRUD router for Shopware feed sources.

Shopware connections need three fields from the connector extension:
Store Key, Bridge Endpoint, and API Access Key.  Store Key and API
Access Key are credentials (encrypted in ``integration_secrets``).
Bridge Endpoint is a non-sensitive URL stored in ``feed_sources.config``
JSONB.

The endpoint layout mirrors the Lightspeed and generic-API-key routers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, SecretStr

from app.api.dependencies import (
    enforce_action_scope,
    enforce_subaccount_action,
    get_current_user,
)
from app.core.config import load_settings
from app.integrations.generic_api_key.service import probe_store_url
from app.integrations.shopware import service as sw_service
from app.integrations.shopware.config import (
    validate_bridge_endpoint,
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
    prefix="/integrations/shopware",
    tags=["shopware", "integrations"],
)

_source_repo = FeedSourceRepository()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ShopwareSourceCreateRequest(BaseModel):
    source_name: str = Field(min_length=1, max_length=255)
    store_url: HttpUrl
    store_key: str = Field(min_length=1, max_length=512)
    bridge_endpoint: str = Field(min_length=1, max_length=512)
    api_access_key: SecretStr
    catalog_type: str = Field(default="product", min_length=1, max_length=50)
    catalog_variant: str = Field(default="physical_products", min_length=1, max_length=50)


class ShopwareSourceUpdateRequest(BaseModel):
    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    store_url: HttpUrl | None = None
    store_key: str | None = Field(default=None, min_length=1, max_length=512)
    bridge_endpoint: str | None = Field(default=None, min_length=1, max_length=512)
    api_access_key: SecretStr | None = None
    catalog_type: str | None = Field(default=None, min_length=1, max_length=50)
    catalog_variant: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class ShopwareSourceResponse(BaseModel):
    source_id: str
    subaccount_id: int
    source_name: str
    platform: str = "shopware"
    store_url: str
    bridge_endpoint: str = ""
    has_credentials: bool = False
    store_key_masked: str | None = None
    api_access_key_masked: str | None = None
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    connection_status: str = "pending"
    last_connection_check: str | None = None
    last_error: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class ShopwareTestConnectionResponse(BaseModel):
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


def _require_shopware_source(
    source_id: str, subaccount_id: int
) -> FeedSourceResponse:
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopware source not found",
        ) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopware source not found",
        )
    if source.source_type != FeedSourceType.shopware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopware source not found",
        )
    return source


def _source_to_response(
    source: FeedSourceResponse,
    *,
    masked_credentials: dict[str, Any] | None = None,
) -> ShopwareSourceResponse:
    config = source.config or {}
    extra = config.get("extra") or {}

    if masked_credentials is None:
        creds = sw_service.get_credentials(source_id=source.id)
        masked_credentials = sw_service.mask_credentials(creds)

    return ShopwareSourceResponse(
        source_id=source.id,
        subaccount_id=source.subaccount_id,
        source_name=source.name,
        store_url=str(config.get("store_url") or ""),
        bridge_endpoint=str(extra.get("bridge_endpoint") or ""),
        has_credentials=bool(masked_credentials.get("has_credentials")),
        store_key_masked=masked_credentials.get("store_key_masked"),
        api_access_key_masked=masked_credentials.get("api_access_key_masked"),
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
    response_model=ShopwareSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    payload: ShopwareSourceCreateRequest,
    subaccount_id: int = Query(
        ..., description="Subaccount that owns this Shopware source"
    ),
    user: AuthUser = Depends(get_current_user),
) -> ShopwareSourceResponse:
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
        bridge_endpoint = validate_bridge_endpoint(payload.bridge_endpoint)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    api_access_key_value = payload.api_access_key.get_secret_value()

    try:
        source = _source_repo.create(
            FeedSourceCreate(
                subaccount_id=subaccount_id,
                source_type=FeedSourceType.shopware,
                name=payload.source_name,
                config=FeedSourceConfig(
                    store_url=store_url,
                    extra={"bridge_endpoint": bridge_endpoint},
                ),
                catalog_type=payload.catalog_type,
                catalog_variant=payload.catalog_variant,
            )
        )
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    try:
        sw_service.store_credentials(
            source_id=source.id,
            store_key=payload.store_key,
            api_access_key=api_access_key_value,
        )
    except ValueError as exc:
        try:
            _source_repo.delete(source.id)
        except Exception:  # noqa: BLE001
            logger.exception("shopware_source_rollback_failed source_id=%s", source.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    masked = sw_service.mask_credentials(
        {"store_key": payload.store_key, "api_access_key": api_access_key_value},
    )
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopware.source.created",
        resource=f"feed_source:{source.id}",
        details={"subaccount_id": subaccount_id, "store_url": store_url},
    )
    return _source_to_response(source, masked_credentials=masked)


@router.get(
    "/sources",
    response_model=list[ShopwareSourceResponse],
)
def list_sources(
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> list[ShopwareSourceResponse]:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    sources = _source_repo.get_by_subaccount(subaccount_id)
    return [
        _source_to_response(src)
        for src in sources
        if src.source_type == FeedSourceType.shopware
    ]


@router.get(
    "/sources/{source_id}",
    response_model=ShopwareSourceResponse,
)
def get_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> ShopwareSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="dashboard:view", subaccount_id=subaccount_id
    )
    source = _require_shopware_source(source_id, subaccount_id)
    return _source_to_response(source)


@router.put(
    "/sources/{source_id}",
    response_model=ShopwareSourceResponse,
)
def update_source(
    source_id: str,
    payload: ShopwareSourceUpdateRequest,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> ShopwareSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )
    source = _require_shopware_source(source_id, subaccount_id)

    store_url_update: str | None = None
    if payload.store_url is not None:
        try:
            store_url_update = validate_store_url(str(payload.store_url))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    bridge_endpoint_update: str | None = None
    if payload.bridge_endpoint is not None:
        try:
            bridge_endpoint_update = validate_bridge_endpoint(payload.bridge_endpoint)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    # Merge config
    existing_config = dict(source.config or {})
    existing_extra = dict(existing_config.get("extra") or {})
    if store_url_update is not None:
        existing_config["store_url"] = store_url_update
    if bridge_endpoint_update is not None:
        existing_extra["bridge_endpoint"] = bridge_endpoint_update
    existing_config["extra"] = existing_extra
    config_update = FeedSourceConfig(**existing_config)

    has_any_source_update = any(
        v is not None
        for v in (payload.source_name, store_url_update, bridge_endpoint_update,
                  payload.catalog_type, payload.catalog_variant, payload.is_active)
    )
    updated_source = source
    if has_any_source_update:
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
                detail="Shopware source not found",
            ) from exc

    # Credential update (merge with existing)
    masked: dict[str, Any] | None = None
    has_credential_update = payload.store_key is not None or payload.api_access_key is not None
    if has_credential_update:
        existing_creds = sw_service.get_credentials(source_id=source_id) or {}
        new_store_key = (
            payload.store_key.strip() if payload.store_key is not None
            else existing_creds.get("store_key", "")
        )
        new_api_access_key = (
            payload.api_access_key.get_secret_value().strip() if payload.api_access_key is not None
            else existing_creds.get("api_access_key", "")
        )
        try:
            sw_service.store_credentials(
                source_id=source_id,
                store_key=new_store_key,
                api_access_key=new_api_access_key or "",
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        masked = sw_service.mask_credentials(
            {"store_key": new_store_key, "api_access_key": new_api_access_key or ""},
        )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopware.source.updated",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id},
    )
    return _source_to_response(updated_source, masked_credentials=masked)


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
    source = _require_shopware_source(source_id, subaccount_id)

    try:
        sw_service.delete_credentials(source_id=source_id)
    except Exception:  # noqa: BLE001
        logger.warning("shopware_credentials_delete_failed source_id=%s", source_id, exc_info=True)

    try:
        _source_repo.delete(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shopware source not found",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopware.source.deleted",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id},
    )
    return {"status": "ok", "id": source_id}


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


@router.post(
    "/sources/{source_id}/test-connection",
    response_model=ShopwareTestConnectionResponse,
)
def test_source_connection(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> ShopwareTestConnectionResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(
        user=user, action="data:write", subaccount_id=subaccount_id
    )
    source = _require_shopware_source(source_id, subaccount_id)
    store_url = str((source.config or {}).get("store_url") or "")
    result = probe_store_url(store_url)
    try:
        _source_repo.record_connection_check(
            source_id,
            success=bool(result.get("success")),
            error=None if result.get("success") else result.get("message"),
        )
    except Exception:  # noqa: BLE001
        logger.warning("shopware_probe_persist_failed source_id=%s", source_id, exc_info=True)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopware.source.test_connection",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "success": bool(result.get("success"))},
    )
    return ShopwareTestConnectionResponse(**result)


@router.post(
    "/test-connection",
    response_model=ShopwareTestConnectionResponse,
)
def test_connection_pre_save(
    store_url: str = Query(..., min_length=1, description="Shopware store URL"),
    user: AuthUser = Depends(get_current_user),
) -> ShopwareTestConnectionResponse:
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="data:write", scope="agency")

    try:
        cleaned = validate_store_url(store_url)
    except ValueError as exc:
        return ShopwareTestConnectionResponse(success=False, message=str(exc))

    result = probe_store_url(cleaned)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="shopware.test_connection.before_save",
        resource="integration:shopware",
        details={"success": bool(result.get("success")), "store_url": cleaned},
    )
    return ShopwareTestConnectionResponse(**result)
