# TODO — Inline editing + navigation refactor for Agency Client Details

- [x] Add back navigation control near client title to return quickly to `/agency/clients`.
- [x] Replace title display with inline name editing (pencil toggle, save on blur/Enter, visual success indicator).
- [x] Move `Tip client` editing into platform account rows with inline pencil-to-dropdown interaction and immediate autosave.
- [x] Remove the large `Salvează profil client` button and switch to per-field autosave (name, type, account manager).
- [x] Extend backend profile PATCH payload to support inline name updates alongside type/manager.
- [x] Run verification (build/tests) and capture screenshot of UI changes.

## Review
- Added back arrow action next to client title for fast return navigation.
- Implemented inline edit for client name and account manager with blur/Enter save and temporary green check feedback.
- Refactored client type editing into each platform account row with pencil-to-dropdown toggle and autosave on selection.
- Removed bulk save action; updates are now granular and immediate via PATCH.
- Backend PATCH contract now supports optional `name`, `client_type`, and `account_manager`, allowing single-field updates required by inline UX.
