from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

MediaFileKind = Literal["image", "video", "document"]
MediaFileSource = Literal["user_upload", "backend_ingest", "platform_sync"]
MediaFileStatus = Literal["draft", "ready", "delete_requested", "purged"]

MEDIA_FILE_STATUS_DRAFT: MediaFileStatus = "draft"
MEDIA_FILE_STATUS_READY: MediaFileStatus = "ready"
MEDIA_FILE_STATUS_DELETE_REQUESTED: MediaFileStatus = "delete_requested"
MEDIA_FILE_STATUS_PURGED: MediaFileStatus = "purged"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_media_id() -> str:
    return uuid4().hex


@dataclass(frozen=True)
class MediaStorageDescriptor:
    provider: str
    bucket: str
    key: str
    region: str
    etag: str | None = None
    version_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": str(self.provider or "").strip(),
            "bucket": str(self.bucket or "").strip(),
            "key": str(self.key or "").strip(),
            "region": str(self.region or "").strip(),
            "etag": str(self.etag or "").strip() or None,
            "version_id": str(self.version_id or "").strip() or None,
        }
