from __future__ import annotations

import json

from app.workers import storage_media_cleanup_runner as runner_module


class _FakeService:
    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload or {"processed": 0, "purged": 0, "skipped": 0, "failed": 0}
        self.error = error
        self.calls: list[int] = []

    def run_batch(self, *, limit: int):
        self.calls.append(limit)
        if self.error is not None:
            raise self.error
        return dict(self.payload)


def test_runner_uses_explicit_limit_over_config(monkeypatch):
    fake_service = _FakeService(payload={"processed": 1, "purged": 1, "skipped": 0, "failed": 0})
    logs: list[str] = []

    monkeypatch.setattr(runner_module, "storage_media_cleanup_service", fake_service)
    monkeypatch.setattr(runner_module, "load_settings", lambda: type("S", (), {"storage_media_cleanup_batch_limit": 99})())

    code = runner_module.run_cleanup_batch(limit=5, emit=logs.append)

    assert code == 0
    assert fake_service.calls == [5]
    summary = json.loads(logs[0])
    assert summary["limit"] == 5


def test_runner_falls_back_to_config_limit(monkeypatch):
    fake_service = _FakeService()
    logs: list[str] = []

    monkeypatch.setattr(runner_module, "storage_media_cleanup_service", fake_service)
    monkeypatch.setattr(runner_module, "load_settings", lambda: type("S", (), {"storage_media_cleanup_batch_limit": 33})())

    code = runner_module.run_cleanup_batch(limit=None, emit=logs.append)

    assert code == 0
    assert fake_service.calls == [33]


def test_runner_summary_contains_main_fields(monkeypatch):
    fake_service = _FakeService(payload={"processed": 4, "purged": 2, "skipped": 1, "failed": 1})
    logs: list[str] = []

    monkeypatch.setattr(runner_module, "storage_media_cleanup_service", fake_service)
    monkeypatch.setattr(runner_module, "load_settings", lambda: type("S", (), {"storage_media_cleanup_batch_limit": 10})())

    code = runner_module.run_cleanup_batch(limit=None, emit=logs.append)

    assert code == 0
    summary = json.loads(logs[0])
    assert summary == {
        "status": "ok",
        "limit": 10,
        "processed": 4,
        "purged": 2,
        "skipped": 1,
        "failed": 1,
    }


def test_runner_returns_success_even_with_item_failures(monkeypatch):
    fake_service = _FakeService(payload={"processed": 3, "purged": 1, "skipped": 1, "failed": 1})

    monkeypatch.setattr(runner_module, "storage_media_cleanup_service", fake_service)
    monkeypatch.setattr(runner_module, "load_settings", lambda: type("S", (), {"storage_media_cleanup_batch_limit": 20})())

    assert runner_module.run_cleanup_batch(limit=None, emit=lambda _line: None) == 0


def test_runner_returns_non_zero_on_global_error(monkeypatch):
    fake_service = _FakeService(error=runner_module.StorageMediaCleanupError("S3 unavailable", status_code=503))
    logs: list[str] = []

    monkeypatch.setattr(runner_module, "storage_media_cleanup_service", fake_service)
    monkeypatch.setattr(runner_module, "load_settings", lambda: type("S", (), {"storage_media_cleanup_batch_limit": 20})())

    code = runner_module.run_cleanup_batch(limit=None, emit=logs.append)

    assert code == 1
    summary = json.loads(logs[0])
    assert summary["status"] == "error"
    assert summary["status_code"] == 503


def test_main_parses_cli_limit_and_does_not_depend_on_web_startup(monkeypatch):
    captured: dict[str, int | None] = {}

    def _fake_run_cleanup_batch(*, limit, emit=print):
        captured["limit"] = limit
        return 0

    monkeypatch.setattr(runner_module, "run_cleanup_batch", _fake_run_cleanup_batch)

    code = runner_module.main(["--limit", "77"])

    assert code == 0
    assert captured["limit"] == 77
    assert "app.main" not in runner_module.__dict__
