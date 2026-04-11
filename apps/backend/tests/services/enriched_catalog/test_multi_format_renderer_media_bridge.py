from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.enriched_catalog import multi_format_renderer as renderer_module


class _FakeFolderService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._ids = 0

    def ensure_system_folder(self, *, client_id, parent_folder_id, name):  # noqa: D401 — mock shape
        self._ids += 1
        self.calls.append(
            {
                "client_id": client_id,
                "parent_folder_id": parent_folder_id,
                "name": name,
            }
        )
        return {
            "folder_id": f"folder-{self._ids}",
            "client_id": client_id,
            "parent_folder_id": parent_folder_id,
            "name": name,
            "system": True,
            "status": "active",
        }


class _FakeIngestService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def register_existing_s3_asset(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "media_id": f"mid-{len(self.calls)}",
            **kwargs,
            "status": "ready",
        }


@pytest.fixture
def fake_bridge(monkeypatch):
    fake_folder = _FakeFolderService()
    fake_ingest = _FakeIngestService()

    import app.services.media_folder_service as folder_module
    import app.services.storage_media_ingest as ingest_module
    import app.services.s3_provider as s3_module

    monkeypatch.setattr(folder_module, "media_folder_service", fake_folder)
    monkeypatch.setattr(ingest_module, "storage_media_ingest_service", fake_ingest)
    monkeypatch.setattr(s3_module, "get_s3_bucket_name", lambda: "media-bucket")
    return fake_folder, fake_ingest


def test_bridge_creates_system_folders_and_registers_asset(fake_bridge):
    folder_svc, ingest_svc = fake_bridge

    renderer_module._bridge_render_to_media_library(
        subaccount_id=42,
        feed_name="Spring Collection",
        output_feed_id="of-1",
        template_id="tpl-1",
        product_id="prod-9",
        format_label="1080x1350",
        s3_key="enriched-catalog/of-1/tpl-1/prod-9.png",
        image_url="https://media-bucket.s3.amazonaws.com/enriched-catalog/of-1/tpl-1/prod-9.png",
    )

    assert len(folder_svc.calls) == 2
    assert folder_svc.calls[0]["name"] == "Enriched Catalog"
    assert folder_svc.calls[0]["parent_folder_id"] is None
    assert folder_svc.calls[1]["name"] == "Spring Collection"
    assert folder_svc.calls[1]["parent_folder_id"] == "folder-1"

    assert len(ingest_svc.calls) == 1
    call = ingest_svc.calls[0]
    assert call["client_id"] == 42
    assert call["kind"] == "image"
    assert call["source"] == "enriched_catalog"
    assert call["bucket"] == "media-bucket"
    assert call["key"] == "enriched-catalog/of-1/tpl-1/prod-9.png"
    assert call["folder_id"] == "folder-2"
    assert call["metadata"]["enriched_catalog"]["output_feed_id"] == "of-1"
    assert call["metadata"]["enriched_catalog"]["template_id"] == "tpl-1"
    assert call["metadata"]["enriched_catalog"]["product_id"] == "prod-9"


def test_bridge_is_noop_without_subaccount_id(fake_bridge):
    folder_svc, ingest_svc = fake_bridge
    renderer_module._bridge_render_to_media_library(
        subaccount_id=None,
        feed_name="Ignored",
        output_feed_id="of-2",
        template_id="tpl-2",
        product_id="p",
        format_label="x",
        s3_key="k",
        image_url="u",
    )
    assert folder_svc.calls == []
    assert ingest_svc.calls == []


def test_bridge_swallows_ingest_errors(fake_bridge, caplog):
    folder_svc, ingest_svc = fake_bridge

    def _raise(**kwargs):
        raise RuntimeError("Mongo down")

    ingest_svc.register_existing_s3_asset = _raise  # type: ignore[assignment]

    caplog.clear()
    renderer_module._bridge_render_to_media_library(
        subaccount_id=42,
        feed_name="Whatever",
        output_feed_id="of-3",
        template_id="tpl-3",
        product_id="p",
        format_label="x",
        s3_key="k",
        image_url="u",
    )
    # No exception raised — the bridge never breaks rendering.
    assert any("enriched_catalog_media_bridge_error" in message for message in caplog.messages)


def test_bridge_truncates_long_feed_name(fake_bridge):
    folder_svc, _ = fake_bridge
    long_name = "a" * 500

    renderer_module._bridge_render_to_media_library(
        subaccount_id=42,
        feed_name=long_name,
        output_feed_id="of-4",
        template_id="tpl-4",
        product_id="p",
        format_label="x",
        s3_key="enriched-catalog/of-4/tpl-4/p.png",
        image_url="u",
    )

    feed_folder_call = folder_svc.calls[1]
    assert len(str(feed_folder_call["name"])) <= 120


def test_bridge_noop_when_bucket_or_key_missing(monkeypatch, fake_bridge):
    folder_svc, ingest_svc = fake_bridge
    import app.services.s3_provider as s3_module

    monkeypatch.setattr(s3_module, "get_s3_bucket_name", lambda: "")

    renderer_module._bridge_render_to_media_library(
        subaccount_id=42,
        feed_name="Whatever",
        output_feed_id="of-5",
        template_id="tpl-5",
        product_id="p",
        format_label="x",
        s3_key="enriched-catalog/of-5/tpl-5/p.png",
        image_url="u",
    )
    assert len(folder_svc.calls) == 2  # system folders still created
    assert ingest_svc.calls == []  # but no ingest happens
