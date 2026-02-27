# TODO — UI refinement for Agency Client Details row editing

- [x] Fix per-row editing bug so pencil/edit mode is isolated per account row (by row key), not global for entire list.
- [x] Place `Tip client` + `Responsabil` inline on each account row and make both editable only when that row is in edit mode.
- [x] Move Back button from body/title card into main page header (left of `Client: ...`).
- [x] Remove legacy global `Responsabil cont` section from top card.
- [x] Validate frontend build and capture screenshot.

## Review
- Refactored row editing state to use unique row IDs (`platform:account_id`) so activating edit for one row does not open editors for all rows.
- Each row now shows `Tip client` and `Responsabil` on the same line block, with a single row pencil controlling edit mode and autosave behavior for that row.
- Back navigation was moved into the AppShell header via new `headerPrefix` support, matching standard system navigation placement.
- Removed the old global responsible section under the client title card.
