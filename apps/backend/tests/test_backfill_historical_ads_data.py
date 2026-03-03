from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "backfill_historical_ads_data.py"
_SPEC = importlib.util.spec_from_file_location("backfill_historical_ads_data", SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
backfill_script = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = backfill_script
_SPEC.loader.exec_module(backfill_script)


def _args(**kwargs):
    base = {
        "platform": "google_ads",
        "client_id": 10,
        "all_clients": False,
        "start_date": date(2024, 9, 1),
        "end_date": date(2024, 9, 30),
        "chunk_days": 7,
        "mode": "dry-run",
        "continue_on_error": False,
        "max_clients": None,
        "max_accounts": None,
        "transport": "local",
        "base_url": None,
        "auth_token": None,
        "poll_interval": 5.0,
        "poll_timeout": 7200,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_parse_args_requires_client_scope():
    try:
        backfill_script.parse_args(["--platform", "google_ads", "--mode", "dry-run", "--transport", "local"])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert int(exc.code) == 2


def test_parse_args_validates_date_and_chunk():
    try:
        backfill_script.parse_args([
            "--platform",
            "google_ads",
            "--client-id",
            "11",
            "--transport",
            "local",
            "--start-date",
            "2024-10-10",
            "--end-date",
            "2024-09-10",
        ])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert int(exc.code) == 2

    try:
        backfill_script.parse_args([
            "--platform",
            "google_ads",
            "--client-id",
            "11",
            "--transport",
            "local",
            "--chunk-days",
            "0",
        ])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert int(exc.code) == 2


def test_dry_run_does_not_call_google_sync(monkeypatch):
    called = {"sync": 0}

    monkeypatch.setattr(backfill_script, "_resolve_clients", lambda **_: [11])
    monkeypatch.setattr(backfill_script, "_resolve_client_accounts", lambda **_: ["1234567890", "0987654321"])

    def _sync(**kwargs):
        called["sync"] += 1
        return {"rows_upserted": 10}

    monkeypatch.setattr(backfill_script.google_ads_service, "sync_customer_for_client_historical_range", _sync)

    summary = backfill_script.run_backfill(_args(mode="dry-run"))

    assert called["sync"] == 0
    assert summary["planned"] == 2
    assert summary["failed"] == 0


def test_google_apply_calls_backfill_with_range(monkeypatch):
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(backfill_script, "_resolve_clients", lambda **_: [7])
    monkeypatch.setattr(backfill_script, "_resolve_client_accounts", lambda **_: ["1112223333"])

    def _sync(**kwargs):
        calls.append(dict(kwargs))
        return {"rows_upserted": 42, "planned_chunks": 3, "executed_chunks": 3, "empty_chunks": 1, "failed_chunks": 0}

    monkeypatch.setattr(backfill_script.google_ads_service, "sync_customer_for_client_historical_range", _sync)

    summary = backfill_script.run_backfill(
        _args(mode="apply", start_date=date(2024, 9, 1), end_date=date(2024, 9, 15), chunk_days=5)
    )

    assert len(calls) == 1
    assert calls[0]["start_date"] == date(2024, 9, 1)
    assert calls[0]["end_date"] == date(2024, 9, 15)
    assert int(calls[0]["chunk_days"]) == 5
    assert summary["succeeded"] == 1
    assert summary["items"][0]["rows_upserted"] == 42
    assert summary["rows_upserted"] == 42
    assert summary["planned_chunks"] == 3
    assert summary["executed_chunks"] == 3
    assert summary["empty_chunks"] == 1
    assert summary["failed_chunks"] == 0


def test_unsupported_platform_marked_skipped(monkeypatch):
    monkeypatch.setattr(backfill_script, "_resolve_clients", lambda **_: [1, 2])

    summary = backfill_script.run_backfill(_args(platform="meta_ads", client_id=None, all_clients=True))

    assert summary["skipped"] == 2
    assert summary["succeeded"] == 0
    assert all(item["status"] == "skipped" for item in summary["items"])


def test_client_selection_modes(monkeypatch):
    monkeypatch.setattr(backfill_script.client_registry_service, "list_clients", lambda: [{"id": 3}, {"id": 4}])

    by_id = backfill_script._resolve_clients(client_id=99, all_clients=False, max_clients=None)
    assert by_id == [99]

    all_clients = backfill_script._resolve_clients(client_id=None, all_clients=True, max_clients=1)
    assert all_clients == [3]


def test_summary_contains_expected_counters(monkeypatch):
    monkeypatch.setattr(backfill_script, "_resolve_clients", lambda **_: [1])
    monkeypatch.setattr(
        backfill_script,
        "_run_google_backfill_for_client",
        lambda **_: [
            backfill_script.BackfillItemResult(platform="google_ads", client_id=1, account_id="111", status="succeeded", rows_upserted=5),
            backfill_script.BackfillItemResult(platform="google_ads", client_id=1, account_id="222", status="failed", reason="boom"),
            backfill_script.BackfillItemResult(platform="google_ads", client_id=1, account_id=None, status="skipped", reason="none"),
        ],
    )

    summary = backfill_script.run_backfill(_args(mode="apply", continue_on_error=True))

    assert summary["processed_clients"] == 1
    assert summary["processed_accounts"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["skipped"] == 1
    assert summary["errors"] == ["boom"]


def test_http_transport_starts_and_polls(monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_http_json(*, method: str, url: str, token: str, payload=None):
        calls.append((method, url))
        if method.upper() == "POST":
            return {"job_id": "ghb-1", "status": "queued"}
        return {
            "job_id": "ghb-1",
            "status": "done",
            "processed_accounts": 2,
            "planned_chunks": 4,
            "executed_chunks": 4,
            "empty_chunks": 1,
            "failed_chunks": 0,
            "rows_upserted": 33,
            "errors": [],
        }

    monkeypatch.setattr(backfill_script, "_http_json", fake_http_json)

    summary = backfill_script.run_backfill_http(
        _args(
            transport="http",
            client_id=77,
            platform="google_ads",
            base_url="https://api.example.com",
            auth_token="token",
            poll_interval=0.01,
            poll_timeout=5,
        )
    )

    assert summary["status"] == "done"
    assert len(calls) >= 2
    assert calls[0][0] == "POST"
    assert "/historical-backfill" in calls[0][1]
    assert calls[1][0] == "GET"
    assert "/historical-backfill/jobs/ghb-1" in calls[1][1]
