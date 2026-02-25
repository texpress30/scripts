# TODO — Google Ads 404 deep debug (MCC 3986597205)

- [x] Attempt mandatory sync command (`git fetch origin && git reset --hard origin/main`) and record blockers.
- [x] Add extended Google error logging (request_id + failure details + full payload body when available).
- [x] Implement discovery fallback check through `customers:listAccessibleCustomers` before manager search flow.
- [x] Ensure a single consistent API version strategy across Google Ads service requests.
- [x] Add `scripts/test_google_connection.py` to validate headers (`developer-token`, `login-customer-id`) and discovery behavior.
- [x] Run targeted test suite and script help/smoke checks.
- [x] Commit and create PR.

## Review
- Attempted exact sync command requested by user; runtime policy blocks `git reset --hard` and environment lacks authenticated GitHub access for `git fetch origin`.
- Added Google Ads error-detail extraction to include `request_id` + `error.details` and log full payload body for `googleads.googleapis.com` failures.
- Added service preflight to `customers:listAccessibleCustomers` with `developer-token` and `login-customer-id`; if empty, returns actionable auth/token access error before manager search.
- Standardized discovery to a single configured API version (`GOOGLE_ADS_API_VERSION`) to eliminate mixed v17/v18 behavior during debugging.
- Added `scripts/test_google_connection.py` that monkeypatches transport and prints outbound headers to prove `login-customer-id` is sent.
- Validated with backend tests and local debug script run.
