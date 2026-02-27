# TODO — Critical row-level state isolation fix (Agency Client Details)

- [x] Implement true per-row state isolation so edit mode/value are keyed by `platform + account_id`.
- [x] Ensure row updates for `Tip client` and `Responsabil` use per-row values (not shared global fallback).
- [x] Add row-scoped saving indicator near each row pencil while save is in progress.
- [x] Include `platform` and `account_id` in frontend PATCH payload for row edits.
- [x] Extend backend PATCH contract and persistence logic to update only targeted mapping row.
- [x] Return row-specific `client_type` and `account_manager` in account detail payloads for UI binding.
- [x] Run backend compile + frontend build and capture screenshot evidence.

## Review
- Frontend now keeps isolated drafts by row key and compares/saves against the specific row’s current values.
- Saving is row-scoped (`savingRowId`) with spinner feedback on the row pencil only.
- Backend accepts `platform` + `account_id` on profile PATCH and applies updates to exactly one mapping row (`platform/account_id/client_id`).
- Client detail account rows now include row-level `client_type` and `account_manager`, eliminating list-wide mirroring behavior caused by global values.
