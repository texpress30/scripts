# TODO — Google Ads API version upgrade and de-hardcode URL

- [x] Replace hardcoded `v18` in accessible-customers URL with dynamic `self._google_api_version()` path.
- [x] Update default Google Ads API version to `v23` in config/service fallbacks.
- [x] Update tests/scripts expecting previous default/API version.
- [x] Run targeted backend tests and debug script.
- [x] Commit and create PR.

## Review
- `customers:listAccessibleCustomers` URL now uses `_build_google_ads_url(self._google_api_version(), ...)`, eliminating hardcoded version segments.
- Default Google Ads API version is now `v23` in both config env defaults and service fallback path.
- Tests and debug script were updated to reflect v23 behavior and dynamic URL construction.
- Validation confirms backend tests pass and debug script now hits v23 manager search URL.
- Sunset-doc probe in this environment shows `v23` marker present and no `v18` marker in fetched page content.
