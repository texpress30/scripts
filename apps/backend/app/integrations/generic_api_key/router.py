"""Parametrised CRUD router for the generic-API-key e-commerce platforms.

A single :class:`APIRouter` factory that ``main.py`` instantiates six
times — once per platform. Each instance hangs off
``/integrations/{platform}/sources`` and exposes the same five CRUD
endpoints + a test-connection probe:

* ``POST   /sources``                — create a new source
* ``GET    /sources``                — list sources for a subaccount
* ``GET    /sources/{source_id}``    — read one source
* ``PUT    /sources/{source_id}``    — update cosmetic fields
* ``DELETE /sources/{source_id}``    — wipe row + credentials
* ``POST   /sources/{source_id}/test-connection`` — reachability probe

Mirrors the layout of ``app/api/integrations/magento.py`` so the
existing tests + auth gates apply uniformly. The only difference is
that this router is platform-agnostic — the per-request platform key
comes from the closure passed to :func:`build_router`, not from a path
parameter, so each mount stays a clean URL.
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
from app.integrations.generic_api_key import config as gak_config
from app.integrations.generic_api_key import service as gak_service
from app.integrations.generic_api_key.config import PlatformDefinition
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


_source_repo = FeedSourceRepository()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class GenericApiKeySourceCreate(BaseModel):
    """Wizard payload for creating a new generic-API-key source.

    ``api_secret`` is optional in the schema even for platforms that
    require it — the router enforces presence inside
    :func:`gak_service.store_credentials` so we surface a 400 with the
    platform-specific label (e.g. "Integration Secret Key is required"
    for Shopware) instead of a generic Pydantic ValidationError.
    """

    source_name: str = Field(min_length=1, max_length=255)
    store_url: HttpUrl
    api_key: str = Field(min_length=1, max_length=512)
    api_secret: SecretStr | None = None
    catalog_type: str = Field(default="product", min_length=1, max_length=50)
    catalog_variant: str = Field(default="physical_products", min_length=1, max_length=50)


class GenericApiKeySourceUpdate(BaseModel):
    """Partial update for an existing generic-API-key source.

    Every field is optional. If any credential field is supplied, the
    update handler re-encrypts the stored credential blob by merging
    with the existing row — sending only ``api_key`` does NOT wipe the
    secret.
    """

    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    store_url: HttpUrl | None = None
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    api_secret: SecretStr | None = None
    catalog_type: str | None = Field(default=None, min_length=1, max_length=50)
    catalog_variant: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class GenericApiKeySourceResponse(BaseModel):
    source_id: str
    subaccount_id: int
    source_name: str
    platform: str
    store_url: str
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    has_credentials: bool = False
    api_key_masked: str | None = None
    api_secret_masked: str | None = None
    connection_status: str = "pending"
    last_connection_check: str | None = None
    last_error: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class GenericApiKeyTestConnectionResponse(BaseModel):
    success: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _isoformat_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def _source_to_response(
    *,
    platform: PlatformDefinition,
    source: FeedSourceResponse,
    masked_credentials: dict[str, Any] | None = None,
) -> GenericApiKeySourceResponse:
    """Project a generic ``FeedSourceResponse`` row onto the platform shape.

    ``masked_credentials`` is optional — when omitted the response is
    populated by re-fetching the credential bag through the service.
    Callers that just stored credentials inline pass the masked dict
    explicitly so the UI sees the masked preview immediately after
    create / update without an extra round-trip.
    """
    if masked_credentials is None:
        creds = gak_service.get_credentials(
            platform=platform.key, source_id=source.id
        )
        masked_credentials = gak_service.mask_credentials(platform.key, creds)

    config = source.config or {}
    store_url = str(config.get("store_url") or "")

    return GenericApiKeySourceResponse(
        source_id=source.id,
        subaccount_id=source.subaccount_id,
        source_name=source.name,
        platform=platform.key,
        store_url=store_url,
        catalog_type=source.catalog_type,
        catalog_variant=source.catalog_variant,
        has_credentials=bool(masked_credentials.get("has_credentials")),
        api_key_masked=masked_credentials.get("api_key_masked"),
        api_secret_masked=masked_credentials.get("api_secret_masked"),
        connection_status=source.connection_status,
        last_connection_check=_isoformat_or_none(source.last_connection_check),
        last_error=source.last_error,
        is_active=source.is_active,
        created_at=_isoformat_or_none(source.created_at),
        updated_at=_isoformat_or_none(source.updated_at),
    )


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


def _require_source_for_platform(
    *,
    platform: PlatformDefinition,
    source_id: str,
    subaccount_id: int,
) -> FeedSourceResponse:
    """Load a source row that MUST belong to ``subaccount_id`` + ``platform``.

    Returns 404 — never 403 — for cross-tenant lookups so the API does
    not leak the existence of sources owned by other clients. Mirrors
    ``_require_magento_source`` from the Magento router.
    """
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{platform.display_name} source not found",
        ) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{platform.display_name} source not found",
        )
    if source.source_type != platform.feed_source_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{platform.display_name} source not found",
        )
    return source


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_router(platform_key: str) -> APIRouter:
    """Build a CRUD router for one generic-API-key platform.

    Each platform gets its own router instance so the URL prefix is
    static and the OpenAPI tags don't collide. The platform definition
    is captured in the closure once at construction time.
    """
    platform = gak_config.get_platform(platform_key)

    router = APIRouter(
        prefix=f"/integrations/{platform.key}",
        tags=[platform.key, "integrations"],
    )

    # ---- create -----------------------------------------------------------

    @router.post(
        "/sources",
        response_model=GenericApiKeySourceResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_source(
        payload: GenericApiKeySourceCreate,
        subaccount_id: int = Query(
            ..., description=f"Subaccount that owns this {platform.display_name} source"
        ),
        user: AuthUser = Depends(get_current_user),
    ) -> GenericApiKeySourceResponse:
        _enforce_feature_flag()
        enforce_subaccount_action(
            user=user, action="data:write", subaccount_id=subaccount_id
        )

        try:
            store_url = gak_config.validate_store_url(str(payload.store_url))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        try:
            source = _source_repo.create(
                FeedSourceCreate(
                    subaccount_id=subaccount_id,
                    source_type=platform.feed_source_type,
                    name=payload.source_name,
                    config=FeedSourceConfig(
                        store_url=store_url,
                    ),
                    catalog_type=payload.catalog_type,
                    catalog_variant=payload.catalog_variant,
                )
            )
        except FeedSourceAlreadyExistsError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

        api_secret_value = (
            payload.api_secret.get_secret_value()
            if payload.api_secret is not None
            else None
        )
        try:
            gak_service.store_credentials(
                platform=platform.key,
                source_id=source.id,
                api_key=payload.api_key,
                api_secret=api_secret_value,
            )
        except ValueError as exc:
            try:
                _source_repo.delete(source.id)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "%s_source_rollback_failed source_id=%s",
                    platform.key,
                    source.id,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "%s_credentials_store_failed source_id=%s",
                platform.key,
                source.id,
            )
            try:
                _source_repo.delete(source.id)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "%s_source_rollback_failed source_id=%s",
                    platform.key,
                    source.id,
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to persist {platform.display_name} credentials",
            ) from exc

        masked = gak_service.mask_credentials(
            platform.key,
            {
                "api_key": payload.api_key,
                "api_secret": api_secret_value or "",
            },
        )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action=f"{platform.key}.source.created",
            resource=f"feed_source:{source.id}",
            details={
                "subaccount_id": subaccount_id,
                "store_url": store_url,
            },
        )
        return _source_to_response(
            platform=platform, source=source, masked_credentials=masked
        )

    # ---- list -------------------------------------------------------------

    @router.get(
        "/sources",
        response_model=list[GenericApiKeySourceResponse],
    )
    def list_sources(
        subaccount_id: int = Query(...),
        user: AuthUser = Depends(get_current_user),
    ) -> list[GenericApiKeySourceResponse]:
        _enforce_feature_flag()
        enforce_subaccount_action(
            user=user, action="dashboard:view", subaccount_id=subaccount_id
        )
        sources = _source_repo.get_by_subaccount(subaccount_id)
        return [
            _source_to_response(platform=platform, source=src)
            for src in sources
            if src.source_type == platform.feed_source_type
        ]

    # ---- read -------------------------------------------------------------

    @router.get(
        "/sources/{source_id}",
        response_model=GenericApiKeySourceResponse,
    )
    def get_source(
        source_id: str,
        subaccount_id: int = Query(...),
        user: AuthUser = Depends(get_current_user),
    ) -> GenericApiKeySourceResponse:
        _enforce_feature_flag()
        enforce_subaccount_action(
            user=user, action="dashboard:view", subaccount_id=subaccount_id
        )
        source = _require_source_for_platform(
            platform=platform, source_id=source_id, subaccount_id=subaccount_id
        )
        return _source_to_response(platform=platform, source=source)

    # ---- update -----------------------------------------------------------

    @router.put(
        "/sources/{source_id}",
        response_model=GenericApiKeySourceResponse,
    )
    def update_source(
        source_id: str,
        payload: GenericApiKeySourceUpdate,
        subaccount_id: int = Query(...),
        user: AuthUser = Depends(get_current_user),
    ) -> GenericApiKeySourceResponse:
        _enforce_feature_flag()
        enforce_subaccount_action(
            user=user, action="data:write", subaccount_id=subaccount_id
        )
        source = _require_source_for_platform(
            platform=platform, source_id=source_id, subaccount_id=subaccount_id
        )

        store_url_update: str | None = None
        if payload.store_url is not None:
            try:
                store_url_update = gak_config.validate_store_url(str(payload.store_url))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc

        config_update: FeedSourceConfig | None = None
        if store_url_update is not None:
            existing_config = dict(source.config or {})
            existing_config["store_url"] = store_url_update
            config_update = FeedSourceConfig(**existing_config)

        update_payload = FeedSourceUpdate(
            name=payload.source_name,
            config=config_update,
            catalog_type=payload.catalog_type,
            catalog_variant=payload.catalog_variant,
            is_active=payload.is_active,
        )
        has_any_source_field_update = any(
            value is not None
            for value in (
                payload.source_name,
                store_url_update,
                payload.catalog_type,
                payload.catalog_variant,
                payload.is_active,
            )
        )
        updated_source = source
        if has_any_source_field_update:
            try:
                updated_source = _source_repo.update(source_id, update_payload)
            except FeedSourceNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{platform.display_name} source not found",
                ) from exc

        masked: dict[str, Any] | None = None
        has_credential_update = (
            payload.api_key is not None or payload.api_secret is not None
        )
        if has_credential_update:
            existing = gak_service.get_credentials(
                platform=platform.key, source_id=source_id
            ) or {}
            new_api_key = (
                payload.api_key.strip()
                if payload.api_key is not None
                else existing.get("api_key", "")
            )
            new_api_secret = (
                payload.api_secret.get_secret_value().strip()
                if payload.api_secret is not None
                else existing.get("api_secret", "")
            )
            try:
                gak_service.store_credentials(
                    platform=platform.key,
                    source_id=source_id,
                    api_key=new_api_key,
                    api_secret=new_api_secret or None,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
                ) from exc
            masked = gak_service.mask_credentials(
                platform.key,
                {"api_key": new_api_key, "api_secret": new_api_secret or ""},
            )

        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action=f"{platform.key}.source.updated",
            resource=f"feed_source:{source_id}",
            details={
                "subaccount_id": subaccount_id,
                "source_fields_changed": has_any_source_field_update,
                "credentials_rotated": has_credential_update,
            },
        )
        return _source_to_response(
            platform=platform, source=updated_source, masked_credentials=masked
        )

    # ---- delete -----------------------------------------------------------

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
        source = _require_source_for_platform(
            platform=platform, source_id=source_id, subaccount_id=subaccount_id
        )

        try:
            gak_service.delete_credentials(
                platform=platform.key, source_id=source_id
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "%s_credentials_delete_failed source_id=%s",
                platform.key,
                source_id,
                exc_info=True,
            )

        try:
            _source_repo.delete(source_id)
        except FeedSourceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{platform.display_name} source not found",
            ) from exc

        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action=f"{platform.key}.source.deleted",
            resource=f"feed_source:{source_id}",
            details={"subaccount_id": subaccount_id, "store_url": (source.config or {}).get("store_url")},
        )
        return {"status": "ok", "id": source_id}

    # ---- test connection (post-save) -------------------------------------

    @router.post(
        "/sources/{source_id}/test-connection",
        response_model=GenericApiKeyTestConnectionResponse,
    )
    def test_source_connection(
        source_id: str,
        subaccount_id: int = Query(...),
        user: AuthUser = Depends(get_current_user),
    ) -> GenericApiKeyTestConnectionResponse:
        _enforce_feature_flag()
        enforce_subaccount_action(
            user=user, action="data:write", subaccount_id=subaccount_id
        )
        source = _require_source_for_platform(
            platform=platform, source_id=source_id, subaccount_id=subaccount_id
        )
        store_url = str((source.config or {}).get("store_url") or "")
        result = gak_service.probe_store_url(store_url)
        try:
            _source_repo.record_connection_check(
                source_id,
                success=bool(result.get("success")),
                error=None if result.get("success") else result.get("message"),
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "%s_probe_persist_failed source_id=%s",
                platform.key,
                source_id,
                exc_info=True,
            )
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action=f"{platform.key}.source.test_connection",
            resource=f"feed_source:{source_id}",
            details={
                "subaccount_id": subaccount_id,
                "success": bool(result.get("success")),
            },
        )
        return GenericApiKeyTestConnectionResponse(**result)

    # ---- test connection (pre-save) --------------------------------------

    @router.post(
        "/test-connection",
        response_model=GenericApiKeyTestConnectionResponse,
    )
    def test_connection_pre_save(
        store_url: str = Query(..., min_length=1, description=f"{platform.display_name} store URL"),
        user: AuthUser = Depends(get_current_user),
    ) -> GenericApiKeyTestConnectionResponse:
        _enforce_feature_flag()
        enforce_action_scope(user=user, action="data:write", scope="agency")

        try:
            cleaned = gak_config.validate_store_url(store_url)
        except ValueError as exc:
            return GenericApiKeyTestConnectionResponse(
                success=False, message=str(exc)
            )

        result = gak_service.probe_store_url(cleaned)
        audit_log_service.log(
            actor_email=user.email,
            actor_role=user.role,
            action=f"{platform.key}.test_connection.before_save",
            resource=f"integration:{platform.key}",
            details={
                "success": bool(result.get("success")),
                "store_url": cleaned,
            },
        )
        return GenericApiKeyTestConnectionResponse(**result)

    return router
