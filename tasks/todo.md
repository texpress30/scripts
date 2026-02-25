# TODO — Urgent Google Ads SDK fix for list_accessible_customers

- [x] Attempt mandatory sync (`git fetch origin && git reset --hard origin/main`) and record blockers.
- [x] Replace manual `customers:listAccessibleCustomers` URL call with official Google Ads SDK `CustomerService.list_accessible_customers`.
- [x] Ensure `login-customer-id` is NOT sent for list_accessible_customers flow, but remains for customer-specific search/metrics calls.
- [x] Align dependency version in `requirements.txt` for official `google-ads` SDK compatibility.
- [x] Update tests for SDK-based accessible-customer flow + header behavior.
- [x] Update debug script to validate new behavior.
- [x] Run targeted tests and script checks.
- [x] Commit and create PR.

## Review
- Attempted exact mandatory sync command first; runtime policy blocks `git reset --hard origin/main` in this environment.
- Replaced manual REST path `.../customers:listAccessibleCustomers` with official SDK flow: `GoogleAdsClient` + `CustomerService.list_accessible_customers()`.
- Removed `login-customer-id` usage from list-accessible discovery preflight path by design; retained `login-customer-id` for customer-specific search calls.
- Added explicit `google-ads==25.1.0` dependency in backend requirements for SDK compatibility.
- Updated unit tests to mock SDK preflight helper and validate customer-specific calls still send required headers.
- Updated `scripts/test_google_connection.py` to show SDK preflight invocation and manager search header usage.
