from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import enforce_action_scope, enforce_agency_navigation_access, get_current_user
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service
from app.services.storage_upload_complete import StorageUploadCompleteError, storage_upload_complete_service
from app.services.storage_upload_init import StorageUploadInitError, storage_upload_init_service

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
