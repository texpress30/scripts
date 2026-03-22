from types import SimpleNamespace

from app.services import s3_provider


def test_get_s3_client_builds_cached_client(monkeypatch):
    created_clients: list[dict[str, object]] = []

    class FakeSession:
        def client(self, service_name: str, **kwargs):
            created_clients.append({"service_name": service_name, "kwargs": kwargs})
            return {"service_name": service_name, "kwargs": kwargs}

    monkeypatch.setattr(
        s3_provider,
        "load_settings",
        lambda: SimpleNamespace(
            storage_s3_region="us-east-1",
            storage_s3_endpoint_url="http://localhost:9000",
            storage_s3_bucket="assets",
            storage_s3_presigned_ttl_seconds=900,
        ),
    )
    monkeypatch.setattr(s3_provider, "_load_boto3_session_factory", lambda: FakeSession)
    s3_provider.clear_s3_provider_cache()

    first = s3_provider.get_s3_client()
    second = s3_provider.get_s3_client()

    assert first == second
    assert len(created_clients) == 1
    assert created_clients[0]["service_name"] == "s3"
    assert created_clients[0]["kwargs"] == {"region_name": "us-east-1", "endpoint_url": "http://localhost:9000"}
    assert s3_provider.get_s3_bucket_name() == "assets"
    assert s3_provider.get_s3_presigned_ttl_seconds() == 900
