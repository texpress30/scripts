# TODO — Fix Google Ads listAccessibleCustomers verb + version check

- [x] Change `customers:listAccessibleCustomers` preflight back to HTTP GET with no body.
- [x] Ensure `_http_json` usage sends `payload=None` for GET in discovery flow.
- [x] Update tests and debug script expectations from POST to GET.
- [x] Verify Google Ads API sunset status for v18 from official docs and document finding.
- [x] Run targeted tests/checks.
- [x] Commit and create PR.

## Review
- Reverted preflight discovery to `GET https://googleads.googleapis.com/v18/customers:listAccessibleCustomers` with `Authorization` + `developer-token`, and no body (`payload=None`).
- Kept manager customer-specific queries on POST with `login-customer-id`.
- Added/kept Google error logging that includes `response_headers` for endpoint/version diagnostics.
- Updated tests and debug script to assert/reflect GET for accessible-customer preflight.
- Checked official sunset docs page; page content in this environment includes `v22` references and no visible `v18` marker, so default API version was moved from `v18` to `v22` (while env override remains supported).
