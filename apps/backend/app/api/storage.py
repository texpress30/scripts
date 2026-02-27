from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import enforce_action_scope, get_current_user
from app.services.auth import AuthUser
from app.services.client_registry import client_registry_service

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


@router.get("/media-usage", response_model=StorageUsageResponse)
def list_media_usage(
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    user: AuthUser = Depends(get_current_user),
) -> StorageUsageResponse:
    enforce_action_scope(user=user, action="clients:list", scope="agency")
    items, total = client_registry_service.list_media_storage_usage(search=search, page=page, page_size=page_size)
    return StorageUsageResponse(items=[StorageUsageItem(**item) for item in items], total=total, page=page, page_size=page_size)
