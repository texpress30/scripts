# TODO — Google Ads login-customer-id enforcement for MCC hierarchy

- [x] Attempt mandatory workspace sync (`git fetch origin` + `git reset --hard origin/main`) and record environment blockers.
- [x] Audit Google Ads production request paths to confirm where `developer-token` and `login-customer-id` headers are attached.
- [x] Refactor Google Ads service to enforce required manager ID (`GOOGLE_ADS_MANAGER_CUSTOMER_ID`) for all Google Ads API calls and always send as `login-customer-id`.
- [x] Update/add tests to verify `login-customer-id` header usage in both account discovery and production metrics fetch.
- [x] Run backend tests for changed scope.
- [x] Commit and create PR note.

## Review
- Exact user-requested sync command was attempted first; runtime policy blocked `git reset --hard`, and remote fetch is blocked in this environment due missing GitHub credentials (`origin` unavailable/auth required).
- Added `_required_manager_customer_id()` to normalize + strictly validate manager ID from `GOOGLE_ADS_MANAGER_CUSTOMER_ID` for production API paths.
- `list_accessible_customers()` now consumes the required manager helper so MCC login context is guaranteed when building Google Ads headers.
- `_fetch_production_metrics()` now also enforces required manager ID and always sends normalized `login-customer-id` with `developer-token`.
- Added tests that assert `developer-token` and `login-customer-id` headers are present, including the concrete manager ID normalization case (`398-659-7205` -> `3986597205`).
