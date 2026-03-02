#!/usr/bin/env python3
"""Operational historical ads backfill runner.

This script is the dedicated path for large historical ranges.
UI Google Sync is intentionally rolling-only (last 30 days).

Usage examples:
  PYTHONPATH=apps/backend python scripts/backfill_historical_ads_data.py --platform google_ads --client-id 123 --mode dry-run
  PYTHONPATH=apps/backend python scripts/backfill_historical_ads_data.py --platform all --all-clients --mode apply --chunk-days 7
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib import parse, request, error

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "apps" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service

SUPPORTED_PLATFORMS: tuple[str, ...] = (
    "google_ads",
    "meta_ads",
    "tiktok_ads",
    "pinterest_ads",
    "snapchat_ads",
)
SUPPORTED_DATE_RANGE_BACKFILL: tuple[str, ...] = ("google_ads",)
DEFAULT_START_DATE = date(2024, 9, 1)


@dataclass
class BackfillItemResult:
    platform: str
    client_id: int
    account_id: str | None
    status: str
    reason: str | None = None
    rows_upserted: int | None = None
    planned_chunks: int | None = None
    executed_chunks: int | None = None
    empty_chunks: int | None = None
    failed_chunks: int | None = None


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO date: '{value}'") from exc


def _default_yesterday() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Historical ads backfill into ad_performance_reports (UI sync stays rolling 30 days)")
    parser.add_argument("--platform", choices=[*SUPPORTED_PLATFORMS, "all"], required=True)
    parser.add_argument("--client-id", type=int, help="Run only for one client id")
    parser.add_argument("--all-clients", action="store_true", help="Run for all clients")
    parser.add_argument("--start-date", type=_parse_iso_date, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=_parse_iso_date, default=_default_yesterday())
    parser.add_argument("--chunk-days", type=int, default=7)
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--max-clients", type=int)
    parser.add_argument("--max-accounts", type=int)
    parser.add_argument("--transport", choices=["http", "local"], default="http")
    parser.add_argument("--base-url", default=os.getenv("BACKFILL_API_BASE_URL"))
    parser.add_argument("--auth-token", default=os.getenv("BACKFILL_API_TOKEN"))
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--poll-timeout", type=int, default=7200)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.client_id is None and not bool(args.all_clients):
        parser.error("must provide one of --client-id or --all-clients")
    if args.client_id is not None and bool(args.all_clients):
        parser.error("--client-id and --all-clients are mutually exclusive")
    if int(args.chunk_days) <= 0:
        parser.error("--chunk-days must be a positive integer")
    if args.max_clients is not None and int(args.max_clients) <= 0:
        parser.error("--max-clients must be a positive integer")
    if args.max_accounts is not None and int(args.max_accounts) <= 0:
        parser.error("--max-accounts must be a positive integer")
    if args.start_date > args.end_date:
        parser.error("--start-date must be <= --end-date")
    if str(args.transport) == "http":
        if str(args.platform) not in ("google_ads",):
            parser.error("--transport http currently supports only --platform google_ads")
        if args.client_id is None:
            parser.error("--transport http requires --client-id")
        if not str(args.base_url or "").strip():
            parser.error("--base-url (or BACKFILL_API_BASE_URL) is required for --transport http")
        if not str(args.auth_token or "").strip():
            parser.error("--auth-token (or BACKFILL_API_TOKEN) is required for --transport http")
    return args


def _resolve_platforms(platform_flag: str) -> list[str]:
    if platform_flag == "all":
        return list(SUPPORTED_PLATFORMS)
    return [platform_flag]


def _resolve_clients(*, client_id: int | None, all_clients: bool, max_clients: int | None) -> list[int]:
    if client_id is not None:
        return [int(client_id)]

    rows = client_registry_service.list_clients()
    client_ids = [int(item["id"]) for item in rows if isinstance(item, dict) and item.get("id") is not None]
    if max_clients is not None:
        return client_ids[: int(max_clients)]
    return client_ids


def _resolve_client_accounts(*, platform: str, client_id: int, max_accounts: int | None) -> list[str]:
    accounts = client_registry_service.list_client_platform_accounts(platform=platform, client_id=client_id)
    resolved: list[str] = []
    for item in accounts:
        account_id = str(item.get("id") or "").strip()
        if account_id != "":
            resolved.append(account_id)
    if max_accounts is not None:
        return resolved[: int(max_accounts)]
    return resolved


def _run_google_backfill_for_client(*, client_id: int, start_date: date, end_date: date, chunk_days: int, mode: str, max_accounts: int | None) -> list[BackfillItemResult]:
    account_ids = _resolve_client_accounts(platform="google_ads", client_id=client_id, max_accounts=max_accounts)
    if len(account_ids) == 0:
        return [
            BackfillItemResult(
                platform="google_ads",
                client_id=client_id,
                account_id=None,
                status="skipped",
                reason="no mapped accounts for client/platform",
            )
        ]

    items: list[BackfillItemResult] = []
    for account_id in account_ids:
        if mode == "dry-run":
            items.append(
                BackfillItemResult(
                    platform="google_ads",
                    client_id=client_id,
                    account_id=account_id,
                    status="planned",
                    reason="dry-run",
                )
            )
            continue

        try:
            payload = google_ads_service.sync_customer_for_client_historical_range(
                client_id=client_id,
                customer_id=account_id,
                start_date=start_date,
                end_date=end_date,
                chunk_days=chunk_days,
            )
            items.append(
                BackfillItemResult(
                    platform="google_ads",
                    client_id=client_id,
                    account_id=account_id,
                    status="succeeded",
                    rows_upserted=int(payload.get("rows_upserted", 0) or 0),
                    planned_chunks=int(payload.get("planned_chunks", 0) or 0),
                    executed_chunks=int(payload.get("executed_chunks", 0) or 0),
                    empty_chunks=int(payload.get("empty_chunks", 0) or 0),
                    failed_chunks=int(payload.get("failed_chunks", 0) or 0),
                )
            )
        except GoogleAdsIntegrationError as exc:
            items.append(
                BackfillItemResult(
                    platform="google_ads",
                    client_id=client_id,
                    account_id=account_id,
                    status="failed",
                    reason=str(exc)[:300],
                )
            )
        except Exception as exc:  # noqa: BLE001
            items.append(
                BackfillItemResult(
                    platform="google_ads",
                    client_id=client_id,
                    account_id=account_id,
                    status="failed",
                    reason=str(exc)[:300],
                )
            )
    return items




def _http_json(*, method: str, url: str, token: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method.upper(), data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=60) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp is not None else ""
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc


def run_backfill_http(args: argparse.Namespace) -> dict[str, Any]:
    base_url = str(args.base_url).rstrip("/")
    token = str(args.auth_token)
    params = {
        "start_date": args.start_date.isoformat(),
        "end_date": args.end_date.isoformat(),
        "chunk_days": int(args.chunk_days),
        "continue_on_error": str(bool(args.continue_on_error)).lower(),
    }
    start_url = f"{base_url}/integrations/google-ads/clients/{int(args.client_id)}/historical-backfill?{parse.urlencode(params)}"
    start_payload = _http_json(method="POST", url=start_url, token=token)
    job_id = str(start_payload.get("job_id") or "").strip()
    if job_id == "":
        raise RuntimeError("historical backfill start endpoint did not return job_id")

    status_url = f"{base_url}/integrations/google-ads/clients/{int(args.client_id)}/historical-backfill/jobs/{job_id}"
    deadline = datetime.now(timezone.utc).timestamp() + int(args.poll_timeout)
    poll_interval = max(1.0, float(args.poll_interval))

    while True:
        payload = _http_json(method="GET", url=status_url, token=token)
        state = str(payload.get("status") or "").lower()
        if state in ("done", "error", "partial"):
            return payload
        if datetime.now(timezone.utc).timestamp() >= deadline:
            raise RuntimeError(f"poll timeout exceeded for job_id={job_id}")
        import time

        time.sleep(poll_interval)

def run_backfill(args: argparse.Namespace) -> dict[str, Any]:
    platforms = _resolve_platforms(str(args.platform))
    clients = _resolve_clients(client_id=args.client_id, all_clients=bool(args.all_clients), max_clients=args.max_clients)

    results: list[BackfillItemResult] = []
    for platform in platforms:
        for client_id in clients:
            if platform not in SUPPORTED_DATE_RANGE_BACKFILL:
                results.append(
                    BackfillItemResult(
                        platform=platform,
                        client_id=client_id,
                        account_id=None,
                        status="skipped",
                        reason="date-range backfill not supported yet for this platform",
                    )
                )
                continue

            platform_results = _run_google_backfill_for_client(
                client_id=client_id,
                start_date=args.start_date,
                end_date=args.end_date,
                chunk_days=int(args.chunk_days),
                mode=str(args.mode),
                max_accounts=args.max_accounts,
            )
            results.extend(platform_results)

            if not bool(args.continue_on_error) and any(item.status == "failed" for item in platform_results):
                raise RuntimeError("Stopping on first platform/client failure; use --continue-on-error to proceed")

    summary = {
        "processed_clients": len(clients),
        "processed_accounts": sum(1 for item in results if item.account_id is not None),
        "succeeded": sum(1 for item in results if item.status == "succeeded"),
        "failed": sum(1 for item in results if item.status == "failed"),
        "skipped": sum(1 for item in results if item.status == "skipped"),
        "planned": sum(1 for item in results if item.status == "planned"),
        "errors": [item.reason for item in results if item.status == "failed" and item.reason],
        "planned_chunks": sum(int(item.planned_chunks or 0) for item in results),
        "executed_chunks": sum(int(item.executed_chunks or 0) for item in results),
        "empty_chunks": sum(int(item.empty_chunks or 0) for item in results),
        "failed_chunks": sum(int(item.failed_chunks or 0) for item in results),
        "rows_upserted": sum(int(item.rows_upserted or 0) for item in results),
        "items": [item.__dict__ for item in results],
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    os.environ.setdefault("APP_AUTH_SECRET", "backfill-historical-ads-data")
    args = parse_args(argv)

    print("note: UI Google Sync endpoint runs rolling_30d only; use this script for historical backfill ranges.")

    print(
        json.dumps(
            {
                "mode": args.mode,
                "platform": args.platform,
                "start_date": args.start_date.isoformat(),
                "end_date": args.end_date.isoformat(),
                "chunk_days": int(args.chunk_days),
                "client_id": args.client_id,
                "all_clients": bool(args.all_clients),
                "continue_on_error": bool(args.continue_on_error),
                "transport": args.transport,
            },
            indent=2,
        )
    )

    try:
        summary = run_backfill_http(args) if str(args.transport) == "http" else run_backfill(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {str(exc)[:500]}")
        return 1

    print("[backfill-summary]")
    print(json.dumps(summary, indent=2))
    if str(args.transport) == "http":
        return 0 if str(summary.get("status") or "").lower() == "done" else 1
    return 0 if int(summary.get("failed", 0)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
