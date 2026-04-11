from __future__ import annotations

import re
from typing import Any, Literal

from app.services.media_metadata_models import (
    MEDIA_FILE_STATUS_DELETE_REQUESTED,
    MEDIA_FILE_STATUS_DRAFT,
    MEDIA_FILE_STATUS_PURGED,
    MEDIA_FILE_STATUS_READY,
)
from app.services.media_metadata_repository import media_metadata_repository
from app.services.s3_provider import get_s3_client, get_s3_presigned_ttl_seconds

StorageAccessDisposition = Literal["inline", "attachment"]
_DISPOSITION_VALUES: tuple[str, ...] = ("inline", "attachment")
_FILENAME_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


class StorageMediaAccessError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


def sanitize_disposition_filename(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate == "":
        return "file"
    sanitized = _FILENAME_SAFE_PATTERN.sub("_", candidate).strip("._")
    return sanitized or "file"


class StorageMediaAccessService:
    def build_access_url(
        self,
        *,
        client_id: int,
        media_id: str,
        disposition: StorageAccessDisposition = "inline",
    ) -> dict[str, Any]:
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaAccessError("client_id must be a positive integer", status_code=400)

        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageMediaAccessError("media_id is required", status_code=400)

        normalized_disposition = str(disposition or "inline").strip().lower() or "inline"
        if normalized_disposition not in _DISPOSITION_VALUES:
            raise StorageMediaAccessError("disposition must be one of: inline, attachment", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageMediaAccessError("Media record not found", status_code=404)
        if int(record.get("client_id") or 0) != normalized_client_id:
            raise StorageMediaAccessError("Media record not found", status_code=404)

        record_status = str(record.get("status") or "").strip().lower()
        if record_status == MEDIA_FILE_STATUS_PURGED:
            raise StorageMediaAccessError("Media record not found", status_code=404)
        if record_status in {MEDIA_FILE_STATUS_DRAFT, MEDIA_FILE_STATUS_DELETE_REQUESTED}:
            raise StorageMediaAccessError(f"Media record cannot be accessed from status={record_status}", status_code=409)
        if record_status != MEDIA_FILE_STATUS_READY:
            raise StorageMediaAccessError(f"Media record cannot be accessed from status={record_status}", status_code=409)

        storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
        bucket = str(storage.get("bucket") or "").strip()
        key = str(storage.get("key") or "").strip()
        if bucket == "" or key == "":
            raise StorageMediaAccessError("Media record storage is incomplete", status_code=409)

        mime_type = str(record.get("mime_type") or "").strip()
        filename = sanitize_disposition_filename(str(record.get("original_filename") or ""))
        content_disposition = f'{normalized_disposition}; filename="{filename}"'

        params: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "ResponseContentDisposition": content_disposition,
        }
        if mime_type != "":
            params["ResponseContentType"] = mime_type

        try:
            s3_client = get_s3_client()
            expires_in = int(get_s3_presigned_ttl_seconds())
            access_url = s3_client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in,
                HttpMethod="GET",
            )
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaAccessError(f"Failed to generate S3 access URL: {exc}", status_code=503) from exc

        return {
            "media_id": normalized_media_id,
            "status": record_status,
            "mime_type": mime_type,
            "method": "GET",
            "url": access_url,
            "expires_in": expires_in,
            "disposition": normalized_disposition,
            "filename": filename,
        }

    def fetch_bytes(
        self,
        *,
        client_id: int,
        media_id: str,
    ) -> dict[str, Any]:
        """Download the raw object bytes from S3 server-side. Used by the
        backend-proxied content endpoint so browsers never need direct access
        to the bucket (CORS-free + works against internal S3 endpoints)."""
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaAccessError("client_id must be a positive integer", status_code=400)

        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageMediaAccessError("media_id is required", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageMediaAccessError("Media record not found", status_code=404)
        if int(record.get("client_id") or 0) != normalized_client_id:
            raise StorageMediaAccessError("Media record not found", status_code=404)

        record_status = str(record.get("status") or "").strip().lower()
        if record_status == MEDIA_FILE_STATUS_PURGED:
            raise StorageMediaAccessError("Media record not found", status_code=404)
        if record_status != MEDIA_FILE_STATUS_READY:
            raise StorageMediaAccessError(f"Media record cannot be accessed from status={record_status}", status_code=409)

        storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
        bucket = str(storage.get("bucket") or "").strip()
        key = str(storage.get("key") or "").strip()
        if bucket == "" or key == "":
            raise StorageMediaAccessError("Media record storage is incomplete", status_code=409)

        mime_type = str(record.get("mime_type") or "").strip() or "application/octet-stream"
        filename = sanitize_disposition_filename(str(record.get("original_filename") or ""))

        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(Bucket=bucket, Key=key)
            body = response.get("Body")
            if body is None:
                raise StorageMediaAccessError("S3 response had no body", status_code=503)
            content = body.read()
        except StorageMediaAccessError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaAccessError(f"Failed to download media content from S3: {exc}", status_code=503) from exc

        return {
            "media_id": normalized_media_id,
            "mime_type": mime_type,
            "filename": filename,
            "content": content,
        }


storage_media_access_service = StorageMediaAccessService()
