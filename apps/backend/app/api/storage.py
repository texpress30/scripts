from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, get_current_user
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.storage_upload_complete import StorageUploadCompleteError, storage_upload_complete_service
from app.services.storage_upload_init import StorageUploadInitError, storage_upload_init_service
from app.services.storage_media_read import StorageMediaReadError, storage_media_read_service

router = APIRouter(prefix="/storage", tags=["storage"])


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
    kind: Literal["image", "video", "document"]
    original_filename: str
    mime_type: str
    size_bytes: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


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
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
    try:
        response_payload = storage_upload_init_service.init_upload(
            client_id=payload.client_id,
            kind=payload.kind,
            original_filename=payload.original_filename,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            metadata=payload.metadata,
        )
    except StorageUploadInitError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize upload") from exc
    return StorageUploadInitResponse(**response_payload)


@router.post("/uploads/complete", response_model=StorageUploadCompleteResponse)
def complete_direct_upload(
    payload: StorageUploadCompleteRequest,
    user: AuthUser = Depends(get_current_user),
) -> StorageUploadCompleteResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
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
    kind: Literal["image", "video", "document"] | None = Query(default=None),
    status_filter: Literal["draft", "ready", "delete_requested", "purged"] | None = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthUser = Depends(get_current_user),
) -> StorageMediaListResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
    try:
        payload = storage_media_read_service.list_media(
            client_id=client_id,
            kind=kind,
            status=status_filter,
            limit=limit,
            offset=offset,
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
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    enforce_agency_navigation_access(user=user, permission_key="settings_media_storage_usage")
    try:
        payload = storage_media_read_service.get_media_detail(client_id=client_id, media_id=media_id)
    except StorageMediaReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get media detail") from exc
    return StorageMediaDetailResponse(**payload)
