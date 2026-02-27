# TODO — Many-to-many Google account mappings + README refresh

- [x] Attempt required workspace sync commands and record environment limitations.
- [x] Inspect current one-to-one Google account attachment model in backend and frontend.
- [x] Implement many-to-many-compatible mapping model using link table semantics (client can have multiple Google accounts; account maps to one client).
- [x] Add/adjust endpoints: attach (idempotent), detach, list client accounts.
- [x] Update Agency Accounts dropdown UX to keep all clients selectable and show current attachment with change/detach actions.
- [x] Update repository README with current architecture/endpoints/UI workflow.
- [x] Run backend/frontend checks and take screenshot.
- [x] Commit changes and create PR with title reflecting this specific scope.

## Review
- Added table-backed mapping model `agency_account_client_mappings` (unique per platform/account) and backfill from legacy `agency_clients.google_customer_id`.
- Implemented idempotent attach (upsert), detach endpoint, and per-client account listing endpoint for Google mappings.
- Updated `GET /clients/accounts/google` to return attached client metadata per account, enabling reliable UI binding.
- Updated Agency Accounts UI to keep all clients available in each dropdown, display current attachment, and allow detach/reassign.
- Refreshed root README with current architecture, endpoints, mapping model, and operational scripts.
- Validation executed with backend targeted tests, frontend build, and screenshot artifact.

