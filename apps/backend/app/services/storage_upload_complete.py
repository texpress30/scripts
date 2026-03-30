from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_PURGED,
    MEDIA_FILE_STATUS_READY,
)
from app.services.media_metadata_repository import media_metadata_repository
from app.services.s3_provider import get_s3_client


class StorageUploadCompleteError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


def _object_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("nosuchkey", "notfound", "404", "no such key"))


class StorageUploadCompleteService:
    def complete_upload(self, *, client_id: int, media_id: str) -> dict[str, Any]:
        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageUploadCompleteError("media_id is required", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageUploadCompleteError("Media record not found", status_code=404)

        if int(record.get("client_id") or 0) != int(client_id):
            raise StorageUploadCompleteError("Media record not found", status_code=404)

        status = str(record.get("status") or "").strip().lower()
        storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
        bucket = str(storage.get("bucket") or "").strip()
        key = str(storage.get("key") or "").strip()
        region = str(storage.get("region") or "").strip()
        if bucket == "" or key == "":
            raise StorageUploadCompleteError("Media record storage is incomplete", status_code=409)

        if status in {MEDIA_FILE_STATUS_DELETE_REQUESTED, MEDIA_FILE_STATUS_PURGED}:
            raise StorageUploadCompleteError(f"Media record cannot be completed from status={status}", status_code=409)

        if status == MEDIA_FILE_STATUS_READY:
            return self._response_payload(record)

        try:
            s3_client = get_s3_client()
            head_payload = s3_client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            if _object_missing_error(exc):
                raise StorageUploadCompleteError("S3 object is not available yet", status_code=409) from exc
            raise StorageUploadCompleteError(f"Failed to verify S3 object: {exc}", status_code=503) from exc

        final_size = head_payload.get("ContentLength")
        final_mime = str(head_payload.get("ContentType") or record.get("mime_type") or "").strip()
        final_etag = str(head_payload.get("ETag") or "").strip() or None
        final_version_id = str(head_payload.get("VersionId") or "").strip() or None
        ready_record = media_metadata_repository.mark_ready(
            media_id=normalized_media_id,
            size_bytes=int(final_size) if final_size is not None else None,
            mime_type=final_mime if final_mime != "" else None,
            etag=final_etag,
            version_id=final_version_id,
            uploaded_at=datetime.now(timezone.utc),
        )
        if ready_record is None:
            raise StorageUploadCompleteError("Failed to persist ready media record", status_code=500)
        return self._response_payload(ready_record)

    def _response_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
        return {
            "media_id": str(record.get("media_id") or ""),
            "status": str(record.get("status") or ""),
            "bucket": str(storage.get("bucket") or ""),
            "key": str(storage.get("key") or ""),
            "region": str(storage.get("region") or ""),
            "mime_type": str(record.get("mime_type") or ""),
            "size_bytes": int(record.get("size_bytes")) if record.get("size_bytes") is not None else None,
            "uploaded_at": record.get("uploaded_at"),
            "etag": str(storage.get("etag") or "").strip() or None,
            "version_id": str(storage.get("version_id") or "").strip() or None,
        }


storage_upload_complete_service = StorageUploadCompleteService()
