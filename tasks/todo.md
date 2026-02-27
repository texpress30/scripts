# TODO — Persist `/settings/profile` form with backend APIs

- [x] Review existing `/settings/profile` frontend and backend auth flow.
- [x] Add backend profile persistence service + schema initialization for `users` profile data.
- [x] Add authenticated profile endpoints (`GET/PATCH /user/profile`, `POST /user/profile/password`).
- [x] Wire profile page to load and submit data with loading/success/error states.
- [x] Run targeted checks and collect evidence.
- [x] Commit changes and open PR.

## Review
- Added `user_profile` backend service with Postgres-backed `users` table initialization and CRUD-style profile/password updates.
- Registered new profile router in FastAPI app and initialized schema at startup.
- Updated `/settings/profile` page to fetch initial profile data, submit updates via backend APIs, and surface loading/toast/error UX.
