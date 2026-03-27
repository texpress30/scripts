# Task Plan: Fix Cost per Client Nou Chart

- [x] Add `cost_per_new_client` extraction to backend `build_overview_charts_payload`.
- [x] Expose `financial.cost_per_new_client` in `media_tracker_worksheet.py` response.
- [x] Add `cost_per_new_client` type to `OverviewChartsPayload` in `OverviewCharts.tsx`.
- [x] Add the `Cost per Client Nou` BarChart below `Profitabilitatea` in `OverviewCharts.tsx`.
- [x] Update frontend tests (`page.test.tsx`) with missing mock data and UI assertions.
- [x] Run backend verification tests.
- [~] Run frontend verification tests (Skipped due to no local pnpm).
- [ ] Commit and create a new pull request on GitHub.
