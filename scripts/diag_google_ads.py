#!/usr/bin/env python3
"""Google Ads end-to-end diagnostics (OAuth/API/DB).

Usage:
  PYTHONPATH=apps/backend python scripts/diag_google_ads.py
"""

from __future__ import annotations

import json
import os
import sys

from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service


def mask(value: str) -> str:
    raw = value.strip()
    if raw == "":
        return ""
    if len(raw) <= 4:
        return "****"
    return f"***{raw[-4:]}"


def main() -> int:
    os.environ.setdefault("APP_AUTH_SECRET", "diag-auth-secret")

    try:
        diagnostics = google_ads_service.run_diagnostics()
    except GoogleAdsIntegrationError as exc:
        print(f"[diag] failed: {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[diag] unexpected failure: {exc}")
        return 1

    print(f"OAuth OK: {bool(diagnostics.get('oauth_ok'))}")
    print(f"Accessible customers: {int(diagnostics.get('accessible_customers_count', 0))}")
    print(f"Child accounts under MCC: {int(diagnostics.get('child_accounts_count', 0))}")

    sample = diagnostics.get("sample_metrics_last_30_days", {})
    impressions = int(sample.get("impressions", 0) or 0)
    clicks = int(sample.get("clicks", 0) or 0)
    cost_micros = int(sample.get("cost_micros", 0) or 0)
    print(
        "Sample metrics last 30 days: "
        f"customer={mask(str(sample.get('customer_id_masked') or ''))} "
        f"impressions={impressions} clicks={clicks} cost_micros={cost_micros}"
    )

    print(f"DB rows last 30 days: {int(diagnostics.get('db_rows_last_30_days', 0))}")
    print(f"Last sync at: {diagnostics.get('last_sync_at')}")
    if diagnostics.get("last_error"):
        print(f"Last error: {str(diagnostics['last_error'])[:400]}")

    print("[diag-json]")
    print(json.dumps(diagnostics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
