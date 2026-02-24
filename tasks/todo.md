# TODO — Data Normalization (Slice 1)

- [x] Sync workspace to latest `origin/main`.
- [x] Define normalization scope for backend dashboard payload (platform fields + totals).
- [x] Implement normalization in backend aggregation (`UnifiedDashboardService`).
- [x] Fix Agency aggregated ROAS calculation to use revenue/spend.
- [x] Add/adjust tests to validate normalized payload behavior.
- [x] Run focused validation (`pytest`, frontend build).
- [x] Commit and push.

## Review
- Implemented a normalization layer in backend dashboard aggregation so each platform now exposes consistent numeric fields (`spend`, `impressions`, `clicks`, `conversions`, `revenue`, `roas`) plus sync metadata fields (`is_synced`, `synced_at`, `attempts`).
- Fixed Agency Dashboard aggregation bug: ROAS now uses `revenue / spend` instead of `conversions / spend`.
- Added/updated service test assertions to validate normalized totals and normalized per-platform shape.
