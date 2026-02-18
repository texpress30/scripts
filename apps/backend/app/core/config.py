"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    app_auth_secret: str
    openai_api_key: str
    google_ads_token: str
    meta_access_token: str
    bigquery_project_id: str
    database_url: str
    redis_url: str


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and (value is None or value.strip() == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value is None:
        raise RuntimeError(f"Environment variable {name} is not set and no default was provided")
    return value


def load_settings() -> Settings:
    return Settings(
        app_env=_get_env("APP_ENV", default="development"),
        app_host=_get_env("APP_HOST", default="0.0.0.0"),
        app_port=int(_get_env("APP_PORT", default="8000")),
        app_auth_secret=_get_env("APP_AUTH_SECRET", required=True),
        openai_api_key=_get_env("OPENAI_API_KEY", required=True),
        google_ads_token=_get_env("GOOGLE_ADS_TOKEN", required=True),
        meta_access_token=_get_env("META_ACCESS_TOKEN", required=True),
        bigquery_project_id=_get_env("BIGQUERY_PROJECT_ID", required=True),
        database_url=_get_env("DATABASE_URL", default="postgresql://postgres:postgres@localhost:5432/mcc"),
        redis_url=_get_env("REDIS_URL", default="redis://localhost:6379/0"),
    )
