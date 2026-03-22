from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import load_settings


def _load_boto3_session_factory() -> Any:
    from boto3.session import Session

    return Session


@lru_cache(maxsize=8)
def _build_s3_client(*, region: str, endpoint_url: str | None) -> Any:
    session_factory = _load_boto3_session_factory()
    session = session_factory()
    client_kwargs: dict[str, Any] = {}
    normalized_region = str(region or "").strip()
    normalized_endpoint = str(endpoint_url or "").strip()
    if normalized_region != "":
        client_kwargs["region_name"] = normalized_region
    if normalized_endpoint != "":
        client_kwargs["endpoint_url"] = normalized_endpoint
    return session.client("s3", **client_kwargs)


def get_s3_client() -> Any:
    settings = load_settings()
    return _build_s3_client(
        region=settings.storage_s3_region,
        endpoint_url=settings.storage_s3_endpoint_url or None,
    )


def get_s3_bucket_name() -> str:
    return str(load_settings().storage_s3_bucket or "").strip()


def get_s3_presigned_ttl_seconds() -> int:
    return int(load_settings().storage_s3_presigned_ttl_seconds)


def clear_s3_provider_cache() -> None:
    _build_s3_client.cache_clear()
