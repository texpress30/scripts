# TODO — Agency Accounts pagination refactor

- [x] Add pagination for Google accounts list with default page size 50.
- [x] Add page size selector options 25, 50, 100, 200, 500.
- [x] Add previous/next controls and display current range/page.
- [x] Keep existing attach/detach interactions functional on paged rows.
- [x] Run frontend build and capture screenshot.

## Review
- Implemented client-side pagination over imported Google accounts in Agency Accounts page.
- Default list now shows 50 rows/page, with selectable larger page sizes before moving to next page.
- Added paging footer showing visible interval and page navigation actions.
- Attach/detach controls remain unchanged per row and continue to work on current page items.
