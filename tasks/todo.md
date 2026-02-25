# TODO — Data Normalization (Slice 2: UI Update)

- [x] Sync workspace to latest `origin/main` and resolve pull strategy conflict.
- [x] Review current Agency/Sub-account UI usage of dashboard payload.
- [x] Update Agency Dashboard cards/tables to display normalized metrics: Spend, Impressions, Clicks, Conversions, Revenue, ROAS.
- [x] Update Sub-account Dashboard and Campaigns views to display the same normalized metric set.
- [x] Add UI-level defensive formatting to avoid `undefined`/`NaN` (fallback to `0` or `-`).
- [x] Validate ROAS display aligns with backend formula (`revenue / spend`, guarded for zero spend).
- [x] Run frontend checks (build/lint where available) and capture visual screenshot.
- [x] Commit and prepare PR.

## Review
- Agency Dashboard now aggregates and renders normalized totals (`spend`, `impressions`, `clicks`, `conversions`, `revenue`, `roas`) in both cards and a totals table.
- Sub-account Dashboard now consumes normalized metrics for totals and each platform, renders all required columns, and computes ROAS as `revenue / spend` with zero-guard.
- Sub-account Campaigns now includes normalized totals and per-platform metrics tables so campaign operators can validate the unified data shape after sync actions.
- Defensive `safeNumber` normalization is applied in each page so missing provider fields render safely (`0` instead of `undefined`/`NaN`).
