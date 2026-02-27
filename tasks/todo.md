# TODO — Restore client endpoints after mapping migration crash

- [x] Remove runtime seed/sync SQL from `ClientRegistryService._ensure_schema()` that caused `ON CONFLICT DO UPDATE command cannot affect row a second time`.
- [x] Change mapping uniqueness to many-to-many (`UNIQUE(platform, account_id, client_id)`) and drop legacy one-to-one unique constraint.
- [x] Stop calling schema bootstrap from request-time read paths; initialize schema once at API startup.
- [x] Update in-memory mapping behavior to match many-to-many semantics used by Postgres path.
- [x] Run validation checks (compile + backend pytest smoke) and capture outcomes.

## Review
- Removed the `INSERT ... SELECT ... ON CONFLICT` backfill from `_ensure_schema`, eliminating the runtime crash source during request processing.
- `_ensure_schema` now enforces the many-to-many unique constraint and drops the old `(platform, account_id)` unique key when present.
- Added startup-time schema initialization in `app/main.py` and removed per-method `_ensure_schema()` calls to avoid migrations on read endpoints.
- Updated in-memory mapping structure from one-to-one to one-to-many client sets to keep test behavior consistent with DB semantics.
- Validation: Python compilation passes; backend tests run with one unrelated pre-existing Google Ads failure in `test_google_ads_exchange_discovers_accounts_after_token_exchange`.
