"""FastAPI router for the Magento 2 Feed Integration.

Exposes:

* Full CRUD for Magento sources at ``/integrations/magento/sources`` — a
  thin layer over :class:`FeedSourceRepository` that stores non-sensitive
  routing (``magento_base_url`` + ``magento_store_code``) on the
  ``feed_sources`` row and the four OAuth 1.0a credentials encrypted-at-rest
  in ``integration_secrets`` via ``app.integrations.magento.service``.
* Per-source live connection probe at
  ``POST /integrations/magento/sources/{source_id}/test-connection`` that
  uses the stored credentials to hit Magento's ``GET /store/storeConfigs``.
* Pre-save connection probe at ``POST /integrations/magento/test-connection``
  that accepts credentials straight from the request body (wizard Step 3)
  and never persists anything.

Auth mirrors the Shopify / feed_sources routers: ``get_current_user`` +
``enforce_subaccount_action`` for subaccount-scoped endpoints, and
``enforce_action_scope(scope="agency")`` for the pre-save probe which
has no source to pin ownership to yet.

Ownership check: ``_require_magento_source`` returns 404 (not 403) when a
source belongs to another subaccount so we never disclose its existence.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, SecretStr

from app.api.dependencies import (
    enforce_action_scope,
    enforce_subaccount_action,
    get_current_user,
)
from app.core.config import load_settings
from app.integrations.magento import client as magento_client_module
from app.integrations.magento import config as magento_config
from app.integrations.magento import service as magento_service
from app.integrations.magento.client import MagentoClient
from app.integrations.magento.exceptions import (
    MagentoAPIError,
    MagentoAuthError,
    MagentoConnectionError,
    MagentoNotFoundError,
    MagentoRateLimitError,
)
from app.integrations.magento.schemas import (
    MagentoSourceCreate,
    MagentoSourceResponse,
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

router = APIRouter(prefix="/integrations/magento", tags=["magento", "integrations"])

# Interactive UI probes should fail fast — the operator is waiting.
TEST_CONNECTION_TIMEOUT_SECONDS: float = 12.0

_source_repo = FeedSourceRepository()


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed management is not enabled",
        )


# ---------------------------------------------------------------------------
# Request/response schemas that are router-local (Magento-specific wrappers)
# ---------------------------------------------------------------------------


class MagentoSourceUpdateRequest(BaseModel):
    """Partial update for a Magento source. Every field is optional.

    If any credential field is supplied, ``update_magento_source`` re-encrypts
    the stored blob by merging with the existing row; sending a single secret
    does not wipe the others.
    """

    source_name: str | None = Field(default=None, min_length=1, max_length=255)
    magento_base_url: HttpUrl | None = None
    magento_store_code: str | None = Field(default=None, min_length=1, max_length=100)
    consumer_key: str | None = None
    consumer_secret: SecretStr | None = None
    access_token: str | None = None
    access_token_secret: SecretStr | None = None
    catalog_type: str | None = None
    catalog_variant: str | None = None
    is_active: bool | None = None


class MagentoTestConnectionRequest(BaseModel):
    """Payload for the pre-save probe — credentials travel in the body and
    are never persisted."""

    magento_base_url: HttpUrl
    magento_store_code: str = Field(default="default", min_length=1, max_length=100)
    consumer_key: str = Field(min_length=1)
    consumer_secret: SecretStr
    access_token: str = Field(min_length=1)
    access_token_secret: SecretStr


class MagentoTestConnectionResponse(BaseModel):
    """Normalised probe result returned by both test-connection endpoints."""

    success: bool
    store_name: str | None = None
    base_currency: str | None = None
    magento_version: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Response mapping + ownership helpers
# ---------------------------------------------------------------------------


def _isoformat_or_none(value) -> str | None:
    return value.isoformat() if value is not None else None


def _source_to_response(
    source: FeedSourceResponse,
    *,
    credentials: dict[str, str] | None = None,
) -> MagentoSourceResponse:
    """Project a ``FeedSourceResponse`` row onto the Magento-specific response.

    ``credentials`` is optional — when omitted the response still reports
    whether credentials exist (via ``has_credentials``) without decrypting
    anything extra. Callers that already have the plaintext dict in hand
    (e.g. the POST handler) pass it explicitly so the UI sees masked last-4
    previews immediately after create.
    """
    return MagentoSourceResponse.from_source_and_credentials(
        source_id=source.id,
        subaccount_id=source.subaccount_id,
        source_name=source.name,
        magento_base_url=source.magento_base_url or "",
        magento_store_code=source.magento_store_code or magento_config.DEFAULT_STORE_CODE,
        catalog_type=source.catalog_type,
        catalog_variant=source.catalog_variant,
        connection_status=source.connection_status,
        credentials=credentials,
        last_connection_check=_isoformat_or_none(source.last_connection_check),
        last_error=source.last_error,
        created_at=_isoformat_or_none(source.created_at),
        updated_at=_isoformat_or_none(source.updated_at),
    )


def _require_magento_source(source_id: str, subaccount_id: int) -> FeedSourceResponse:
    """Load a source row that MUST belong to ``subaccount_id`` and be Magento.

    Returns 404 — never 403 — for cross-tenant lookups so the API does not
    leak the existence of sources owned by other clients.
    """
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Magento source not found"
        ) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Magento source not found"
        )
    if source.source_type != FeedSourceType.magento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Magento source not found"
        )
    return source


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/sources",
    response_model=MagentoSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_magento_source(
    payload: MagentoSourceCreate,
    subaccount_id: int = Query(..., description="Subaccount that owns this Magento source"),
    user: AuthUser = Depends(get_current_user),
) -> MagentoSourceResponse:
    """Create a new Magento source + persist its four OAuth 1.0a credentials.

    On success the ``feed_sources`` row starts in ``connection_status='pending'``
    — the caller should immediately follow up with ``test-connection`` to flip
    it to ``connected``. A credential-storage failure rolls back the source
    row so we never end up with an un-authable ``feed_sources`` entry.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    try:
        base_url = magento_config.validate_magento_base_url(str(payload.magento_base_url))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        store_code = magento_config.validate_magento_store_code(payload.magento_store_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    try:
        source = _source_repo.create(
            FeedSourceCreate(
                subaccount_id=subaccount_id,
                source_type=FeedSourceType.magento,
                name=payload.source_name,
                config=FeedSourceConfig(
                    magento_base_url=base_url,
                    magento_store_code=store_code,
                ),
                catalog_type=payload.catalog_type,
                catalog_variant=payload.catalog_variant,
                magento_base_url=base_url,
                magento_store_code=store_code,
            )
        )
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    plaintext_credentials = payload.dump_credentials()
    try:
        magento_service.store_magento_credentials(
            source_id=source.id,
            **plaintext_credentials,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("magento_credentials_store_failed source_id=%s", source.id)
        try:
            _source_repo.delete(source.id)
        except Exception:  # noqa: BLE001
            logger.exception("magento_source_rollback_failed source_id=%s", source.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist Magento credentials",
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="magento.source.created",
        resource=f"feed_source:{source.id}",
        details={
            "subaccount_id": subaccount_id,
            "magento_base_url": base_url,
            "magento_store_code": store_code,
        },
    )
    return _source_to_response(source, credentials=plaintext_credentials)


@router.get("/sources", response_model=list[MagentoSourceResponse])
def list_magento_sources(
    subaccount_id: int = Query(..., description="Subaccount to scope the listing by"),
    user: AuthUser = Depends(get_current_user),
) -> list[MagentoSourceResponse]:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    sources = _source_repo.get_by_subaccount(subaccount_id)
    return [
        _source_to_response(src)
        for src in sources
        if src.source_type == FeedSourceType.magento
    ]


@router.get("/sources/{source_id}", response_model=MagentoSourceResponse)
def get_magento_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> MagentoSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    source = _require_magento_source(source_id, subaccount_id)
    return _source_to_response(source)


@router.put("/sources/{source_id}", response_model=MagentoSourceResponse)
def update_magento_source(
    source_id: str,
    payload: MagentoSourceUpdateRequest,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> MagentoSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    source = _require_magento_source(source_id, subaccount_id)

    # Pre-validate the Magento-specific fields before touching the repo so we
    # surface 400 directly instead of surfacing a DB error.
    base_url_update: str | None = None
    if payload.magento_base_url is not None:
        try:
            base_url_update = magento_config.validate_magento_base_url(str(payload.magento_base_url))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    store_code_update: str | None = None
    if payload.magento_store_code is not None:
        try:
            store_code_update = magento_config.validate_magento_store_code(
                payload.magento_store_code
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

    update_payload = FeedSourceUpdate(
        name=payload.source_name,
        catalog_type=payload.catalog_type,
        catalog_variant=payload.catalog_variant,
        is_active=payload.is_active,
        magento_base_url=base_url_update,
        magento_store_code=store_code_update,
    )

    has_any_source_field_update = any(
        value is not None
        for value in (
            payload.source_name,
            payload.catalog_type,
            payload.catalog_variant,
            payload.is_active,
            base_url_update,
            store_code_update,
        )
    )

    updated_source = source
    if has_any_source_field_update:
        try:
            updated_source = _source_repo.update(source_id, update_payload)
        except FeedSourceNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Magento source not found"
            ) from exc

    # Merge any supplied credential fields with the existing encrypted blob.
    has_any_credential_update = any(
        value is not None
        for value in (
            payload.consumer_key,
            payload.consumer_secret,
            payload.access_token,
            payload.access_token_secret,
        )
    )
    latest_credentials: dict[str, str] | None = None
    if has_any_credential_update:
        existing = magento_service.get_magento_credentials(source_id) or {}
        merged = {
            "consumer_key": payload.consumer_key
            if payload.consumer_key is not None
            else existing.get("consumer_key", ""),
            "consumer_secret": payload.consumer_secret.get_secret_value()
            if payload.consumer_secret is not None
            else existing.get("consumer_secret", ""),
            "access_token": payload.access_token
            if payload.access_token is not None
            else existing.get("access_token", ""),
            "access_token_secret": payload.access_token_secret.get_secret_value()
            if payload.access_token_secret is not None
            else existing.get("access_token_secret", ""),
        }
        if not all(merged.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update Magento credentials: missing existing values to merge with",
            )
        magento_service.store_magento_credentials(source_id=source_id, **merged)
        latest_credentials = merged

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="magento.source.updated",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "source_fields_changed": has_any_source_field_update,
            "credentials_rotated": has_any_credential_update,
        },
    )
    return _source_to_response(updated_source, credentials=latest_credentials)


@router.delete("/sources/{source_id}")
def delete_magento_source(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> dict:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    source = _require_magento_source(source_id, subaccount_id)

    # Delete credentials first so we never end up with orphaned secrets
    # pointing at a deleted source row. Best-effort on failure — the source
    # row delete still proceeds, and a future background sweep can clean up.
    try:
        magento_service.delete_magento_credentials(source_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "magento_credentials_delete_failed source_id=%s", source_id, exc_info=True
        )

    try:
        _source_repo.delete(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Magento source not found"
        ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="magento.source.deleted",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "magento_base_url": source.magento_base_url,
            "magento_store_code": source.magento_store_code,
        },
    )
    return {"status": "ok", "id": source_id}


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------


async def _probe_store_configs(client: MagentoClient) -> MagentoTestConnectionResponse:
    """Hit Magento's ``/store/storeConfigs`` and map the result to our normalised
    probe response. Every Magento exception is caught and folded into a
    ``success=False`` payload so callers get a predictable shape."""
    try:
        data = await client.get("store/storeConfigs")
    except MagentoAuthError as exc:
        return MagentoTestConnectionResponse(
            success=False, error=f"Invalid credentials: {exc.message}"
        )
    except MagentoNotFoundError as exc:
        return MagentoTestConnectionResponse(
            success=False, error=f"Endpoint not found: {exc.message}"
        )
    except MagentoRateLimitError as exc:
        return MagentoTestConnectionResponse(
            success=False, error=f"Rate limit hit: {exc.message}"
        )
    except MagentoConnectionError as exc:
        return MagentoTestConnectionResponse(
            success=False, error=f"Connection failed: {exc.message}"
        )
    except MagentoAPIError as exc:
        return MagentoTestConnectionResponse(
            success=False, error=f"Magento API error: {exc.message}"
        )

    if isinstance(data, list) and data:
        first = data[0] if isinstance(data[0], dict) else {}
        return MagentoTestConnectionResponse(
            success=True,
            store_name=str(first.get("name") or first.get("code") or "") or None,
            base_currency=str(
                first.get("base_currency_code")
                or first.get("default_display_currency_code")
                or ""
            )
            or None,
            magento_version=None,
        )
    return MagentoTestConnectionResponse(
        success=False,
        error="Magento returned an unexpected /store/storeConfigs payload",
    )


@router.post(
    "/sources/{source_id}/test-connection",
    response_model=MagentoTestConnectionResponse,
)
async def test_magento_source_connection(
    source_id: str,
    subaccount_id: int = Query(...),
    user: AuthUser = Depends(get_current_user),
) -> MagentoTestConnectionResponse:
    """Probe an existing Magento source using the stored (encrypted) credentials.

    On success/failure the outcome is recorded via
    ``FeedSourceRepository.record_connection_check`` so the source list UI
    can show a fresh badge without a round-trip.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    _require_magento_source(source_id, subaccount_id)

    try:
        client = magento_client_module.create_magento_client_from_source(
            source_id,
            timeout_seconds=TEST_CONNECTION_TIMEOUT_SECONDS,
        )
    except MagentoAuthError:
        result = MagentoTestConnectionResponse(
            success=False,
            error="No credentials stored — reconnect required",
        )
    except ValueError as exc:
        result = MagentoTestConnectionResponse(success=False, error=str(exc))
    else:
        result = await _probe_store_configs(client)

    try:
        if result.success:
            _source_repo.record_connection_check(source_id, success=True)
        else:
            _source_repo.record_connection_check(
                source_id, success=False, error=result.error
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "magento_probe_persist_failed source_id=%s", source_id, exc_info=True
        )

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="magento.source.test_connection",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "success": result.success},
    )
    return result


@router.post("/test-connection", response_model=MagentoTestConnectionResponse)
async def test_magento_connection_before_save(
    payload: MagentoTestConnectionRequest,
    user: AuthUser = Depends(get_current_user),
) -> MagentoTestConnectionResponse:
    """Probe Magento credentials BEFORE persisting a source (wizard Step 3).

    Credentials travel in the request body and are used only for this single
    probe — they are **never** persisted. Handy for a "Test Connection"
    button that lets the merchant validate their OAuth Integration before
    committing to creating a source row.
    """
    _enforce_feature_flag()
    enforce_action_scope(user=user, action="data:write", scope="agency")

    try:
        base_url = magento_config.validate_magento_base_url(str(payload.magento_base_url))
    except ValueError as exc:
        return MagentoTestConnectionResponse(success=False, error=str(exc))
    try:
        store_code = magento_config.validate_magento_store_code(payload.magento_store_code)
    except ValueError as exc:
        return MagentoTestConnectionResponse(success=False, error=str(exc))

    try:
        client = MagentoClient(
            base_url=base_url,
            store_code=store_code,
            consumer_key=payload.consumer_key,
            consumer_secret=payload.consumer_secret.get_secret_value(),
            access_token=payload.access_token,
            access_token_secret=payload.access_token_secret.get_secret_value(),
            timeout_seconds=TEST_CONNECTION_TIMEOUT_SECONDS,
        )
    except ValueError as exc:
        return MagentoTestConnectionResponse(success=False, error=str(exc))

    result = await _probe_store_configs(client)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="magento.test_connection.before_save",
        resource="integration:magento",
        details={
            "success": result.success,
            "magento_base_url": base_url,
            "magento_store_code": store_code,
        },
    )
    return result
