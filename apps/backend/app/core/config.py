"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    app_auth_secret: str
    app_login_email: str
    app_login_password: str
    openai_api_key: str
    google_ads_token: str
    meta_access_token: str
    bigquery_project_id: str
    database_url: str
    redis_url: str
    cors_origins: tuple[str, ...]
    cors_origin_regex: str | None
    ff_tiktok_integration: bool
    ff_pinterest_integration: bool
    tiktok_sync_retry_attempts: int
    tiktok_sync_backoff_ms: int
    tiktok_sync_force_transient_failures: int


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and (value is None or value.strip() == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    if value is None:
        raise RuntimeError(f"Environment variable {name} is not set and no default was provided")
    return value


def _parse_csv_env(name: str, default: str) -> tuple[str, ...]:
    raw = _get_env(name, default=default)
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = _get_env(name, default="1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}




def _parse_int_env(name: str, default: int) -> int:
    raw = _get_env(name, default=str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default

def _safe_regex_env(name: str, default: str) -> str | None:
    value = _get_env(name, default=default).strip()
    if value == "":
        return None
    try:
        re.compile(value)
        return value
    except re.error:
        return default


def load_settings() -> Settings:
    return Settings(
        app_env=_get_env("APP_ENV", default="development"),
        app_host=_get_env("APP_HOST", default="0.0.0.0"),
        app_port=int(_get_env("APP_PORT", default="8000")),
        app_auth_secret=_get_env("APP_AUTH_SECRET", required=True),
        app_login_email=_get_env("APP_LOGIN_EMAIL", default="admin@example.com"),
        app_login_password=_get_env("APP_LOGIN_PASSWORD", default="admin123"),
        openai_api_key=_get_env("OPENAI_API_KEY", default=""),
        google_ads_token=_get_env("GOOGLE_ADS_TOKEN", default=""),
        meta_access_token=_get_env("META_ACCESS_TOKEN", default=""),
        bigquery_project_id=_get_env("BIGQUERY_PROJECT_ID", default=""),
        database_url=_get_env("DATABASE_URL", default="postgresql://postgres:postgres@localhost:5432/mcc"),
        redis_url=_get_env("REDIS_URL", default="redis://localhost:6379/0"),
        cors_origins=_parse_csv_env("APP_CORS_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000"),
        cors_origin_regex=_safe_regex_env("APP_CORS_ORIGIN_REGEX", default=r"https://.*\.vercel\.app"),
        ff_tiktok_integration=_parse_bool_env("FF_TIKTOK_INTEGRATION", default=False),
        ff_pinterest_integration=_parse_bool_env("FF_PINTEREST_INTEGRATION", default=False),
        tiktok_sync_retry_attempts=_parse_int_env("TIKTOK_SYNC_RETRY_ATTEMPTS", default=2),
        tiktok_sync_backoff_ms=_parse_int_env("TIKTOK_SYNC_BACKOFF_MS", default=75),
        tiktok_sync_force_transient_failures=_parse_int_env("TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES", default=0),
    )
