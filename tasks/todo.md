# TODO — Investigate disappearing clients/accounts and harden registry behavior

- [x] Reproduce/analyze failure path after wrong Google account attach and identify likely root causes.
- [x] Fix risky in-memory fallback trigger so production never silently uses test-memory registry.
- [x] Remove deadlock-prone test-mode lock nesting and harden list/create/attach test paths.
- [x] Improve frontend data-load error handling so backend failures are visible (not shown as empty lists).
- [x] Run validation checks and capture screenshot.
- [x] Commit and create PR with specific title.

## Review
- Root-cause analysis indicates data disappearance can happen if app accidentally runs with `APP_ENV=test`, which previously forced in-memory registry fallback and loses all state on restart.
- Hardened `_is_test_mode()` to activate in-memory registry only during pytest (`PYTEST_CURRENT_TEST` present), preventing silent production data loss.
- Removed lock re-entrancy deadlocks in test mode by avoiding nested lock-acquire flows in list/create/attach paths.
- Added frontend load error handling in Agency Clients and Agency Accounts so backend failures are explicit instead of silently rendering empty tables/cards.
- Verified service behavior in test mode with a direct script and rebuilt backend/frontend successfully.

