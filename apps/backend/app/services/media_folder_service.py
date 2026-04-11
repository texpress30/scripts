from __future__ import annotations

from typing import Any

from app.services.media_folder_repository import (
    FOLDER_STATUS_ACTIVE,
    media_folder_repository,
)
from app.services.media_metadata_repository import media_metadata_repository

_MAX_FOLDER_NAME_LENGTH = 120
_MAX_FOLDER_DEPTH = 8


class MediaFolderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class MediaFolderService:
    def _normalize_name(self, name: str) -> str:
        normalized = str(name or "").strip()
        if normalized == "":
            raise MediaFolderError("Folder name is required", status_code=400)
        if len(normalized) > _MAX_FOLDER_NAME_LENGTH:
            raise MediaFolderError(
                f"Folder name must be at most {_MAX_FOLDER_NAME_LENGTH} characters",
                status_code=400,
            )
        if normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
            raise MediaFolderError("Folder name contains invalid characters", status_code=400)
        return normalized

    def _resolve_folder_depth(self, *, client_id: int, parent_folder_id: str | None) -> int:
        depth = 0
        current = parent_folder_id
        while current:
            parent_record = media_folder_repository.get_by_id(client_id=client_id, folder_id=current)
            if parent_record is None:
                raise MediaFolderError("Parent folder not found", status_code=404)
            if parent_record.get("status") != FOLDER_STATUS_ACTIVE:
                raise MediaFolderError("Parent folder not found", status_code=404)
            depth += 1
            if depth >= _MAX_FOLDER_DEPTH:
                raise MediaFolderError(
                    f"Maximum folder nesting depth of {_MAX_FOLDER_DEPTH} exceeded",
                    status_code=400,
                )
            current = parent_record.get("parent_folder_id") or None
        return depth

    def _ensure_unique_name(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
        name: str,
        exclude_folder_id: str | None = None,
    ) -> None:
        existing = media_folder_repository.find_active_by_name(
            client_id=client_id,
            parent_folder_id=parent_folder_id,
            name=name,
        )
        if existing is None:
            return
        if exclude_folder_id and existing.get("folder_id") == exclude_folder_id:
            return
        raise MediaFolderError(
            "A folder with this name already exists in the selected location",
            status_code=409,
        )

    def _require_folder(self, *, client_id: int, folder_id: str) -> dict[str, Any]:
        record = media_folder_repository.get_by_id(client_id=client_id, folder_id=folder_id)
        if record is None:
            raise MediaFolderError("Folder not found", status_code=404)
        if record.get("status") != FOLDER_STATUS_ACTIVE:
            raise MediaFolderError("Folder not found", status_code=404)
        return record

    def create_folder(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
        name: str,
    ) -> dict[str, Any]:
        if int(client_id) <= 0:
            raise MediaFolderError("client_id must be a positive integer", status_code=400)
        normalized_name = self._normalize_name(name)
        normalized_parent = str(parent_folder_id or "").strip() or None
        if normalized_parent:
            self._require_folder(client_id=client_id, folder_id=normalized_parent)
        self._resolve_folder_depth(client_id=client_id, parent_folder_id=normalized_parent)
        self._ensure_unique_name(
            client_id=client_id,
            parent_folder_id=normalized_parent,
            name=normalized_name,
        )
        return media_folder_repository.create(
            client_id=client_id,
            parent_folder_id=normalized_parent,
            name=normalized_name,
            system=False,
        )

    def list_children(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
    ) -> list[dict[str, Any]]:
        if int(client_id) <= 0:
            raise MediaFolderError("client_id must be a positive integer", status_code=400)
        normalized_parent = str(parent_folder_id or "").strip() or None
        if normalized_parent:
            self._require_folder(client_id=client_id, folder_id=normalized_parent)
        return media_folder_repository.list_children(
            client_id=client_id,
            parent_folder_id=normalized_parent,
        )

    def rename_folder(
        self,
        *,
        client_id: int,
        folder_id: str,
        name: str,
    ) -> dict[str, Any]:
        record = self._require_folder(client_id=client_id, folder_id=folder_id)
        if record.get("system"):
            raise MediaFolderError("System folders cannot be renamed", status_code=403)
        normalized_name = self._normalize_name(name)
        self._ensure_unique_name(
            client_id=client_id,
            parent_folder_id=record.get("parent_folder_id"),
            name=normalized_name,
            exclude_folder_id=folder_id,
        )
        updated = media_folder_repository.update(
            client_id=client_id,
            folder_id=folder_id,
            name=normalized_name,
        )
        if updated is None:
            raise MediaFolderError("Failed to rename folder", status_code=500)
        return updated

    def move_folder(
        self,
        *,
        client_id: int,
        folder_id: str,
        new_parent_folder_id: str | None,
    ) -> dict[str, Any]:
        record = self._require_folder(client_id=client_id, folder_id=folder_id)
        if record.get("system"):
            raise MediaFolderError("System folders cannot be moved", status_code=403)
        normalized_parent = str(new_parent_folder_id or "").strip() or None
        if normalized_parent == folder_id:
            raise MediaFolderError("A folder cannot be moved inside itself", status_code=400)
        if normalized_parent:
            self._require_folder(client_id=client_id, folder_id=normalized_parent)
            # Walk the parent chain to prevent cycles.
            current: str | None = normalized_parent
            while current:
                if current == folder_id:
                    raise MediaFolderError(
                        "A folder cannot be moved inside one of its descendants",
                        status_code=400,
                    )
                parent_record = media_folder_repository.get_by_id(
                    client_id=client_id,
                    folder_id=current,
                )
                current = (parent_record or {}).get("parent_folder_id") or None
            self._resolve_folder_depth(client_id=client_id, parent_folder_id=normalized_parent)
        self._ensure_unique_name(
            client_id=client_id,
            parent_folder_id=normalized_parent,
            name=str(record.get("name") or ""),
            exclude_folder_id=folder_id,
        )
        updated = media_folder_repository.update(
            client_id=client_id,
            folder_id=folder_id,
            parent_folder_id=normalized_parent,
            clear_parent=normalized_parent is None,
        )
        if updated is None:
            raise MediaFolderError("Failed to move folder", status_code=500)
        return updated

    def delete_folder(self, *, client_id: int, folder_id: str) -> dict[str, Any]:
        record = self._require_folder(client_id=client_id, folder_id=folder_id)
        if record.get("system"):
            raise MediaFolderError("System folders cannot be deleted", status_code=403)

        child_folders = media_folder_repository.list_children(
            client_id=client_id,
            parent_folder_id=folder_id,
        )
        if child_folders:
            raise MediaFolderError(
                "Folder is not empty. Move or delete child folders first.",
                status_code=409,
            )
        child_file_count = media_metadata_repository.count_for_client(
            client_id=client_id,
            folder_id=folder_id,
        )
        if child_file_count > 0:
            raise MediaFolderError(
                "Folder is not empty. Move or delete files inside first.",
                status_code=409,
            )

        deleted = media_folder_repository.soft_delete(
            client_id=client_id,
            folder_id=folder_id,
        )
        if deleted is None:
            raise MediaFolderError("Failed to delete folder", status_code=500)
        return deleted

    def list_ancestors(
        self,
        *,
        client_id: int,
        folder_id: str,
    ) -> list[dict[str, Any]]:
        """Return the path from the root to the given folder as an ordered list
        (root-most first, target last). Each entry is a folder record, so the
        UI can rebuild the breadcrumb after a page reload."""
        record = self._require_folder(client_id=client_id, folder_id=folder_id)
        chain: list[dict[str, Any]] = [record]
        current_parent: str | None = record.get("parent_folder_id") or None
        depth_guard = 0
        while current_parent:
            depth_guard += 1
            if depth_guard > _MAX_FOLDER_DEPTH + 2:
                break
            parent_record = media_folder_repository.get_by_id(
                client_id=client_id,
                folder_id=current_parent,
            )
            if parent_record is None:
                break
            if parent_record.get("status") != FOLDER_STATUS_ACTIVE:
                break
            chain.append(parent_record)
            current_parent = parent_record.get("parent_folder_id") or None
        chain.reverse()
        return chain

    def ensure_system_folder(
        self,
        *,
        client_id: int,
        parent_folder_id: str | None,
        name: str,
    ) -> dict[str, Any]:
        """Create (or fetch) a system folder — idempotent, used by auto-ingest pipelines."""
        if int(client_id) <= 0:
            raise MediaFolderError("client_id must be a positive integer", status_code=400)
        normalized_name = self._normalize_name(name)
        normalized_parent = str(parent_folder_id or "").strip() or None
        existing = media_folder_repository.find_active_by_name(
            client_id=client_id,
            parent_folder_id=normalized_parent,
            name=normalized_name,
        )
        if existing is not None:
            return existing
        if normalized_parent:
            self._require_folder(client_id=client_id, folder_id=normalized_parent)
        self._resolve_folder_depth(client_id=client_id, parent_folder_id=normalized_parent)
        return media_folder_repository.create(
            client_id=client_id,
            parent_folder_id=normalized_parent,
            name=normalized_name,
            system=True,
        )


media_folder_service = MediaFolderService()
