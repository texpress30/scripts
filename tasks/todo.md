# TODO — Client ID display normalization + client details page

- [x] Attempt mandatory workspace sync commands and note environment limitations.
- [x] Ensure client IDs shown in Agency UI start from 1 for manual clients.
- [x] Add client details backend endpoint with enabled platforms + attached accounts per platform.
- [x] Add clickable client name in Agency Clients list and new client details page UI.
- [x] Update README with client details navigation and API.
- [x] Run checks (backend + frontend) and capture screenshot.
- [x] Commit changes and create PR with title specific to this scope.

## Review
- Normalized manual-client display IDs in API/UI to start from 1 using ranked/manual ordering while preserving internal primary keys for relations.
- Added client details endpoint (`GET /clients/{id}`) with platform activation + attached account lists.
- Added new Agency Client details page and linked client names from Agency Clients table.
- Kept many-to-many mapping behavior and updated Agency Accounts dropdown labels to use display IDs.
- Updated README with current agency navigation and client-details workflow.

