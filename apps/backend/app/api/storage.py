import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import (
    enforce_action_scope,
    enforce_agency_navigation_access,
    enforce_subaccount_action,
    enforce_subaccount_navigation_access,
    get_current_user,
)
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.media_folder_service import MediaFolderError, media_folder_service
from app.services.media_metadata_repository import media_metadata_repository
from app.services.storage_upload_complete import StorageUploadCompleteError, storage_upload_complete_service
from app.services.storage_upload_init import StorageUploadInitError, storage_upload_init_service
from app.services.storage_media_read import StorageMediaReadError, storage_media_read_service
from app.services.storage_media_access import StorageMediaAccessError, storage_media_access_service
from app.services.storage_media_delete import StorageMediaDeleteError, storage_media_delete_service
from app.services.storage_media_update import StorageMediaUpdateError, storage_media_update_service

router = APIRouter(prefix="/storage", tags=["storage"])
logger = logging.getLogger(__name__)


class StorageUsageItem(BaseModel):
    id: int
    name: str
    address: str
    media_storage_bytes: int


class StorageUsageResponse(BaseModel):
    items: list[StorageUsageItem]
    total: int
    page: int
    page_size: int


class StorageUploadInitRequest(BaseModel):
    client_id: int
    kind: Literal["image", "video", "document", "audio", "other"]
    original_filename: str
    mime_type: str
    size_bytes: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    folder_id: str | None = None


class StorageUploadInitDescriptor(BaseModel):
    method: str
    url: str
    expires_in: int
    headers: dict[str, str] = Field(default_factory=dict)


class StorageUploadInitResponse(BaseModel):
    media_id: str
    status: str
    bucket: str
    key: str
    region: str
    upload: StorageUploadInitDescriptor


class StorageUploadCompleteRequest(BaseModel):
    client_id: int
    media_id: str


class StorageUploadCompleteResponse(BaseModel):
    media_id: str
    status: str
    bucket: str
    key: str
    region: str
    mime_type: str
    size_bytes: int | None = None
    uploaded_at: Any | None = None
    etag: str | None = None
    version_id: str | None = None


class StorageMediaListItem(BaseModel):
    media_id: str
    client_id: int
    kind: str
    source: str
    status: str
    original_filename: str
    display_name: str = ""
    folder_id: str | None = None
    mime_type: str
    size_bytes: int | None = None
    created_at: Any | None = None
    uploaded_at: Any | None = None


class StorageMediaListResponse(BaseModel):
    items: list[StorageMediaListItem]
    limit: int
    offset: int
    total: int


class StorageMediaDetailStorage(BaseModel):
    provider: str
    bucket: str
    key: str
    region: str
    etag: str | None = None
    version_id: str | None = None


class StorageMediaDetailResponse(StorageMediaListItem):
    metadata: dict[str, Any] = Field(default_factory=dict)
    storage: StorageMediaDetailStorage
    updated_at: Any | None = None
    deleted_at: Any | None = None
    purged_at: Any | None = None


class StorageMediaAccessResponse(BaseModel):
    media_id: str
    status: str
    mime_type: str
    method: str
    url: str
    expires_in: int
    disposition: Literal["inline", "attachment"]
    filename: str


class StorageMediaDeleteResponse(BaseModel):
    media_id: str
    status: str
    client_id: int
    kind: str
    original_filename: str
    deleted_at: Any | None = None
    updated_at: Any | None = None


class StorageMediaUpdateRequest(BaseModel):
    client_id: int
    display_name: str | None = None
    folder_id: str | None = None
    clear_folder: bool = False


class StorageFolderCreateRequest(BaseModel):
    client_id: int
    name: str
    parent_folder_id: str | None = None


class StorageFolderRenameRequest(BaseModel):
    client_id: int
    name: str


class StorageFolderMoveRequest(BaseModel):
    client_id: int
    parent_folder_id: str | None = None


class StorageFolderResponse(BaseModel):
    folder_id: str
    client_id: int
    parent_folder_id: str | None = None
    name: str
    system: bool = False
    status: str
    created_at: Any | None = None
    updated_at: Any | None = None


class StorageFolderListResponse(BaseModel):
    items: list[StorageFolderResponse]


class StorageMediaSummaryResponse(BaseModel):
    client_id: int
    total_files: int
    total_bytes: int


def _enforce_media_scope_access(*, user: AuthUser, client_id: int) -> None:
    """Permit agency users (with either the legacy `settings_media_storage_usage`
    permission used by the settings aggregate page, or the new top-level
    `agency_media` permission used by the Stocare Media page) and sub-account
    users (with the new `media` module) to work with the media library for a
    specific client."""
    role = str(user.role or "").strip().lower()
    if role.startswith("subaccount_"):
        enforce_subaccount_navigation_access(user=user, subaccount_id=int(client_id), permission_key="media")
        return
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    # Accept either permission key — agency_media is the new top-level nav
    # entry, settings_media_storage_usage is the old settings page. Only the
    # second one needs to be enforced for legacy callers; if the user has
    # access to agency_media we skip the media-storage-usage gate.
    try:
        enforce_agency_navigation_access(user=user, permission_key="agency_media")
    except HTTPException:
        enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
    enforce_subaccount_action(user=user, action="dashboard:view", subaccount_id=int(client_id))


@router.get("/media-usage", response_model=StorageUsageResponse)
def list_media_usage(
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> StorageUsageResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
    items, total = client_registry_service.list_media_storage_usage(search=search, page=page, page_size=page_size)
    return StorageUsageResponse(items=[StorageUsageItem(**item) for item in items], total=total, page=page, page_size=page_size)


@router.post("/uploads/init", response_model=StorageUploadInitResponse)
def init_direct_upload(
    payload: StorageUploadInitRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageUploadInitResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        response_payload = storage_upload_init_service.init_upload(
            client_id=payload.client_id,
            kind=payload.kind,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            metadata=payload.metadata,
            folder_id=payload.folder_id,
        )
    except StorageUploadInitError as exc:
        logger.warning(
            "storage_upload_init_error client_id=%s kind=%s original_filename=%s detail=%s",
            payload.client_id,
            payload.kind,
            payload.original_filename,
            str(exc),
        )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "storage_upload_init_runtime_error client_id=%s kind=%s original_filename=%s",
            payload.client_id,
            payload.kind,
            payload.original_filename,
        )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "storage_upload_init_unexpected_error client_id=%s kind=%s original_filename=%s",
            payload.client_id,
            payload.kind,
            payload.original_filename,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize upload") from exc
    return StorageUploadInitResponse(**response_payload)


@router.post("/uploads/complete", response_model=StorageUploadCompleteResponse)
def complete_direct_upload(
    payload: StorageUploadCompleteRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageUploadCompleteResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        response_payload = storage_upload_complete_service.complete_upload(
            client_id=payload.client_id,
            media_id=payload.media_id,
        )
    except StorageUploadCompleteError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to complete upload") from exc
    return StorageUploadCompleteResponse(**response_payload)


@router.get("/media", response_model=StorageMediaListResponse)
def list_media(
    client_id: int = Query(..., ge=1),
    kind: Literal["image", "video", "document", "audio", "other"] | None = Query(default=None),
    status_filter: Literal["draft", "ready", "delete_requested", "purged"] | None = Query(default=None, alias="status"),
    folder_id: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: Literal["newest", "oldest", "name_asc", "name_desc", "size_asc", "size_desc"] | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaListResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        payload = storage_media_read_service.list_media(
            client_id=client_id,
            kind=kind,
            status=status_filter,
            limit=limit,
            offset=offset,
            folder_id=folder_id,
            search=search,
            sort=sort,
        )
    except StorageMediaReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list media") from exc
    return StorageMediaListResponse(**payload)


@router.get("/media/{media_id}", response_model=StorageMediaDetailResponse)
def get_media_detail(
    media_id: str,
    client_id: int = Query(..., ge=1),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaDetailResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        payload = storage_media_read_service.get_media_detail(client_id=client_id, media_id=media_id)
    except StorageMediaReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get media detail") from exc
    return StorageMediaDetailResponse(**payload)


@router.get("/media/{media_id}/access-url", response_model=StorageMediaAccessResponse)
def get_media_access_url(
    media_id: str,
    client_id: int = Query(..., ge=1),
    disposition: Literal["inline", "attachment"] = Query(default="inline"),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaAccessResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        payload = storage_media_access_service.build_access_url(
            client_id=client_id,
            media_id=media_id,
            disposition=disposition,
        )
    except StorageMediaAccessError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate media access URL") from exc
    return StorageMediaAccessResponse(**payload)


@router.delete("/media/{media_id}", response_model=StorageMediaDeleteResponse)
def soft_delete_media(
    media_id: str,
    client_id: int = Query(..., ge=1),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaDeleteResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        payload = storage_media_delete_service.soft_delete_media(client_id=client_id, media_id=media_id)
    except StorageMediaDeleteError as exc:
        detail: Any = str(exc)
        if exc.references:
            detail = {"message": str(exc), "references": exc.references}
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to soft-delete media") from exc
    return StorageMediaDeleteResponse(**payload)


@router.patch("/media/{media_id}", response_model=StorageMediaDetailResponse)
def update_media(
    media_id: str,
    payload: StorageMediaUpdateRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaDetailResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        updated = storage_media_update_service.update_media(
            client_id=payload.client_id,
            media_id=media_id,
            display_name=payload.display_name,
            folder_id=payload.folder_id,
            clear_folder=payload.clear_folder,
        )
    except StorageMediaUpdateError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update media") from exc
    detail_payload = storage_media_read_service.get_media_detail(
        client_id=int(payload.client_id),
        media_id=str(updated.get("media_id") or media_id),
    )
    return StorageMediaDetailResponse(**detail_payload)


@router.get("/media-summary", response_model=StorageMediaSummaryResponse)
def get_media_summary(
    client_id: int = Query(..., ge=1),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaSummaryResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        summary = media_metadata_repository.summarize_for_client(client_id=int(client_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load media summary") from exc
    return StorageMediaSummaryResponse(
        client_id=int(client_id),
        total_files=int(summary.get("total_files") or 0),
        total_bytes=int(summary.get("total_bytes") or 0),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Folders
# ──────────────────────────────────────────────────────────────────────────────


def _folder_payload(folder: dict[str, Any]) -> dict[str, Any]:
    return {
        "folder_id": str(folder.get("folder_id") or ""),
        "client_id": int(folder.get("client_id") or 0),
        "parent_folder_id": str(folder.get("parent_folder_id") or "").strip() or None,
        "name": str(folder.get("name") or ""),
        "system": bool(folder.get("system") or False),
        "status": str(folder.get("status") or ""),
        "created_at": folder.get("created_at"),
        "updated_at": folder.get("updated_at"),
    }


@router.get("/folders", response_model=StorageFolderListResponse)
def list_folders(
    client_id: int = Query(..., ge=1),
    parent_folder_id: str | None = Query(default=None),
    user: AuthUser = Depends(get_current_user),
) -> StorageFolderListResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        items = media_folder_service.list_children(
            client_id=int(client_id),
            parent_folder_id=parent_folder_id,
        )
    except MediaFolderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StorageFolderListResponse(items=[StorageFolderResponse(**_folder_payload(item)) for item in items])


@router.post("/folders", response_model=StorageFolderResponse)
def create_folder(
    payload: StorageFolderCreateRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageFolderResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        created = media_folder_service.create_folder(
            client_id=int(payload.client_id),
            parent_folder_id=payload.parent_folder_id,
            name=payload.name,
        )
    except MediaFolderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StorageFolderResponse(**_folder_payload(created))


@router.patch("/folders/{folder_id}/rename", response_model=StorageFolderResponse)
def rename_folder(
    folder_id: str,
    payload: StorageFolderRenameRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageFolderResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        updated = media_folder_service.rename_folder(
            client_id=int(payload.client_id),
            folder_id=folder_id,
            name=payload.name,
        )
    except MediaFolderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StorageFolderResponse(**_folder_payload(updated))


@router.patch("/folders/{folder_id}/move", response_model=StorageFolderResponse)
def move_folder(
    folder_id: str,
    payload: StorageFolderMoveRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageFolderResponse:
    _enforce_media_scope_access(user=user, client_id=int(payload.client_id))
    try:
        updated = media_folder_service.move_folder(
            client_id=int(payload.client_id),
            folder_id=folder_id,
            new_parent_folder_id=payload.parent_folder_id,
        )
    except MediaFolderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StorageFolderResponse(**_folder_payload(updated))


@router.delete("/folders/{folder_id}", response_model=StorageFolderResponse)
def delete_folder(
    folder_id: str,
    client_id: int = Query(..., ge=1),
    user: AuthUser = Depends(get_current_user),
) -> StorageFolderResponse:
    _enforce_media_scope_access(user=user, client_id=int(client_id))
    try:
        deleted = media_folder_service.delete_folder(
            client_id=int(client_id),
            folder_id=folder_id,
        )
    except MediaFolderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return StorageFolderResponse(**_folder_payload(deleted))
