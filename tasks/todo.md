# TODO — Fix Google Ads SDK ValueError during OAuth exchange

- [x] Attempt mandatory sync (`git fetch origin && git reset --hard origin/main`) and record blocker.
- [x] Make GoogleAdsClient initialization lazy and refresh-token aware so SDK is never instantiated without full OAuth credentials.
- [x] Keep manual OAuth code exchange via token endpoint, then perform preflight discovery only after refresh token is confirmed.
- [x] Add friendly error path in `_google_ads_client` when refresh token is missing.
- [x] Update tests for exchange flow + SDK init guard behavior.
- [x] Run backend tests and debug script checks.
- [x] Commit and create PR.

## Review
- Mandatory sync command was attempted exactly; runtime policy blocks `git reset --hard`.
- `_google_ads_client` now accepts optional explicit refresh token, validates it before SDK init, and wraps SDK ValueError with a friendly integration error.
- `exchange_oauth_code` still does manual token exchange first, stores the returned refresh token, and then runs account discovery by passing that token explicitly.
- `list_accessible_customers` now supports optional refresh token propagation so post-exchange preflight cannot race on missing env state.
- Unit tests now cover refresh-token guard and exchange flow passing token into discovery; all targeted tests are green.
