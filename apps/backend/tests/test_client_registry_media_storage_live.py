from __future__ import annotations

import pytest

from app.services import client_registry as client_registry_module
from app.services.client_registry import client_registry_service


@pytest.fixture(autouse=True)
def _reset_registry():
    client_registry_service.clear()
    yield
    client_registry_service.clear()


def _seed_clients(ids_and_names: list[tuple[str, str]]) -> list[int]:
    created_ids: list[int] = []
    for name, email in ids_and_names:
        record = client_registry_service.add_client(name=name, owner_email=email)
        created_ids.append(int(record["id"]))
    return created_ids


def test_list_media_storage_usage_overlays_live_mongo_bytes(monkeypatch):
    ids = _seed_clients(
        [
            ("ROC Automobile", "owner@roc.ro"),
            ("Scoala Montessori", "hq@scoala.ro"),
            ("Kumperi Ltd", "ops@kumperi.ro"),
        ]
    )

    captured: dict[str, object] = {}

    class _FakeRepo:
        def summarize_for_clients(self, *, client_ids: list[int]) -> dict[int, dict[str, int]]:
            captured["client_ids"] = list(client_ids)
            return {
                ids[0]: {"total_files": 3, "total_bytes": 7_340_032},  # 7 MB
                ids[2]: {"total_files": 1, "total_bytes": 524_288},    # 0.5 MB
                # ids[1] intentionally missing → should render as 0.
            }

    # Patch the module-level singleton that `_overlay_live_media_bytes` imports
    # lazily; importlib returns the already-bound module instance so we must
    # install the fake on the real module.
    import app.services.media_metadata_repository as repository_module

    monkeypatch.setattr(repository_module, "media_metadata_repository", _FakeRepo())

    items, total = client_registry_service.list_media_storage_usage(
        search="", page=1, page_size=10
    )

    assert total == 3
    assert set(captured["client_ids"]) == set(ids)  # the batch call received the page ids
    by_id = {int(item["id"]): item for item in items}
    assert by_id[ids[0]]["media_storage_bytes"] == 7_340_032
    assert by_id[ids[1]]["media_storage_bytes"] == 0  # absent from live summary
    assert by_id[ids[2]]["media_storage_bytes"] == 524_288


def test_list_media_storage_usage_falls_back_when_mongo_unavailable(monkeypatch):
    ids = _seed_clients([("ROC Automobile", "owner@roc.ro")])

    class _FailingRepo:
        def summarize_for_clients(self, *, client_ids: list[int]) -> dict[int, dict[str, int]]:
            raise RuntimeError("Mongo unavailable")

    import app.services.media_metadata_repository as repository_module

    monkeypatch.setattr(repository_module, "media_metadata_repository", _FailingRepo())

    items, total = client_registry_service.list_media_storage_usage(
        search="", page=1, page_size=10
    )
    assert total == 1
    # test-mode default is whatever the stored column holds (0), but the
    # important assertion is that the call did not raise.
    assert int(items[0]["media_storage_bytes"]) >= 0
