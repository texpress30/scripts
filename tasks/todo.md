# TODO — Agency Clients main page refactor (search + inline edit + pagination)

- [x] Add instant search input above the table and filter by client name while typing.
- [x] Remove `Google Account` column from Agency Clients table.
- [x] Add inline name editing per table row with pencil icon and save on Enter/Blur.
- [x] Add pagination with configurable page sizes: 10, 25, 50, 100, 200, 500.
- [x] Keep row interactions isolated (edit/saving states tied to specific client row).
- [x] Run frontend build validation and capture screenshot.

## Review
- Implemented client-side search state and filtered table rendering in real-time.
- Table now has `ID`, `Nume`, and `Owner` columns only.
- Added row-level inline rename flow that PATCHes only the selected row and shows spinner/check feedback near that row’s pencil.
- Added page size selector + previous/next pagination controls with summary range text.
