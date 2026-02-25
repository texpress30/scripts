# TODO — Google Ads listAccessibleCustomers POST debug change

- [x] Change list-accessible call to POST with required headers and empty body.
- [x] Ensure URL is sanitized and log response headers on HTTP failures.
- [x] Update tests/debug script expectations for POST behavior.
- [x] Run targeted checks.
- [x] Commit and create PR.

## Review
- Updated preflight account discovery to `POST https://googleads.googleapis.com/v18/customers:listAccessibleCustomers` with `Authorization` and `developer-token` headers and `{}` payload.
- URL is sanitized using `.strip()` before request dispatch.
- Added response-header diagnostics to Google Ads HTTP error logging and propagated headers in raised integration errors.
- Added a focused unit test validating POST method, URL, payload, and required headers (without `login-customer-id`) for preflight call.
- Updated debug script output text to reflect POST preflight behavior.
