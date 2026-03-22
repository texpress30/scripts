from app.core.config import load_settings


def test_load_settings_storage_foundation_defaults(monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.delenv("STORAGE_S3_BUCKET", raising=False)
    monkeypatch.delenv("STORAGE_S3_REGION", raising=False)
    monkeypatch.delenv("STORAGE_S3_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("STORAGE_S3_PRESIGNED_TTL_SECONDS", raising=False)
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("STORAGE_MEDIA_CLEANUP_BATCH_LIMIT", raising=False)
    monkeypatch.delenv("STORAGE_MEDIA_REMOTE_FETCH_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("STORAGE_MEDIA_REMOTE_FETCH_MAX_BYTES", raising=False)
    monkeypatch.delenv("STORAGE_MEDIA_SYNC_WORKER_REMOTE_INGEST_ENABLED", raising=False)
    monkeypatch.delenv("CREATIVE_WORKFLOW_MONGO_SHADOW_WRITE_ENABLED", raising=False)
    monkeypatch.delenv("CREATIVE_WORKFLOW_MONGO_READ_THROUGH_ENABLED", raising=False)
    monkeypatch.delenv("MONGO_DATABASE", raising=False)

    settings = load_settings()

    assert settings.storage_s3_bucket == ""
    assert settings.storage_s3_region == ""
    assert settings.storage_s3_endpoint_url == ""
    assert settings.storage_s3_presigned_ttl_seconds == 900
    assert settings.storage_media_cleanup_batch_limit == 100
    assert settings.storage_media_remote_fetch_timeout_seconds == 15
    assert settings.storage_media_remote_fetch_max_bytes == 10485760
    assert settings.storage_media_sync_worker_remote_ingest_enabled is False
    assert settings.creative_workflow_mongo_shadow_write_enabled is False
    assert settings.creative_workflow_mongo_read_through_enabled is False
    assert settings.mongo_uri == ""
    assert settings.mongo_database == ""


def test_load_settings_storage_foundation_custom_values(monkeypatch):
    monkeypatch.setenv("APP_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("STORAGE_S3_BUCKET", "assets-bucket")
    monkeypatch.setenv("STORAGE_S3_REGION", "eu-central-1")
    monkeypatch.setenv("STORAGE_S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("STORAGE_S3_PRESIGNED_TTL_SECONDS", "1200")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("STORAGE_MEDIA_CLEANUP_BATCH_LIMIT", "42")
    monkeypatch.setenv("STORAGE_MEDIA_REMOTE_FETCH_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("STORAGE_MEDIA_REMOTE_FETCH_MAX_BYTES", "2048")
    monkeypatch.setenv("STORAGE_MEDIA_SYNC_WORKER_REMOTE_INGEST_ENABLED", "true")
    monkeypatch.setenv("CREATIVE_WORKFLOW_MONGO_SHADOW_WRITE_ENABLED", "true")
    monkeypatch.setenv("CREATIVE_WORKFLOW_MONGO_READ_THROUGH_ENABLED", "true")
    monkeypatch.setenv("MONGO_DATABASE", "mcc_assets")

    settings = load_settings()

    assert settings.storage_s3_bucket == "assets-bucket"
    assert settings.storage_s3_region == "eu-central-1"
    assert settings.storage_s3_endpoint_url == "http://localhost:9000"
    assert settings.storage_s3_presigned_ttl_seconds == 1200
    assert settings.storage_media_cleanup_batch_limit == 42
    assert settings.storage_media_remote_fetch_timeout_seconds == 20
    assert settings.storage_media_remote_fetch_max_bytes == 2048
    assert settings.storage_media_sync_worker_remote_ingest_enabled is True
    assert settings.creative_workflow_mongo_shadow_write_enabled is True
    assert settings.creative_workflow_mongo_read_through_enabled is True
    assert settings.mongo_uri == "mongodb://localhost:27017"
    assert settings.mongo_database == "mcc_assets"
