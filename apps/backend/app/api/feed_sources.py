from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_subaccount_action, get_current_user
from app.core.config import load_settings
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
)
from app.services.feed_management.repository import FeedImportRepository, FeedSourceRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subaccount/{subaccount_id}/feed-sources", tags=["feed-sources"])

_source_repo = FeedSourceRepository()
_import_repo = FeedImportRepository()


def _enforce_feature_flag() -> None:
    if not load_settings().ff_feed_management_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed management is not enabled")


class CreateFeedSourceRequest(BaseModel):
    source_type: FeedSourceType
    name: str = Field(min_length=1, max_length=255)
    config: FeedSourceConfig = Field(default_factory=FeedSourceConfig)
    credentials_secret_id: str | None = None


class UpdateFeedSourceRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: FeedSourceConfig | None = None
    credentials_secret_id: str | None = None
    is_active: bool | None = None


class FeedSourceListResponse(BaseModel):
    items: list[FeedSourceResponse]


class FeedImportListResponse(BaseModel):
    items: list[FeedImportResponse]


class SyncTriggerResponse(BaseModel):
    import_id: str
    status: str
    message: str


@router.get("", response_model=FeedSourceListResponse)
def list_feed_sources(
    subaccount_id: int,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceListResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=subaccount_id)
    sources = _source_repo.get_by_subaccount(subaccount_id)
    return FeedSourceListResponse(items=sources)


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
    return source


@router.post("", response_model=FeedSourceResponse, status_code=status.HTTP_201_CREATED)
def create_feed_source(
    subaccount_id: int,
    payload: CreateFeedSourceRequest,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="clients:create", subaccount_id=subaccount_id)
    try:
        source = _source_repo.create(FeedSourceCreate(
            subaccount_id=subaccount_id,
            source_type=payload.source_type,
            name=payload.name,
            config=payload.config,
            credentials_secret_id=payload.credentials_secret_id,
        ))
    except FeedSourceAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.created",
        resource=f"feed_source:{source.id}",
        details={"subaccount_id": subaccount_id, "source_type": payload.source_type.value, "name": payload.name},
    )
    return source


@router.put("/{source_id}", response_model=FeedSourceResponse)
def update_feed_source(
    subaccount_id: int,
    source_id: str,
    payload: UpdateFeedSourceRequest,
    user: AuthUser = Depends(get_current_user),
) -> FeedSourceResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="clients:create", subaccount_id=subaccount_id)
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
        ))
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.updated",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id},
    )
    return updated


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed_source(
    subaccount_id: int,
    source_id: str,
    user: AuthUser = Depends(get_current_user),
) -> None:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="clients:create", subaccount_id=subaccount_id)
    try:
        existing = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if existing.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    _source_repo.delete(source_id)
    audit_log_service.log(
        actor_email=user.email,
        actor_role=user.role,
        action="feed_source.deleted",
        resource=f"feed_source:{source_id}",
        details={"subaccount_id": subaccount_id, "name": existing.name},
    )


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse)
def trigger_sync(
    subaccount_id: int,
    source_id: str,
    background_tasks: BackgroundTasks,
    user: AuthUser = Depends(get_current_user),
) -> SyncTriggerResponse:
    _enforce_feature_flag()
    enforce_subaccount_action(user=user, action="clients:create", subaccount_id=subaccount_id)
    try:
        source = _source_repo.get_by_id(source_id)
    except FeedSourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if source.subaccount_id != subaccount_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed source not found")
    if not source.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Feed source is not active")
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
    return SyncTriggerResponse(import_id=feed_import.id, status="pending", message="Sync has been queued and will start shortly")


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
