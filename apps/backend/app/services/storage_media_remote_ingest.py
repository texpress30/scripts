from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

from app.core.config import load_settings
from app.services.storage_media_ingest import (
    StorageMediaIngestError,
    StorageMediaIngestResult,
    storage_media_ingest_service,
)
from app.services.storage_upload_init import sanitize_filename

_ALLOWED_SCHEMES: tuple[str, ...] = ("http", "https")
_BLOCKED_HOSTS: set[str] = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


class StorageMediaRemoteIngestError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = int(status_code)


class StorageMediaRemoteIngestService:
    def _settings(self):
        settings = load_settings()
        return {
            "timeout_seconds": max(1, int(settings.storage_media_remote_fetch_timeout_seconds)),
            "max_bytes": max(1, int(settings.storage_media_remote_fetch_max_bytes)),
        }

    def _validate_url(self, remote_url: str) -> tuple[str, str]:
        normalized_url = str(remote_url or "").strip()
        if normalized_url == "":
            raise StorageMediaRemoteIngestError("remote_url is required", status_code=400)

        parsed = urlparse(normalized_url)
        scheme = str(parsed.scheme or "").strip().lower()
        hostname = str(parsed.hostname or "").strip().lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise StorageMediaRemoteIngestError("remote_url must use http or https", status_code=400)
        if hostname == "":
            raise StorageMediaRemoteIngestError("remote_url host is invalid", status_code=400)
        if hostname in _BLOCKED_HOSTS:
            raise StorageMediaRemoteIngestError("remote_url host is not allowed", status_code=400)
        return normalized_url, hostname

    def _resolve_filename(self, *, explicit_filename: str | None, remote_url: str) -> str:
        normalized = str(explicit_filename or "").strip()
        if normalized != "":
            return normalized
        parsed = urlparse(remote_url)
        candidate = unquote(str(parsed.path or "").split("/")[-1]).strip()
        if candidate == "" or candidate in {".", ".."}:
            return "download.bin"
        safe = sanitize_filename(candidate)
        return safe or "download.bin"

    def _resolve_mime_type(self, *, explicit_mime_type: str | None, response_content_type: str | None) -> str:
        normalized = str(explicit_mime_type or "").strip()
        if normalized != "":
            return normalized
        response_value = str(response_content_type or "").strip()
        if response_value == "":
            return "application/octet-stream"
        return response_value.split(";")[0].strip() or "application/octet-stream"

    def upload_from_url(
        self,
        *,
        client_id: int,
        kind: str,
        source: str,
        remote_url: str,
        original_filename: str | None = None,
        mime_type: str | None = None,
        metadata: dict[str, Any] | None = None,
        request_headers: dict[str, str] | None = None,
    ) -> StorageMediaIngestResult:
        validated_url, _hostname = self._validate_url(remote_url)
        config = self._settings()
        timeout_seconds = int(config["timeout_seconds"])
        max_bytes = int(config["max_bytes"])

        headers = {str(k): str(v) for k, v in dict(request_headers or {}).items()}
        request = Request(url=validated_url, headers=headers)

        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
                status_code = int(getattr(response, "status", 200) or 200)
                if status_code < 200 or status_code >= 300:
                    raise StorageMediaRemoteIngestError(f"Remote fetch failed with status={status_code}", status_code=400)

                content_length_header = response.headers.get("Content-Length") if response.headers is not None else None
                if content_length_header is not None:
                    try:
                        content_length = int(str(content_length_header).strip())
                    except ValueError:
                        content_length = None
                    if content_length is not None and content_length > max_bytes:
                        raise StorageMediaRemoteIngestError("Remote file exceeds max allowed size", status_code=400)

                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise StorageMediaRemoteIngestError("Remote file exceeds max allowed size", status_code=400)
                response_content_type = response.headers.get("Content-Type") if response.headers is not None else None
        except StorageMediaRemoteIngestError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaRemoteIngestError(f"Remote fetch failed: {exc}", status_code=503) from exc

        resolved_filename = self._resolve_filename(explicit_filename=original_filename, remote_url=validated_url)
        resolved_mime_type = self._resolve_mime_type(explicit_mime_type=mime_type, response_content_type=response_content_type)

        try:
            return storage_media_ingest_service.upload_bytes(
                client_id=int(client_id),
                kind=kind,
                source=source,
                original_filename=resolved_filename,
                mime_type=resolved_mime_type,
                content=bytes(content),
                metadata=metadata,
            )
        except StorageMediaIngestError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise StorageMediaRemoteIngestError(f"Remote ingest failed: {exc}", status_code=503) from exc


storage_media_remote_ingest_service = StorageMediaRemoteIngestService()
