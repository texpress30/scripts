# TODO — Context-aware settings sidebar (Agency vs Sub-Account)

- [x] Make `Go Back` dynamic based on settings context (agency -> agency dashboard, sub-account -> matching sub dashboard).
- [x] Add context-aware settings menu lists (Agency list vs Sub-Account list).
- [x] Persist sub-account settings context via ID-based routes (`/subaccount/[id]/settings/*`).
- [x] Keep active-state highlighting and update settings header label by context (`AGENCY SETTINGS` / `SUB-ACCOUNT SETTINGS`).
- [x] Ensure Settings entry in main sidebar routes to context-appropriate destination.
- [x] Run frontend build and capture screenshot evidence.

## Review
- AppShell now detects agency/sub-account settings mode from route prefixes and swaps sidebar link sets accordingly.
- `Go Back` destination is dynamic and returns to `/agency/dashboard` or `/sub/{id}/dashboard`.
- Added sub-account settings routes with persistent `id` in URL for refresh-safe context.
- Sidebar section title now clearly indicates context: `AGENCY SETTINGS` or `SUB-ACCOUNT SETTINGS`.
