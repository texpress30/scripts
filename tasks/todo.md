# TODO — Urgent Agency Accounts page + strict manual clients filtering

- [x] Review current navigation and client/account flows (sidebar, Agency Clients, Google import naming/mapping).
- [x] Backend: enforce manual-only Agency Clients visibility and hide legacy imported accounts from Agency Clients list.
- [x] Backend: ensure Google account naming uses descriptive_name or fallback ID only (no `Google Account [ID]`).
- [x] Frontend: remove platform cards from sidebar; add single `Agency Accounts` menu entry between `Agency Clients` and `Agency Audit`.
- [x] Frontend: create dedicated `/agency-accounts` page containing platform cards + imported accounts list + attach dropdown.
- [x] Frontend: keep Agency Clients page manual-only (no imported accounts area).
- [x] Validate with targeted backend tests + frontend build and capture screenshot.
- [ ] Commit changes and create PR.

## Review
- Added strict manual/client separation by introducing a persisted `source` marker on `agency_clients`, and listing/updating only `source = manual` in Agency Clients workflows.
- Added legacy cleanup step to mark prior auto-imported Google rows as `imported` so they disappear from Agency Clients visualization.
- Sidebar now contains only navigation entries; platform cards were removed and replaced with a single `Agency Accounts` menu item.
- Added dedicated `/agency-accounts` page containing platform cards and Google imported accounts list with attach-to-client dropdown.
- Attach dropdown sources only `/clients` records, so only manual Agency Clients are selectable for mapping.
- Google account naming remains descriptive-name first, then ID fallback (no `Google Account [ID]` synthetic prefix).

