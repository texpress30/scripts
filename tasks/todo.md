# TODO — Agency Clients manual-only + sidebar accounts restructure

- [x] Sync local workspace with latest main snapshot (remote unavailable in this environment; proceeded from clean local main state).
- [x] Ensure Google account import updates only Agency platform account registry (no auto-created Agency Clients).
- [x] Use Google Ads descriptive account names for all imported/listed accounts.
- [x] Move Agency Accounts UI from Agency Clients page into AppShell sidebar under Agency Clients navigation.
- [x] Keep attach dropdown scoped to manually created Agency Clients.
- [x] Run targeted backend/frontend checks.
- [x] Commit and open PR.

## Review
- Refactored Google account discovery to return `{id, name}` account objects and use `descriptive_name` globally when available.
- Updated Google endpoints to expose real account names and to import only into `agency_platform_accounts`, preserving Agency Clients as manual entities.
- Simplified Agency Clients page to manual client CRUD/list only.
- Added Agency Accounts cards + Google account attachment workflow in the sidebar, under core agency navigation.
- Attach-to-client dropdown now inherently uses `/clients` data only (manual Agency Clients), excluding imported ad accounts.
