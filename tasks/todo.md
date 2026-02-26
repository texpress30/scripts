# TODO — Agency connected-state UX + persistent accounts/client mapping

- [x] Persist Agency Clients data in Postgres so records survive deploy/restart.
- [x] Add Google account import metadata persistence (last import timestamp + imported account registry).
- [x] Update Integrations UI to show active Google connected state and persistent last-import info.
- [x] Add Agency Accounts section under Agency Clients with platform cards and Google account attach workflow.
- [x] Wire Google customer mapping to client registry so Sub-Account sync can use attached Google account IDs.
- [x] Apply account naming override: `7563058696` -> `OMA-Test 2`.
- [x] Run backend/frontend checks and produce screenshot evidence.
- [x] Commit and create PR.

## Review
- Implemented persistent `agency_clients`, `agency_platform_accounts`, and `agency_platform_imports` tables with in-memory test fallback.
- Google import now upserts imported accounts + last import timestamp and exposes metadata to UI.
- Integrations page now fetches Google status on load and clearly displays connected state, connected account count, and last import time.
- Agency Clients now includes a new Agency Accounts section with platform cards; Google card lists available accounts and allows attaching an account to an existing client.
- Google mapping is now resolved from persisted client registry before env CSV fallback, so sub-account sync uses attached account IDs.
- Added naming override for account `7563058696` to display as `OMA-Test 2` in imported/listed accounts.
- Captured updated Agency Clients screenshot artifact.
