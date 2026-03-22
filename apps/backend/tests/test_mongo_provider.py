from types import SimpleNamespace

from app.services import mongo_provider


def test_get_mongo_client_and_database_are_cached(monkeypatch):
    class FakeMongoClient:
        instances: list[dict[str, object]] = []

        def __init__(self, uri: str, connect: bool = True):
            self.uri = uri
            self.connect = connect
            FakeMongoClient.instances.append({"uri": uri, "connect": connect})

        def __getitem__(self, name: str):
            return {"db_name": name, "uri": self.uri}

    monkeypatch.setattr(
        mongo_provider,
        "load_settings",
        lambda: SimpleNamespace(
            mongo_uri="mongodb://localhost:27017",
            mongo_database="creative_assets",
        ),
    )
    monkeypatch.setattr(mongo_provider, "_load_mongo_client_class", lambda: FakeMongoClient)
    mongo_provider.clear_mongo_provider_cache()

    first = mongo_provider.get_mongo_client()
    second = mongo_provider.get_mongo_client()
    db = mongo_provider.get_mongo_database()

    assert first is second
    assert len(FakeMongoClient.instances) == 1
    assert FakeMongoClient.instances[0] == {"uri": "mongodb://localhost:27017", "connect": False}
    assert db == {"db_name": "creative_assets", "uri": "mongodb://localhost:27017"}


def test_get_mongo_database_returns_none_when_config_missing(monkeypatch):
    monkeypatch.setattr(
        mongo_provider,
        "load_settings",
        lambda: SimpleNamespace(
            mongo_uri="",
            mongo_database="",
        ),
    )
    mongo_provider.clear_mongo_provider_cache()

    assert mongo_provider.get_mongo_client() is None
    assert mongo_provider.get_mongo_database() is None
