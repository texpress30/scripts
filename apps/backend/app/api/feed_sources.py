from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, SecretStr

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.core.config import load_settings
from app.integrations.file_source import service as file_source_service
from app.services.audit import audit_log_service
from app.services.auth import AuthUser
from app.services.feed_management.exceptions import (
    FeedImportInProgressError,
    FeedSourceAlreadyExistsError,
    FeedSourceNotFoundError,
)
from app.services.feed_management.models import (
    FeedImportCreate,
    FeedImportResponse,
    FeedSourceConfig,
    FeedSourceCreate,
    FeedSourceResponse,
    FeedSourceType,
    FeedSourceUpdate,
    ProductListResponse,
    ProductStatsResponse,
    SYNC_UNSUPPORTED_SOURCE_TYPES,
)
from app.services.feed_management.products_repository import feed_products_repository
from app.services.feed_management.repository import FeedImportRepository, FeedSourceRepository

logger = logging.getLogger(__name__)


_FILE_SOURCE_AUTH_TYPES: frozenset[FeedSourceType] = frozenset(
    {FeedSourceType.csv, FeedSourceType.json, FeedSourceType.xml}
)

router = APIRouter(prefix="/subaccount/{subaccount_id}/feed-sources", tags=["feed-sources"])

_source_repo = FeedSourceRepository()
_import_repo = FeedImportRepository()


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed management is not enabled")


def _enrich_with_file_auth(source: FeedSourceResponse) -> FeedSourceResponse:
    """Populate the ``has_file_auth`` / ``file_auth_username`` / masked
    password fields from ``integration_secrets`` for file sources.

    Non-file sources (shopify, magento, bigcommerce, woocommerce) and
    file sources without stored credentials pass through unchanged with
    the default ``has_file_auth=False`` and null username / masked.
    """
    if source.source_type not in _FILE_SOURCE_AUTH_TYPES:
        return source
    try:
        creds = file_source_service.get_file_source_credentials(source.id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "file_source_credentials_lookup_failed source_id=%s",
            source.id,
            exc_info=True,
        )
        return source
    masked = file_source_service.mask_file_source_credentials(creds)
    if not masked.get("has_auth"):
        return source
    return source.model_copy(
        update={
            "has_file_auth": True,
            "file_auth_username": masked.get("username"),
            "file_auth_password_masked": masked.get("password_masked"),
        }
    )


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateFeedSourceRequest(BaseModel):
    source_type: FeedSourceType
    name: str = Field(min_length=1, max_length=255)
    config: FeedSourceConfig = Field(default_factory=FeedSourceConfig)
    credentials_secret_id: str | None = None
    catalog_type: str = "product"
    catalog_variant: str = "physical_products"
    shop_domain: str | None = Field(default=None, description="Required for source_type=shopify")
    # Optional HTTP Basic Auth for file sources (CSV / JSON / XML).
    # Google Sheets never uses these — its share model is public URL /
    # service-account, not Basic Auth. Credentials are persisted encrypted
    # via ``app.integrations.file_source.service`` and never round-trip
    # back to the frontend.
    feed_auth_username: str | None = Field(
        default=None,
        max_length=255,
        description="Optional HTTP Basic Auth username for file sources (CSV/JSON/XML).",
    )
    feed_auth_password: SecretStr | None = Field(
        default=None,
        description="Optional HTTP Basic Auth password for file sources (CSV/JSON/XML).",
    )


class UpdateFeedSourceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: FeedSourceConfig | None = None
    credentials_secret_id: str | None = None
    is_active: bool | None = None
    catalog_type: str | None = None
    catalog_variant: str | None = None
    feed_auth_username: str | None = Field(
        default=None,
        max_length=255,
        description="Update the file-source Basic Auth username.",
    )
    feed_auth_password: SecretStr | None = Field(
        default=None,
        description="Update the file-source Basic Auth password.",
    )
    clear_file_auth: bool = Field(
        default=False,
        description="When true, wipe every stored HTTP Basic Auth credential for this source.",
    )


class CreateFeedSourceResponse(BaseModel):
    source: FeedSourceResponse
    authorize_url: str | None = None
    state: str | None = None


class CompleteOAuthRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    shop: str | None = Field(default=None, description="Optional override; defaults to source.shop_domain")


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    source: FeedSourceResponse


class FeedSourceListResponse(BaseModel):
    items: list[FeedSourceResponse]


class FeedImportListResponse(BaseModel):
    items: list[FeedImportResponse]


class SyncTriggerResponse(BaseModel):
    import_id: str
    status: str
    message: str


class ImportRunResponse(BaseModel):
    import_id: str
    status: str
    total: int
    imported: int
    deactivated: int
    errors: list[dict] = Field(default_factory=list)
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=FeedSourceListResponse)
def list_feed_sources(
    subaccount_id: int,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceListResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    sources = _source_repo.get_by_subaccount(subaccount_id)
    return FeedSourceListResponse(items=[_enrich_with_file_auth(src) for src in sources])


@router.get("/{source_id}", response_model=FeedSourceResponse)
def get_feed_source(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    return _enrich_with_file_auth(source)


@router.post("", response_model=CreateFeedSourceResponse, status_code=status.HTTP_201_CREATED)
def create_feed_source(
    subaccount_id: int,
    payload: CreateFeedSourceRequest,
    user: AuthUser = Depends(get_current_user),
) -> CreateFeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    shop_domain: str | None = None
    authorize_payload: dict[str, str] | None = None

    if payload.source_type == FeedSourceType.shopify:
        if not payload.shop_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="shop_domain is required for source_type=shopify",
            )
        from app.integrations.shopify import config as shopify_config
        from app.integrations.shopify import service as shopify_oauth_service
        from app.integrations.shopify.service import ShopifyIntegrationError

        try:
            shop_domain = shopify_config.validate_shop_domain(payload.shop_domain)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if shopify_config.oauth_configured():
            try:
                authorize_payload = shopify_oauth_service.generate_connect_url(shop=shop_domain)
            except (ValueError, ShopifyIntegrationError) as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        source = _source_repo.create(FeedSourceCreate(
            subaccount_id=subaccount_id,
            source_type=payload.source_type,
            name=payload.name,
            config=payload.config,
            credentials_secret_id=payload.credentials_secret_id,
            catalog_type=payload.catalog_type,
            catalog_variant=payload.catalog_variant,
            shop_domain=shop_domain,
        ))
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    # File source Basic Auth (CSV/JSON/XML): persist credentials encrypted
    # after the source row is created so the scope key (source.id) is
    # stable. Roll back the row on any credential-store failure so we
    # never leave behind an orphan ``feed_sources`` entry the connector
    # can't authenticate.
    stored_file_auth = False
    if (
        payload.source_type in _FILE_SOURCE_AUTH_TYPES
        and payload.feed_auth_username
        and payload.feed_auth_password
    ):
        password_plain = payload.feed_auth_password.get_secret_value().strip()
        username_plain = payload.feed_auth_username.strip()
        if username_plain and password_plain:
            try:
                file_source_service.store_file_source_credentials(
                    source_id=source.id,
                    username=username_plain,
                    password=password_plain,
                )
                stored_file_auth = True
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "file_source_credentials_store_failed source_id=%s", source.id
                )
                try:
                    _source_repo.delete(source.id)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "file_source_create_rollback_failed source_id=%s", source.id
                    )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist file source credentials",
                ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.created",
        resource=f"feed_source:{source.id}",
        details={
            "subaccount_id": subaccount_id,
            "source_type": payload.source_type.value,
            "name": payload.name,
            "shop_domain": shop_domain,
            "has_file_auth": stored_file_auth,
        },
    )
    return CreateFeedSourceResponse(
        source=_enrich_with_file_auth(source),
        authorize_url=authorize_payload.get("authorize_url") if authorize_payload else None,
        state=authorize_payload.get("state") if authorize_payload else None,
    )


@router.put("/{source_id}", response_model=FeedSourceResponse)
def update_feed_source(
    subaccount_id: int,
    source_id: str,
    payload: UpdateFeedSourceRequest,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    try:
        existing = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if existing.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    try:
        updated = _source_repo.update(source_id, FeedSourceUpdate(
            name=payload.name,
            config=payload.config,
            credentials_secret_id=payload.credentials_secret_id,
            is_active=payload.is_active,
            catalog_type=payload.catalog_type,
            catalog_variant=payload.catalog_variant,
        ))
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    # File source Basic Auth (CSV/JSON/XML): rotate or clear credentials
    # according to the update payload. The three possibilities are:
    #   * ``clear_file_auth=True`` → wipe every stored credential row
    #   * both username + password supplied → upsert (rotates either)
    #   * only username supplied + existing password row → merge
    #   * only password supplied + existing username row → merge
    #   * neither supplied → no-op (cosmetic update of other fields only)
    file_auth_changed = False
    file_auth_cleared = False
    if updated.source_type in _FILE_SOURCE_AUTH_TYPES:
        if payload.clear_file_auth:
            try:
                file_source_service.delete_file_source_credentials(source_id)
                file_auth_cleared = True
                file_auth_changed = True
            except Exception:  # noqa: BLE001
                logger.warning(
                    "file_source_credentials_clear_failed source_id=%s",
                    source_id,
                    exc_info=True,
                )
        elif payload.feed_auth_username is not None or payload.feed_auth_password is not None:
            existing_creds = (
                file_source_service.get_file_source_credentials(source_id) or {}
            )
            new_username = (
                payload.feed_auth_username.strip()
                if payload.feed_auth_username is not None
                else existing_creds.get("username", "")
            )
            new_password = (
                payload.feed_auth_password.get_secret_value().strip()
                if payload.feed_auth_password is not None
                else existing_creds.get("password", "")
            )
            if not new_username or not new_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Both feed_auth_username and feed_auth_password are "
                        "required to enable HTTP Basic Auth on a file source."
                    ),
                )
            try:
                file_source_service.store_file_source_credentials(
                    source_id=source_id,
                    username=new_username,
                    password=new_password,
                )
                file_auth_changed = True
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "file_source_credentials_update_failed source_id=%s", source_id
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist file source credentials",
                ) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.updated",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "file_auth_changed": file_auth_changed,
            "file_auth_cleared": file_auth_cleared,
        },
    )
    return _enrich_with_file_auth(updated)


@router.delete("/{source_id}")
def delete_feed_source(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    try:
        existing = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if existing.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    try:
        deleted_products = feed_products_repository.delete_products_by_source(source_id)
    except Exception:
        deleted_products = 0

    # Best-effort: drop the encrypted Shopify token tied to this shop domain.
    if existing.source_type == FeedSourceType.shopify and existing.shop_domain:
        try:
            from app.services.integration_secrets_store import integration_secrets_store

            integration_secrets_store.delete_secret(
                provider="shopify",
                secret_key="access_token",
                scope=existing.shop_domain,
            )
            integration_secrets_store.delete_secret(
                provider="shopify",
                secret_key="scope",
                scope=existing.shop_domain,
            )
        except Exception:
            logger.warning("shopify_token_delete_failed source_id=%s", source_id, exc_info=True)

    # File source Basic Auth cleanup: drop any encrypted credentials we
    # stored for CSV / JSON / XML sources. Idempotent — runs even for
    # sources that never had auth configured.
    if existing.source_type in _FILE_SOURCE_AUTH_TYPES:
        try:
            file_source_service.delete_file_source_credentials(source_id)
        except Exception:  # noqa: BLE001
            logger.warning(
                "file_source_credentials_delete_failed source_id=%s",
                source_id,
                exc_info=True,
            )

    _source_repo.delete(source_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.deleted",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "name": existing.name, "deleted_products": deleted_products},
    )
    return {"status": "ok", "id": str(source_id)}


class UpdateSyncScheduleRequest(BaseModel):
    schedule: str = Field(description="manual, hourly, every_6h, every_12h, daily, weekly")


@router.put("/{source_id}/schedule")
def update_sync_schedule(
    subaccount_id: int,
    source_id: str,
    payload: UpdateSyncScheduleRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    from datetime import datetime, timezone
    from app.services.feed_management.models import SyncSchedule, SCHEDULE_INTERVALS

    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")

    schedule_val = payload.schedule
    valid = [s.value for s in SyncSchedule]
    if schedule_val not in valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid schedule. Must be one of: {', '.join(valid)}")

    schedule_enum = SyncSchedule(schedule_val)
    next_sync = None
    if schedule_enum != SyncSchedule.manual:
        interval = SCHEDULE_INTERVALS.get(schedule_enum)
        if interval:
            next_sync = datetime.now(timezone.utc) + interval

    from app.db.pool import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE feed_sources SET sync_schedule = %s, next_scheduled_sync = %s, updated_at = NOW() WHERE id = %s",
                (schedule_val, next_sync, source_id),
            )
        conn.commit()

    return {
        "status": "ok",
        "source_id": source_id,
        "sync_schedule": schedule_val,
        "next_scheduled_sync": next_sync.isoformat() if next_sync else None,
    }


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse)
def trigger_sync(
    subaccount_id: int,
    source_id: str,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> SyncTriggerResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    if not source.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Feed source is not active")

    # Block sync triggers for source types that have no connector wired up
    # yet (the six "generic API key" e-commerce stubs). Without this gate
    # the BackgroundTasks runner would create a ``feed_imports`` row in
    # ``pending`` and then crash inside ``_get_connector`` (which raises
    # ValueError for unknown source types), leaving the import row stuck.
    if source.source_type in SYNC_UNSUPPORTED_SOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Sync is not yet available for source_type='{source.source_type.value}'. "
                "The connector is in development — credentials are saved and the source "
                "will start syncing automatically when support lands."
            ),
        )

    try:
        feed_import = _import_repo.create(FeedImportCreate(feed_source_id=source_id))
    except FeedImportInProgressError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    from app.services.feed_management.sync_service import feed_sync_service
    background_tasks.add_task(feed_sync_service.run_sync_background, source_id)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.sync_triggered",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "import_id": feed_import.id},
    )
    return SyncTriggerResponse(
        import_id=feed_import.id,
        status="pending",
        message="Sync has been queued and will start shortly",
    )


@router.get("/{source_id}/imports", response_model=FeedImportListResponse)
def list_imports(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> FeedImportListResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    imports = _import_repo.get_by_source(source_id)
    return FeedImportListResponse(items=imports)


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------

def _resolve_source_or_404(subaccount_id: int, source_id: str) -> FeedSourceResponse:
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    return source


@router.get("/{source_id}/products/categories")
def list_product_categories(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    _resolve_source_or_404(subaccount_id, source_id)
    categories = feed_products_repository.get_distinct_categories(source_id)
    return {"categories": categories}


@router.get("/{source_id}/products/stats", response_model=ProductStatsResponse)
def product_stats(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ProductStatsResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    _resolve_source_or_404(subaccount_id, source_id)

    total = feed_products_repository.count_products(source_id)
    categories = feed_products_repository.get_distinct_categories(source_id)
    by_category: dict[str, int] = {}
    for cat in categories:
        by_category[cat] = feed_products_repository.count_products(source_id, category=cat)

    latest_import = _import_repo.get_latest_by_source(source_id)
    last_sync = latest_import.completed_at if latest_import else None

    return ProductStatsResponse(total=total, by_category=by_category, last_sync=last_sync)


@router.get("/{source_id}/products", response_model=ProductListResponse)
def list_products(
    subaccount_id: int,
    source_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> ProductListResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    _resolve_source_or_404(subaccount_id, source_id)

    items = feed_products_repository.list_products(source_id, skip=skip, limit=limit, search=search, category=category)
    total = feed_products_repository.count_products(source_id, search=search, category=category)
    # Return just the data field from each document
    product_items = [doc.get("data", doc) for doc in items if doc]
    return ProductListResponse(items=product_items, total=total, skip=skip, limit=limit)


@router.get("/{source_id}/products/{product_id}")
def get_product(
    subaccount_id: int,
    source_id: str,
    product_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    _resolve_source_or_404(subaccount_id, source_id)

    doc = feed_products_repository.get_product(source_id, product_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product not found: {product_id}")
    return doc.get("data", doc)


# ---------------------------------------------------------------------------
# Shopify OAuth lifecycle endpoints (per-source)
# ---------------------------------------------------------------------------


def _require_shopify_source(subaccount_id: int, source_id: str) -> FeedSourceResponse:
    source = _resolve_source_or_404(subaccount_id, source_id)
    if source.source_type != FeedSourceType.shopify:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only valid for Shopify feed sources",
        )
    if not source.shop_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shopify feed source has no shop_domain configured",
        )
    return source


@router.post("/{source_id}/complete-oauth", response_model=FeedSourceResponse)
def complete_shopify_oauth(
    subaccount_id: int,
    source_id: str,
    payload: CompleteOAuthRequest,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceResponse:
    """Finalise a Shopify OAuth flow started via ``POST /``: exchange the code,
    persist the encrypted token, and flip the source to ``connected``."""
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    source = _require_shopify_source(subaccount_id, source_id)
    shop = (payload.shop or source.shop_domain or "").strip()
    if not shop:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="shop is required")

    from app.integrations.shopify import service as shopify_oauth_service
    from app.integrations.shopify.service import ShopifyIntegrationError

    state_valid, state_reason = shopify_oauth_service.verify_shopify_oauth_state(payload.state)
    if not state_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state for Shopify connect callback: {state_reason}",
        )

    try:
        exchange = shopify_oauth_service.exchange_code_for_token(code=payload.code, shop=shop)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ShopifyIntegrationError as exc:
        code = exc.http_status if exc.http_status in (400, 403, 502) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    if exchange["shop"] != source.shop_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth callback shop '{exchange['shop']}' does not match source shop '{source.shop_domain}'",
        )

    try:
        shopify_oauth_service.store_shopify_token(
            shop=exchange["shop"],
            access_token=exchange["access_token"],
            scope=exchange.get("scope", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("shopify_token_store_failed source_id=%s", source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist Shopify access token",
        ) from exc

    updated = _source_repo.mark_oauth_connected(source_id, scopes=exchange.get("scope") or None)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.shopify.connected",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "shop_domain": exchange["shop"]},
    )
    return updated


@router.post("/{source_id}/reconnect")
def reconnect_shopify_source(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> dict:
    """Generate a fresh authorize URL for an existing Shopify source whose token
    is missing, expired, or revoked."""
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    source = _require_shopify_source(subaccount_id, source_id)
    if source.connection_status not in {"error", "disconnected", "pending"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source is already in status '{source.connection_status}'; nothing to reconnect",
        )

    from app.integrations.shopify import config as shopify_config
    from app.integrations.shopify import service as shopify_oauth_service
    from app.integrations.shopify.service import ShopifyIntegrationError

    if not shopify_config.oauth_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify OAuth is not configured",
        )

    try:
        payload = shopify_oauth_service.generate_connect_url(shop=source.shop_domain or "")
    except (ValueError, ShopifyIntegrationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.shopify.reconnect_started",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "shop_domain": source.shop_domain},
    )
    return {
        "authorize_url": payload["authorize_url"],
        "state": payload["state"],
        "source_id": source_id,
    }


@router.post("/{source_id}/test-connection", response_model=ConnectionTestResponse)
def test_shopify_source_connection(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ConnectionTestResponse:
    """Probe Shopify ``/admin/api/{version}/shop.json`` with the stored token."""
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    source = _require_shopify_source(subaccount_id, source_id)
    if source.connection_status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source is not connected (status='{source.connection_status}')",
        )

    from app.integrations.shopify import config as shopify_config
    from app.integrations.shopify import service as shopify_oauth_service

    token = shopify_oauth_service.get_access_token_for_shop(source.shop_domain or "")
    if not token:
        updated = _source_repo.record_connection_check(source_id, success=False, error="No stored token")
        return ConnectionTestResponse(success=False, message="No stored token", source=updated)

    from urllib import error as _err
    from urllib import request as _req
    import json as _json

    url = f"{shopify_config.get_shopify_api_base_url(source.shop_domain or '')}/shop.json"
    req = _req.Request(
        url=url,
        method="GET",
        headers={"X-Shopify-Access-Token": token, "Accept": "application/json"},
    )
    try:
        with _req.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        payload = _json.loads(data) if data else {}
        shop_payload = payload.get("shop") if isinstance(payload, dict) else None
        message = (
            f"Connected to {shop_payload.get('name')}" if isinstance(shop_payload, dict) and shop_payload.get("name")
            else "Connection OK"
        )
        updated = _source_repo.record_connection_check(source_id, success=True)
        return ConnectionTestResponse(success=True, message=message, source=updated)
    except _err.HTTPError as exc:
        if exc.code in (401, 403):
            updated = _source_repo.record_connection_check(
                source_id, success=False, error="Token invalid or revoked"
            )
            return ConnectionTestResponse(success=False, message="Token invalid or revoked", source=updated)
        updated = _source_repo.record_connection_check(
            source_id, success=False, error=f"Shopify HTTP {exc.code}"
        )
        return ConnectionTestResponse(success=False, message=f"Shopify HTTP {exc.code}", source=updated)
    except (_err.URLError, TimeoutError) as exc:
        updated = _source_repo.record_connection_check(
            source_id, success=False, error=f"Network error: {exc}"
        )
        return ConnectionTestResponse(success=False, message="Could not reach Shopify", source=updated)


@router.post("/{source_id}/import", response_model=ImportRunResponse)
async def import_shopify_products(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> ImportRunResponse:
    """Run a synchronous Shopify products import for a connected source.

    This is a thin wrapper around :func:`feed_sync_service.run_sync` that
    surfaces the per-run counts (imported / deactivated / total) directly in
    the HTTP response, instead of fire-and-forget like ``POST /sync``.
    Long-running stores should still prefer ``/sync`` (BackgroundTasks);
    ``/import`` is intended for UI flows that want immediate feedback.
    """
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="data:write", subaccount_id=subaccount_id)

    source = _require_shopify_source(subaccount_id, source_id)
    if source.connection_status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source not connected (status='{source.connection_status}')",
        )

    from app.integrations.shopify.service import get_access_token_for_shop

    if not get_access_token_for_shop(source.shop_domain or ""):
        # Token was revoked or never persisted — surface a clean 400 instead of
        # letting the connector hit a 401 inside the sync.
        try:
            _source_repo.record_connection_check(
                source_id, success=False, error="Token revoked — reconnect required"
            )
        except Exception:
            logger.warning("Failed to mark source after missing token", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source not connected (no stored token)",
        )

    from app.services.feed_management.sync_service import feed_sync_service

    try:
        feed_import = await feed_sync_service.run_sync(source_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Synchronous Shopify import failed for source %s", source_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {exc}",
        ) from exc

    # Pull post-sync product count to derive a deactivation delta. This is
    # informational only — the authoritative numbers come from the FeedImport
    # row that the sync service already persists.
    try:
        from app.services.feed_management.products_repository import feed_products_repository

        total_after = feed_products_repository.count_products(source_id)
    except Exception:
        total_after = feed_import.imported_products

    deactivated = max(0, feed_import.total_products - feed_import.imported_products)

    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.shopify.import_run",
        resource=f"feed_source:{source_id}",
        details={
            "subaccount_id": subaccount_id,
            "import_id": feed_import.id,
            "status": feed_import.status.value,
            "imported": feed_import.imported_products,
            "total": feed_import.total_products,
            "after_count": total_after,
        },
    )

    return ImportRunResponse(
        import_id=feed_import.id,
        status=feed_import.status.value,
        total=feed_import.total_products,
        imported=feed_import.imported_products,
        deactivated=deactivated,
        errors=feed_import.errors or [],
        message=(
            f"Imported {feed_import.imported_products} products"
            if feed_import.status.value == "completed"
            else f"Import finished with status {feed_import.status.value}"
        ),
    )
