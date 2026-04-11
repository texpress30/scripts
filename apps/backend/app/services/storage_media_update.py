from __future__ import annotations

from typing import Any

from app.services.media_folder_service import MediaFolderError, media_folder_service
from app.services.media_metadata_models import MEDIA_FILE_STATUS_PURGED
from app.services.media_metadata_repository import media_metadata_repository


_MAX_DISPLAY_NAME_LENGTH = 255


class StorageMediaUpdateError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class StorageMediaUpdateService:
    def update_media(
        self,
        *,
        client_id: int,
        media_id: str,
        display_name: str | None = None,
        folder_id: str | None = None,
        clear_folder: bool = False,
    ) -> dict[str, Any]:
        normalized_client_id = int(client_id)
        if normalized_client_id <= 0:
            raise StorageMediaUpdateError("client_id must be a positive integer", status_code=400)

        normalized_media_id = str(media_id or "").strip()
        if normalized_media_id == "":
            raise StorageMediaUpdateError("media_id is required", status_code=400)

        record = media_metadata_repository.get_by_media_id(normalized_media_id)
        if record is None:
            raise StorageMediaUpdateError("Media record not found", status_code=404)
        if int(record.get("client_id") or 0) != normalized_client_id:
            raise StorageMediaUpdateError("Media record not found", status_code=404)
        status = str(record.get("status") or "").strip().lower()
        if status == MEDIA_FILE_STATUS_PURGED:
            raise StorageMediaUpdateError("Media record not found", status_code=404)

        effective_display_name: str | None = None
        if display_name is not None:
            candidate = str(display_name or "").strip()
            if candidate == "":
                raise StorageMediaUpdateError("display_name cannot be empty", status_code=400)
            if len(candidate) > _MAX_DISPLAY_NAME_LENGTH:
                raise StorageMediaUpdateError(
                    f"display_name must be at most {_MAX_DISPLAY_NAME_LENGTH} characters",
                    status_code=400,
                )
            effective_display_name = candidate

        effective_clear_folder = bool(clear_folder)
        effective_folder_id: str | None = None
        if folder_id is not None and not clear_folder:
            candidate_folder = str(folder_id or "").strip()
            if candidate_folder == "":
                # empty string is treated as "move to root"
                effective_clear_folder = True
            else:
                try:
                    folder_record = media_folder_service._require_folder(  # noqa: SLF001
                        client_id=normalized_client_id,
                        folder_id=candidate_folder,
                    )
                except MediaFolderError as exc:
                    raise StorageMediaUpdateError(str(exc), status_code=exc.status_code) from exc
                effective_folder_id = str(folder_record.get("folder_id") or "").strip() or None

        if effective_display_name is None and effective_folder_id is None and not effective_clear_folder:
            return record

        updated = media_metadata_repository.update_attributes(
            media_id=normalized_media_id,
            display_name=effective_display_name,
            folder_id=effective_folder_id,
            clear_folder=effective_clear_folder,
        )
        if updated is None:
            raise StorageMediaUpdateError("Failed to update media record", status_code=500)
        return updated


storage_media_update_service = StorageMediaUpdateService()
