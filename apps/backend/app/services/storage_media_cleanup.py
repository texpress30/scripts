from __future__ import annotations

from typing import Any

from app.services.media_metadata_repository import media_metadata_repository
from app.services.s3_provider import get_s3_client


class StorageMediaCleanupError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


def _object_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("nosuchkey", "notfound", "404", "no such key"))


class StorageMediaCleanupService:
    def run_batch(self, *, limit: int = 100) -> dict[str, Any]:
        resolved_limit = max(1, int(limit))
        try:
            candidates = media_metadata_repository.list_cleanup_candidates(limit=resolved_limit)
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaCleanupError(f"Failed to load cleanup candidates: {exc}", status_code=503) from exc

        if len(candidates) == 0:
            return {
                "processed": 0,
                "purged": 0,
                "skipped": 0,
                "failed": 0,
                "items": [],
            }

        try:
            s3_client = get_s3_client()
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaCleanupError(f"S3 provider unavailable: {exc}", status_code=503) from exc

        items: list[dict[str, Any]] = []
        purged_count = 0
        skipped_count = 0
        failed_count = 0

        for record in candidates:
            media_id = str(record.get("media_id") or "")
            storage = record.get("storage") if isinstance(record.get("storage"), dict) else {}
            bucket = str(storage.get("bucket") or "").strip()
            key = str(storage.get("key") or "").strip()
            version_id = str(storage.get("version_id") or "").strip() or None

            if bucket == "" or key == "":
                skipped_count += 1
                items.append({"media_id": media_id, "outcome": "skipped", "reason": "storage_incomplete"})
                continue

            delete_params: dict[str, Any] = {"Bucket": bucket, "Key": key}
            if version_id is not None:
                delete_params["VersionId"] = version_id

            delete_succeeded = False
            try:
                s3_client.delete_object(**delete_params)
                delete_succeeded = True
            except Exception as exc:  # noqa: BLE001
                if _object_missing_error(exc):
                    delete_succeeded = True
                else:
                    failed_count += 1
                    items.append({"media_id": media_id, "outcome": "failed", "reason": f"s3_delete_failed: {exc}"})

            if not delete_succeeded:
                continue

            try:
                updated = media_metadata_repository.mark_purged(media_id=media_id)
            except Exception as exc:  # noqa: BLE001
                failed_count += 1
                items.append({"media_id": media_id, "outcome": "failed", "reason": f"mongo_mark_purged_failed: {exc}"})
                continue

            if updated is None:
                failed_count += 1
                items.append({"media_id": media_id, "outcome": "failed", "reason": "mongo_mark_purged_failed: empty_result"})
                continue

            purged_count += 1
            items.append({"media_id": media_id, "outcome": "purged"})

        return {
            "processed": len(candidates),
            "purged": purged_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "items": items,
        }


storage_media_cleanup_service = StorageMediaCleanupService()
