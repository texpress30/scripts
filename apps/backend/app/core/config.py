"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    app_auth_secret: str
    app_login_email: str
    app_login_password: str
    frontend_base_url: str
    auth_reset_token_ttl_minutes: int
    openai_api_key: str
    google_ads_token: str
    google_ads_mode: str
    google_ads_client_id: str
    google_ads_client_secret: str
    google_ads_developer_token: str
    google_ads_manager_customer_id: str
    google_ads_redirect_uri: str
    google_ads_refresh_token: str
    integration_secret_encryption_key: str
    google_ads_customer_ids_csv: str
    google_ads_api_version: str
    google_ads_ui_rolling_sync_days: int
    google_ads_ui_rolling_chunk_days: int
    google_ads_historical_backfill_start_date: date
    meta_access_token: str
    meta_app_id: str
    meta_app_secret: str
    meta_redirect_uri: str
    meta_api_version: str
    bigquery_project_id: str
    database_url: str
    redis_url: str
    storage_s3_bucket: str
    storage_s3_region: str
    storage_s3_endpoint_url: str
    storage_s3_presigned_ttl_seconds: int
    storage_media_cleanup_batch_limit: int
    storage_media_remote_fetch_timeout_seconds: int
    storage_media_remote_fetch_max_bytes: int
    storage_media_sync_worker_remote_ingest_enabled: bool
    mongo_uri: str
    mongo_database: str
    cors_origins: tuple[str, ...]
    cors_origin_regex: str | None
    ff_tiktok_integration: bool
    tiktok_app_id: str
    tiktok_app_secret: str
    tiktok_redirect_uri: str
    tiktok_api_base_url: str
    tiktok_api_version: str
    ff_pinterest_integration: bool
    ff_snapchat_integration: bool
    tiktok_sync_retry_attempts: int
    tiktok_sync_backoff_ms: int
    tiktok_sync_force_transient_failures: int
    pinterest_sync_retry_attempts: int
    pinterest_sync_backoff_ms: int
    pinterest_sync_force_transient_failures: int
    snapchat_sync_retry_attempts: int
    snapchat_sync_backoff_ms: int
    snapchat_sync_force_transient_failures: int
    sync_run_repair_stale_minutes: int
    mailgun_api_key: str
    mailgun_domain: str
    mailgun_base_url: str
    mailgun_from_email: str
    mailgun_from_name: str
    mailgun_reply_to: str
    mailgun_enabled: bool
    creative_workflow_mongo_shadow_write_enabled: bool
    creative_workflow_mongo_core_writes_source_enabled: bool
    creative_workflow_mongo_derived_writes_source_enabled: bool
    creative_workflow_mongo_publish_persist_enabled: bool
    creative_workflow_mongo_read_through_enabled: bool
    creative_workflow_mongo_reads_source_enabled: bool
    creative_workflow_media_id_linking_enabled: bool
    ai_recommendations_mongo_source_enabled: bool
    ff_feed_management_enabled: bool


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


def _parse_bool_env_alias(names: tuple[str, ...], default: bool = False) -> bool:
    for candidate in names:
        raw = os.environ.get(candidate)
        if raw is None:
            continue
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    return default




def _parse_int_env(name: str, default: int) -> int:
    raw = _get_env(name, default=str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_positive_int_env(name: str, default: int) -> int:
    value = _parse_int_env(name, default)
    if value <= 0:
        return default
    return value


def _parse_iso_date_env(name: str, default: str) -> date:
    raw = _get_env(name, default=default).strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return date.fromisoformat(default)

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
        frontend_base_url=_get_env("FRONTEND_BASE_URL", default="http://localhost:3000"),
        auth_reset_token_ttl_minutes=_parse_positive_int_env("AUTH_RESET_TOKEN_TTL_MINUTES", default=60),
        openai_api_key=_get_env("OPENAI_API_KEY", default=""),
        google_ads_token=_get_env("GOOGLE_ADS_TOKEN", default=""),
        google_ads_mode=_get_env("GOOGLE_ADS_MODE", default="mock").strip().lower(),
        google_ads_client_id=_get_env("GOOGLE_ADS_CLIENT_ID", default=""),
        google_ads_client_secret=_get_env("GOOGLE_ADS_CLIENT_SECRET", default=""),
        google_ads_developer_token=_get_env("GOOGLE_ADS_DEVELOPER_TOKEN", default=""),
        google_ads_manager_customer_id=_get_env("GOOGLE_ADS_MANAGER_CUSTOMER_ID", default=""),
        google_ads_redirect_uri=_get_env("GOOGLE_ADS_REDIRECT_URI", default=""),
        google_ads_refresh_token=_get_env("GOOGLE_ADS_REFRESH_TOKEN", default=""),
        integration_secret_encryption_key=_get_env("INTEGRATION_SECRET_ENCRYPTION_KEY", default=""),
        google_ads_customer_ids_csv=_get_env("GOOGLE_ADS_CUSTOMER_IDS_CSV", default=""),
        google_ads_api_version=_get_env("GOOGLE_ADS_API_VERSION", default="v23"),
        google_ads_ui_rolling_sync_days=_parse_positive_int_env("GOOGLE_ADS_UI_ROLLING_SYNC_DAYS", default=7),
        google_ads_ui_rolling_chunk_days=_parse_positive_int_env("GOOGLE_ADS_UI_ROLLING_CHUNK_DAYS", default=7),
        google_ads_historical_backfill_start_date=_parse_iso_date_env("GOOGLE_ADS_HISTORICAL_BACKFILL_START_DATE", default="2024-01-09"),
        meta_access_token=_get_env("META_ACCESS_TOKEN", default=""),
        meta_app_id=_get_env("META_APP_ID", default=""),
        meta_app_secret=_get_env("META_APP_SECRET", default=""),
        meta_redirect_uri=_get_env("META_REDIRECT_URI", default=""),
        meta_api_version=_get_env("META_API_VERSION", default="v20.0"),
        bigquery_project_id=_get_env("BIGQUERY_PROJECT_ID", default=""),
        database_url=_get_env("DATABASE_URL", default="postgresql://postgres:postgres@localhost:5432/mcc"),
        redis_url=_get_env("REDIS_URL", default="redis://localhost:6379/0"),
        storage_s3_bucket=_get_env("STORAGE_S3_BUCKET", default=""),
        storage_s3_region=_get_env("STORAGE_S3_REGION", default=""),
        storage_s3_endpoint_url=_get_env("STORAGE_S3_ENDPOINT_URL", default=""),
        storage_s3_presigned_ttl_seconds=_parse_positive_int_env("STORAGE_S3_PRESIGNED_TTL_SECONDS", default=900),
        storage_media_cleanup_batch_limit=_parse_positive_int_env("STORAGE_MEDIA_CLEANUP_BATCH_LIMIT", default=100),
        storage_media_remote_fetch_timeout_seconds=_parse_positive_int_env("STORAGE_MEDIA_REMOTE_FETCH_TIMEOUT_SECONDS", default=15),
        storage_media_remote_fetch_max_bytes=_parse_positive_int_env("STORAGE_MEDIA_REMOTE_FETCH_MAX_BYTES", default=10485760),
        storage_media_sync_worker_remote_ingest_enabled=_parse_bool_env("STORAGE_MEDIA_SYNC_WORKER_REMOTE_INGEST_ENABLED", default=False),
        mongo_uri=_get_env("MONGO_URI", default=""),
        mongo_database=_get_env("MONGO_DATABASE", default=""),
        cors_origins=_parse_csv_env("APP_CORS_ORIGINS", default="http://localhost:3000,http://127.0.0.1:3000"),
        cors_origin_regex=_safe_regex_env("APP_CORS_ORIGIN_REGEX", default=r"https://.*\.vercel\.app"),
        ff_tiktok_integration=_parse_bool_env_alias(("TIKTOK_SYNC_ENABLED", "FF_TIKTOK_INTEGRATION"), default=False),
        tiktok_app_id=_get_env("TIKTOK_APP_ID", default=""),
        tiktok_app_secret=_get_env("TIKTOK_APP_SECRET", default=""),
        tiktok_redirect_uri=_get_env("TIKTOK_REDIRECT_URI", default=""),
        tiktok_api_base_url=_get_env("TIKTOK_API_BASE_URL", default="https://business-api.tiktok.com"),
        tiktok_api_version=_get_env("TIKTOK_API_VERSION", default="v1.3"),
        ff_pinterest_integration=_parse_bool_env("FF_PINTEREST_INTEGRATION", default=False),
        ff_snapchat_integration=_parse_bool_env("FF_SNAPCHAT_INTEGRATION", default=False),
        tiktok_sync_retry_attempts=_parse_int_env("TIKTOK_SYNC_RETRY_ATTEMPTS", default=2),
        tiktok_sync_backoff_ms=_parse_int_env("TIKTOK_SYNC_BACKOFF_MS", default=75),
        tiktok_sync_force_transient_failures=_parse_int_env("TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES", default=0),
        pinterest_sync_retry_attempts=_parse_int_env("PINTEREST_SYNC_RETRY_ATTEMPTS", default=2),
        pinterest_sync_backoff_ms=_parse_int_env("PINTEREST_SYNC_BACKOFF_MS", default=75),
        pinterest_sync_force_transient_failures=_parse_int_env("PINTEREST_SYNC_FORCE_TRANSIENT_FAILURES", default=0),
        snapchat_sync_retry_attempts=_parse_int_env("SNAPCHAT_SYNC_RETRY_ATTEMPTS", default=2),
        snapchat_sync_backoff_ms=_parse_int_env("SNAPCHAT_SYNC_BACKOFF_MS", default=75),
        snapchat_sync_force_transient_failures=_parse_int_env("SNAPCHAT_SYNC_FORCE_TRANSIENT_FAILURES", default=0),
        sync_run_repair_stale_minutes=_parse_positive_int_env("SYNC_RUN_REPAIR_STALE_MINUTES", default=30),
        mailgun_api_key=_get_env("MAILGUN_API_KEY", default=""),
        mailgun_domain=_get_env("MAILGUN_DOMAIN", default=""),
        mailgun_base_url=_get_env("MAILGUN_BASE_URL", default="https://api.mailgun.net"),
        mailgun_from_email=_get_env("MAILGUN_FROM_EMAIL", default=""),
        mailgun_from_name=_get_env("MAILGUN_FROM_NAME", default=""),
        mailgun_reply_to=_get_env("MAILGUN_REPLY_TO", default=""),
        mailgun_enabled=_parse_bool_env("MAILGUN_ENABLED", default=True),
        creative_workflow_mongo_shadow_write_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_SHADOW_WRITE_ENABLED", default=False),
        creative_workflow_mongo_core_writes_source_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_CORE_WRITES_SOURCE_ENABLED", default=False),
        creative_workflow_mongo_derived_writes_source_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_DERIVED_WRITES_SOURCE_ENABLED", default=False),
        creative_workflow_mongo_publish_persist_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_PUBLISH_PERSIST_ENABLED", default=False),
        creative_workflow_mongo_read_through_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_READ_THROUGH_ENABLED", default=False),
        creative_workflow_mongo_reads_source_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MONGO_READS_SOURCE_ENABLED", default=False),
        creative_workflow_media_id_linking_enabled=_parse_bool_env("CREATIVE_WORKFLOW_MEDIA_ID_LINKING_ENABLED", default=False),
        ai_recommendations_mongo_source_enabled=_parse_bool_env("AI_RECOMMENDATIONS_MONGO_SOURCE_ENABLED", default=False),
        ff_feed_management_enabled=_parse_bool_env("FF_FEED_MANAGEMENT_ENABLED", default=False),
    )
