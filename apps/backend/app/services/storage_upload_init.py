from __future__ import annotations

import re
from threading import Lock
from typing import Any

from app.core.config import load_settings
from app.services.media_metadata_models import MediaFileKind, new_media_id
from app.services.media_metadata_repository import media_metadata_repository
from app.services.s3_provider import get_s3_client, get_s3_presigned_ttl_seconds

_SUPPORTED_KINDS: tuple[str, ...] = ("image", "video", "document")
_FILENAME_SAFE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")


class StorageUploadInitError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


def sanitize_filename(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate == "":
        return "file"
    sanitized = _FILENAME_SAFE_PATTERN.sub("_", candidate).strip("._")
    return sanitized or "file"


class StorageUploadInitService:
    def __init__(self) -> None:
        self._index_lock = Lock()
        self._indexes_initialized = False

    def _ensure_indexes(self) -> None:
        if self._indexes_initialized:
            return
        with self._index_lock:
            if self._indexes_initialized:
                return
            media_metadata_repository.initialize_indexes()
            self._indexes_initialized = True

    def _validate(self, *, kind: str, original_filename: str, mime_type: str) -> None:
        normalized_kind = str(kind or "").strip().lower()
        normalized_filename = str(original_filename or "").strip()
        normalized_mime = str(mime_type or "").strip()
        if normalized_kind not in _SUPPORTED_KINDS:
            raise StorageUploadInitError("kind must be one of: image, video, document", status_code=400)
        if normalized_filename == "":
            raise StorageUploadInitError("original_filename is required", status_code=400)
        if normalized_mime == "":
            raise StorageUploadInitError("mime_type is required", status_code=400)

    def _require_storage_config(self) -> tuple[str, str]:
        settings = load_settings()
        bucket = str(settings.storage_s3_bucket or "").strip()
        region = str(settings.storage_s3_region or "").strip()
        if bucket == "" or region == "":
            raise StorageUploadInitError("Storage S3 is not configured (STORAGE_S3_BUCKET/STORAGE_S3_REGION).", status_code=503)
        return bucket, region

    def build_storage_key(self, *, client_id: int, kind: MediaFileKind, media_id: str, original_filename: str) -> str:
        safe_filename = sanitize_filename(original_filename)
        return f"clients/{int(client_id)}/{str(kind)}/{str(media_id)}/{safe_filename}"

    def init_upload(
        self,
        *,
        client_id: int,
        kind: MediaFileKind,
        original_filename: str,
        mime_type: str,
        size_bytes: int | None = None,
        metadata: dict[str, Any] | None = None,
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        self._validate(kind=kind, original_filename=original_filename, mime_type=mime_type)
        bucket, region = self._require_storage_config()
        try:
            self._ensure_indexes()
        except (StorageUploadInitError, RuntimeError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Storage metadata repository is unavailable for upload initialization.") from exc

        # Validate folder_id before creating the S3 draft so a bad folder_id
        # aborts cleanly without leaving orphaned records.
        resolved_folder_id = str(folder_id or "").strip() or None
        if resolved_folder_id is not None:
            from app.services.media_folder_service import MediaFolderError, media_folder_service

            try:
                media_folder_service._require_folder(  # noqa: SLF001
                    client_id=int(client_id),
                    folder_id=resolved_folder_id,
                )
            except MediaFolderError as exc:
                raise StorageUploadInitError(str(exc), status_code=exc.status_code) from exc

        media_id = new_media_id()
        storage_key = self.build_storage_key(
            client_id=client_id,
            kind=kind,
            media_id=media_id,
            original_filename=original_filename,
        )

        try:
            draft = media_metadata_repository.create_draft(
                media_id=media_id,
                client_id=int(client_id),
                kind=kind,
                source="user_upload",
                original_filename=original_filename,
                mime_type=mime_type,
                size_bytes=size_bytes,
                metadata=metadata,
                storage_key=storage_key,
                storage_bucket=bucket,
                folder_id=resolved_folder_id,
                display_name=original_filename,
            )
        except (StorageUploadInitError, RuntimeError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Storage metadata draft creation failed for upload initialization.") from exc

        try:
            s3_client = get_s3_client()
            expires_in = int(get_s3_presigned_ttl_seconds())
            upload_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": storage_key,
                    "ContentType": str(mime_type),
                },
                ExpiresIn=expires_in,
                HttpMethod="PUT",
            )
        except StorageUploadInitError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StorageUploadInitError(f"Failed to generate S3 presigned URL: {exc}", status_code=503) from exc

        return {
            "media_id": draft.get("media_id"),
            "status": draft.get("status"),
            "bucket": bucket,
            "key": storage_key,
            "region": region,
            "upload": {
                "method": "PUT",
                "url": upload_url,
                "expires_in": expires_in,
                "headers": {
                    "Content-Type": str(mime_type),
                },
            },
        }


storage_upload_init_service = StorageUploadInitService()
