# TODO — Replace Google Ads SDK discovery with direct HTTP in OAuth flow

- [x] Refactor `list_accessible_customers` to use direct HTTP GET to `https://googleads.googleapis.com/v18/customers:listAccessibleCustomers` with bearer token + developer token.
- [x] Remove SDK usage from login/callback discovery path (`exchange_oauth_code` -> `list_accessible_customers`).
- [x] Keep GoogleAdsClient isolated (not invoked in auth/discovery flow), update helper naming and debug script accordingly.
- [x] Update tests for HTTP-based accessible-customer discovery and no-SDK auth flow.
- [x] Run targeted tests and debug script.
- [x] Commit and create PR.

## Review
- Discovery preflight now uses direct HTTP GET to `v18/customers:listAccessibleCustomers` with only `Authorization` + `developer-token` headers.
- SDK preflight path was removed from `list_accessible_customers`, so OAuth callback/login flow no longer triggers GoogleAdsClient config validation.
- `exchange_oauth_code` still obtains refresh token manually via token endpoint before any account discovery steps.
- Customer-specific manager discovery calls continue to include `login-customer-id` and `developer-token`.
- Targeted backend tests pass and debug script confirms the expected header behavior.
