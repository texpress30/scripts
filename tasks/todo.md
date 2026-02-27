# TODO — Dynamic sidebar settings mode (GHL-style)

- [x] Add `Settings` link in bottom section of primary sidebar above `Schimbă tema`.
- [x] Route settings entry to `/settings/profile`.
- [x] Implement settings-mode sidebar for `/settings/*` routes that replaces main nav links.
- [x] Add prominent `← Go Back` action in settings mode, routing to `/agency-dashboard`.
- [x] Add settings nav list: Profile, Company, My Team, Tags, Audit Logs, Ai Agents, Media Storage Usage.
- [x] Implement active-state highlighting for current settings route.
- [x] Add pages for settings routes and alias route `/agency-dashboard` -> `/agency/dashboard`.
- [x] Run frontend build and capture screenshot.

## Review
- Sidebar now has a dedicated Settings entry near the bottom in normal navigation mode.
- When path starts with `/settings/`, sidebar switches to settings-only navigation with go-back CTA and active link highlight.
- Added concrete settings pages for all requested routes plus an agency-dashboard alias route for back navigation.
