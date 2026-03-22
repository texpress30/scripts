from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import load_settings
from app.services.media_metadata_models import MediaFileKind, MediaFileSource, new_media_id
from app.services.media_metadata_repository import media_metadata_repository
from app.services.s3_provider import get_s3_client
from app.services.storage_upload_init import sanitize_filename

_ALLOWED_KINDS: tuple[str, ...] = ("image", "video", "document")
_ALLOWED_SOURCES: tuple[str, ...] = ("backend_ingest", "platform_sync")


class StorageMediaIngestError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


@dataclass(frozen=True)
class StorageMediaIngestResult:
    media_id: str
    status: str
    client_id: int
    kind: str
    source: str
    bucket: str
    key: str
    region: str
    mime_type: str
    size_bytes: int
    uploaded_at: Any | None = None
    etag: str | None = None
    version_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StorageMediaIngestService:
    def _require_storage_config(self) -> tuple[str, str]:
        settings = load_settings()
        bucket = str(settings.storage_s3_bucket or "").strip()
        region = str(settings.storage_s3_region or "").strip()
        if bucket == "" or region == "":
            raise StorageMediaIngestError("Storage S3 is not configured (STORAGE_S3_BUCKET/STORAGE_S3_REGION).", status_code=503)
        return bucket, region

    def _build_storage_key(self, *, client_id: int, kind: MediaFileKind, media_id: str, original_filename: str) -> str:
        safe_filename = sanitize_filename(original_filename)
        return f"clients/{int(client_id)}/{str(kind)}/{str(media_id)}/{safe_filename}"

    def _validate(self, *, client_id: int, kind: str, source: str, original_filename: str, mime_type: str, content: bytes) -> None:
        if int(client_id) <= 0:
            raise StorageMediaIngestError("client_id must be a positive integer", status_code=400)
        normalized_kind = str(kind or "").strip().lower()
        normalized_source = str(source or "").strip().lower()
        normalized_filename = str(original_filename or "").strip()
        normalized_mime = str(mime_type or "").strip()
        if normalized_kind not in _ALLOWED_KINDS:
            raise StorageMediaIngestError("kind must be one of: image, video, document", status_code=400)
        if normalized_source not in _ALLOWED_SOURCES:
            raise StorageMediaIngestError("source must be one of: backend_ingest, platform_sync", status_code=400)
        if normalized_filename == "":
            raise StorageMediaIngestError("original_filename is required", status_code=400)
        if normalized_mime == "":
            raise StorageMediaIngestError("mime_type is required", status_code=400)
        if not isinstance(content, (bytes, bytearray)):
            raise StorageMediaIngestError("content must be bytes", status_code=400)

    def upload_bytes(
        self,
        *,
        client_id: int,
        kind: MediaFileKind,
        source: MediaFileSource,
        original_filename: str,
        mime_type: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> StorageMediaIngestResult:
        self._validate(
            client_id=client_id,
            kind=str(kind),
            source=str(source),
            original_filename=original_filename,
            mime_type=mime_type,
            content=content,
        )

        bucket, region = self._require_storage_config()
        media_id = new_media_id()
        size_bytes = len(bytes(content))
        storage_key = self._build_storage_key(
            client_id=int(client_id),
            kind=kind,
            media_id=media_id,
            original_filename=original_filename,
        )

        draft = media_metadata_repository.create_draft(
            media_id=media_id,
            client_id=int(client_id),
            kind=kind,
            source=source,
            original_filename=original_filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            metadata=metadata,
            storage_key=storage_key,
            storage_bucket=bucket,
        )

        try:
            s3_client = get_s3_client()
            put_response = s3_client.put_object(
                Bucket=bucket,
                Key=storage_key,
                Body=bytes(content),
                ContentType=str(mime_type),
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaIngestError(f"Failed to upload media content to S3: {exc}", status_code=503) from exc

        etag = str(put_response.get("ETag") or "").strip() or None
        version_id = str(put_response.get("VersionId") or "").strip() or None
        ready_record = media_metadata_repository.mark_ready(
            media_id=media_id,
            size_bytes=size_bytes,
            mime_type=str(mime_type),
            etag=etag,
            version_id=version_id,
            uploaded_at=datetime.now(timezone.utc),
        )
        if ready_record is None:
            raise StorageMediaIngestError("Failed to persist ready media record after S3 upload", status_code=500)

        return StorageMediaIngestResult(
            media_id=str(ready_record.get("media_id") or draft.get("media_id") or media_id),
            status=str(ready_record.get("status") or ""),
            client_id=int(ready_record.get("client_id") or client_id),
            kind=str(ready_record.get("kind") or kind),
            source=str(ready_record.get("source") or source),
            bucket=bucket,
            key=storage_key,
            region=region,
            mime_type=str(ready_record.get("mime_type") or mime_type),
            size_bytes=int(ready_record.get("size_bytes") or size_bytes),
            uploaded_at=ready_record.get("uploaded_at"),
            etag=etag,
            version_id=version_id,
        )


storage_media_ingest_service = StorageMediaIngestService()
