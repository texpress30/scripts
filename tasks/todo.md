# TODO — Fix attach persistence + enforce real Google account names

- [x] Execute mandatory workspace sync commands (`git fetch origin`, `git reset --hard origin/main`) and document environment limitations.
- [x] Diagnose attach mapping persistence path (frontend onChange + backend attach endpoint + registry update query).
- [x] Fix backend/client registry behavior to ensure manual client attachment persists reliably in Postgres.
- [x] Remove any remaining synthetic `Google Account [ID]` naming logic from API responses.
- [x] Add refresh mechanism to overwrite existing imported Google account names with live descriptive names from Google API.
- [x] Wire refresh action in Agency Accounts UI and revalidate mapping flow.
- [x] Run backend/frontend validation and capture screenshot.
- [ ] Commit and create PR.

## Review
- Ran requested sync command; environment has no `origin` remote so fetch/reset cannot be completed here.
- Fixed alias API route still returning synthetic names by switching it to `list_accessible_customer_accounts()`.
- Added `POST /integrations/google-ads/refresh-account-names` to refresh persisted names in `agency_platform_accounts` from live Google account discovery.
- Added utility script `scripts/refresh_google_account_names.py` for operational refresh runs.
- Updated Agency Accounts page with `Refresh Names` action and reload of summary/account lists.
- Narrowed legacy source cleanup in client registry to avoid over-marking manual clients, which could block attach persistence.
