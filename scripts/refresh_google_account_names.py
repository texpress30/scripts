"""Refresh Google Ads account names in agency_platform_accounts using live descriptive names.

Usage:
  cd apps/backend
  python ../../scripts/refresh_google_account_names.py
"""

from app.services.client_registry import client_registry_service
from app.services.google_ads import GoogleAdsIntegrationError, google_ads_service


def main() -> int:
    try:
        accounts = google_ads_service.list_accessible_customer_accounts()
    except GoogleAdsIntegrationError as exc:
        print(f"error: {exc}")
        return 1

    normalized = [{"id": item["id"], "name": item["name"]} for item in accounts]
    client_registry_service.upsert_platform_accounts(platform="google_ads", accounts=normalized)
    print(f"refreshed {len(normalized)} accounts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
