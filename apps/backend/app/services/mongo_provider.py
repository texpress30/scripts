from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.core.config import load_settings


def _load_mongo_client_class() -> Any:
    from pymongo import MongoClient

    return MongoClient


@lru_cache(maxsize=4)
def _build_mongo_client(uri: str) -> Any:
    mongo_client_class = _load_mongo_client_class()
    return mongo_client_class(uri, connect=False)


def get_mongo_client() -> Any | None:
    settings = load_settings()
    mongo_uri = str(settings.mongo_uri or "").strip()
    if mongo_uri == "":
        return None
    return _build_mongo_client(mongo_uri)


def get_mongo_database() -> Any | None:
    settings = load_settings()
    mongo_database = str(settings.mongo_database or "").strip()
    mongo_client = get_mongo_client()
    if mongo_client is None or mongo_database == "":
        return None
    return mongo_client[mongo_database]


def get_mongo_collection(collection_name: str) -> Any | None:
    normalized_collection_name = str(collection_name or "").strip()
    if normalized_collection_name == "":
        raise ValueError("collection_name is required")
    mongo_db = get_mongo_database()
    if mongo_db is None:
        return None
    return mongo_db[normalized_collection_name]


def clear_mongo_provider_cache() -> None:
    _build_mongo_client.cache_clear()
