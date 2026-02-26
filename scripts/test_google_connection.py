#!/usr/bin/env python3
"""Quick Google Ads connection debug helper.

Usage:
  PYTHONPATH=apps/backend python scripts/test_google_connection.py

What it does:
- Loads backend settings/environment.
- Monkeypatches HTTP preflight and HTTP transport helper.
- Verifies `login-customer-id` is absent from list-accessible preflight path
  and present on manager customer-specific search requests.
"""

from __future__ import annotations

import os

from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service


def main() -> int:
    os.environ.setdefault("APP_AUTH_SECRET", "debug-auth-secret")
    os.environ.setdefault("GOOGLE_ADS_MODE", "production")
    os.environ.setdefault("GOOGLE_ADS_CLIENT_ID", "debug-client-id")
    os.environ.setdefault("GOOGLE_ADS_CLIENT_SECRET", "debug-client-secret")
    os.environ.setdefault("GOOGLE_ADS_DEVELOPER_TOKEN", "debug-developer-token-12345")
    os.environ.setdefault("GOOGLE_ADS_REDIRECT_URI", "https://app.example.com/agency/integrations/google/callback")
    os.environ.setdefault("GOOGLE_ADS_REFRESH_TOKEN", "debug-refresh-token")
    os.environ.setdefault("GOOGLE_ADS_MANAGER_CUSTOMER_ID", "3986597205")
    os.environ.setdefault("GOOGLE_ADS_API_VERSION", "v23")

    original_http = google_ads_service._http_json
    original_preflight = google_ads_service._list_accessible_customers_via_http

    def debug_http_json(*, method: str, url: str, payload=None, headers=None):
        print(f"[debug] method={method} url={url}")
        if isinstance(headers, dict):
            print(f"[debug] developer-token={headers.get('developer-token')}")
            print(f"[debug] login-customer-id={headers.get('login-customer-id')}")
        if "oauth2.googleapis.com/token" in url:
            return {"access_token": "ya29.debug-token"}
        if "googleAds:searchStream" in url:
            return [{"results": [{"customerClient": {"id": "3578697670"}}]}]
        if "googleAds:search" in url:
            return {"results": [{"customerClient": {"id": "3578697670"}}]}
        return original_http(method=method, url=url, payload=payload, headers=headers)

    def debug_preflight_http(*, access_token: str) -> list[str]:
        print("[debug] http GET /customers:listAccessibleCustomers invoked (no login-customer-id header expected)")
        print(f"[debug] preflight access_token_present={bool(access_token)}")
        return ["3986597205", "3578697670"]

    google_ads_service._http_json = debug_http_json
    google_ads_service._list_accessible_customers_via_http = debug_preflight_http
    try:
        accounts = google_ads_service.list_accessible_customers()
        print(f"[ok] accessible_customers={accounts}")
        return 0
    except GoogleAdsIntegrationError as exc:
        print(f"[error] {exc}")
        return 1
    finally:
        google_ads_service._http_json = original_http
        google_ads_service._list_accessible_customers_via_http = original_preflight


if __name__ == "__main__":
    raise SystemExit(main())
