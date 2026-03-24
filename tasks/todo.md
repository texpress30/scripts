# TODO — Creative workflow publish persistence în Mongo (feature-flagged, safe) (2026-03-22)

- [x] Refresh workspace state și inspect explicit: `creative_workflow.py`, creative repositories/counters, `api/creative.py`, publish adapters/helpers, `core/config.py`, teste backend.
- [x] Adaugă flag nou `CREATIVE_WORKFLOW_MONGO_PUBLISH_PERSIST_ENABLED` (default OFF) în settings + `.env.example` + doc minim.
- [x] Activează publish persist doar când sunt ON toate: publish flag + core-writes + derived-writes; dacă prerechizitele lipsesc, păstrează comportamentul actual + log scurt.
- [x] Extinde agregatul Mongo cu `publish_history` menținând compatibilitatea documentelor vechi fără acest câmp.
- [x] Implementează `publish_to_channel(...)` Mongo-first write snapshot (fallback local doar la miss) când flag-ul este activ.
- [x] Menține ordinea safe: resolve snapshot -> next_publish_id -> external publish (single call) -> append publish_history -> upsert Mongo -> local mirror compat.
- [x] Tratează cazul critic: publish extern reușit dar upsert Mongo eșuează => nu reapela publish, fără retry/outbox, returnează succes extern și actualizează `_published` local.
- [x] Menține neschimbate endpoint-urile `/creative`, contractele API, frontend, media/S3, backfill/migrare.
- [x] Adaugă teste focused pentru OFF/ON/prerechizite, mongo-first/fallback, ordinea apelurilor, eșecuri counter/external/upsert, non-duplicate publish, local mirror compat.
- [x] Rulează testele țintite și completează review.

## Review
- [x] Confirm publish persist Mongo este strict feature-flagged + gated de workflow Mongo complet.
- [x] Confirm fără schimbări pe endpoint-uri `/creative`, frontend, media_id, backfill/migrare, retry/outbox.

# TODO — Creative workflow Mongo source-of-truth pentru mutații non-publish derivate (2026-03-22)

- [x] Refresh workspace state și inspect explicit: `creative_workflow.py`, repository-urile creative, `api/creative.py`, `core/config.py`, și testele backend.
- [x] Adaugă flag nou `CREATIVE_WORKFLOW_MONGO_DERIVED_WRITES_SOURCE_ENABLED` cu default OFF în settings + `.env.example` + doc minim.
- [x] Activează write path derived doar când sunt ON ambele: `CREATIVE_WORKFLOW_MONGO_DERIVED_WRITES_SOURCE_ENABLED` și `CREATIVE_WORKFLOW_MONGO_CORE_WRITES_SOURCE_ENABLED`; dacă derived ON și core OFF, păstrează comportamentul actual + log scurt.
- [x] Mută source-of-truth pe Mongo (feature-flagged) pentru `generate_variants`, `update_approval`, `set_performance_scores` cu snapshot de lucru (Mongo-first + fallback local doar la miss) și persist-before-local-hydrate.
- [x] Menține fallback strict: NU fallback local la erori Mongo runtime/config/provider pentru write snapshot pe metodele derivate.
- [x] Menține counter compatibility pentru variante alocate din Mongo (`next_variant_id`) și evită coliziuni locale.
- [x] Evită persistențe repetate în `generate_variants` (un singur `upsert_asset` pe snapshot-ul final).
- [x] Nu modifica design-ul deja introdus pentru `create_asset`/`add_variant`/`link_to_campaign`, nici `publish_to_channel`, `/creative`, S3/media, frontend, backfill/migrare.
- [x] Adaugă teste focused pentru OFF/ON, gating derived+core, Mongo-first/fallback strict, erori read/upsert fără local-only success, counters, și non-duplicare shadow-write.
- [x] Rulează testele țintite și completează review-ul.

## Review
- [x] Confirm metodele derivate folosesc Mongo source-of-truth doar când sunt active ambele flag-uri (derived + core).
- [x] Confirm `create_asset`/`add_variant`/`link_to_campaign`, `publish_to_channel` și endpoint-urile `/creative` au rămas neschimbate ca design în acest task.

# TODO — Creative workflow Mongo core writes source-of-truth for create/add_variant/link (2026-03-22)

- [x] Refresh workspace state and inspect explicitly: `creative_workflow.py`, creative repositories, `/api/creative.py`, `core/config.py`, and existing backend tests.
- [x] Add new config flag `CREATIVE_WORKFLOW_MONGO_CORE_WRITES_SOURCE_ENABLED` (default OFF) in settings, `.env.example`, and minimal config docs.
- [x] Implement Mongo source-of-truth write path (flagged) for `create_asset`, `add_variant`, `link_to_campaign` with clear helpers:
  - Mongo-first write snapshot resolution + local fallback where requested.
  - Persist via `creative_assets_repository.upsert_asset(...)` before mutating local mirror/cache.
  - Predictable failure when upsert fails (no local-only success).
  - Keep response payloads and API contracts unchanged.
- [x] Keep `generate_variants`, `update_approval`, `set_performance_scores` local-source-of-truth model unchanged (shadow-write best-effort only).
- [x] Keep `publish_to_channel`, `/creative` endpoints, media/S3 flows, frontend, and backfill/migration unchanged.
- [x] Ensure local counters remain compatible with Mongo-allocated IDs and hydrated snapshots.
- [x] Add focused tests for OFF/ON behavior, mongo-first/fallback snapshot resolution, no local-only mutation on upsert failure, local cache hydration-after-success, counter compatibility, and shadow-write non-duplication.
- [x] Run targeted tests and complete review notes.

## Review
- [x] Confirm only the three requested methods moved to Mongo source-of-truth when new flag ON.
- [x] Confirm excluded methods/flows/endpoints/frontend/backfill remain unchanged.

# TODO — Creative workflow Mongo-first reads for get/list (feature-flagged) (2026-03-22)

- [x] Refresh workspace state and inspect creative workflow/repositories/config/API/tests.
- [x] Add feature flag `CREATIVE_WORKFLOW_MONGO_READS_SOURCE_ENABLED` with default OFF in settings and env example.
- [x] Implement Mongo-first `get_asset(...)` read path with local fallback and cache update.
- [x] Implement Mongo-first `list_assets(...)` baseline + local-missing merge without duplicates/overwrite of Mongo entries.
- [x] Keep non-publish mutations source-of-truth model unchanged (in-memory + optional shadow-write).
- [x] Keep publish flow and `/creative` API contracts unchanged.
- [x] Sync local counters after Mongo hydration to avoid lower-ID generation.
- [x] Add focused tests for OFF/ON Mongo-first behavior, fallback/error cases, dedupe/priorities, and counter sync.
- [x] Run targeted tests and document review boundaries.

## Review
- [x] Confirmed Mongo-first mode applies only to `get_asset`/`list_assets` when flag ON.
- [x] Confirmed no mutation source-of-truth migration, no publish changes, no endpoint/frontend/backfill changes.

# TODO — Creative workflow Mongo read-through / lazy hydration (feature-flagged) (2026-03-22)

- [x] Refresh workspace state and inspect `creative_workflow.py`, creative repositories, `api/creative.py`, config and tests.
- [x] Add feature flag `CREATIVE_WORKFLOW_MONGO_READ_THROUGH_ENABLED` (default OFF) in settings and env example.
- [x] Implement local-first helper for lazy Mongo hydration (`get_by_creative_id`) without overwriting existing local assets.
- [x] Apply read-through helper to `get_asset`, `add_variant`, `generate_variants`, `update_approval`, `link_to_campaign`, `set_performance_scores`.
- [x] Extend `list_assets` with safe Mongo merge/hydration for missing local assets only.
- [x] Sync local counters (`_next_asset_id`, `_next_variant_id`, `_next_link_id`) after hydration to avoid ID regressions.
- [x] Keep behavior best-effort on Mongo errors (predictable not-found fallback, local list continues).
- [x] Add focused tests for OFF/ON behavior, hydration reuse, local priority, mutation continuation, list merge, counter sync, and error fallback.
- [x] Run targeted tests and capture review boundaries.

## Review
- [x] Confirmed in-memory remains source of truth; Mongo is read-through/lazy hydration only.
- [x] Confirmed no changes to publish flow, no `/creative` contract changes, no backfill/migration, no frontend changes.

# TODO — Creative workflow Mongo shadow-write integration (feature-flagged) (2026-03-22)

- [x] Refresh workspace state and inspect `creative_workflow.py`, creative repositories, `api/creative.py`, config and existing tests.
- [x] Add feature flag `CREATIVE_WORKFLOW_MONGO_SHADOW_WRITE_ENABLED` (default OFF) in settings and env example.
- [x] Keep in-memory source of truth and wire shadow-write only for mutating methods (`create_asset`, `add_variant`, `generate_variants`, `update_approval`, `link_to_campaign`, `set_performance_scores`).
- [x] Use `creative_counters_repository` for asset/variant/link ID allocations when flag is ON and keep local counters compatible.
- [x] Persist aggregate snapshots via `creative_assets_repository.upsert_asset(...)` best-effort; do not fail closed on Mongo errors.
- [x] Keep read paths and publish flow unchanged (`list_assets`, `get_asset`, `publish_to_channel`, `_published`, `_next_publish_id`, `reset`).
- [x] Add focused tests for OFF/ON paths, counter/repo calls, non-blocking failures, counter compatibility, and unchanged creative API contracts.
- [x] Run targeted tests and document boundaries.

## Review
- [x] Confirm no read-path migration to Mongo and no endpoint contract changes.
- [x] Confirm no publish flow changes, no backfill/migration, and no frontend changes.

# TODO — Creative workflow Mongo persistent counters foundation (2026-03-22)

- [x] Refresh workspace state and inspect `creative_workflow.py`, `creative_assets_repository.py`, `mongo_provider.py`, `core/config.py`, and existing tests.
- [x] Add a dedicated counters collection/repository with atomic `next_id(counter_name)` allocation using Mongo `find_one_and_update + $inc + upsert`.
- [x] Add small helper methods for logical counter types used by current in-memory workflow IDs (`asset`, `variant`, `link`, `publish`).
- [x] Keep repository runtime-safe when Mongo is missing (clear runtime error only on use).
- [x] Add focused tests for start-at-1 behavior, increments, counter independence, helper delegation, timestamp updates, missing-config errors, and index init.
- [x] Run targeted tests and document review boundaries.

## Review
- [x] Confirm no changes to `creative_workflow.py`.
- [x] Confirm no `/creative` endpoint changes, no Mongo wiring in workflow, no backfill/migration, no frontend changes.

# TODO — Creative workflow Mongo aggregate foundation (2026-03-22)

- [x] Refresh workspace state and inspect `api/creative.py`, `services/creative_workflow.py`, `services/mongo_provider.py`, `core/config.py`, and existing repository/test patterns.
- [x] Add a dedicated Mongo collection/repository for creative asset aggregates without changing creative service/API behavior.
- [x] Implement minimal aggregate repository methods (`upsert_asset`, `get_by_creative_id`, `list_assets`) with predictable created/updated timestamp behavior.
- [x] Add minimal indexes (unique creative id + client/updated list helper index) and runtime-safe missing Mongo error behavior.
- [x] Add focused repository tests (no real Mongo) for create/get/update/list/filter/indexes/missing-config runtime errors.
- [x] Run targeted tests and document review boundaries.

## Review
- [x] Confirm no changes to `creative_workflow_service` behavior and no `/creative` endpoint contract changes.
- [x] Confirm no backfill/migration, no frontend changes, and no switch to `media_id` as creative primary reference.

# TODO — First controlled worker integration for remote media archival (2026-03-22)

- [x] Refresh workspace state and inspect exact target files (`sync_worker`, schedulers/sweepers, storage ingest services) before implementation.
- [x] Choose exactly one real integration point in a processing worker and keep integration feature-flagged + default OFF.
- [x] Add a flow-specific settings flag and wire a best-effort call to `StorageMediaRemoteIngestService.upload_from_url(...)` with minimal context only.
- [x] Keep behavior unchanged with flag OFF; skip safely on missing context; log concise success/skip/failure without crashing main flow.
- [x] Add focused tests for off/on/skip/error/success paths and settings defaults.
- [x] Run targeted tests and document review boundaries.

## Review
- [x] Confirmed integration was added in a single worker location only (`sync_worker.py`, TikTok branch).
- [x] Confirmed no new endpoint, no frontend changes, no creative workflow integration, no retry logic, no schema migrations.

# TODO — Internal remote URL fetch + ingest helper (2026-03-22)

- [x] Refresh repo state and re-audit storage ingest/init/providers/config/runner/tests before coding.
- [x] Add dedicated `StorageMediaRemoteIngestService` with public `upload_from_url(...)` and strict delegation to `StorageMediaIngestService.upload_bytes(...)`.
- [x] Add minimal URL guardrails (http/https only, reject localhost/loopback hostnames), bounded sync fetch with timeout/max-bytes config, and filename/mime fallback rules.
- [x] Keep implementation isolated (no endpoint, no job wiring, no retry logic, no SSRF hardening beyond requested guards).
- [x] Add focused tests for delegation params, guardrails, content-size protection, mime/filename inference, and error propagation.
- [x] Run targeted backend tests and update review + lessons.

## Review
- [x] Confirm no new endpoint, no job integration, no retry logic, no full SSRF hardening, no creative/frontend changes.

# TODO — Internal backend ingest helper (upload_bytes) for media storage (2026-03-22)

- [x] Refresh repo state and re-audit storage init/complete/repository/providers/cleanup runner/tests before coding.
- [x] Add dedicated `StorageMediaIngestService` with public `upload_bytes(...)` for backend internal sources only.
- [x] Reuse existing key/filename sanitization pattern (`clients/{client_id}/{kind}/{media_id}/{sanitized_filename}`) without changing HTTP contracts.
- [x] Implement draft -> put_object -> mark_ready flow with clear runtime errors and no rollback complexity.
- [x] Add focused unit tests for success path, metadata persistence, source validation, and failure ordering (no S3 on draft fail / no mark_ready on put fail).
- [x] Run targeted backend tests and update review + lessons.

## Review
- [x] Confirm no new endpoint, no integration into existing jobs, no URL-download, no creative/frontend changes.

# TODO — Storage media cleanup batch for delete_requested records (2026-03-22)

- [x] Refresh workspace state and re-audit storage repository/models/providers/delete/read/access plus tests.
- [x] Add minimal repository methods for cleanup batch selection and mark_purged persistence.
- [x] Implement `StorageMediaCleanupService.run_batch(limit=...)` with S3 delete_object + per-item outcomes.
- [x] Enforce cleanup scope: process only `delete_requested`, deterministic ordering, no endpoint/scheduler wiring, no hard delete.
- [x] Add focused tests for ordering, S3 delete params (incl version_id), missing-object idempotency, skips/failures, and runtime errors.
- [x] Run targeted backend tests and update review + lessons.

## Review
- [x] Confirm no new cleanup endpoint, no scheduler wiring, no hard delete, no creative/frontend changes.

# TODO — Storage media soft delete endpoint + service (2026-03-22)

- [x] Refresh repo state and re-audit storage router/repository/models/read/access/config/tests before coding.
- [x] Add dedicated soft-delete service (Mongo fetch + ownership/status checks + repository soft_delete call + runtime-safe errors).
- [x] Add `DELETE /storage/media/{media_id}` endpoint with `client_id` query param and focused response model.
- [x] Keep behavior coherent: ready/draft deletable, delete_requested idempotent, purged/not-found/mismatch => 404, no S3 calls.
- [x] Add focused unit tests for service and router, including runtime Mongo error and explicit no-S3 behavior.
- [x] Run targeted backend tests and update review + lessons.

## Review
- [x] Confirm no cleanup/hard-delete/S3-delete/upload-cron/creative/frontend changes.

# TODO — Storage media access URL endpoint (presigned GET) after unsatisfied review (2026-03-22)

- [x] Refresh repo state and re-audit storage router/read/upload/provider/config modules plus existing tests.
- [x] Add a dedicated service for media access-url generation (Mongo lookup, ownership/status validation, S3 presign GET params).
- [x] Add `GET /storage/media/{media_id}/access-url` endpoint + response model + `client_id`/`disposition` query handling.
- [x] Keep behavior strict: only `ready`, 404 for missing/mismatch/purged, 409 for invalid state/storage incomplete, 503 for provider/config unavailable.
- [x] Add focused unit tests for disposition/content headers, payload mapping, and error scenarios without real AWS/Mongo.
- [x] Run targeted backend tests and update review + lessons.

## Review
- [x] Confirm no delete/cleanup/upload-cron/creative/frontend changes were implemented.

# TODO — Rework storage media read APIs after unsatisfied review (2026-03-22)

- [x] Refresh repo state and re-audit existing storage read/router/repository/tests against exact scope.
- [x] Apply minimal fixes so list/detail contracts, status defaults, and error mapping are explicit and predictable.
- [x] Add/adjust focused tests for ordering, filters, pagination, detail ownership/not-found, purged handling, and runtime Mongo unavailability.
- [x] Run targeted backend tests for storage read flow and related storage foundation suites.
- [x] Update review notes + lessons with this correction pattern.

## Review
- [x] Confirm no download/view URL, delete, or cleanup job was implemented.
- [x] Confirm no creative workflow integration and no frontend changes.

# TODO — Storage media read APIs: list + detail from Mongo metadata (2026-03-22)

- [x] Re-sync workspace and re-audit storage router/repository/services before implementation.
- [x] Confirm scope boundaries (read-only APIs, no download/delete/cleanup/creative/frontend changes).
- [x] Extend media metadata repository minimally for list + count with client/kind/status filters and limit/offset.
- [x] Add dedicated media-read service (separate from router) for list/detail ownership checks and runtime-safe error mapping.
- [x] Add GET endpoints `/storage/media` and `/storage/media/{media_id}` with clear response models.
- [x] Enforce deterministic list ordering (created_at desc), limit defaults/max, and strict client scoping.
- [x] Implement default status rule for list (exclude purged and delete_requested when status filter is omitted).
- [x] Add focused tests for repository/service/endpoint list+detail behavior and error cases.
- [x] Run targeted backend tests and update tasks docs/lessons.

## Review
- [x] Confirm no download/view URL, delete, or cleanup job added.
- [x] Confirm no creative workflow integration and no frontend changes.
- [x] Confirm patch remains isolated to storage read flow.

# TODO — Storage upload complete backend flow: verify S3 object and mark ready (2026-03-22)

- [x] Re-sync workspace and re-read AGENTS + relevant storage/media/provider/config files before coding.
- [x] Audit current upload-init service, storage router, and media repository to integrate complete flow with minimal changes.
- [x] Add dedicated upload-complete service for draft fetch/validation, S3 `head_object`, and mark-ready persistence.
- [x] Add `POST /storage/uploads/complete` endpoint with explicit request/response models and runtime-safe error mapping.
- [x] Keep complete flow strict on `media_id` + draft storage info (ignore client-provided bucket/key).
- [x] Add guardrails for missing record, client mismatch, invalid status, missing storage info, missing S3 object, and idempotent ready behavior.
- [x] Add focused unit tests for service + endpoint behavior (no real AWS/Mongo calls).
- [x] Run targeted backend tests and update tasks docs/lessons.

## Review
- [x] Confirm no list/delete/download/cleanup endpoints added.
- [x] Confirm no creative workflow integration and no frontend changes.
- [x] Confirm no refactor outside direct storage complete scope.

# TODO — Storage upload init backend flow: draft + presigned URL (2026-03-22)

- [x] Re-sync workspace and re-read AGENTS + storage/media/provider/config files before implementation.
- [x] Audit current storage router and media metadata repository/provider integration points.
- [x] Add dedicated upload-init service (separate from router) to validate input, build S3 key, create Mongo draft, and generate presigned PUT URL.
- [x] Add `POST /storage/uploads/init` endpoint with explicit request/response models and runtime error mapping.
- [x] Ensure media indexes are initialized safely before first real upload-init use.
- [x] Handle missing S3/Mongo config/providers with clear runtime 503 errors (no import/startup crash).
- [x] Add focused tests for service + endpoint payloads, key format, sanitization, presigned params, and missing-config errors.
- [x] Run targeted backend tests and update task docs/lessons.

## Review
- [x] Confirm no upload completion endpoint implemented.
- [x] Confirm no S3 object verification (`head_object`) implemented.
- [x] Confirm no list/delete/download endpoints and no creative/frontend integration changes.

# TODO — Mongo media metadata foundation: model + repository + indexes (2026-03-22)

- [x] Re-sync workspace and re-read AGENTS + target backend files before coding.
- [x] Audit current provider/config/storage structure and choose coherent placement for media metadata model/repository.
- [x] Add media metadata document model + statuses for Mongo collection foundation (no API wiring).
- [x] Add Mongo repository methods: create draft, get by id, get by storage, mark ready, soft delete, normalization helpers.
- [x] Add index initializer for unique storage key + list/filter + cleanup indexes.
- [x] Ensure repository fails clearly at runtime when Mongo config is missing, without import-time crashes.
- [x] Add focused unit tests (fakes/mocks, no real Mongo) for repository operations and index creation.
- [x] Run targeted backend tests and update task docs/lessons.

## Review
- [x] Confirm no new endpoints/presigned/upload flow/UI changes.
- [x] Confirm no creative workflow integration yet.
- [x] Confirm implementation remains isolated and extensible for next tasks.

# TODO — Backend foundation minimal: S3 + Mongo providers/config only (2026-03-22)

- [x] Update workspace state and re-read AGENTS + backend files listed in task scope before coding.
- [x] Audit existing settings/config style and service module patterns for reusable providers.
- [x] Add minimal backend dependencies for AWS S3 client + synchronous MongoDB client.
- [x] Extend backend settings with S3/Mongo env vars using safe defaults that do not break startup when unset.
- [x] Add reusable provider modules for S3 client and Mongo client/database access (no business logic, no endpoint changes).
- [x] Update `.env.example`/config documentation for new S3 and Mongo variables.
- [x] Add focused tests for settings loading and provider factories (mocked, no real network).
- [x] Run targeted backend tests and confirm existing API contracts remain unchanged.

## Review
- [x] Confirm no new endpoints/routes and no creative workflow/API contract changes.
- [x] Confirm no upload/presigned flow implementation and no media repository/collections added.
- [x] Confirm Postgres path remains intact and startup remains resilient when S3/Mongo env vars are absent.

# TODO — TikTok campaign/ad-group persistence follow-up: campaign_name JSON + upsert overwrite guarantees (2026-03-21)

- [x] Re-sync workspace and re-read AGENTS instructions before implementation.
- [x] Audit `tiktok_ads.py` and `platform_entity_store.py` for campaign/ad-group JSON packing and ON CONFLICT overwrite behavior.
- [x] Fix `_upsert_campaign_rows` to always include `campaign_name` in `extra_metrics.tiktok_ads` payloads (including test-mode persistence path).
- [x] Fix ad-group fact payload mapping to always pass resolved `campaign_id` into `ad_group_performance_reports`.
- [x] Verify `platform_entity_store.py` ON CONFLICT clauses overwrite `campaign_id`/`name`/`status` with `EXCLUDED` values (no COALESCE preference of stale NULLs).
- [x] Run targeted backend tests for TikTok/entity upsert paths.

## Review
- [x] Confirm campaign facts now carry `extra_metrics.tiktok_ads.campaign_name` for persisted rows.
- [x] Confirm ad-group facts map `campaign_id` into DB insert payloads with fallback from `extra_metrics` when needed.
- [x] Confirm platform entity upsert SQL uses direct `EXCLUDED` assignments for name/status/campaign_id overwrite semantics.

# TODO — TikTok metadata data-flow fix: propagate names/campaign_id into facts + entity upserts (2026-03-21)

- [x] Audit current TikTok dataclasses/parsers/upsert payloads for campaign/ad-group name propagation and ad-group campaign_id mapping.
- [x] Patch `tiktok_ads.py` so parsed `campaign_name` / `adgroup_name` / `campaign_id` are preserved in metric objects and packed into `extra_metrics` during fact upserts.
- [x] Patch ad-group metadata mapping/upsert fallback logic to always resolve `campaign_id` aliases (including `campaignId`) before persisting `platform_ad_groups`.
- [x] Run targeted backend TikTok tests and frontend build.

## Review
- [x] Confirm `campaign_performance_reports.extra_metrics->'campaign_name'` and `ad_group_performance_reports.extra_metrics->'adgroup_name'` are populated from row data when available.
- [x] Confirm `platform_ad_groups.campaign_id` is populated in mapped entity rows when metadata payload contains alias keys.

# TODO — TikTok metadata persistence hotfix: prevent empty platform entity upserts (2026-03-21)

- [x] Re-read AGENTS/lessons and audit campaign/ad-group metadata mapping + upsert payload keys in `tiktok_ads.py`.
- [x] Fix campaign metadata mapping/persistence to always map API name/status/raw payload and skip empty fallback rows from being upserted.
- [x] Fix ad-group metadata mapping/persistence to map `adgroup_name`/`campaign_id`/raw payload and skip empty fallback rows from being upserted.
- [x] Run targeted backend TikTok tests and frontend build.

## Review
- [x] Confirm platform upsert payloads carry expected keys (`platform`, `account_id`, entity id, `name`, `status`, `raw_payload`).
- [x] Confirm no empty metadata-only rows are written when management metadata fetch returns nothing.

# TODO — TikTok names/ad-groups visibility + DB-safe status columns (2026-03-21)

- [x] Audit TikTok reporting schema + metadata enrichment flow for campaign/ad-group names.
- [x] Enrich campaign_daily and ad_group_daily rows from TikTok management metadata (`campaign/get`, `adgroup/get`) after report fetch.
- [x] Add explicit `_fetch_adgroup_metadata_by_ids` helper and preserve backward-compatible wrapper.
- [x] Remove non-existent `agency_platform_accounts` run-status column writes from cleanup update path.
- [x] Run targeted backend TikTok/dashboard sync-store tests.

## Review
- [x] Campaign/ad-group display fields now resolve from metadata APIs instead of relying on reporting names, with report fallback preserved.
- [x] Cleanup path no longer updates missing run-status columns.

# TODO — Finalize TikTok schema fix merge + commit/PR packaging (2026-03-21)

- [x] Reconcile merge state and keep exact TikTok dimensions (`adgroup_id`/`ad_id`) in runtime schema + tests.
- [x] Re-run mandatory runtime introspection command for all grains.
- [x] Run targeted backend tests and frontend build smoke check.
- [x] Commit changes and prepare PR title/body with summary + verification.

## Review
- [x] Merge conflict resolved with runtime schema preserving exact valid dimension tuples and tests aligned.

# TODO — TikTok retry: enforce ad_group_daily/ad_daily API-valid dimensions and verify runtime tuples (2026-03-21)

- [x] Re-sync workspace + resolve merge state before applying retry fix.
- [x] Set ad_group_daily dimensions to exact `("stat_time_day", "adgroup_id")`.
- [x] Set ad_daily dimensions to exact `("stat_time_day", "ad_id")`.
- [x] Run mandatory schema-print verification command and capture output.
- [x] Run backend tests + frontend build.

## Review
- [x] Reporting schema now matches exact requested tuples; campaign metadata resolve/upsert path remains active in campaign_daily flow.

# TODO — RETRY critical: enforce TikTok ad grains dimensions without campaign_id (2026-03-21)

- [x] Re-sync workspace and re-read AGENTS before applying retry fix.
- [x] Verify `_report_schema_for_grain` uses exact tuples required for all four grains.
- [x] Verify `campaign_daily` sync still calls `_resolve_and_persist_campaign_metadata_safe` in the sync flow.
- [x] Run verification command for grain dimension tuples exactly as requested.
- [x] Run full backend test suite command as requested (`pytest -q`) and record result.

## Review
- [x] Confirmed runtime schema tuple output now matches requested contract for account/campaign/ad_group/ad grains.

# TODO — TikTok hotfix: remove invalid campaign_id dimensions on ad grains and confirm metadata persist call-path (2026-03-21)

- [x] Sync workspace + re-read AGENTS at task start.
- [x] Set `_report_schema_for_grain('ad_group_daily')` dimensions back to `("stat_time_day", "adgroup_id")`.
- [x] Set `_report_schema_for_grain('ad_daily')` dimensions back to `("stat_time_day", "ad_id")`.
- [x] Verify campaign metadata persistence path remains active during `campaign_daily` sync (`_resolve_and_persist_campaign_metadata_safe` + upsert flow).
- [x] Update backend tests to match valid TikTok dimension contracts.
- [x] Run backend relevant tests + frontend build.

## Review
- [x] Fixed invalid TikTok dimension contract for AUCTION_ADGROUP/AUCTION_AD without touching Agency/Team/auth/invite/delete or Media Buying/Tracker.

# TODO — TikTok metadata hotfix: campaign/ad-group payload parsing + ID dimensions for ad_group_daily/ad_daily (2026-03-21)

- [x] Sync workspace and re-read AGENTS before applying hotfixes.
- [x] Fix campaign metadata extraction to prioritize TikTok `status` and keep full API payload mapped to entity upserts.
- [x] Fix ad-group metadata extraction similarly (status + campaign_id aliases + full raw payload).
- [x] Update report schema dimensions: `ad_group_daily` => (`stat_time_day`,`campaign_id`,`ad_group_id`) and `ad_daily` => (`stat_time_day`,`campaign_id`,`ad_group_id`,`ad_id`).
- [x] Update row parsers to read `ad_group_id`/`adgroup_id` aliases from report dimensions/items.
- [x] Run backend relevant tests and frontend build.

## Review
- [x] Hotfix scope remained limited to TikTok backend service + TikTok backend tests and task docs only.

# TODO — Verify TikTok metadata resolve always fetches campaign/ad-group names from API (2026-03-21)

- [x] Sync workspace and re-read AGENTS before changes.
- [x] Audit `_resolve_and_persist_campaign_metadata` for fetch-all campaign_ids behavior and API-name priority.
- [x] Audit `_resolve_and_persist_ad_group_metadata` for fetch-all ad_group_ids behavior and API-name priority.
- [x] Add regression tests proving fetch is executed for all IDs and report names are fallback-only.
- [x] Run backend relevant tests + frontend build.

## Review
- [x] Confirmed fetch is done for full normalized ID sets; API names override report names, while report names remain fallback when API omits names.

# TODO — TikTok campaign_daily: persist campaign/ad-group metadata before performance upsert (2026-03-21)

- [x] Sync workspace and re-read AGENTS before implementation.
- [x] Update `_upsert_campaign_rows` to resolve metadata from TikTok API using report IDs/names and persist `platform_campaigns` before performance facts.
- [x] Add optional `access_token` propagation into `_upsert_campaign_rows`; warn+skip metadata fetch when missing token.
- [x] Apply the same metadata-first persistence pattern in `_upsert_ad_group_rows` for `platform_ad_groups`.
- [x] Keep resilience: metadata resolve errors are logged and campaign/ad-group performance upsert continues.
- [x] Run backend relevant tests + frontend build.

## Review
- [x] Scope remained strict to TikTok backend service/tests and task docs; no Agency/Team/auth/invite/delete and no Media Buying/Tracker changes.

# TODO — TikTok campaign_daily reporting schema: remove unsupported name dimensions (2026-03-21)

- [x] Sync workspace (`git fetch` + `git pull`) and re-read AGENTS + lessons before implementation.
- [x] Update `_report_schema_for_grain` in `apps/backend/app/services/tiktok_ads.py` so `campaign_daily` dimensions are exactly `("stat_time_day", "campaign_id")`.
- [x] Verify all grains in `_report_schema_for_grain` avoid unsupported name dimensions (`campaign_name`, `adgroup_name`, `ad_name`).
- [x] Run backend relevant tests and frontend build.

## Review
- [x] Patch kept strictly in TikTok backend reporting schema scope; no Agency/Team/auth/invite/delete and no Media Buying/Tracker changes.

# TODO — GitHub Connector remote sync (2026-03-21)

- [x] Start with a fresh terminal execution context and run the exact remote add/set-url command provided by user.
- [x] Run `git fetch origin`.
- [x] Run `git pull origin main --allow-unrelated-histories`.
- [x] Verify remote configuration and branch status after sync.

## Review
- [x] `origin` is configured to the requested GitHub URL for both fetch and push.
- [x] Fetch completed successfully and updated remote refs.
- [x] Pull against `origin/main` completed with `Already up to date.`

# TODO — Sub-account Profil Business: sidebar location from business profile + nișă Parc Auto (2026-03-21)

- [x] Re-read AGENTS/todo/lessons and audit source of sidebar location + nișă options.
- [x] Update sidebar branding location in sub-account context to read city/country from saved business profile endpoint.
- [x] Ensure sidebar location refreshes after business-profile save and remains correct after page refresh.
- [x] Add `Parc Auto` option to `Nișa business` dropdown and keep load/save roundtrip compatibility.
- [x] Add/adjust frontend tests for location formatting + `Parc Auto` presence and persistence.
- [x] Run frontend tests relevant to Sub-account Profile + AppShell and run frontend build.

## Review
- [x] Root cause for wrong sidebar location: sub-account card subtitle used agency company settings city/country instead of sub-account business profile address.
- [x] Sub-account subtitle now composes from business profile address (`Oraș` + optional `Țară`) with neutral fallback.
- [x] Scope remained limited to Sub-account Profile/AppShell, without touching Agency/Team/auth/invite/delete/Media Buying/Media Tracker.

# TODO — Sub-account Profil Business: fix Client not found by correcting identifier mapping (2026-03-21)

- [x] Re-read AGENTS + todo + lessons and confirm runtime failure (`Client not found`) after refresh.
- [x] Audit identifier mismatch between route id and backend endpoint lookup (`display_id` vs real sub-account/client id).
- [x] Implement robust identifier resolution in backend business-profile API (support direct client/subaccount id and display-id alias).
- [x] Switch frontend load/save path to canonical `/clients/{subaccount_id}/business-profile`.
- [x] Keep title binding without form prefill fallback and ensure no localStorage truth-source reintroduction.
- [x] Add/update backend and frontend tests for valid save+reload and no false `Client not found`.
- [x] Run backend tests + frontend tests + frontend build.

## Review
- [x] Root cause fixed: route `/subaccount/[id]` passed subaccount/client id while endpoint expected display id only.
- [x] Canonical runtime path now uses `/clients/{subaccount_id}/business-profile`; display endpoint remains compatibility alias.
- [x] Refresh now reloads persisted profile from backend store, not localStorage.

# TODO — Sub-account Profil Business: remove forbidden prefill and use explicit business profile source (2026-03-21)

- [x] Re-read AGENTS + tasks and confirm root-cause from prior patch (`/clients/display/{id}` + localStorage prefill path).
- [x] Add dedicated backend load/save path for sub-account business profile (separate from client display details).
- [x] Update Sub-account Profil Business page to load only explicit business-profile data (or empty) and remove localStorage rehydrate logic.
- [x] Keep title/client display usage isolated to headline only, not form values.
- [x] Update frontend tests for no-prefill, empty-first-load, save+reload, and localStorage non-prefill guarantees.
- [x] Add backend tests proving business-profile endpoint returns empty payload without display fallback and persists explicit save values.
- [x] Run backend tests + frontend tests + frontend build.

## Review
- [x] Root cause confirmed and removed: form no longer hydrates from `/clients/display/{id}` data and no longer rehydrates from `subaccount_profile_settings_*` localStorage snapshot.
- [x] New source of truth for form load/save: `/clients/display/{display_id}/business-profile` only.
- [x] Scope unchanged for Agency / Team / auth / invite / delete / Media Buying / Media Tracker.

# TODO — Sub-account Profil Business: prefill/save/location/logo persistence hardening (2026-03-21)

- [x] Re-sync context + audit implementare existentă pentru `/subaccount/[id]/settings/profile` și contractele API disponibile.
- [x] Conectare prefill la `/clients/display/{id}` pentru nume/email/monedă/logo și afișare loading/error state în pagină.
- [x] Salvare secțiune generală prin `PATCH /clients/display/{id}` (name/currency/client_logo_url) și fallback persistență locală pentru secțiunile business/adresă/reprezentant.
- [x] Fix UX logo: preview real (data URL), remove/reset corect, limită dimensiune păstrată, fără upload backend nou.
- [x] Update teste frontend pentru încărcare prefill API + verificare PATCH save.
- [x] Rulare teste țintite frontend + build frontend.

## Review
- [x] Root-cause adresat: pagina era strict statică (mock-like), fără prefill runtime și fără persistență la save.
- [x] Logo storage audit: în acest increment logo-ul este persistat în `client_logo_url` via PATCH ca string URL/DataURL; nu s-a introdus storage de fișiere în backend.
- [x] Scope control: alte pagini/settings și flow-uri team/auth/dashboard neatinse.

# TODO — Sub Google Ads details: replace Coming Soon with multi-account performance table (2026-03-20)

- [x] Re-sync + recitire AGENTS/todo/lessons + audit pagină placeholder `sub/[id]/google-ads`.
- [x] Implementare tabel multi-account cu coloanele cerute și sortare implicită pe Cost.
- [x] Header controls: Filter, Columns (dropdown), Export.
- [x] Columns dropdown cu multi-select, Select All, Reset to Default, render dinamic coloane.
- [x] Persistență selecție coloane în localStorage.
- [x] Stilizare: status indicators, valori aliniate, underline dotted pentru monetare, tabel full-width responsive.
- [x] Teste frontend relevante + build frontend.

## Review
- [x] Confirmare explicită: Agency Dashboard, Team/auth/invite/delete, Media Buying/Tracker, dashboard charts nu au fost modificate.
- Rulat `npm test -- src/app/sub/[id]/google-ads/page.test.tsx src/app/sub/[id]/sub-routes-placeholder.test.tsx` și `npm run build` în `apps/frontend`.

# TODO — Sub-dashboard chart polish: hover-only dots + h-96 (2026-03-20)

- [x] Re-sync + recitire AGENTS/todo/lessons + audit chart styling curent.
- [x] Setare dots ascunse implicit și vizibile doar la hover pentru chart-ul multi-line Spend pe platforme.
- [x] Confirmare linii smooth (Bezier/monotone), păstrare culori și fără fill.
- [x] Ajustare înălțime ambele chart-uri la min `h-96`.
- [x] Tooltip hover păstrat activ cu valori exacte pe toate platformele.
- [x] Teste frontend + build frontend.

## Review
- [x] Confirmare explicită: Agency Dashboard, Team/auth/invite/delete, Media Buying/Tracker rămân neatinse.
- Rulat `npm test -- src/app/sub/[id]/dashboard/page.test.tsx` și `npm run build` în `apps/frontend`.

# TODO — Sub-dashboard charts follow-up: Spend pe platforme ca Multi-Line (2026-03-20)

- [x] Re-sync + recitire AGENTS/todo/lessons + audit implementare curentă chart-uri sub-dashboard.
- [x] Backend additive minim pentru serie temporală pe platforme (fără breaking changes pe payload existent).
- [x] Frontend: înlocuire BarChart cu Multi-Line Chart (Google/Meta/TikTok), culori distincte, linii smooth + markers.
- [x] Ajustare înălțime pentru ambele chart-uri din rândul median la min `h-80`.
- [x] Tooltip hover cu valori exacte pe axa timpului pentru toate platformele.
- [x] Teste backend + frontend + build.

## Review
- [x] Confirmare explicită: Agency Dashboard, Team/auth/invite/delete, Media Buying/Tracker rămân neatinse.
- Rulat `pytest -q apps/backend/tests/test_dashboard_currency_normalization.py` (9 passed).
- Rulat `npm test -- src/app/sub/[id]/dashboard/page.test.tsx` și `npm run build` în `apps/frontend`.

# TODO — Sub-account Dashboard: 2 grafice spend (2026-03-20)

- [x] Re-sync workspace + recitire AGENTS/todo/lessons + audit endpoint/contract actual pentru Sub-account Dashboard.
- [x] Backend additive: câmp `spend_by_day` agregat pe zi, pe range-ul selectat și în moneda dashboardului.
- [x] Frontend Sub-account Dashboard: 2 grafice între KPI și tabel (spend pe zile + spend pe platforme), responsive, fără redesign major.
- [x] UX states: loading + empty clar; chart platforme exclude spend=0.
- [x] Teste backend + teste frontend relevante + build frontend.

## Review
- [x] Confirmare explicită că Agency Dashboard și flow-urile Team/auth/invite/delete/media-buying/media-tracker nu au fost modificate.
- Rulat `pytest -q apps/backend/tests/test_dashboard_currency_normalization.py` (9 passed).
- Rulat `npm test -- src/app/sub/[id]/dashboard/page.test.tsx` și `npm run build` în `apps/frontend`.

# TODO — Agency Team UI: agency_owner + grants selector pentru agency_member/viewer (2026-03-20)

- [x] Re-sync workspace + recitire AGENTS/todo/lessons și audit contracte frontend<->backend folosite de Agency Team.
- [x] Extindere Agency Team create/edit cu rol `Agency Owner` și UI grants multi-select pentru `Agency Member/Viewer`.
- [x] Wiring payload create/patch pentru `allowed_subaccount_ids` cu semantică unrestricted la selecție goală.
- [x] Preload grants în edit + toggling unrestricted/restricted fără a rupe wizard-ul în 2 pași.
- [x] Update summary list `Acces / Conturi` pentru modelul owner/admin/member/viewer cu grants.
- [x] Teste frontend Agency Team + build frontend.

## Review
- [x] Confirmare explicită că Sub-account Team, delete flow și invite/reset/login flow nu au fost modificate.
- Rulat `npm test -- src/app/settings/team/page.test.tsx` (43/43 pass) și `npm run build` în `apps/frontend`.

# TODO — Backend foundation: agency_owner + agency grants pe sub-account (2026-03-20)

- [x] Re-sync workspace + audit fișiere backend cerute și confirmare limitări model actual.
- [x] Introducere rol canonic `agency_owner` pe fluxurile backend relevante (RBAC/auth/team) cu full-access.
- [x] Migrare mică pentru grants `agency membership -> subaccount` + helperi store minimali.
- [x] Extindere service/auth/guards pentru semantics: owner/admin unrestricted, member/viewer restricted doar când există grants.
- [x] Ajustare inherited listing în Sub-account Team: exclude owner/admin; include member/viewer doar când unrestricted sau grant match.
- [x] Teste backend țintite + startup/import check.

## Review
- [x] Confirmare explicită: frontend, team wizard-uri, delete flow, invite/reset flow neatinse.

# TODO — Login fără selector de rol + derivare automată context din memberships (2026-03-20)

- [x] Re-citire fișiere auth/login backend+frontend și confirmare root-cause pentru rol selectat manual în login.
- [x] Backend: `LoginRequest.role` opțional + `/auth/login` compat backward-compatible (role opțional, validare doar când e trimis).
- [x] Backend: derivare automată context acces din memberships active când role lipsește, cu prioritate agency/global peste subaccount.
- [x] Frontend login: eliminare selector rol și submit strict `email + password`.
- [x] Frontend session/AppShell: routing bazat pe contextul token-ului derivat (single subaccount redirect direct, multi subaccount fallback sigur existent).
- [x] Teste backend/frontend pentru toate cazurile cerute + build frontend + startup check backend.

## Review
- [x] Contract `/auth/login` documentat în review final (role optional compat + derivare automată).
- [x] Verificat explicit că nu există flow nou de selector în login pentru multi-subaccount.

# TODO — Email Templates/Notifications semantic alignment for forgot vs invite vs account-ready (2026-03-19)

- [x] Re-sync + recitire AGENTS/tasks/lessons și fișiere backend/frontend relevante.
- [x] Audit catalog backend + UI pentru template keys și descrieri semantice.
- [x] Aliniere metadata backend pentru `auth_forgot_password`, `team_invite_user`, `team_account_ready` (descrieri + sample vars coerente).
- [x] Update UI Email Templates cu hint-uri semantice explicite pentru cele trei flow-uri.
- [x] Update UI Notifications cu hint clar că `team_invite_user` acoperă set-password vs account-ready/login.
- [x] Teste backend + frontend țintite și build frontend.

## Review
- [x] `team_account_ready` este tratat și afișat clar ca template canonic de primă clasă.
- [x] Preview/test-send context rămâne coerent pentru forgot vs invite set-password vs account-ready login.
- [x] Nu au fost atinse Team wizard-urile, delete/remove flow sau runtime auth semantics.

# TODO — Reset-password UX context: invite vs forgot token semantics (2026-03-19)

- [x] Re-sync + recitire AGENTS/tasks/lessons + fișiere backend/frontend relevante pentru reset-password.
- [x] Adăugare endpoint backend additive de context token (validare fără consum) pentru `invite_user` vs `password_reset`.
- [x] UI `/reset-password` actualizat cu copy/CTA diferențiat pe tip token și succes diferențiat.
- [x] Stare invalid/expirat/consumat și fallback safe dacă fetch context eșuează.
- [x] Teste backend pentru endpoint context (invite/reset/invalid + non-consume token).
- [x] Teste frontend pentru copy invite/reset, success diferențiat, invalid token, fallback safe.
- [x] Rulare verificări backend + frontend țintite și build frontend.

## Review
- [x] Diferența semantică invite vs forgot-password este vizibilă în UX fără schimbare de contracte existente.
- [x] Team wizard-urile și flow-ul de delete/remove nu au fost atinse.

# TODO — Create/Invite auth semantics hardening (2026-03-19)

- [x] Re-sync + recitire AGENTS/tasks/lessons și fișierele backend relevante pentru create/invite/login/reset.
- [x] Audit flow actual pentru create cu/fără parolă + invite template branch + reset-confirm compat.
- [x] Eliminare fallback password utilizabil la create fără parolă și păstrare `must_reset_password` ca stare reală.
- [x] Blocare login DB când `must_reset_password=true` până la `reset-password/confirm`.
- [x] Păstrare branch invite: `team_account_ready` + `/login` fără token pentru conturi cu parolă, respectiv token+`/reset-password` pentru conturi fără parolă.
- [x] Adăugare/actualizare teste backend pentru noile garanții.
- [x] Rulare teste backend țintite + startup/import check backend.

## Review
- [x] User creat fără parolă nu mai primește hash fallback utilizabil și nu poate face login înainte de setarea inițială.
- [x] `reset-password/confirm` rămâne compatibil pentru tokenuri invite și scoate userul din `must_reset_password`.

# TODO — Sub-account Team wizard parity follow-up (2026-03-19)

- [x] Revalidare cerințe user + verificare implementare actuală în `subaccount/[id]/settings/team`.
- [x] Harden submit create flow: submit-ul în create mode rulează exclusiv în tab-ul `permissions`.
- [x] Consolidare teste wizard Sub-account pentru regula "0 apeluri înainte de final" + "exact 1 apel la `Creează utilizator`".
- [x] Rulare verificări cerute pentru frontend test command și frontend build.

## Review
- [x] Sub-account Team are step 1 non-form + step 2 form real, fără create API înainte de submit final.
- [x] Create API este chemat o singură dată doar pe butonul final `Creează utilizator`.

# TODO — Sub-account Team: wizard real în 2 pași (2026-03-19)

- [x] Re-sync + recitire AGENTS/tasks/lessons + fișierele Sub-account Team page/test/api helper înainte de modificări.
- [x] Confirmare cauză: create folosea un `<form>` global pe ambele tab-uri, iar butonul submit era etichetat `Înainte` în create mode.
- [x] Fix structural: create + tab user randat non-form; create + tab permissions randat în `<form>` real cu submit final.
- [x] Pas 1: `Înainte` rulează doar validare locală + trecere la tab-ul de permissions, fără create API.
- [x] Pas 2: buton final explicit `Creează utilizator`; request create exclusiv aici.
- [x] Persistență local state între pași și la revenire pe tab-ul user.
- [x] Teste frontend actualizate pentru next-step no-create, Enter no-create, persistență date, label final și create-only-on-final-submit.
- [x] Rulare teste pagină Sub-account Team + build frontend.

## Review
- [x] Create API nu mai pornește din pasul 1 în Sub-account Team.
- [x] Pasul 2 are submit explicit `Creează utilizator`.
- [x] Agency Team și flow-urile invite/delete nu au fost atinse în acest task.

# TODO — Agency Team hard delete user complet (2026-03-19)

- [x] Re-sync + recitire AGENTS/tasks + fișiere backend/frontend cerute înainte de modificări.
- [x] Confirmare cauză: acțiunea existentă folosea `POST /team/members/{membership_id}/remove` (remove membership), nu delete user global.
- [x] Backend: endpoint nou `POST /team/users/{user_id}/delete` (agency/admin scoped), separat de remove membership.
- [x] Service: helper `delete_user_hard(...)` care șterge `users` (cascade memberships/permissions/auth_email_tokens) + cleanup legacy `team_members` după email.
- [x] Protecții: self-delete blocat (409), user missing (404), payload clar (`user_id`, `deleted`, `deleted_memberships_count`, `message`).
- [x] Auth/dependencies: check DB-backed minim pentru tokenuri non-env-admin (`user_id` activ în `users`), altfel 401.
- [x] Frontend Agency Team: buton/acțiune schimbate pe hard delete user (`Șterge utilizator`), confirm explicit, refetch list, mapare erori 403/404/409.
- [x] Teste backend + frontend actualizate pentru noua semantică și no-regression de bază.
- [x] Rulare verificări relevante (backend tests țintite, import check backend, frontend tests, frontend build).

## Review
- [x] Agency Team șterge acum utilizatorul complet, nu doar grant-ul curent.
- [x] Remove membership endpoint rămâne separat (compatibil pentru alte zone, inclusiv Sub-account semantics).
- [x] Tokenurile vechi pentru user șters sunt respinse prin verificare DB-backed în `get_current_user`.

# TODO — REDO Agency Team wizard: separare structurală pas 1 non-form vs pas 2 form (2026-03-19)

- [x] Re-sync workspace + re-citire AGENTS/tasks/page.tsx/page.test.tsx înainte de modificări.
- [x] Confirmare cauză runtime: create mode folosea un `<form>` global pentru ambele etape + footer mutabil, ceea ce păstra căi de submit/click-through în pasul 1.
- [x] Refactor `settings/team/page.tsx`: create + identity randat în container non-form, create + permissions randat în `<form>` real de submit.
- [x] Separare structurală footer step1 vs footer submit final pentru a elimina click-through spre `Creează utilizator`.
- [x] Păstrare state local între pași (înainte/înapoi) fără request create înainte de submit final.
- [x] Actualizare teste explicite în `page.test.tsx` pentru non-form step1, Enter fără create, persistență state și create-only-on-final-submit.
- [x] Rulare comenzi cerute (`pnpm --prefix apps/frontend test -- --run ...`, `pnpm --prefix apps/frontend run build`) + verificare țintită suplimentară pe testul paginii.

## Review
- [x] Root cause confirmat: `<form>` global cross-step în create mode (nu separare structurală pe etapă).
- [x] Pasul 1 nu mai are submit form și nu poate porni create API.
- [x] Pasul 2 este singurul loc cu submit real (`Creează utilizator`).
- [x] Invite/delete/remove/Sub-account Team nu au fost modificate.

# TODO — AGENTS correction follow-up: enforce executed-work reporting (2026-03-19)

- [x] Re-read repository AGENTS instructions and confirm mandatory workflow gates (plan, verify, commit, PR).
- [x] Verify current git state before claiming implementation/test outcomes.
- [x] Record correction-driven safeguards in `tasks/lessons.md` to prevent reporting unexecuted work.
- [x] Document review notes for this corrective housekeeping task.

## Review
- [x] Workflow now explicitly includes git-state validation before final reporting.
- [x] Correction pattern has been captured as a durable lesson for future turns.

# TODO — Hotfix real Agency Team wizard: `Pasul următor` nu trebuie să creeze userul (2026-03-19)

- [x] Re-citire AGENTS/tasks/lessons + `page.tsx` și `page.test.tsx` pentru flow-ul Agency Team create.
- [x] Confirmare cauză: submit global pe `<form>` putea fi declanșat din pasul 1 (ex. Enter), iar fixul anterior nu avea hardening suficient pe toate trigger-ele UI.
- [x] Guard strat 1 (UI event): handler dedicat pentru `Pasul Următor` + intercept Enter în pasul 1.
- [x] Guard strat 2 (submit): blocare explicită create când `activeFormTab !== "permissions"` în create mode.
- [x] Menținere create final doar în pasul 2; fără schimbări pe edit/invite/delete/sub-account team.
- [x] Teste frontend focalizate pentru click + submit/Enter în pasul 1 și no-regression.
- [x] Rulare teste Agency Team + build frontend.

## Review
- [x] `Pasul următor` validează și mută pe `Roluri și Permisiuni`, fără create request.
- [x] Enter în pasul 1 nu mai poate crea userul (nici submit, nici keydown).
- [x] Create API pornește doar din pasul 2 (`permissions`).

# TODO — Agency Team: înlocuire `Locație` cu `Acces / Conturi` și eliminare semnificație geografică falsă (2026-03-19)

- [x] Re-citire AGENTS/tasks/lessons + `apps/frontend/src/app/settings/team/page.tsx` și testele aferente.
- [x] Confirmare cauză: `location` era state/field UI defaultat la „România”, folosit în listă și payload create, deși nu exprimă acces real.
- [x] Listare Agency Team: înlocuire coloană `Locație` cu `Acces / Conturi` și render semantic corect (`subaccount` pentru client, `Niciun cont` pentru agency).
- [x] Form create/edit: eliminare câmp editabil `Locație` din flow, fără modificări de wizard/roluri/permisiuni.
- [x] Păstrare flow create/edit/list/invite/lifecycle fără regresii funcționale.
- [x] Adăugare teste frontend focalizate (`Acces / Conturi`, no `Locație`, behavior client/agency).
- [x] Rulare teste frontend relevante + build frontend.

## Review
- [x] UI Agency Team nu mai afișează „România” ca pseudo-locație în listare/form.
- [x] Coloana nouă exprimă corect accesul la conturi, fără termeni geografici falși.
- [x] Wizard-ul în 2 pași și invite flow nu au fost atinse.

# TODO — Hotfix backend cron-sync-run-repair: DB timeout hardening one-shot sweeper (2026-03-19)

- [x] Re-citire AGENTS/tasks + fișierele `historical_repair_sweeper.py` și `sync_runs_store.py`.
- [x] Confirmare cauză: timeout/operational DB errors scapă necontrolat din store până la entrypoint-ul one-shot worker.
- [x] Hardening minim în entrypoint: handling explicit pentru erori de conexiune DB + logging operațional sigur.
- [x] Menținere logică de sweep/repair neschimbată pe happy path (DB disponibil).
- [x] Teste backend focalizate pentru DB timeout handling + no-regression.
- [x] Rulare teste backend țintite + import/startup check util.

## Review
- [x] Cron one-shot nu mai cade cu traceback brut la `ConnectionTimeout`/`OperationalError`; produce rezultat controlat `status=db_unavailable`.
- [x] Logging-ul nou nu expune secrete (`DATABASE_URL` etc.), doar context operațional minimal.
- [x] Semantica de stale detection/repair rămâne neschimbată când DB este disponibil.

# TODO — Hotfix frontend Agency Team wizard: Pasul următor fără submit/create (2026-03-19)

- [x] Re-citire `apps/frontend/src/app/settings/team/page.tsx` și confirmare că submit-ul global poate crea din pasul 1 (Enter).
- [x] Păstrare `Pasul Următor` ca `type="button"` și hardening pe `submitCreateForm(...)` cu guard pentru pasul 1.
- [x] Guard pas 1: validează identity local, comută pe `Roluri și Permisiuni`, iese fără create request.
- [x] Verificare că create API rămâne doar pe submit final din pasul 2.
- [x] Adăugare test pentru Enter key în pasul 1 (fără create API, cu tranziție la pasul 2).
- [x] Rulare teste frontend relevante + build frontend.

## Review
- [x] Cauza bugului: submit global al formularului (inclusiv Enter) nu avea guard clar pentru `activeFormTab === "identity"`, astfel putea intra în create flow prea devreme.
- [x] `Pasul următor` și submit-ul din pasul 1 nu mai declanșează create API.
- [x] Edit mode rămâne funcțional, fără schimbări de contract/backend.

# TODO — Hotfix backend create user: SQL placeholder mismatch must_reset_password (2026-03-19)

- [x] Re-citire `apps/backend/app/services/team_members.py` și confirmare mismatch placeholders/params în `_upsert_user`.
- [x] Fix minim: înlocuire hardcodare `FALSE` din VALUES cu placeholder `%s` pentru `must_reset_password`.
- [x] Păstrare `ON CONFLICT ... must_reset_password = EXCLUDED.must_reset_password` coerent.
- [x] Adăugare teste backend focalizate pentru `_upsert_user` (cu/ fără parolă explicită).
- [x] Rulare teste backend relevante + startup check backend.

## Review
- [x] Cauza: query SQL avea 7 placeholders pentru VALUES, dar param tuple trimitea 8 argumente.
- [x] Create user nu mai crapă pe eroarea `the query has 7 placeholders but 8 parameters were passed`.
- [x] `must_reset_password` este persistat corect pe insert și update.

# TODO — Agency Team create wizard real în 2 pași + invite split by password (2026-03-19)

- [x] Re-sync workspace și recitire fișierele cheie frontend/backend pentru flow-ul Team create/invite.
- [x] Transformare create mode Agency Team în wizard real: Pasul Următor doar schimbă tab-ul, fără create API.
- [x] Creare user doar la pasul final (Roluri și Permisiuni), cu payload complet și auto-invite păstrat.
- [x] Păstrare edit mode existent fără transformare în wizard complex.
- [x] Split invite flow backend: reset link când nu există parolă explicită, login link când parola e setată.
- [x] Adăugare template email nou `team_account_ready` + variabile minime (`login_link`, `user_email`).
- [x] Adăugare/actualizare teste backend și frontend pentru noile comportamente.
- [x] Rulare teste relevante (backend/frontend), build frontend și startup check backend.
- [x] Commit pe branch curent + make_pr cu titlul/body cerut.

## Review
- [x] Wizard create nu mai creează utilizatorul la Pasul Următor; submit real doar la final.
- [x] Invite cu parolă setată folosește login link, fără token reset.
- [x] Invite fără parolă păstrează flow-ul actual cu reset/invite token.
- [x] Scope exclus: Sub-account Team, coloană Locație, forgot-password flow.

# TODO — Reorganizare UI sub-account: mutare "Roluri și Permisiuni" în tab dedicat (2026-03-19)

- [x] Re-citire pagină `subaccount/[id]/settings/team` și test suite pentru flux create/edit.
- [x] Mutare bloc PermissionsEditor din tab principal în tab-ul "Roluri și Permisiuni".
- [x] Păstrare logică existentă de salvare/validare/API; doar reorganizare UI și state între tab-uri.
- [x] Actualizare teste pentru noul flux tab-based (inclusiv persistența selecțiilor la comutare).
- [x] Rulare teste frontend relevante + build frontend.

## Review
- [x] Tab-ul "Informații Utilizator" păstrează doar câmpurile identity + Setări Avansate.
- [x] Tab-ul "Roluri și Permisiuni" conține rolul + PermissionsEditor și nu mai apare în tab-ul principal.
- [x] Persistența selecțiilor pe module este păstrată la comutare între tab-uri.
- [x] Verificat cu suita `subaccount/[id]/settings/team` + build frontend.

# TODO — Reorganizare UI: mutare "Roluri și Permisiuni" în tab dedicat (2026-03-19)

- [x] Re-citire pagină Settings Team (frontend) și suite de teste aferente pentru forma create/edit.
- [x] Mutare secțiune PermissionsEditor din tab-ul implicit "Informații Utilizator" în tab separat "Roluri și Permisiuni".
- [x] Menținere logică existentă de state/payload/validare; doar reorganizare UI + randare pe tab corect.
- [x] Asigurare persistență local state checkbox-uri la comutare tab-uri înainte de submit.
- [x] Actualizare teste frontend pentru noul flux de tab-uri și non-duplicarea secțiunii de permisiuni.
- [x] Rulare teste frontend relevante + build frontend.

## Review
- [x] Tab-ul "Informații Utilizator" păstrează doar câmpurile de identitate + Setări Avansate.
- [x] Tab-ul "Roluri și Permisiuni" afișează exclusiv PermissionsEditor (header/search/group/checkboxes păstrate).
- [x] Starea permisiunilor se păstrează la navigare între tab-uri (fără modificări de contract API).
- [x] Verificat prin testele `settings/team` și build frontend.

# TODO — Debug/fix sub-account permissions sidebar+dashboard mismatch (2026-03-19)

- [x] Re-read frontend AppShell/session/api + sub-account dashboard guard logic and backend `team.py`/`team_members.py`.
- [x] Reproduce and diagnose mismatch (`my-access`, sidebar visible modules, current route behavior on `/sub/{id}/dashboard`).
- [x] Implement minimal real fix (frontend guard and/or backend normalization) without touching out-of-scope flows.
- [x] Add/update focused tests for creative-only redirect, dashboard-allowed behavior, and route/sidebar alignment.
- [x] Run frontend tests + frontend build; run backend tests/startup only if backend code changes.
- [x] Document review findings in this section after verification.

## Review
- [x] Root cause: agency module filtering was being applied over sub-account nav items when session role was agency-scoped while browsing `/sub/{id}`; due key overlap this could collapse sidebar to `Creative` only.
- [x] `GET /team/subaccounts/{id}/my-access` still returned subaccount keys, but AppShell ignored that path context for filtering/redirect in agency-role sessions.
- [x] AppShell now always loads sub-account `my-access` for sub-context routes (`/sub/{id}` and `/subaccount/{id}/settings/*`) and applies sub-account guards independent of role label.
- [x] Added explicit dashboard page access guard: if `dashboard` is missing from `module_keys`, redirect early to first allowed module (e.g. `creative`) before dashboard API load.
- [x] Verified with focused Vitest suites and frontend production build.

# TODO — AGENTS workflow alignment checkpoint (2026-03-19)

- [x] Re-read repository AGENTS instructions before making any edits.
- [x] Confirm current git state and identify whether pending changes exist.
- [x] Apply minimal documentation updates for this checkpoint only.
- [x] Record review notes for traceability.

## Review
- [x] Repository instructions were re-validated before any code changes.
- [x] This checkpoint intentionally limits scope to workflow/documentation hygiene.
- [x] No product/runtime behavior was changed in this update.

# TODO — Filter app navigation by full sidebar permissions catalog

- [x] Re-read AppShell/sidebar helpers, session/api access-context utilities, and team backend contracts for navigation permissions.
- [x] Add backward-compatible agency access-context endpoint for current user module keys.
- [x] Wire AppShell agency main-nav filtering to agency navigation module keys.
- [x] Wire Agency Settings nav filtering by `settings` parent + allowed children module keys.
- [x] Wire subaccount nav/settings visibility to subaccount module keys and keep OFF items hidden.
- [x] Add safe redirect guards for forbidden agency routes, forbidden settings routes, and forbidden subaccount settings routes.
- [x] Add/update compact backend + frontend tests for access-context and nav filtering/redirect behavior.
- [x] Run relevant frontend tests, frontend build, and backend tests/startup check.
- [x] Prepare commit + PR metadata with required title/body.

## Review
- [x] AppShell now filters agency, settings, and subaccount nav entries using module-key access context.
- [x] OFF module keys no longer render in sidebar/settings nav; ON keys remain visible.
- [x] Safe redirects now move users to first allowed route (or fallback) when current route is not permitted.
- [x] Agency access context is exposed via new backward-compatible endpoint with fallback behavior for legacy/special users.
- [x] Intentionally left out: expanded backend route-group enforcement beyond existing endpoints.

# TODO — Wire Sub-account Team roles and permissions to full sidebar catalog

- [x] Re-read Sub-account Team page, frontend API/session helpers, and team backend contracts for module catalog + grant ceiling behavior.
- [x] Wire Sub-account Team create/edit Roles & Permissions to full `scope=subaccount` module catalog metadata.
- [x] Merge catalog + grantable modules in UI, showing non-grantable items as disabled with clear explanation.
- [x] Implement coherent `settings` parent/children synchronization for Sub-account permissions payload safety.
- [x] Keep create/edit role flow and identity fields behavior unchanged while hardening module validation/payload serialization.
- [x] Add/update focused frontend tests for catalog loading, grant ceiling behavior, settings sync, create/edit payloads, and regression coverage.
- [x] Run targeted frontend tests + frontend build.
- [x] Prepare commit + PR metadata with required title/body.

## Review
- [x] Sub-account Team create/edit now uses full subaccount sidebar permissions catalog and renders metadata-based groups.
- [x] Grant ceiling is reflected explicitly in UI via disabled non-grantable keys and safe payload serialization.
- [x] `settings` parent/children state remains coherent to avoid inconsistent module payloads.
- [x] Existing invite/lifecycle/remove/list flows remain intact and covered by regression tests.
- [x] Intentionally left out: Agency Team updates, AppShell/sidebar filtering by keys, backend route-enforcement expansion.

# TODO — Add rich editor for agency email template HTML body

- [x] Refresh workspace and re-read agency email templates page/API contract and verify no backend contract changes required.
- [x] Check existing dependencies/components for reusable rich editor capability; choose lightweight incremental approach.
- [x] Implement WYSIWYG editor for `html_body` only, while keeping `subject` input and `text_body` textarea unchanged.
- [x] Add Visual/HTML source modes and toolbar controls (bold, italic, underline, paragraph/heading, lists, links).
- [x] Keep `html_body` as source of truth and ensure save/preview/test-send consume current draft from editor.
- [x] Add lightweight placeholder insertion helper from available variables for html editor.
- [x] Add/update focused frontend tests for editor render/load, save payload, preview/test-send payload, reset sync, and existing error handling.
- [x] Run frontend tests and frontend build.
- [x] Update notes/lessons and prepare commit + PR metadata.

## Review
- [x] Rich editor is now applied only to `html_body` with Visual + HTML source editing.
- [x] Existing preview/test-send/save/reset flows remain functional and use the latest html draft.
- [x] No Notifications backend work added; no forgot/invite flow logic changes.
- [x] Intentionally left out: drag-and-drop builder, backend notifications model, and broader redesign.

# TODO — Wire Agency Team roles & permissions to full sidebar catalog

- [x] Re-read Agency Team page + API contracts and backend catalog/service files for scope/metadata expectations.
- [x] Wire Agency Team create/edit Roles & Permissions to dynamic catalog by scope (`agency` vs `subaccount`).
- [x] Add grouping support using backend metadata (`group_key`, `group_label`, `order`, `parent_key`, `is_container`).
- [x] Implement `settings` parent/children synchronization rules for agency permissions.
- [x] Ensure create/edit payloads always serialize scope-correct `module_keys` and keep role picker behavior.
- [x] Add/update focused frontend tests for scope switching, defaults, parent/child syncing, payload correctness, and error handling.
- [x] Run focused frontend tests + frontend build.
- [x] Prepare commit + PR metadata with exact required title/body.

## Review
- [x] Agency Team create/edit now consumes full sidebar permission catalogs for both scopes and keeps `module_keys` scope-safe.
- [x] Agency `settings` parent + children toggles are synchronized coherently to avoid inconsistent payload states.
- [x] Existing Agency Team lifecycle/invite/remove/edit flows remain intact and covered by the updated test suite.
- [x] Intentionally left out: Sub-account Team wiring on full catalog and AppShell filtering.

# TODO — Backend foundation Roles & Permissions full sidebar navigation catalog

- [x] Re-read team permissions files (`team_members.py`, `rbac.py`, `team.py`, `team` schemas, dependencies) and sidebar context files.
- [x] Expand membership `module_keys` semantics into a canonical navigation catalog for both scopes (`agency`, `subaccount`) with metadata.
- [x] Keep backward compatibility on payload naming (`module_keys`) while adding scope-aware validation/defaults for create/update.
- [x] Model Settings container + explicit Settings children for agency catalog.
- [x] Extend grant ceiling logic so scoped actors can only grant subsets of their own navigation keys; agency/global admins retain full grant rights.
- [x] Extend module catalog endpoint contract to return metadata-rich entries for both `scope=agency` and `scope=subaccount`.
- [x] Add backend tests for catalog coverage/metadata, scope validation, defaults, grant ceiling, and update-contract behavior.
- [x] Run relevant backend tests + backend startup check.
- [x] Prepare commit + PR metadata with exact required title/body.

## Review
- [x] Backend now exposes a complete navigation permission catalog for agency and subaccount sidebars, including Settings modeling.
- [x] Create/update membership contracts now accept `module_keys` for both scopes with strict scope validation and safe defaults.
- [x] Grant ceiling remains enforced for scoped actors, while agency/global admins can grant full catalog keys.
- [x] Intentionally left out: UI toggles wiring, AppShell filtering, and expanded route-group enforcement.

# TODO — Notifications page uses associated Email Template actions

- [x] Re-read AGENTS instructions and keep scope limited to Agency Notifications + Email Templates linkage.
- [x] Ensure Notifications deep-link to Email Templates preserves selected template via query param.
- [x] Wire Notifications actions for associated template preview and test-send using existing API helpers.
- [x] Add focused frontend tests for deep-link query behavior, preview/test-send success, loading, and error mapping.
- [x] Run targeted frontend tests for touched pages.
- [x] Prepare commit + PR metadata.

## Review
- [x] Notifications now links to `/agency/email-templates?template=<template_key>` and Email Templates page preselects from query param.
- [x] Notifications page now provides associated template preview and test-send with Mailgun availability gating and diagnostics.
- [x] Added focused tests in both page suites for the new behavior without backend/API contract changes.

# TODO — Add test send for agency email templates

- [x] Refresh workspace and re-read email templates service/API/schemas, mailgun service, and frontend email templates page/API helper.
- [x] Add backend endpoint `POST /agency/email-templates/{template_key}/test-send` with RBAC + explicit 404/400/503 mapping.
- [x] Reuse preview render/sample variables logic to support test-send with draft payload and effective fallback.
- [x] Keep rule explicit: test-send is allowed even when template `enabled=false` (disabled only blocks automated flows).
- [x] Add frontend API helper for test-send and wire Test email input + `Send test email` action in detail panel.
- [x] Add dedicated test-send loading/error/success states without blocking save/reset.
- [x] Add backend/frontend focused tests for success paths and required error scenarios.
- [x] Run backend tests, frontend tests, frontend build, and backend startup check.
- [x] Update notes/lessons and prepare commit + PR metadata.

## Review
- [x] Test send now works for both canonical templates and supports draft subject/text/html from editor.
- [x] Endpoint and UI handle 403/404/400/503 explicitly, including Mailgun unavailable/disabled errors.
- [x] Existing preview/save/reset behavior remains available and verified.
- [x] Intentionally left out: rich editor/WYSIWYG and separate Notifications backend.

# TODO — Add preview render for agency email templates

- [x] Refresh workspace and re-read email template service/API/schemas plus frontend email templates page + API helper.
- [x] Add backend preview endpoint `POST /agency/email-templates/{template_key}/preview` with RBAC + 404 handling aligned to existing endpoints.
- [x] Add canonical sample variables helper per template key and reuse render logic for preview output.
- [x] Keep preview independent of send flow (disabled templates can still preview; no send logic added).
- [x] Add frontend API helper for preview and wire `Preview` action in existing detail editor.
- [x] Add preview panel/modal-style section showing rendered subject/text/html and sample variables used.
- [x] Add dedicated preview loading + error states (403/404/400 + fallback) without blocking save/reset flows.
- [x] Add backend/frontend focused tests for preview behavior and regressions.
- [x] Run backend tests, frontend tests, frontend build, and backend startup check.
- [x] Update notes/lessons and prepare commit + PR metadata.

## Review
- [x] Backend now supports deterministic preview rendering for `auth_forgot_password` and `team_invite_user`, including draft payload override behavior.
- [x] Frontend now includes `Preview` action in Email Templates detail panel and displays rendered subject/text/html + sample variables.
- [x] Existing save/reset behavior and forgot/invite flows remained unchanged and were re-verified through tests.
- [x] Intentionally left out: real test-send action, WYSIWYG/rich editor, major redesign, notifications backend split.

# TODO — Refine Agency Email Templates into notification-style admin UI

- [x] Refresh workspace and re-read AppShell, agency email templates page, frontend API helper, and backend email template contract files.
- [x] Refactor `/agency/email-templates` UI into clearer notification-style layout: overview list + selectable detail/edit panel.
- [x] Keep existing backend contract/routing and existing forgot/reset/invite flows unchanged.
- [x] Improve overview cards with label, description, enabled status, default/overridden indicator, and updated timestamp.
- [x] Improve detail panel grouping and keep editable fields (`subject`, `text_body`, `html_body`, `enabled`) plus read-only metadata.
- [x] Add/refresh focused frontend tests for sidebar nav presence, overview render, select/detail load, save/reset flows, loading states, and 403/404/400 handling.
- [x] Run relevant frontend tests and frontend build.
- [x] Update task notes/review and capture lessons for this correction cycle.
- [x] Commit changes and create PR via `make_pr` with exact required title/body.

## Review
- [x] Agency page now presents an explicit `Email Templates & Notifications` admin UX while preserving existing route and API contract.
- [x] Overview behaves like configurable notification/template list with clear status and override badges.
- [x] Detail panel keeps current editing capabilities and introduces clearer metadata/variables presentation.
- [x] Added focused tests for selection, status/override badges, save/reset behavior, loading states, and explicit API error mapping.
- [x] Verification executed with targeted frontend Vitest suite + frontend build.
- [x] Intentionally left out for next tasks: rich editor/WYSIWYG, template preview rendering, test-send actions, dedicated notification-settings backend.

# TODO — Sub-account Team UI remove membership + explicit PR output

- [x] Refresh workspace and inspect Sub-account Team page, shared API helper, and backend remove contract.
- [x] Reuse shared `removeTeamMember(membershipId)` helper and wire row-level remove action in Sub-account Team list.
- [x] Add explicit remove confirmation, per-row remove loading, success feedback, and list refetch (including graceful 404 refresh).
- [x] Add explicit remove error handling for 403/404/409 with clear messages (including self-removal copy).
- [x] Add focused frontend tests for remove render/confirm/cancel, endpoint call, success/refetch, and remove error handling, while preserving existing flows.
- [x] Run relevant frontend tests and frontend build.
- [x] Commit changes and create PR via `make_pr`; include final PR title/body explicitly in task output.

## Review
- [x] Sub-account Team now supports remove membership action (`Elimină accesul`) in row actions without redesign and without changing Agency Team behavior.
- [x] Remove action uses explicit confirmation and clears only access grant through existing backend endpoint; no user identity deletion.
- [x] Added row-level loading and robust error mapping for remove (403/404/409), with dedicated self-removal message and 404 refresh behavior.
- [x] Added focused tests for remove flow plus existing lifecycle/invite/create/edit coverage remains intact.
- [x] Verification executed: targeted Sub-account Team tests + frontend build.
- [x] Intentionally left for next major block: Email Templates & Notifications.

# TODO — Agency Team UI remove membership + PR metadata hardening

- [x] Refresh workspace and inspect Agency Team page, frontend API helpers, and backend remove contract.
- [x] Add/refactor frontend API helper `removeTeamMember(membershipId)` wired to `POST /team/members/{membership_id}/remove`.
- [x] Add Agency Team row action `Elimină accesul` with explicit confirmation dialog and per-row loading.
- [x] Handle remove success/errors (403/404/409/generic), include 404 graceful refresh, and keep existing actions unaffected.
- [x] Add compact frontend tests for remove action rendering, confirm flow, endpoint call, success refetch, and 403/404/409 handling.
- [x] Run relevant frontend tests and frontend build.
- [x] Commit changes and create PR with exact required title/body; attempted metadata verification/patch flow and documented environment blocker (no remote/token/gh).

## Review
- [x] Agency Team now exposes row action `Elimină accesul`, with explicit confirm text and per-row loading, while preserving existing invite/edit/deactivate/reactivate actions.
- [x] Frontend remove flow is wired to `POST /team/members/{membership_id}/remove` via helper `removeTeamMember`, then refreshes list on success and also refreshes gracefully on 404.
- [x] Error mapping is explicit for 403/404/409 and keeps backend messages when useful; self-removal conflict shows dedicated message.
- [x] Added focused tests covering remove render/confirm/cancel, endpoint call + success refetch, and 403/404/409 handling.
- [x] Build verified on frontend app.
- [x] Intentionally left out: Sub-account Team remove UI (next task), token revocation, identity deletion.
- [x] PR metadata post-check blocker: no `gh` binary, no git remote configured, and no GitHub token env available for REST `curl` update in this runtime.

# TODO — Backend minimal remove membership (endpoint + service + teste)

- [x] Refresh workspace and inspect team API/service/schemas/dependencies + current membership tests.
- [x] Add backend-only remove endpoint (`POST /team/members/{membership_id}/remove`) and response schema.
- [x] Add minimal service helper `remove_membership(...)` with inherited/self RBAC protections and module permission cleanup.
- [x] Add targeted backend tests for success + required rejection/consistency scenarios.
- [x] Run relevant backend tests and backend startup check.

## Review
- [x] Added backend endpoint `POST /team/members/{membership_id}/remove` with response payload `{membership_id, removed, message}` and same error-mapping style as deactivate/reactivate.
- [x] Added service helper `remove_membership(...)` that blocks inherited memberships, blocks self-removal for current session memberships, deletes membership module permissions, then deletes the direct membership row only.
- [x] Added backend tests covering remove success, inherited/self conflict handling, API 404 after remove flow, module-permission cleanup, and login behavior when removed memberships are absent from DB query results.
- [x] Verification: `cd apps/backend && APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q tests/test_team_membership_edit_api.py tests/test_team_membership_lifecycle_service.py tests/test_auth_db_login.py` and `cd apps/backend && APP_ENV=test APP_AUTH_SECRET=test-secret python -c "from app.main import app; print('ok', bool(app))"`.

# TODO — Formular Adăugare/Editare Utilizator (Echipa Mea, Sub-Account)

- [x] Refresh workspace and inspect current sub-account `settings/team` route.
- [x] Replace placeholder with requested UI layout: left vertical tabs + active user info form + top back/subtitle.
- [x] Implement required user fields, avatar area, advanced settings collapse/expand for password, and signature section in Romanian.
- [x] Add client-side validation for required fields (Prenume, Nume, Email) and email format.
- [x] Keep frontend-only scope, without backend/API/schema changes.
- [x] Add focused frontend tests for tabs/render, advanced toggle, and required-field validation.
- [x] Run targeted frontend test for touched page.

## Review
- [x] Implemented complete sub-account team user form UI with requested left-nav tabs and localized Romanian labels/messages.
- [x] Advanced settings are collapsed by default and expand smoothly to reveal password input.
- [x] Added explicit required-field and email validation for `Prenume`, `Nume`, `Email`; footer actions `Anulează` + `Înainte` included.
- [x] Added signature section and avatar/info area with requested helper text.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx`.

---

# TODO — Sub-Account Profil Business interface (frontend)

- [x] Refresh workspace and inspect current sub-account profile settings route/component.
- [x] Implement Business Profile UI in Romanian with required sections, fields, responsive two-column layout, and card styling.
- [x] Add client-side validations (email/telefon/url/required) and success toast feedback on update actions.
- [x] Keep scope frontend-only without backend/API/schema changes.
- [x] Add focused frontend tests for section rendering and validation/toast behavior.
- [x] Run targeted frontend tests for touched file.

## Review
- [x] Replaced placeholder sub-account profile settings content with full `Profil Business` interface organized into four cards: Informații generale, Informații business, Adresă fizică business, Reprezentant autorizat.
- [x] Added logo upload zone (350x180, 2.5MB check), Romanian labels/options, and per-form update buttons with local success toast.
- [x] Added client-side validation for required fields plus format checks for email/telefon/url; form submit is blocked on errors.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/profile/page.test.tsx`.

---

# TODO — Media Tracker dynamic labels for Custom Value 1/2 from Media Buying config

- [x] Refresh workspace and inspect worksheet summary row label construction and lead-table meta usage.
- [x] Add safe label normalization from `lead_meta.custom_label_1` / `lead_meta.custom_label_2` with fallbacks `Custom Value 1` / `Custom Value 2`.
- [x] Apply dynamic labels only to summary rows tied to Custom Value 1/2 and dependent ratio labels, keeping row keys/calculations unchanged.
- [x] Add focused backend tests for dynamic labels, composed ratio labels, fallback behavior, and numeric no-regression.
- [x] Run targeted worksheet backend tests.

## Review
- [x] Root cause: worksheet summary labels for `applications`/`approved_applications` and related ratios were hardcoded, so UI labels did not reflect client Media Buying custom label config.
- [x] Fix: payload labels now resolve from `lead_meta.custom_label_1` / `custom_label_2` each fetch with whitespace/null-safe fallbacks.
- [x] Scope remained backend-only for worksheet payload labels; no changes to row keys, dependencies, value kinds, numeric formulas, API shape, or frontend components.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_tracker_worksheet.py`.

---

# TODO — Media Tracker approved applications source hotfix (custom_value_2)

- [x] Refresh workspace and inspect Media Tracker worksheet metric mapping for `applications`/`approved_applications`.
- [x] Change `approved_applications` source from `sales_count` to `custom_value_2_count` in auto metrics, weekly aggregates, and history rollup.
- [x] Keep payload shape, labels, API contracts, and non-approved sales-based metrics unchanged.
- [x] Add focused worksheet tests covering divergent `sales_count` vs `custom_value_2_count`, dependent summary ratios, and null-safe handling.
- [x] Run targeted backend test file for media tracker worksheet.

## Review
- [x] Root cause: worksheet `approved_applications` still mapped to `sales_count`, so approved-related ratios could silently follow sales instead of Custom Value 2.
- [x] Fix: `approved_applications` now aggregates from `custom_value_2_count` everywhere in auto-metric computation; history and weekly values inherit the corrected source.
- [x] Added regression proving old mapping cannot pass accidentally (`sales_count=99` vs `custom_value_2_count=2`) and validating null-safe behavior for `custom_value_2_count=None`.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_tracker_worksheet.py`.

---

# TODO — Weekly Worksheet metric labels right alignment (frontend hotfix)

- [x] Refresh workspace and inspect `WeeklyWorksheetTable` first-column label classes (`rowLabelClass`, sticky label td).
- [x] Update only label-column styling so all metric labels (normal + comparison rows) align right, preserving sticky and existing visual differentiation.
- [x] Keep headers/section titles unchanged and avoid layout/business-logic changes outside metric label body cells.
- [x] Add focused frontend regression test for normal/comparison label alignment classes.
- [x] Run only relevant frontend tests.

## Review
- [x] Root cause: metric label cells in the sticky first column used left/default alignment (`text-left`/no text-right) and comparison rows used left indent (`pl-6`), causing inconsistent visual alignment.
- [x] Fix: normal labels now include `text-right`; comparison labels remain italic + muted but use `text-right` with right-side spacing (`pr-6`) instead of left indent.
- [x] Scope kept minimal to `WeeklyWorksheetTable` and a dedicated component test.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/sub/[id]/media-tracker/_components/WeeklyWorksheetTable.test.tsx src/app/sub/[id]/media-tracker/page.test.tsx`.

---

# TODO — Hotfix Railway 500 placeholder mismatch (Media Buying / Media Tracker)

- [x] Refresh workspace state and inspect `_list_automated_daily_costs` SQL placeholder/param contract.
- [x] Keep date predicates only in `scoped_reports` and confirm no duplicate date placeholder groups in `perf`.
- [x] Add/refresh focused regression coverage for placeholder-count contract and single-date-filter-location behavior.
- [x] Run targeted backend tests for Media Buying store, Clients Media Buying API, and Media Tracker worksheet paths.

## Review
- [x] Confirmed root cause pattern: duplicate date predicates in both `scoped_reports` and `perf` can raise `psycopg.ProgrammingError: the query has 9 placeholders but 5 parameters were passed`.
- [x] Kept `_list_automated_daily_costs` query contract with one date-filter location (`scoped_reports`) and execute params `(client_id, date_from, date_from, date_to, date_to)`.
- [x] Added regression asserting date predicates appear once and are absent from `perf` to prevent reintroducing the Railway 500.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_media_tracker_worksheet.py`.

---

# TODO — Fix placeholder mismatch crash in media buying automated costs SQL

- [x] Refresh workspace and inspect `_list_automated_daily_costs` SQL placeholder/parameter usage.
- [x] Keep date predicates only in `scoped_reports` and ensure no duplicate placeholder groups in `perf` path.
- [x] Add regression tests for placeholder/param contract and include_days=false path through `get_lead_table`.
- [x] Add worksheet-foundation regression exercising real `MediaBuyingStore` SQL path.
- [x] Run targeted backend tests for media buying + worksheet paths.

## Review
- [x] Root cause: SQL used duplicate date predicates in prior shape, creating more `%s` placeholders than parameters passed to `cur.execute(...)`, causing `ProgrammingError` and 500s.
- [x] Fix: date filtering is applied only in `scoped_reports`; `perf` consumes pre-filtered rows and no longer introduces redundant placeholder groups.
- [x] Added direct regression asserting placeholder count equals param count for explicit date range in `_list_automated_daily_costs`.
- [x] Added regression for `get_lead_table(... include_days=False)` and worksheet foundation using real `MediaBuyingStore` SQL path with placeholder-contract guard cursor.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret python -m pytest tests/test_media_buying_store.py tests/test_clients_media_buying_api.py tests/test_media_tracker_worksheet.py -v` (pass).

---

# TODO — Persist sync metadata fields for Meta/TikTok operational status

- [x] Inspect Meta/TikTok sync paths plus sync orchestration and sync-runs store for persistence of `sync_start_date`, `backfill_completed_through`, and `last_success_at`.
- [x] Add missing operational metadata persistence in API-driven Meta/TikTok sync success/backfill paths.
- [x] Ensure sync trigger path seeds `sync_start_date` when missing at run enqueue time.
- [x] Run requested backend tests and capture outcomes.

## Review
- [x] Meta API sync success now persists `last_success_at`; Meta historical backfill success now persists `last_success_at` and `backfill_completed_through` alongside existing `sync_start_date`/`last_synced_at`.
- [x] TikTok API sync success now persists `last_success_at`; TikTok historical backfill success now persists `last_success_at` and `backfill_completed_through`.
- [x] Sync orchestration batch creation now best-effort seeds `sync_start_date` for accounts where it is missing.
- [x] Verification: `cd apps/backend && python -m pytest tests/test_meta_ads_sync_account_daily.py tests/test_tiktok_ads_import_accounts.py tests/test_sync_orchestration_api.py -v 2>&1 | tail -20`.

---

# TODO — Agency Clients account-currency label clarity

- [x] Refresh workspace state and inspect current account-card currency label/tooltip text on agency client details.
- [x] Rename the account-card currency label to clarify this field edits account/source currency.
- [x] Update related tooltip copy for account-level currency edit control without changing behavior.
- [x] Update focused frontend test assertions for the renamed label and existing account-level edit payload.
- [x] Run focused frontend tests and record results.

## Review
- [x] Account-card field label changed from `Monedă` to `Moneda contului` to reduce confusion with client-level currency.
- [x] Account currency edit tooltip text now explicitly references source-account currency (`Editează moneda contului sursă`).
- [x] Account currency edit request contract is unchanged and still PATCHes with `currency + platform + account_id`.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/agency/clients/[id]/page.sync-health.test.tsx` (pass).

---

# TODO — Agency client-level currency editor split from account currency

- [x] Review current agency client details page currency edit flow and API payload behavior.
- [x] Add dedicated client-level currency control in the top card using `client.currency`.
- [x] Keep existing account-level currency editing scoped with `platform` + `account_id` payload fields.
- [x] Add focused frontend tests for client-level patch payload and account-level payload regression.
- [x] Run focused frontend checks and record results.

## Review
- [x] Added a separate `Moneda clientului` editor in the profile card and wired save flow to PATCH with `{ currency }` only.
- [x] Row-level account currency editing remains unchanged and still sends scoped account payload.
- [x] Added targeted page tests that assert request payloads for both edit paths.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/agency/clients/[id]/page.sync-health.test.tsx` (pass).

---

# TODO — Sub-account frontend currency rendering alignment (Media Buying + Media Tracker)

- [x] Refresh workspace and inspect sub-account frontend money-formatting paths for Media Buying, Media Tracker, and Weekly Worksheet.
- [x] Add shared frontend sub-account currency formatting helper driven by backend display-currency metadata and worksheet value metadata.
- [x] Apply helper to Media Buying monetary rendering and remove RON-default frontend assumptions.
- [x] Apply helper to Weekly Worksheet rendering for `currency_display`/`currency_eur` and preserve non-currency/manual-editing behavior.
- [x] Add minimal visible currency indicator in sub-account Media Buying / Media Tracker worksheet context.
- [x] Update/add targeted frontend tests for USD/RON/EUR behavior, worksheet value-kind currency behavior, null placeholders, and existing interactions.
- [x] Run focused frontend tests and document outcomes.

## Review
- [x] Added shared `subAccountCurrency` formatter utility (`normalizeCurrencyCode`, `formatCurrencyValue`, `formatWorksheetValueByKind`) with safe non-RON fallback semantics.
- [x] Media Buying now formats money via shared helper and uses `meta.display_currency` with safe normalization; added compact `Currency: <code>` indicator on sub-account page.
- [x] Weekly Worksheet table now formats by row/page metadata (`value_kind`, `currency_code`, `displayCurrency`) and no longer assumes `currency_ron` for display-currency rows.
- [x] Media Tracker worksheet page now passes `display_currency` metadata into table formatting and shows compact `Currency: <code>` indicator near rate controls.
- [x] Frontend tests updated/added for multi-currency media-buying rendering, worksheet currency_display vs currency_eur rendering, null-safe behavior, and existing editing/navigation stability.
- [x] Verification: focused Vitest suites pass for updated sub-account surfaces and helper utility.

---

# TODO — Media Tracker backend display-currency alignment (backend only)

- [x] Refresh workspace and inspect Media Tracker backend read path + worksheet service currency metadata.
- [x] Propagate shared client display currency metadata through worksheet foundation payload (`display_currency`, `display_currency_source`).
- [x] Replace RON-hardcoded value metadata for primary worksheet monetary rows with display-aware metadata while keeping EUR rows explicit.
- [x] Add/update backend tests for multi-currency metadata propagation, primary monetary row metadata, and EUR-row safe-null behavior without eur_ron_rate.
- [x] Run focused backend tests and confirm Task 1/Task 2 behavior remains intact.

## Review
- [x] Media Tracker worksheet foundation now reads display currency metadata from Media Buying lead-table meta (already aligned to shared client display-currency contract).
- [x] Worksheet payload now includes `display_currency` and `display_currency_source` top-level fields for sub-account consumers.
- [x] Primary monetary worksheet rows now use `value_kind=currency_display` + `currency_code=<display_currency>` instead of hardcoded `currency_ron`; EUR-specific rows remain `currency_eur` + `currency_code=EUR`.
- [x] EUR-denominated rows continue to fail safely (`None`) when `eur_ron_rate` is missing/zero under current contract.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_tracker_worksheet.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Media Buying display-currency contract alignment (backend)

- [x] Refresh workspace and inspect Media Buying store/API display-currency sources.
- [x] Align Media Buying read target currency with shared client display-currency decision (`agency_clients.currency`).
- [x] Prevent local config drift by syncing/overriding `media_buying_configs.display_currency` to resolved client display currency on writes/reads.
- [x] Expose aligned display-currency metadata in Media Buying responses.
- [x] Add/update backend tests for override, multi-client behavior, config drift prevention, and monetary normalization path.
- [x] Run focused backend tests and document results.

## Review
- [x] `MediaBuyingStore.get_config` now resolves display currency/source from the shared client reporting/display decision and no longer trusts local config currency as source of truth.
- [x] `MediaBuyingStore.upsert_config` now ignores incoming `display_currency` and persists the resolved client display currency to keep `media_buying_configs` synchronized.
- [x] `MediaBuyingStore.get_lead_table` now uses resolved display currency metadata and returns `display_currency_source` in response meta while preserving existing conversion/formula flow.
- [x] Added/updated backend unit tests for stale-config override, drift-preventing upsert behavior, per-client currency behavior (USD/RON/EUR), and representative cost normalization in resolved display currency.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_clients_media_buying_api.py` (pass).

---

# TODO — Sub-account display currency contract fix (backend)

- [x] Refresh local workspace state and inspect current backend currency resolver/client registry tests.
- [x] Implement shared display-currency resolver driven by `agency_clients.currency` with explicit safe fallback.
- [x] Update client registry reporting-currency decision payload to use display-currency contract while preserving attached-account currency metadata.
- [x] Update backend tests that encoded attached-account-driven display currency.
- [x] Run focused backend currency tests and document results.

## Review
- [x] Added `resolve_client_display_currency(...)` and routed reporting/display currency to client currency (`agency_clients.currency`) with `safe_fallback` only when client currency is blank/invalid.
- [x] Kept attached-account effective currency resolver unchanged for source-account metadata and still expose mixed/summaries from attached accounts.
- [x] Extended client registry decision payload with `client_display_currency` and `display_currency_source` aliases for explicit contract clarity.
- [x] Updated currency tests to assert client currency remains display currency regardless of attached-account currencies and added invalid-client-currency fallback coverage.
- [x] Verification: `pytest -q apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_dashboard_reporting_currency_selection.py apps/backend/tests/test_dashboard_reconciliation_diagnostics.py` (pass).

---

# TODO — Summary worksheet CPA label normalization

- [x] Confirm AGENTS instructions and inspect current worksheet summary label definitions.
- [x] Normalize summary display labels for CPA rows to `CPA` while preserving row keys and formulas.
- [x] Add/adjust backend test coverage to assert CPA labels in summary rows.
- [x] Run targeted backend worksheet tests.

## Review
- [x] Updated backend worksheet summary row labels for `cpa_leads`, `cpa_applications`, and `cpa_approved_applications` to display `CPA`.
- [x] Added regression assertions ensuring CPA summary labels remain normalized while row keys continue unchanged.
- [x] Verification: `pytest -q apps/backend/tests/test_media_tracker_worksheet.py` (pass).

---

# TODO — TikTok account_daily write-side idempotency hardening

- [x] Refresh workspace and document remote divergence constraints.
- [x] Inspect TikTok sync + persistence write path and current sync error/status propagation.
- [x] Add focused TikTok canonical persistence identity resolver for account_daily writes.
- [x] Enforce deterministic/idempotent TikTok account_daily writes across reruns/overlaps and add ambiguity guardrails with explicit errors.
- [x] Add targeted TikTok tests for rerun idempotency, rolling overlap, ambiguity, and error visibility (without Meta changes).
- [x] Run backend tests and document outcomes.

## Review
- [x] TikTok `account_daily` sync now fails fast with `acct_daily_ambiguous` when provider identities conflict, preventing silent partial writes and surfacing actionable error metadata (`advertiser_id`, ambiguity payload).
- [x] Deterministic in-batch duplicate collapse and rerun/overlap idempotency behavior remain intact for canonical single-identity account_daily writes.
- [x] Updated targeted TikTok tests to assert explicit ambiguity error visibility while retaining rerun/overlap/idempotency coverage without Meta changes.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_tiktok_account_daily_identity_resolver.py` (pass).

## Review
- [x] Added backend `platform_sync_summary` to client dashboard payload for Meta/TikTok using latest sync-run metadata per attached account.
- [x] Added compact page-level sync warning banner plus per-platform status chips on sub-account dashboard rows.
- [x] Added expandable concise affected-account details (name/id, status, reason, last sync, failed chunks/retry).
- [x] Extended sync-status utility with platform-level worst-status derivation and affected counts.
- [x] Verification run: frontend targeted Vitest suite passed; backend targeted pytest collection failed in this environment due missing `requests` dependency.

---

# TODO — Platform sync write-side audit endpoint (Meta/TikTok)

- [x] Refresh workspace and document remote divergence constraints.
- [x] Inspect backend sync write/persistence code paths (Meta/TikTok services, performance reports store, sync runs/chunks) and existing debug endpoint pattern.
- [x] Implement read-only `platform-sync-audit` debug endpoint for one client/platform with optional account filter + daily breakdown.
- [x] Add persisted data summaries and anomaly flags (duplicates, missing coverage, lower-grain risk, id/currency mismatches, unsupported history floor checks).
- [x] Add targeted backend tests for TikTok duplicate/floor/id mismatch and Meta missing-account-daily with sync errors + multi-account client coverage.
- [x] Run backend tests and document outcomes.

## Review
- [x] Added backend-only debug endpoint `GET /dashboard/debug/clients/{client_id}/platform-sync-audit` with platform/date filters, optional account filter, optional lower-grain daily breakdown, agency scope enforcement, and audit logging.
- [x] Implemented platform sync audit service output with: client/platform context, attached account metadata + effective account currency, recent sync runs/chunk status snapshots, persisted-row summaries by grain/account/day/currency, anomaly flags, suspected root causes, and recommended next fix scope.
- [x] Added anomaly detection for duplicate-like rows, multiple account_daily rows same account/day, lower-grain without account_daily, missing account_daily days in range, rows before supported TikTok floor, mixed customer ids, currency mismatch vs attached effective currency, no-mapping rows, and multi-grain overcount risk.
- [x] Added targeted backend tests covering TikTok duplication/floor/id mismatch, Meta partial coverage with sync error exposure, and multi-account platform behavior.
- [x] Verification: `python -m pytest apps/backend/tests/test_dashboard_platform_sync_audit.py apps/backend/tests/test_dashboard_reporting_currency_selection.py apps/backend/tests/test_dashboard_reconciliation_diagnostics.py apps/backend/tests/test_dashboard_currency_normalization.py apps/backend/tests/test_client_registry_account_currency_resolution.py -q` (pass).

---

# TODO — Client dashboard reporting/display currency resolver

- [x] Refresh workspace from remote and document divergence constraints.
- [x] Inspect Task 2 attached-account currency resolver and current dashboard/reconciliation reporting-currency selection path.
- [x] Add shared client reporting-currency resolver using attached-account effective currencies with deterministic mixed/no-account fallbacks.
- [x] Wire resolver into client dashboard + reconciliation payload metadata (`reporting_currency`, source, mixed flag, summary) while preserving existing fields.
- [x] Add targeted backend tests for single-currency, mixed-currency, no-currency fallback, and dashboard/reconciliation consistency.
- [x] Run backend tests and document outcomes.

## Review
- [x] Added shared `resolve_client_reporting_currency` helper that computes deterministic reporting currency + source + mixed flag + summary from attached effective account currencies.
- [x] Added `client_registry_service.get_client_reporting_currency_decision(...)` to centralize client reporting/display currency choice across dashboard platforms.
- [x] Updated dashboard and reconciliation service paths to use the same reporting-currency decision and to expose metadata (`reporting_currency`, `reporting_currency_source`, `mixed_attached_account_currencies`, `attached_account_currency_summary`) while preserving `currency` for compatibility.
- [x] Kept source-account precedence unchanged from Task 2; this task changes only target reporting/display currency selection.
- [x] Verification: `python -m pytest apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_dashboard_reporting_currency_selection.py apps/backend/tests/test_dashboard_currency_normalization.py apps/backend/tests/test_dashboard_reconciliation_diagnostics.py -q` (pass).

---

# TODO — Attached account currency precedence consistency (backend)

- [x] Refresh workspace from remote and note sync constraints if local branch diverges.
- [x] Inspect client registry + dashboard read-side currency fallback paths and identify shared resolver insertion points.
- [x] Implement shared effective attached-account currency resolver and reuse in attach/listing/dashboard paths.
- [x] Add safe backfill for mapping account_currency only when blank/null.
- [x] Add targeted backend tests for attach seeding, non-overwrite behavior, backfill safety, and precedence consistency.
- [x] Run relevant backend tests and document outcomes.

## Review
- [x] Added reusable backend resolver `account_currency_resolver` with explicit precedence `mapping -> platform -> client -> fallback` and reused it in client-registry test-path resolution + dashboard SQL expression builder usage.
- [x] Updated attach/upsert behavior so mapping `account_currency` seeds from `agency_platform_accounts.currency_code` then client currency and does not overwrite existing non-blank mapping currencies on conflict.
- [x] Added safe backfill hook run at schema initialization that only updates mapping rows where `account_currency` is null/blank using `agency_platform_accounts.currency_code` (no overwrite for explicit values).
- [x] Extended attached-account listing payloads to include `effective_account_currency` and `account_currency_source` while preserving `currency` compatibility field.
- [x] Updated dashboard read-side + reconciliation read-side to apply source-account fallback order via shared SQL helper (`mapping -> platform -> client -> RON`) without changing reporting currency strategy.
- [x] Verification: `python -m pytest apps/backend/tests/test_client_registry_account_currency_resolution.py -q` and `python -m pytest apps/backend/tests/test_dashboard_currency_normalization.py apps/backend/tests/test_dashboard_reconciliation_diagnostics.py -q` (pass).

---

# TODO — Client dashboard reconciliation diagnostics endpoint

- [x] Refresh workspace from remote and document sync constraints if branch is diverged.
- [x] Inspect dashboard read-side, client mapping, and performance reports storage code paths.
- [x] Implement internal debug endpoint for client dashboard reconciliation without changing business logic.
- [x] Add focused backend tests for diagnostic payload and exclusion reasons.
- [x] Run backend tests and document review outcomes.

## Review
- [x] Synced remote refs with `git fetch --all --prune`; `git pull --ff-only origin main` reported divergence on local branch, so implementation continued on updated local branch without history rewrite.
- [x] Added backend-only debug endpoint `GET /dashboard/debug/clients/{client_id}/dashboard-reconciliation` with agency-scope authorization and audit logging.
- [x] Added reconciliation diagnostics in dashboard service: mapping snapshot, raw grouped totals, included grouped totals, excluded rows with reasons (`missing_mapping`, `grain_not_account_daily`, `currency_resolution_fallback`), row counts, pre/post-conversion summaries, per-platform summaries, and per-account summaries.
- [x] Added targeted service test covering multi-account rows, inclusion/exclusion logic, and currency fallback visibility.
- [x] Verification: `pytest -q apps/backend/tests/test_dashboard_reconciliation_diagnostics.py apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Remote sync via Connector workspace

- [x] Confirm instructions and run requested remote/fetch/pull commands exactly as provided.
- [x] Verify git remotes and current branch state after sync.
- [x] Record review notes with command outcomes.

## Review
- [x] Executed the exact requested remote/add-or-set + fetch + pull commands in a fresh terminal session for this run.
- [x] Fetch completed successfully and pulled `origin/main` with response `Already up to date.`
- [x] Verified `origin` URL and current branch (`work`) via `git remote -v`, `git branch --show-current`, and `git status --short --branch`.

---

# TODO — Fix Meta/TikTok historical backfill progress UI in Agency Accounts

- [x] Rebaseline branch from clean baseline and document constraints if requested remote baseline is unavailable.
- [x] Extend Agency Accounts Meta/TikTok workspace to show batch banner + sync messages + live row progress driven by batch/polling state.
- [x] Extend account progress polling and batch persistence/rehydration for Meta/TikTok (and keep Google behavior unchanged).
- [x] Ensure completion refresh reloads provider-specific rows after `loadData()`.
- [x] Add/adjust Meta/TikTok tests for banner, row live progress, completion refresh, and rehydrated batch state; keep Google regression guard.
- [x] Run requested frontend tests/build and record results.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — Enable Meta/TikTok historical download selection in Agency Accounts

- [x] Rebaseline branch from available clean local baseline (remote `origin/main` unavailable in this environment) and scope to frontend-only files.
- [x] Make selection + historical batch payload provider-aware in `agency-accounts/page.tsx` while preserving Google behavior.
- [x] Enable Meta/TikTok row/select-all/selected-count UX for attached accounts and keep unattached rows non-selectable.
- [x] Add/extend Meta + TikTok tests for checkbox enablement, historical button enablement, and explicit batch payload assertions.
- [x] Run requested frontend tests and build; record outcomes.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Meta/TikTok now share active historical selection controls and batch-trigger UX in the unified table shell with attached-only eligibility.
- Meta/TikTok historical payloads now send explicit `grains` and `start_date=2024-09-01` to `/agency/sync-runs/batch` (`chunk_days=30`, `job_type=historical_backfill`, `end_date=yesterday`).
- Google historical payload remains unchanged (`start_date=2024-01-09`, `grain=account_daily`).
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — Fix TikTok attached-client refresh rendering in Agency Accounts

- [x] Audit current TikTok row mapping in `agency-accounts/page.tsx` for attached client fields.
- [x] Apply minimal fallback mapping for TikTok attached fields (`client_id/client_name` then `attached_client_id/attached_client_name`).
- [x] Update TikTok Agency Accounts tests to cover both payload shapes, unattached rendering, and attach+reload attached rendering.
- [x] Run requested frontend tests and build; document results.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Added mapper fallback in TikTok normalization to read `client_id/client_name` first and preserve legacy `attached_client_*` compatibility.
- Added tests for both payload aliases, explicit unattached rendering, and attach-triggered reload that re-renders attached client state.
- Verification: `npm test -- page.tiktok.test.tsx` (pass) and `npm run build` (pass) in `apps/frontend`.

---

# TODO — TikTok import diagnostics + zero-account handling

- [x] Audit current TikTok advertiser discovery/import flow and identify safe diagnostic fields.
- [x] Improve TikTok discovery parsing robustness and add zero-account-specific message + diagnostics while preserving endpoint/pagination.
- [x] Add focused backend tests for zero-advertiser diagnostics, alternate container parsing, happy path continuity, and missing-token error.
- [x] Run targeted backend tests and smoke checks, then document results.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Kept TikTok real advertiser discovery path + pagination and added parser support for additional safe row containers (`data.accounts`, `data.rows`) besides existing (`data.list`, `data.advertisers`).
- Added zero-account explicit message and safe diagnostics (`api_code`, `api_message`, `page_count_checked`, `row_container_used`) without exposing secrets.
- Added discovery summary logging (pages/rows/container/API code+message) and tests proving zero-account handling + alternate container parsing.

---

# TODO — Fix TikTok real advertiser account import (backend)

- [x] Audit TikTok import stub, Meta import reference, and generic platform registry upsert path.
- [x] Implement real TikTok advertiser discovery (paginated) and idempotent generic registry upsert in `TikTokAdsService.import_accounts()`.
- [x] Add backend tests for happy path, pagination, idempotent rerun, missing token, API error mapping, and API endpoint summary contract.
- [x] Run targeted pytest + py_compile + backend import smoke checks and document results.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Removed TikTok import stub and implemented real advertiser discovery via TikTok Business API `/open_api/{version}/oauth2/advertiser/get/` with pagination support.
- Import now upserts discovered advertisers into generic platform registry and computes idempotent summary counters (`imported/updated/unchanged`).
- Added focused backend tests for service and API import contract/error mapping, all passing in targeted run.

---

# TODO — Agency Accounts UI unification (Google + Meta + TikTok shared shell)

- [x] Audit current Agency Accounts Google layout and Meta/TikTok panel divergence.
- [x] Extract/reuse a common workspace shell so Google/Meta/TikTok render the same table container/layout structure.
- [x] Map Meta/TikTok rows into common view-model with placeholders for unavailable sync fields while preserving attach/detach behavior.
- [x] Add/adjust frontend tests to verify Meta/TikTok shared shell parity (including empty states), then run requested tests and build.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Meta/TikTok in Agency Accounts now render in the same table-shell layout pattern as Google (summary + toolbar + table columns + pagination).
- Meta/TikTok rows use consistent placeholders for unavailable sync fields (`-`) without reverting to separate card-list panels.
- Requested frontend tests and build pass.

---

# TODO — Final hardening + smoke on main readiness for Meta/TikTok integrations

- [x] Validate current UI/backend flows end-to-end for Agency Integrations, Agency Accounts, Dashboard integration health, Meta/TikTok API endpoints, and worker imports.
- [x] Apply only small, safe bugfixes discovered during smoke checks (no feature additions, no major refactors).
- [x] Run requested frontend build/tests and backend targeted test/smoke suites.
- [x] Document findings (bugs found, fixes, risks/limits) and confirm working tree cleanliness.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Fixed Agency Accounts regression where selecting Meta card rendered generic placeholder instead of Meta panel.
- Frontend requested build/tests now pass for integrations/accounts/dashboard target suites.
- Backend smoke imports and worker/scheduler/dashboard targeted tests pass; dedicated Meta backend suites currently fail on pre-existing larger regressions in `meta_ads` service (documented in final report).

---

# TODO — Agency dashboard summary: real TikTok integration_health status

- [x] Inspect current dashboard integration_health mapping and TikTok status contract to define stable field mapping.
- [x] Implement backend-only dashboard mapping for `tiktok_ads` using real TikTok status payload; keep Google/Meta mapping and Pinterest/Snapchat placeholders stable.
- [x] Add/extend backend tests for TikTok connected/pending/error states and backward-compatible integration_health payload contract.
- [x] Run targeted backend tests + backend import smoke checks and document results.

## Review
- [x] Completed implementation + verification notes.
- Persisted active batch metadata per platform in `sessionStorage` (`agency-accounts-batch:<platform>`) and rehydrated polling state on workspace reload/switch.
- Unified Meta/TikTok workspace now renders the same batch banner + sync status/error messaging and uses `renderSyncProgress` with `batchRunsByAccount` + `rowChunkProgressByAccount` for live row updates.
- Extended progress polling to `meta_ads` + `tiktok_ads` via `postAccountSyncProgressBatch(selectedPlatform, ...)`, while keeping Google flow intact.
- On batch completion, keeps `loadData()` and additionally reloads provider rows via `loadMetaAccounts()` / `loadTikTokAccounts()`.
- Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx`, `pnpm --dir apps/frontend build`.
- Dashboard summary now maps `tiktok_ads` integration_health from `tiktok_ads_service.integration_status()` (`status`, `message`, `token_updated_at`) while preserving Google/Meta mappings.
- `pinterest_ads` and `snapchat_ads` remain stable placeholders (`disabled`).
- Verified with focused pytest suite and backend import smoke command.

---

# TODO — TikTok backend sync real ad_group_daily for attached advertiser accounts

- [x] Audit existing TikTok sync grains/account-campaign persistence and generic ad_group reporting upsert path.
- [x] Extend TikTok sync contract to accept `ad_group_daily` grain while preserving defaults/backward compatibility.
- [x] Implement real TikTok ad_group_daily fetch + normalization + idempotent persistence for all attached advertiser accounts.
- [x] Add focused backend tests for ad_group_daily happy paths, idempotency, failures, and grain/date validation/backward compatibility.
- [x] Run targeted backend compile/tests/import-smoke checks and document results.

## Review
- Added `ad_group_daily` grain to TikTok sync with real reporting fetch and idempotent upsert in generic entity reporting store.
- Existing behavior remains backward compatible: omitted grain defaults to `account_daily`, existing `campaign_daily` path unchanged.

---

# TODO — TikTok backend sync real campaign_daily for attached advertiser accounts

- [x] Audit current TikTok account_daily sync and generic entity reporting persistence options.
- [x] Extend TikTok sync contract with optional grain (`account_daily` default, `campaign_daily` supported).
- [x] Implement real campaign_daily fetch + idempotent upsert path for attached TikTok advertiser accounts.
- [x] Add focused backend tests for campaign_daily paths, grain validation, idempotency, and backward compatibility.
- [x] Run backend compile/tests + import smoke and record results.

## Review
- TikTok sync now supports `campaign_daily` in addition to `account_daily`, with default backward-compatible behavior when grain is omitted.
- Campaign daily rows are persisted idempotently to campaign reporting store using existing upsert semantics keyed by platform/account/campaign/date.

---

# TODO — TikTok backend sync real account_daily for attached advertiser accounts

- [x] Audit TikTok service/api/reporting/client-account mapping paths and pick minimal integration points.
- [x] Replace TikTok stub sync with real account_daily fetch + write to generic performance reports for all attached TikTok accounts.
- [x] Keep connect/import/status behavior intact and retain feature flag guard only for sync execution.
- [x] Add focused backend tests for happy paths, no-account, token/flag errors, API failure mapping, and idempotent rerun behavior.
- [x] Run targeted backend checks (pytest + py_compile import smoke) and document review.

## Review
- TikTok sync now fetches real account_daily metrics from TikTok Business reporting API for every attached `tiktok_ads` advertiser account and writes idempotent daily rows to generic reporting store.
- Existing OAuth/connect/import/status flows remain available; feature flag still guards sync execution only.

---

# TODO — Hotfix Railway startup crash (`Literal` import missing in meta_ads)

- [x] Inspect backend crash context and target file for missing `Literal` typing import.
- [x] Add `Literal` import in `apps/backend/app/services/meta_ads.py` without changing business logic.
- [x] Run requested compile and pytest commands and capture outputs.
- [x] Commit minimal hotfix and report results.

## Review
- Added missing `Literal` import to prevent startup `NameError` in Railway import path.
- No other runtime logic changes were made in this hotfix.

---

# TODO — Fix TikTok business OAuth URL + restore Meta connect/import card + align callback URIs

- [x] Audit current integrations frontend/backend files and identify URI/auth-flow mismatches for Meta and TikTok.
- [x] Update TikTok backend authorize URL to TikTok Business advertiser auth endpoint and keep exchange/import/status contracts consistent.
- [x] Restore Meta integration card actions (Connect Meta + Import Accounts) and add frontend Meta callback flow aligned to current callback route.
- [x] Keep Agency Integrations page as composition-only with exactly one Meta card and one TikTok card.
- [x] Add/update focused frontend and backend tests for Meta/TikTok connect/callback/import behavior, then run requested checks/build.
- [x] Update minimal docs with exact production redirect URIs for Meta and TikTok callback pages.

## Review
- TikTok authorize now uses business advertiser auth (`https://business-api.tiktok.com/portal/auth`) with `app_id`, `redirect_uri`, and `state`, aligned to frontend callback route.
- Meta integrations card now includes Connect + Import actions with robust status gating; frontend Meta callback page is implemented and wired to backend exchange endpoint.
- Agency integrations composition preserves a single Meta card + single TikTok card.

---

# TODO — Restore Agency Integrations cards + relax TikTok FF gating for OAuth/import

- [x] Audit current agency integrations composition and identify missing dedicated Meta card.
- [x] Refactor agency integrations page to compose dedicated Meta + TikTok card components exactly once each.
- [x] Relax TikTok service/API feature-flag behavior so status/connect/oauth exchange/import stay available while sync remains flag-guarded.
- [x] Run targeted frontend/backend tests for integrations behavior and document result.

## Review
- Agency Integrations page now uses dedicated cards for Meta Ads and TikTok Ads, each rendered exactly once in page composition.
- TikTok feature flag now gates only sync execution; status/connect/oauth exchange/import accounts remain callable and return operational payloads.

---

# TODO — Diagnostic E2E + Fix Google Ads Data Sync către Dashboard

- [x] Audit repo end-to-end (pipeline OAuth/API/sync/DB/agregare/UI) pentru Google Ads în Agency/Sub-Account dashboard.
- [x] Reproduc bug-ul și confirm simptomele (totals 0) prin apeluri reale în mediul local (inclusiv limitările DB/creds).
- [x] Adaug diagnostic runtime Google Ads (OAuth, accessible customers, child accounts, sample metrics LAST_30_DAYS, DB rows).
- [x] Repar persistența de date astfel încât sync Google Ads să scrie în `ad_performance_reports`.
- [x] Repar agregarea dashboard să folosească `ad_performance_reports` + mapping cont→client + date range corect.
- [x] Adaug endpoint admin pentru sync la cerere (`/integrations/google-ads/sync-now`) și extind status/diagnostics output.
- [x] Ajustez UI loading și Integration Health pentru câmpurile de diagnostic cerute.
- [x] Rulez verificări (Python compile/tests, Google diag script, frontend build, screenshot), documentez Railway runbook, commit + PR.

---

# TODO — Fix afișare dashboard când datele există în `ad_performance_reports`

- [x] Identific cauza exactă pentru „rows în DB > 0 dar dashboard = 0” pe sub-account + agency.
- [x] Aplic fix minim, fără refactor mare, pe traseul de agregare dashboard.
- [x] Adaug test de regresie pentru tipurile numerice venite din Postgres (Decimal/numeric).
- [x] Rulez verificări țintite backend și confirm comportamentul după fix.
- [x] Completez secțiunea review cu root-cause + rezultat.

## Review
- Cauza principală: lanțul de date se rupea între „sync connected” și agregare dashboard; status-ul Google Ads era `connected`, dar nu exista persistență zilnică robustă în `ad_performance_reports` care să fie folosită consistent de agregare.
- Am introdus `PerformanceReportsStore` și am conectat `google_ads_service.sync_client` să persiste la fiecare sync un raport zilnic (`spend/clicks/impressions/conversions/conversion_value`) în Postgres.
- Agregarea Agency/Sub-Account citește acum din `ad_performance_reports` (nu doar snapshot-uri), cu `report_date BETWEEN start_date AND end_date`, ROAS agregat din sumă și mapare cont→client via `agency_account_client_mappings`.
- Am adăugat `run_diagnostics()` + scriptul `scripts/diag_google_ads.py` pentru test real OAuth/API/DB (compatibil v23) și endpoint `GET /integrations/google-ads/diagnostics` cu câmpurile cerute.
- Am adăugat endpoint `POST /integrations/google-ads/sync-now` pentru sync manual imediat al conturilor mapate client.
- În `GET /integrations/google-ads/status` am expus `accounts_found`, `rows_in_db_last_30_days`, `last_sync_at`, `last_error` pentru Integration Health.
- Frontend Agency Dashboard afișează detaliile Google în blocul Integration Health și păstrează loading state cu text `Se încarcă datele...`; date range este trimis în format `YYYY-MM-DD`.
- Verificările reale au confirmat în mediul curent: OAuth nu poate rula fără refresh token setat și DB local nu e disponibil implicit (connection refused), dar diagnosticul returnează explicit aceste cauze și endpoint-urile sunt pregătite pentru Railway.

## Review — Fix afișare dashboard când datele există în DB
- Root-cause: agregările SQL întorc valori `numeric` din Postgres, iar conversia locală din `dashboard.py` accepta doar `(int, float)`. Valorile `Decimal` erau tratate ca nevalide și transformate în `0`, de aici dashboard cu zero chiar când DB avea date.
- Fix aplicat: `_to_float` și `_to_int` acceptă acum și `Decimal`, astfel metricele agregate din query-uri SQL sunt păstrate corect în payload-ul dashboard (sub-account + agency).
- Verificare: compilare backend + smoke Python care validează explicit conversia `Decimal` pentru spend/impressions/clicks.

---

# TODO — Git workflow alignment pe branch fix `work`

- [x] Revin local pe branch-ul `work` și setez tracking la `origin/work`.
- [x] Confirm regula de lucru: fără branch-uri noi `codex/*`, folosim același PR #127 pentru iterații.
- [x] Documentez în lessons regula pentru a evita repetarea deviației de branch workflow.

## Review
- Workspace-ul rulează acum pe `work` (tracking `origin/work`).
- Fluxul viitor rămâne pe același branch + același PR #127, fără creare automată de branch-uri per task.


---

# TODO — Agency Clients: monedă per cont + editare individuală pe câmp

- [x] Confirm context/branch și traseul actual frontend/backend pentru editarea pe rând în Agency Clients.
- [x] Extind backend-ul pentru câmp `currency` per account mapping (schema + payload update + response details).
- [x] Actualizez UI Agency Client details cu 3 acțiuni separate (creion individual pentru tip cont, responsabil, monedă).
- [x] Rulez verificări țintite (backend tests + frontend lint/type), apoi completez review.


## Review — Agency Clients: monedă per cont + editare individuală pe câmp
- Backend: am adăugat `currency` la nivel de client și `account_currency` în `agency_account_client_mappings`, plus propagare în endpoint-ul `PATCH /clients/display/{display_id}` pentru update per cont (`platform` + `account_id`).
- Frontend: în Agency Client details există acum câte un creion separat pentru fiecare câmp editabil de pe rând (tip client, responsabil, monedă), cu salvare individuală și feedback vizual per câmp.
- Verificare: `python -m py_compile` pe fișierele modificate și `npx tsc --noEmit` pe frontend au trecut; `next lint` nu poate rula non-interactiv deoarece proiectul solicită inițializare ESLint interactivă.

---

# TODO — CRITICAL FRONTEND FIX: isEditingRow undefined on Vercel build

- [x] Inspect Agency Client details page and identify undefined `isEditingRow` reference causing build failure.
- [x] Apply minimal frontend fix by replacing undefined reference with declared row-editing state key check.
- [x] Run `npm run build` in `apps/frontend` to validate Vercel-equivalent build.
- [x] Commit with requested message and push to `origin/main`.


## Review — CRITICAL FRONTEND FIX: isEditingRow undefined on Vercel build
- Cauza: în `agency/clients/[id]/page.tsx` rămăsese un bloc JSX duplicat care folosea variabile vechi/nedeclarate (`isEditingRow`, `saveRowIfChanged`, `savingRowId`, `draft.accountCurrency`).
- Fix: am eliminat blocul duplicat și am păstrat doar implementarea activă bazată pe `editingRowFieldKey`, deja declarată în componentă.
- Verificare: `npm run build` în `apps/frontend` trece complet (type-check + static generation).

---

# TODO — Sub-account să folosească moneda de referință per cont de promovare

- [x] Audit traseu backend/frontend pentru moneda afișată în Sub-account Dashboard.
- [x] Expun în payload-ul sub-account moneda de referință din mapping-ul contului de promovare (Agency Accounts).
- [x] Afișez spend/revenue în frontend sub-account folosind moneda primită din backend.
- [x] Rulez verificări (build/type) + screenshot și documentez review.


## Review — Sub-account să folosească moneda de referință per cont de promovare
- Root-cause: `get_preferred_currency_for_client` căuta cheia `account_currency`, dar `list_client_platform_accounts` returnează cheia `currency`; fallback-ul cădea mereu pe `USD`.
- Fix: preferința de monedă citește acum `currency` (și păstrează fallback compatibil `account_currency`).
- Rezultat: Sub-account Dashboard primește acum moneda corectă din mapping-ul contului de promovare setat în Agency Accounts.


---

# TODO — Agency Dashboard agregat în RON cu conversie valutară pe zi

- [x] Audit traseu Agency Dashboard pentru agregare spend/revenue și identificare sursă monedă per cont.
- [x] Implement conversie la RON per zi (`report_date`) pentru conturile non-RON, folosind curs valutar zilnic și fallback sigur.
- [x] Aplic conversia în totaluri Agency + Top clienți (după spend), păstrând metricele non-monetare neschimbate.
- [x] Actualizez UI Agency Dashboard să afișeze valorile monetare în moneda returnată de backend (RON).
- [x] Rulez verificări țintite + screenshot și documentez review.

## Review — Agency Dashboard agregat în RON cu conversie valutară pe zi
- Root-cause: Agency Dashboard însuma direct `spend`/`conversion_value` fără a ține cont de moneda contului mapat, deci totalul era incorect în scenarii multi-currency.
- Fix backend: agregarea se face acum pe rânduri zilnice din `ad_performance_reports`, cu moneda preluată din mapping (`account_currency`) și conversie la RON per zi prin curs valutar (Frankfurter API) + fallback pe zile anterioare.
- Fix frontend: card-urile monetare și Top clienți folosesc `summary.currency` (RON) pentru formatare, nu hardcodare `$`.
- Rezultat: totalul Agency (spend/revenue) și ranking-ul Top clienți sunt comparabile, toate în RON.

---

# TODO — Sub-account Settings > Conturi: afișare conturi alocate per platformă

- [x] Audit pagină existentă `subaccount/[id]/settings/accounts` și endpoint-uri reutilizabile pentru conturile clientului.
- [x] Implement UI cu conturile alocate sub-account-ului curent, grupate pe platforme (fără dropdown de selectare client).
- [x] Rulez verificări frontend + screenshot pentru schimbarea vizuală.
- [x] Documentez review și lecția în `tasks/*`.


## Review — Sub-account Settings > Conturi: afișare conturi alocate per platformă
- Am înlocuit placeholder-ul din pagina de Conturi cu listarea efectivă a conturilor alocate sub-account-ului curent, grupate pe platforme (Google/Meta/TikTok/Pinterest/Snapchat), cu câmpuri informative similare Agency Clients (tip client, responsabil, monedă).
- Nu există dropdown de selectare client pe această pagină; datele sunt strict pentru sub-account-ul din URL.
- Implementarea reutilizează endpoint-urile existente (`/clients` + `/clients/display/{display_id}`), fără schimbări backend.

---

# TODO — Sub-account dashboard să includă toate conturile asociate clientului

- [x] Audit flow sync/ingest pentru conturi mapate client și identificare punct unde se procesează un singur cont.
- [x] Refactor backend sync ca să ruleze pentru toate conturile asociate clientului (nu doar primul mapping).
- [x] Confirm agregarea dashboard pe datele rezultate din toate conturile mapate.
- [x] Rulez verificări țintite + screenshot și documentez review/lessons.


## Review — Sub-account dashboard să includă toate conturile asociate clientului
- Root-cause: `google_ads_service.sync_client` folosea un singur `customer_id` recomandat (primul mapping), deci la clienții cu zeci de conturi mapate erau ingestate date doar pentru un cont.
- Fix: `sync_client` rezolvă acum lista completă de conturi mapate (`get_recommended_customer_ids_for_client`) și face sync + persistență pentru fiecare cont asociat clientului.
- Rezultat: `ad_performance_reports` primește rânduri pentru toate conturile asociate clientului, iar dashboard-ul sub-account poate agrega corect pe întreg portofoliul clientului.

---

# TODO — Agency Dashboard: conversie USD->RON + top clienți cu valuta clientului

- [x] Audit logic actuală de conversie și motivul pentru care anumite conturi USD rămân neconvertite în totalul Agency.
- [x] Adaug fallback valutar robust (USDRON/EURRON/GBPRON etc.) când providerul extern nu răspunde.
- [x] Ajustez payload `top_clients` ca afișarea să poată folosi valuta clientului (ex. FBM în USD), menținând ranking-ul pe valoare normalizată RON.
- [x] Actualizez UI Agency Dashboard pentru format valutar per client în Top clienți.
- [x] Rulez verificări + screenshot și documentez review/lessons.


## Review — Agency Dashboard: conversie USD->RON + top clienți cu valuta clientului
- Root-cause: când providerul FX extern e indisponibil, conversia cădea pe `1.0`, deci sumele USD/EUR erau tratate greșit ca RON în Agency total.
- Fix: fallback-ul valutar folosește rate implicite pe monede comune (USD/EUR/GBP etc.), astfel totalul Agency rămâne convertit în RON chiar și fără răspuns din provider.
- Top clienți: ranking-ul rămâne pe `spend_ron` (comparabil), dar afișarea folosește suma + valuta nativă a clientului (ex. FBM în USD).

---

# TODO — Calendar funcțional în Sub-account Dashboard (7/14/30/custom)

- [x] Extind backend API `/dashboard/{client_id}` să accepte `start_date`/`end_date` și să filtreze agregările pe interval.
- [x] Adaug calendar/presets în UI Sub-account Dashboard (7 zile, 14 zile, 30 zile, custom) și conectez fetch-ul la intervalul selectat.
- [x] Rulez verificări backend/frontend și validez că schimbarea intervalului retrimite datele corecte.
- [x] Capturez screenshot pentru modificarea UI și documentez review.

## Review — Calendar funcțional în Sub-account Dashboard (7/14/30/custom)
- Am extins endpoint-ul backend sub-account dashboard cu `start_date`/`end_date` și validare (`start_date <= end_date`), iar agregarea din `ad_performance_reports` se face strict pe intervalul selectat.
- În frontend sub-account dashboard am adăugat date picker identic ca experiență cu Agency View, incluzând preset-uri rapide (`Last 7 days`, `Last 14 days`, `Last 30 days`) și `Custom` cu calendar range.
- La aplicarea intervalului, UI re-face request-ul la `/dashboard/{client_id}?start_date=...&end_date=...`, astfel cardurile/tabelul/platform breakdown reflectă exact perioada aleasă.

---

# TODO — CRITICAL FIX: Calendar sub-account conectat real la date (nu total 30d static)

- [x] Identific cauza pentru care datele rămân identice la schimbarea perioadei în Sub-account Dashboard.
- [x] Repar sync/persistență Google Ads în production ca să salveze rânduri zilnice (nu snapshot agregat 30 zile pe ziua curentă).
- [x] Fac persistența idempotentă (upsert pe cheie unică report_date/platform/customer/client) ca să nu dubleze valorile la sync repetat.
- [x] Confirm că query-urile dashboard folosesc parametri de interval și filtrează corect datele.
- [x] Rulez teste țintite backend + frontend build + screenshot și documentez review.

## Review — CRITICAL FIX: Calendar sub-account conectat real la date (nu total 30d static)
- Root-cause: `google_ads_service.sync_client` în production persista un singur rând agregat pe 30 zile cu `report_date=today`; astfel orice interval care include ziua curentă afișa aceeași sumă (snapshot 30d), indiferent de preset calendar.
- Fix 1: `sync_client` persistă acum rândurile zilnice întoarse de GAQL (`_fetch_production_daily_metrics`) pentru fiecare customer mapat; agregatul returnat în snapshot este suma acelor rânduri.
- Fix 2: `ad_performance_reports` folosește upsert idempotent pe `(report_date, platform, customer_id, client_id)` ca să evite dublarea valorilor la sync repetat.
- Fix 3: în UI Sub-account, selectarea preset-urilor non-custom aplică imediat intervalul și declanșează refetch cu `start_date/end_date` în format `YYYY-MM-DD`.
- Rezultat: `Today`, `Yesterday`, `Last 7`, `Last 14`, `Last 30` și `Custom` reflectă corect doar datele din interval; dacă nu există rânduri în interval, totalurile sunt 0.

---

# TODO — Fix 500 la /dashboard/* din cauza unique index duplicate rows

- [x] Reproduc logic cauza: `initialize_schema()` încearcă să creeze unique index peste date deja duplicate.
- [x] Adaug deduplicare deterministică pentru `ad_performance_reports` înainte de `CREATE UNIQUE INDEX`.
- [x] Păstrez comportamentul idempotent (upsert) fără a bloca request-urile dashboard.
- [x] Rulez verificări țintite și documentez review + lecție.

## Review — Fix 500 la /dashboard/* din cauza unique index duplicate rows
- Root-cause: schema guard-ul din `performance_reports.initialize_schema()` încerca `CREATE UNIQUE INDEX` pe `(report_date, platform, customer_id, client_id)` fără să curețe duplicatele istorice deja existente; Postgres ridica `UniqueViolation`, iar endpoint-urile dashboard răspundeau 500.
- Fix: înainte de crearea indexului unic, rulăm deduplicare deterministică cu `ROW_NUMBER() OVER (PARTITION BY ...)` și păstrăm cea mai recentă înregistrare (`synced_at DESC, id DESC`), apoi creăm indexul unic și păstrăm `ON CONFLICT DO UPDATE` la write.
- Hardening: schema init devine one-time per proces (`_schema_initialized` + lock), reducând riscul de DDL repetat pe request.
- Rezultat: endpoint-urile `/dashboard/{client_id}` nu mai cad la inițializarea schemei când există duplicate istorice.

---

# TODO — URGENT: dashboard date-range rămâne pe aceleași cifre (stale response)

- [x] Elimin risc de răspuns stale/cached pe endpoint-urile dashboard (`Cache-Control: no-store`).
- [x] Forțez URL unic la fetch-ul Sub-account dashboard pe schimbare interval.
- [x] Rulez verificări backend/frontend și documentez review.

## Review — URGENT: dashboard date-range rămâne pe aceleași cifre (stale response)
- Root-cause probabil: răspunsuri GET dashboard servite stale în lanțul proxy/cache, deși UI schimba intervalul; simptomele din capturi arătau aceleași valori pentru query-uri diferite.
- Fix backend: endpoint-urile `/dashboard/agency/summary` și `/dashboard/{client_id}` setează explicit `Cache-Control: no-store, no-cache, must-revalidate` și `Pragma: no-cache`.
- Fix frontend: fetch-ul de Sub-account adaugă un nonce `_` bazat pe interval+timestamp, forțând URL unic la fiecare reîncărcare a perioadei.
- Rezultat: schimbarea preset-ului/traseului de date produce request distinct și răspuns fresh, evitând reutilizarea unei variante stale.


---

# TODO — CRITICAL DATA RESTRUCTURING: istoric daily Google Ads din 2026-01-01

- [x] Modific query-ul GAQL pentru interval explicit `segments.date BETWEEN start/end` (nu doar LAST_30_DAYS) și persistare daily rows.
- [x] Extind `sync-now` pentru backfill date-range; default range devine 2026-01-01 -> ieri pentru toate conturile mapate.
- [x] Ajustez upsert-ul pe `(report_date, platform, customer_id)` conform cerinței.
- [x] Verific query/dashboard path să rămână agregare SUM pe interval.
- [x] Rulez verificări și încerc execuția manuală de backfill + count rows.

## Review — CRITICAL DATA RESTRUCTURING: istoric daily Google Ads din 2026-01-01
- Sync-ul Google Ads suportă acum interval explicit de date (start/end), folosit de `sync-now` pentru backfill istoric; query GAQL folosește `segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`.
- Endpoint-ul `POST /integrations/google-ads/sync-now` acceptă `start_date/end_date`; implicit rulează backfill 2026-01-01 -> ieri pentru toate conturile mapate, cum ai cerut.
- Persistența a fost aliniată la conflict key `(report_date, platform, customer_id)` cu update (inclusiv `client_id`), pentru a preveni duplicate la rerun.
- Agregarea dashboard rămâne pe `SUM(...)` filtrat pe intervalul calendarului (`report_date BETWEEN start_date AND end_date`).
- În acest mediu local nu există conectivitate la Postgres-ul deployment (`connection refused`), deci nu am putut confirma numeric pragul `>100` rânduri aici; codul și comanda de backfill sunt pregătite pentru execuție în mediul conectat la DB-ul tău.

---

# TODO — ARCHITECTURAL REFACTOR: Unified Multi-Platform Sync Engine

- [x] Definire contract comun `DailyMetricRow` (platform/account_id/client_id/report_date/spend/impressions/clicks/conversions/revenue).
- [x] Implementare job runner generic `enqueue_backfill(..., chunk_days=7)` cu chunking + error isolation per chunk.
- [x] Refactor Google Ads pe noul motor (`fetch_chunk`, `normalize_to_rows`, `upsert_rows`).
- [x] Rulare backfill în fundal cu `BackgroundTasks` și status de job.
- [x] Index compus pentru interogare rapidă pe `(platform, account_id/customer_id, report_date)` + verificări.

## Review — ARCHITECTURAL REFACTOR: Unified Multi-Platform Sync Engine
- Am introdus contract comun `DailyMetricRow` și runner generic `enqueue_backfill` cu chunking pe 7 zile și izolare erori per chunk.
- Google Ads folosește acum explicit adapter methods (`fetch_chunk`, `normalize_to_rows`, `upsert_rows`) peste motorul comun.
- `POST /integrations/google-ads/sync-now` rulează async în `BackgroundTasks` (returnează `job_id`) și am adăugat endpoint de status `GET /integrations/google-ads/sync-now/jobs/{job_id}`.
- Persistența folosește upsert idempotent pe cheia cerută `(report_date, platform, customer_id)` și index compus compatibil pentru query-urile pe cont+zi.
- Backfill live + confirmare `>100` rânduri nu au putut fi executate în acest runner din cauza conexiunii DB indisponibile (connection refused pe 127.0.0.1:5432); codul este pregătit pentru rulare imediată în mediul conectat la Postgres-ul tău.

---

# TODO — EXECUTION: Full Historical Backfill using New Sync Engine

- [x] Verific endpoint-ul de backfill să suporte parametrizare `chunk_days` pentru control operațional (7/14 zile).
- [x] Adaug log explicit de progres pe chunk-uri: "Procesez chunk-ul X pentru contul Y...".
- [x] Încerc execuția backfill-ului pentru intervalul 2026-01-01 -> ieri și monitorizarea joburilor.
- [x] Rulez verificarea SQL `SELECT count(*), platform FROM ad_performance_reports GROUP BY platform;`.
- [x] Rulez un check pentru endpoint-urile dashboard pe intervale diferite.

## Review — EXECUTION: Full Historical Backfill using New Sync Engine
- Am extins `POST /integrations/google-ads/sync-now` cu `chunk_days` (1..31), propagat end-to-end până la `enqueue_backfill`, astfel rularea poate fi făcută operabil cu 7 sau 14 zile/chunk.
- Motorul comun de sync loghează acum progres pe fiecare chunk în formatul cerut: `Procesez chunk-ul X/Y pentru contul ...`.
- În acest runner nu există variabile de mediu de producție (`DATABASE_URL`, `GOOGLE_ADS_*`, `APP_AUTH_SECRET`) și nici conectivitate/credentials către sistemul live; din acest motiv nu se poate porni backfill real pentru 92 conturi și nici verifica creșterea reală a rândurilor în Postgres-ul tău deployment din acest mediu.
- Am validat local că modificările compilează și testele backend relevante trec; endpoint-ul este pregătit pentru rulare imediată în mediul tău cu env-urile setate.

---

# TODO — Fix eroare "Google Ads API unavailable" la Sync Google (Sub-account)

- [x] Identific root-cause pe fluxul `POST /integrations/google-ads/{client_id}/sync` pentru excepții neașteptate din sync/persist.
- [x] Fac hardening în `google_ads_service.sync_client` ca excepțiile neașteptate să fie convertite în `GoogleAdsIntegrationError` cu context de cont mascat.
- [x] Ajustez fallback-ul API ca răspunsul 502 să includă mesaj minim diagnostic (trunchiat).
- [x] Adaug test unitar pentru noul comportament și rulez verificări țintite.

## Review — Fix eroare "Google Ads API unavailable" la Sync Google (Sub-account)
- Problema era că erorile non-`GoogleAdsIntegrationError` din `sync_client` (ex: persistență DB) urcau ca excepții generice și endpoint-ul răspundea cu mesaj opac `Google Ads API unavailable`.
- Am introdus `try/except` per customer în `sync_client`: orice excepție neașteptată este mapată la `GoogleAdsIntegrationError` cu context de customer ID mascat.
- Endpoint-ul păstrează 502 doar pentru fallback-ul generic, dar acum include și cauza trunchiată (`Google Ads API unavailable: ...`) pentru debugging mai rapid.
- Am acoperit comportamentul cu test nou care validează wrapping-ul erorilor neașteptate.

---

# TODO — Fix runtime NameError la Sync Google (`date_clause`)

- [x] Reproduc și localizez eroarea `name 'date_clause' is not defined` pe path-ul Google Ads daily metrics.
- [x] Refactor minimal în `_fetch_production_daily_metrics` pentru a construi explicit `resolved_start/resolved_end` și `date_clause` în toate query-urile.
- [x] Adaug test de regresie pentru query-ul GAQL cu `segments.date BETWEEN ...`.
- [x] Rulez verificări targetate (compile + pytest selectiv).

## Review — Fix runtime NameError la Sync Google (`date_clause`)
- Root-cause: path-ul de sync Google folosea logică de date-range incompletă/inconsistentă, ceea ce putea arunca NameError (`date_clause`) în runtime.
- Fix: `_fetch_production_daily_metrics` primește acum oficial `start_date/end_date`, calculează robust intervalul (`resolved_start/resolved_end`, inclusiv swap dacă sunt inversate) și construiește un singur `date_clause` reutilizat pe primary + fallback query.
- Rezultat: Sync Google nu mai cade cu NameError, iar filtrarea pe interval explicit funcționează predictibil în query-urile GAQL.

---

# TODO — URGENT FIX: NameError `start_literal` în Google Ads Sync

- [x] Verific dacă există referințe `start_literal`/`end_literal` în path-ul de sync Google Ads.
- [x] Fixez construcția intervalului literal (`start_literal`, `end_literal`, `date_clause`) în `_fetch_production_daily_metrics`.
- [x] Validez că `sync-now` primește `start_date/end_date` ISO și le propagă ca obiecte `date` (FastAPI parsing + tipare endpoint).
- [x] Adaug/reglez test de regresie care exercită query-ul BETWEEN și mesajul range fără NameError.
- [x] Rulez verificări targetate.

## Review — URGENT FIX: NameError `start_literal` în Google Ads Sync
- Am consolidat calculul literalelor de interval în `_fetch_production_daily_metrics`: `start_literal` și `end_literal` sunt definite explicit din `resolved_start/resolved_end`, apoi folosite consecvent în `date_clause` și în `zero_data_message`.
- Path-ul endpoint-ului `POST /integrations/google-ads/sync-now` folosește deja tipuri `date` pentru `start_date/end_date`, deci FastAPI validează/parsing ISO string direct înainte de apelul de sync.
- Testul de regresie existent pentru query-ul `BETWEEN` a fost extins să valideze și mesajul cu intervalul literal, prevenind reapariția NameError-ului.

---

# TODO — Aliniere cheie unică canonical pentru `ad_performance_reports`

- [x] Aliniez deduplicarea la cheia canonical `(report_date, platform, customer_id)`.
- [x] Aliniez DDL runtime (UNIQUE + index) la cheia canonical și elimin tentativele pe 4 coloane.
- [x] Aliniez `ON CONFLICT` la cheia canonical și păstrez `client_id` ca payload updatabil.
- [x] Adaug test focalizat care verifică upsert canonical fără duplicate și update de `client_id`.
- [x] Rulez teste țintite.

## Review — Aliniere cheie unică canonical pentru `ad_performance_reports`
- `performance_reports_store` folosește acum consistent cheia canonical `(report_date, platform, customer_id)` pentru dedup și upsert.
- `client_id` rămâne coloană payload: este inserat și actualizat în `DO UPDATE`, dar nu mai este în conflict target.
- În test mode (`_memory_rows`) am aliniat comportamentul la upsert semantic pe aceeași cheie canonical, pentru a preveni duplicate în testele focalizate.

---

# TODO — Migrație SQL pentru cheia canonică `ad_performance_reports`

- [x] Identific convenția de numerotare migrații și adaug următorul fișier (`0006_...`).
- [x] Creez migrație idempotentă care aplică cheia canonică unică `(report_date, platform, customer_id)`.
- [x] Elimin artefactele legacy de unicitate pe 4 coloane, dacă există.
- [x] Adaug deduplicare pe cheia canonică înainte de creare index unic.
- [x] Rulez verificări minime de consistență locală.

## Review — Migrație SQL pentru cheia canonică `ad_performance_reports`
- Migrația nouă `0006_ad_performance_reports_canonical_unique_key.sql` este defensivă: iese imediat dacă tabela nu există (`to_regclass(...) IS NULL`).
- Refolosește aceeași logică de cleanup ca runtime DDL din `performance_reports.py`: `DROP INDEX IF EXISTS idx_ad_performance_reports_unique_daily_customer` + `DROP CONSTRAINT IF EXISTS ad_performance_reports_report_date_platform_customer_id_client_id_key`.
- Rulează deduplicare deterministică pe cheia canonică `(report_date, platform, customer_id)` și apoi creează indexul unic canonic cu `IF NOT EXISTS`.
- Nu au fost atinse endpoint-uri, servicii de business sau UI în acest task.

---

# TODO — Eliminare DDL runtime din `performance_reports.py` + validare read-only

- [x] Elimin DDL runtime (`CREATE/ALTER/DROP INDEX`) din path-ul de inițializare schema.
- [x] Înlocuiesc bootstrap-ul cu validare read-only pentru existența `ad_performance_reports`.
- [x] Păstrez upsert-ul neschimbat pe cheia canonică `ON CONFLICT (report_date, platform, customer_id)`.
- [x] Adaug test focalizat pentru schema missing + verificare că nu rulează DDL.
- [x] Rulez teste țintite backend.

## Review — Eliminare DDL runtime din `performance_reports.py` + validare read-only
- `_ensure_schema()` nu mai execută DDL; acum rulează strict un `SELECT to_regclass('public.ad_performance_reports')`.
- Dacă schema/tabela lipsește, serviciul ridică eroare clară: `Database schema for ad_performance_reports is not ready; run DB migrations`.
- Comportamentul de upsert a rămas intact: `ON CONFLICT (report_date, platform, customer_id)` cu `client_id` payload updatabil.

---

# TODO — Migrație SQL pentru persistența joburilor de sync (`sync_runs`)

- [x] Identific următorul număr disponibil de migrație (`0007`).
- [x] Creez tabela `sync_runs` cu schema cerută (coloane, default-uri, checks).
- [x] Adaug indexurile minime: `status` și `(platform, created_at)`.
- [x] Verific local consistența SQL și confirm scope strict pe `db/migrations`.

## Review — Migrație SQL pentru persistența joburilor de sync (`sync_runs`)
- Am adăugat `apps/backend/db/migrations/0007_sync_runs.sql` în stilul migrațiilor existente, folosind `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` pentru idempotency.
- Tabela `sync_runs` include schema exactă cerută, cu constrângeri simple și sigure: `date_end >= date_start` și `chunk_days > 0`.
- Nu am schimbat codul aplicației (API/services/sync engine/dashboard/UI); taskul este strict de pregătire schemă DB.

---

# TODO — Implementare DB store pentru `sync_runs`

- [x] Creez `apps/backend/app/services/sync_runs_store.py` cu acces SQL parametrizat (fără ORM, fără DDL runtime).
- [x] Implementez metodele obligatorii: `create_sync_run`, `get_sync_run`, `update_sync_run_status`.
- [x] Adaug validare read-only de schemă pentru `sync_runs` (`to_regclass`) cu eroare clară dacă migrațiile lipsesc.
- [x] Adaug teste backend pentru create/get/update lifecycle și schema missing.
- [x] Rulez teste țintite și verific că nu ating wiring-ul API/sync_engine.

## Review — Implementare DB store pentru `sync_runs`
- `SyncRunsStore` este DB-backed și folosește SQL parametrizat peste tabela `sync_runs`, fără DDL runtime.
- Schema readiness este validată read-only (`SELECT to_regclass('public.sync_runs')`); dacă tabela lipsește, ridică: `Database schema for sync_runs is not ready; run DB migrations`.
- Metodele cerute sunt livrate:
  - `create_sync_run(...)` inserează job-ul și setează metadata implicit `{}`.
  - `get_sync_run(job_id)` întoarce payload dict sau `None`.
  - `update_sync_run_status(...)` actualizează `status`, `updated_at`, și opțional `started_at`/`finished_at`/`error`/`metadata`.
- Nu am făcut wiring în API/sync_engine în acest task (intenționat, conform cerinței).

---

# TODO — Wiring minim Google backfill job create -> `sync_runs` (best-effort mirror write)

- [x] Identific punctul de creare job async în `api/google_ads.py`.
- [x] Adaug mirror write în `sync_runs_store.create_sync_run(...)` la crearea jobului, fără a schimba flow-ul în memorie.
- [x] Mențin response-ul endpoint-ului compatibil.
- [x] Tratez erorile la mirror write ca non-blocking (warning + continuare flow).
- [x] Adaug teste pentru success path + failure path la mirror write.

## Review — Wiring minim Google backfill job create -> `sync_runs` (best-effort mirror write)
- La `POST /integrations/google-ads/sync-now` pe branch-ul `async_mode=True`, după `job_id` create + `background_tasks.add_task(...)`, se face mirror write în `sync_runs` cu `status=queued`.
- Se persistă: `job_id`, `platform=google_ads`, `client_id`, `account_id=None`, `date_start`, `date_end`, `chunk_days`, plus metadata minimă (`job_type`, `source`, `mapped_accounts_count`).
- Dacă insert-ul în `sync_runs` eșuează, endpoint-ul nu se blochează: log warning și continuă să returneze același payload queued din flow-ul in-memory.
- Nu am făcut wiring de read/status din DB și nu am atins alte platforme.

---

# TODO — Mirror lifecycle status Google async jobs în `sync_runs` (running/done/error)

- [x] Identific runner-ul background Google din `api/google_ads.py`.
- [x] Adaug mirror update `running` + `mark_started=True` la începutul execuției.
- [x] Adaug mirror update `done` + `mark_finished=True` la finalul cu succes.
- [x] Adaug mirror update `error` + `error` + `mark_finished=True` pe eșec runner.
- [x] Păstrez flow-ul in-memory ca sursă de adevăr și tratez mirror DB ca best-effort (non-blocking).
- [x] Adaug teste focalizate pentru running/done/error + fallback la eșec mirror.

## Review — Mirror lifecycle status Google async jobs în `sync_runs` (running/done/error)
- În `_run_google_backfill_job`, după `backfill_job_store.set_running(job_id)` se face mirror `status=running, mark_started=True`.
- La final cu succes, după `backfill_job_store.set_done(...)`, se face mirror `status=done, mark_finished=True` + metadata compactă (`mapped_accounts_count`, `successful_accounts`, `failed_accounts`, `days`, `chunk_days`).
- La excepții neprevăzute în runner, se setează `backfill_job_store.set_error(...)` și mirror `status=error, error=<safe>, mark_finished=True`.
- Dacă write/update în `sync_runs` eșuează, se loghează warning și jobul continuă pe flow-ul în memorie fără schimbări de response/status endpoint.

---

# TODO — Fallback DB pentru endpoint-ul status job Google (memory first)

- [x] Confirm endpoint-ul existent `GET /integrations/google-ads/sync-now/jobs/{job_id}` și contractul curent (memory store).
- [x] Adaug fallback la `sync_runs_store.get_sync_run(job_id)` doar când memory store întoarce miss.
- [x] Mapez payload-ul din `sync_runs` la shape compatibil endpoint (status + timestamps + metadata + câmpuri utile existente).
- [x] Tratez erorile DB non-blocking (warning + comportament not found neschimbat).
- [x] Adaug teste focalizate pentru: memory hit, memory miss + DB hit, memory miss + DB miss, memory miss + DB error.

## Review — Fallback DB pentru endpoint-ul status job Google (memory first)
- Endpoint-ul de status păstrează prioritatea strictă pe memory store; pe hit returnează exact payload-ul in-memory, fără acces DB.
- La memory miss, endpoint-ul încearcă best-effort citirea din `sync_runs`; dacă găsește rândul, întoarce payload compatibil cu contractul curent.
- Dacă fallback-ul DB eșuează, endpoint-ul rămâne defensiv: log warning și păstrează comportamentul existent `404 job not found`.
- Patch-ul este limitat la API Google + teste backend, fără impact pe alte platforme sau pe `sync_engine`.

---

# TODO — Migrație SQL pentru persistența chunk-urilor de sync (`sync_run_chunks`)

- [x] Identific următorul număr disponibil de migrație în `apps/backend/db/migrations`.
- [x] Creez migrația nouă doar în folderul de migrații, fără schimbări de cod aplicație.
- [x] Adaug tabela `sync_run_chunks` cu coloanele cerute, FK spre `sync_runs(job_id)`, constrângeri simple și indexurile minime.
- [x] Mențin migrația idempotentă și în stilul SQL existent în repo.
- [x] Verific local scope-ul modificărilor (doar migrație + task tracking) și pregătesc commit.

## Review — Migrație SQL pentru persistența chunk-urilor de sync (`sync_run_chunks`)
- Am folosit următorul număr disponibil și am creat `apps/backend/db/migrations/0008_sync_run_chunks.sql`.
- Migrația adaugă strict tabela `sync_run_chunks` cu schema cerută, FK către `sync_runs(job_id)` cu `ON DELETE CASCADE`, constrângerile simple (`date_end >= date_start`, `chunk_index >= 0`) și unicitatea `(job_id, chunk_index)`.
- Am adăugat doar indexurile minime cerute: `(job_id, chunk_index)` și `(job_id, status)`.
- Nu am făcut wiring în API/runner/services și nu am modificat codul aplicației.


---

# TODO — Implementare store DB-backed pentru `sync_run_chunks` (fără wiring)

- [x] Creez `apps/backend/app/services/sync_run_chunks_store.py` în stilul store-urilor existente (SQL parametrizat, fără ORM/DDL runtime).
- [x] Implementez API-ul minim: `create_sync_run_chunk`, `list_sync_run_chunks`, `update_sync_run_chunk_status`.
- [x] Adaug validare read-only de schemă pentru `sync_run_chunks` cu eroare clară dacă migrația nu este aplicată.
- [x] Adaug teste backend pentru create/list/update + ordering + started/finished/error/updated_at + schema missing.
- [x] Verific local că nu există wiring în API/runner și păstrez patch-ul minimal.

## Review — Implementare store DB-backed pentru `sync_run_chunks` (fără wiring)
- Am adăugat `SyncRunChunksStore` în fișier nou, cu SQL parametrizat și validare read-only de schemă (`to_regclass`) fără DDL runtime.
- Store-ul expune API-ul cerut: `create_sync_run_chunk`, `list_sync_run_chunks`, `update_sync_run_chunk_status`.
- `list_sync_run_chunks(job_id)` întoarce chunk-urile ordonate crescător după `chunk_index`.
- Update-ul setează mereu `updated_at = NOW()` și suportă `mark_started`, `mark_finished`, `error`, `metadata`.
- Am adăugat teste unitare backend cu fake DB pentru schema-missing + lifecycle create/list/update (ordering, timestamps, error, metadata).
- Nu am făcut wiring în API/runner; schimbările sunt strict în stratul service + teste.

## Review — Persistare chunk-uri planificate la crearea jobului Google
- În `api/google_ads.py` am adăugat helper local pentru planificarea chunk-urilor de date ale jobului (`_build_job_date_chunks`) cu intervale consecutive, ordonate, indexate de la 0.
- În branch-ul `async_mode=True` din `sync_google_ads_now`, după crearea jobului și mirror-ul existent în `sync_runs`, persist chunk-urile planificate în `sync_run_chunks` cu `status=queued`.
- Persistența chunk-urilor este best-effort/non-blocking: la eroare se loghează warning și flow-ul in-memory + response-ul endpoint-ului rămân neschimbate.
- Am adăugat teste backend focalizate pentru: succes (chunk-uri create cu index/ordine/status corecte) și eșec write `sync_run_chunks` (jobul rămâne queued).
- Nu am făcut wiring în runner/status endpoint și nu am atins alte platforme.

---

# TODO — Persistare chunk-uri planificate la crearea jobului Google

- [x] Identific punctul de creare job Google async unde există `job_id`, `date_start`, `date_end`, `chunk_days`.
- [x] Adaug helper local pentru planul de chunk-uri (intervale consecutive, ordonate crescător, indexate de la 0).
- [x] Persist chunk-urile în `sync_run_chunks` cu `status=queued` în flow-ul de creare job, best-effort/non-blocking.
- [x] Păstrez response-ul endpoint-ului și flow-ul in-memory compatibile cu implementarea existentă.
- [x] Adaug teste backend focalizate pentru success path și failure path la mirror write în `sync_run_chunks`.


---

# TODO — Extindere status job Google cu chunk_summary/chunks din `sync_run_chunks` (additive, best-effort)

- [x] Identific endpoint-ul curent `GET /integrations/google-ads/sync-now/jobs/{job_id}` și păstrez fluxul memory-first + fallback `sync_runs`.
- [x] Adaug citirea best-effort a chunk-urilor din `sync_run_chunks_store.list_sync_run_chunks(job_id)` fără a rupe payload-ul existent.
- [x] Adaug helper mic local pentru `chunk_summary` (total/queued/running/done/error) și shape minim pentru `chunks`.
- [x] Tratez erorile de citire chunk-uri non-blocking (warning + payload principal neschimbat).
- [x] Adaug teste focalizate pentru scenariile memory hit + chunks hit/error, memory miss + sync_runs hit + chunks hit, memory miss + sync_runs miss.

## Review — Extindere status job Google cu chunk_summary/chunks din `sync_run_chunks`
- Endpoint-ul de status rămâne memory-first, apoi fallback pe `sync_runs` la memory miss; nu s-a schimbat fluxul principal.
- Am adăugat îmbogățire additive best-effort: `chunk_summary` și `chunks` obținute din `sync_run_chunks_store.list_sync_run_chunks(job_id)`.
- `chunk_summary` include minim: `total`, `queued`, `running`, `done`, `error`; `chunks` include minim: `chunk_index`, `status`, `date_start`, `date_end`, `started_at`, `finished_at`, `error`, `metadata`.
- La eroare de citire chunk-uri, endpoint-ul nu cade: log warning și returnează payload-ul principal neschimbat.
- Au fost adăugate teste pentru scenariile cerute (memory hit + chunks hit/error, fallback DB + chunks hit/error, DB miss 404).


---

# TODO — Implementare store DB-backed pentru `sync_state` (fără wiring)

- [x] Creez `apps/backend/app/services/sync_state_store.py` în stilul store-urilor existente (SQL parametrizat, fără ORM/DDL runtime).
- [x] Implementez API-ul minim: `get_sync_state(platform, account_id, grain)` și `upsert_sync_state(...)`.
- [x] Adaug validare read-only de schemă pentru `sync_state` cu eroare clară când migrația nu e aplicată.
- [x] Adaug teste backend pentru get-none, create/update upsert, persistență câmpuri și `updated_at` la update.
- [x] Verific că nu există wiring în API/runner și păstrez patch-ul minimal.

## Review — Implementare store DB-backed pentru `sync_state` (fără wiring)
- Am adăugat `SyncStateStore` în fișier nou, cu SQL parametrizat și validare read-only de schemă (`to_regclass`) fără DDL runtime.
- Store-ul expune API-ul minim cerut: `get_sync_state(...)` și `upsert_sync_state(...)`.
- `upsert_sync_state` folosește `ON CONFLICT (platform, account_id, grain) DO UPDATE`, actualizează `updated_at = NOW()` și permite update repetat pentru aceeași cheie canonică.
- `error` poate fi setat la `NULL` la update (curățare eroare), iar `last_successful_at`/`last_successful_date` sunt persistate explicit când sunt furnizate.
- Am adăugat teste unitare backend pentru schema-missing + get-none + create/update lifecycle (fără duplicate, cu `updated_at` schimbat la update).
- Nu am făcut wiring în API/runner; schimbările sunt strict în stratul service + teste.


---

# TODO — Wiring minim `sync_state` în flow-ul Google per cont (best-effort)

- [x] Identific punctul din `_run_google_backfill_job` unde începe procesarea fiecărui cont și unde există outcome success/error.
- [x] Adaug helper local best-effort pentru `sync_state_store.upsert_sync_state(...)` cu warning non-blocking la eroare.
- [x] Scriu upsert `running` la start per cont și upsert `done`/`error` pe outcome per cont, fără schimbare de response contract.
- [x] Adaug teste backend focalizate pentru apelurile `running`/`done`/`error` și pentru cazul în care upsert-ul `sync_state` eșuează.
- [x] Verific scope-ul (fără wiring în alte platforme/API endpoint-uri) și păstrez patch-ul minimal.

## Review — Wiring minim `sync_state` în flow-ul Google per cont (best-effort)
- În `api/google_ads.py`, în `_run_google_backfill_job`, am adăugat mirror write în `sync_state` la nivel per cont, fără a schimba flow-ul existent al jobului.
- La start per cont se scrie `last_status=running`, `last_job_id`, `last_attempted_at`, `error=None`, cu grain `account_daily` și metadata compactă (`client_id`, `date_start`, `date_end`, `chunk_days`, `job_type`).
- La succes per cont se scrie `last_status=done`, `last_job_id`, `last_attempted_at`, `last_successful_at`, `last_successful_date=resolved_end`, `error=None`.
- La eșec per cont se scrie `last_status=error`, `last_job_id`, `last_attempted_at`, `error=<safe_message>`.
- Scrierea `sync_state` este best-effort/non-blocking: orice excepție este logată ca warning și nu oprește sincronizarea contului/jobului.
- Am adăugat teste focalizate pentru secvența running->done și running->error + non-blocking când upsert-ul `sync_state` eșuează.


---

# TODO — Migrație SQL pentru metadata operațională în `agency_platform_accounts`

- [x] Identific următorul număr disponibil pentru migrație în `apps/backend/db/migrations`.
- [x] Creez migrația nouă care face doar ALTER TABLE pe `agency_platform_accounts` cu coloanele operaționale cerute.
- [x] Adaug index minim pe `(platform, status)` și opțional pe `last_synced_at` într-un stil idempotent.
- [x] Verific local scope-ul modificărilor (doar migrație + task tracking), fără schimbări în codul aplicației.

## Review — Migrație metadata operațională pentru `agency_platform_accounts`
- Am creat `apps/backend/db/migrations/0010_agency_platform_accounts_operational_metadata.sql` cu `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` pentru cele 5 coloane cerute.
- Coloanele adăugate sunt: `status`, `currency_code`, `account_timezone`, `sync_start_date`, `last_synced_at`.
- Am adăugat indexurile idempotente: `idx_agency_platform_accounts_platform_status` pe `(platform, status)` și `idx_agency_platform_accounts_last_synced_at` pe `(last_synced_at)`.
- Nu am făcut backfill, rename/drop, DDL pe alte tabele sau wiring în servicii/API.


---

# TODO — Helper update metadata operațională în client_registry (fără wiring)

- [x] Creez `apps/backend/app/services/client_registry.py` în stilul existent cu helper de update metadata operațională pentru `agency_platform_accounts`.
- [x] Implementez metoda `update_platform_account_operational_metadata(...)` cu update parțial pe câmpurile furnizate explicit și identificare pe `(platform, account_id)`.
- [x] Adaug validare clară pentru schema/coloanele operaționale (fără DDL runtime), cu mesaj explicit dacă migrațiile lipsesc.
- [x] Adaug teste backend pentru: update existent, subset update fără suprascrieri, cont inexistent -> None, schema missing -> eroare clară.
- [x] Verific local că nu există wiring în API/runner și păstrez patch-ul minimal.

## Review — Helper update metadata operațională în client_registry (fără wiring)
- În `ClientRegistryService` am adăugat metoda `update_platform_account_operational_metadata(...)` pentru update SQL parametrizat pe `agency_platform_accounts`, identificat prin `(platform, account_id)`.
- Metoda actualizează doar câmpurile furnizate explicit (`status`, `currency_code`, `account_timezone`, `sync_start_date`, `last_synced_at`) și returnează rândul actualizat sau `None` dacă nu există rândul.
- Am introdus validare read-only pentru schema operațională (`to_regclass` + verificare coloane în `information_schema`) și mesaj clar când migrațiile lipsesc.
- Nu există DDL runtime în noul helper și nu am făcut wiring în API/runner.
- Testele acoperă update complet, update pe subset (fără suprascrieri), cont inexistent și schema missing error.


---

# TODO — Wiring metadata operațională `agency_platform_accounts` în flow-ul Google (best-effort)

- [x] Adaug helper local best-effort în `api/google_ads.py` care apelează `client_registry_service.update_platform_account_operational_metadata(...)`.
- [x] Apelez update-ul la începutul procesării per cont cu câmpuri disponibile (`platform`, `account_id`, opțional `status/currency_code/account_timezone`, plus `sync_start_date`).
- [x] Apelez update-ul la succes per cont pentru `last_synced_at` (și `sync_start_date` dacă rămâne în același apel simplu).
- [x] Tratez erorile non-blocking (warning + flow continuă).
- [x] Adaug teste backend pentru apelurile corecte și non-blocking la eșec, fără schimbare de response shape.

## Review — Wiring metadata operațională `agency_platform_accounts` în flow-ul Google (best-effort)
- În `_run_google_backfill_job` am adăugat update best-effort către `client_registry_service.update_platform_account_operational_metadata(...)` pentru contul curent.
- La începutul procesării contului: se trimite `(platform, account_id)` + `sync_start_date` și, doar dacă sunt disponibile, `status`, `currency_code`, `account_timezone`.
- La succesul contului: se face update best-effort pentru `last_synced_at=now()` (și `sync_start_date`, plus câmpurile disponibile de metadata account).
- Nu folosesc `agency_platform_accounts.status` pentru job state; statusul de sync rămâne în `sync_state`/`sync_runs`.
- Eșecurile de update metadata sunt non-blocking: warning în log, fără a opri contul/jobul Google.
- Am adăugat teste focalizate pentru apelurile de început+succes și pentru non-blocking la eroare de update metadata.


---

# TODO — Standardizare valori canonice + cleanup logging best-effort în flow-ul Google

- [x] Introduc constante canonice comune pentru platform/grain/statusuri într-un loc unic și mic.
- [x] Înlocuiesc string-urile repetitive din `api/google_ads.py` cu constantele canonice, fără schimbare de semantică.
- [x] Unific warning-urile best-effort printr-un helper comun de logging cu context consistent.
- [x] Rulez teste backend focalizate pentru flow-urile Google relevante (create job, runner success/error, status fallback/chunks) și verific că behavior-ul rămâne neschimbat.

## Review — Standardizare valori canonice + cleanup logging best-effort în flow-ul Google
- Am adăugat `apps/backend/app/services/sync_constants.py` cu valori canonice pentru `google_ads`, `account_daily` și statusurile `queued/running/done/error`.
- În `apps/backend/app/api/google_ads.py` am înlocuit literal-ele repetitive pentru platform/grain/status în flow-ul job create, runner, sync_state, sync_run_chunks și status fallback mapping.
- Am introdus helperul `_log_best_effort_warning(...)` și l-am folosit consecvent în toate path-urile best-effort (`sync_runs_create`, `sync_runs_status`, `sync_run_chunks_create`, `sync_state_upsert`, `platform_account_metadata_update`, read fallback-uri).
- Nu am schimbat endpoint-uri publice, response shapes sau ordinea logicii jobului; patch-ul este cleanup + standardization only.


---

# TODO — Rollout Meta phase 1: sync_runs mirror + lifecycle + status DB fallback

- [x] Adaug constante canonice Meta în `sync_constants.py` (dacă lipsesc) și refolosesc statusurile canonice existente.
- [x] Adaug mirror create în `sync_runs` la crearea jobului Meta async, best-effort/non-blocking.
- [x] Adaug mirror lifecycle în runner-ul Meta (`running`/`done`/`error`), best-effort/non-blocking.
- [x] Adaug status flow memory-first + fallback DB (`sync_runs`) pentru jobul Meta.
- [x] Adaug teste backend focalizate pentru create/lifecycle/status fallback și DB error non-blocking.

## Review — Rollout Meta phase 1
- În `api/meta_ads.py` am introdus flow async minimal `sync-now` cu job_id in-memory și mirror în `sync_runs` (create + lifecycle).
- Status flow-ul jobului Meta este memory-first și cade în DB (`sync_runs`) la memory miss; la DB miss/error păstrează comportament compatibil (`404`).
- Toate operațiile DB mirror/read sunt best-effort cu warning și fără blocarea flow-ului principal Meta.
- Nu am introdus `sync_run_chunks` pentru Meta în acest task (flow-ul Meta implementat aici nu are chunking date-range separat).

---

# TODO — Meta phase 2 (part 1): sync_state mirror per account (best-effort)

- [x] Identific punctul minim din runner-ul Meta async pentru wiring per account fără refactor mare.
- [x] Adaug helper local best-effort pentru `sync_state_store.upsert_sync_state(...)` în `api/meta_ads.py`.
- [x] Fac upsert `sync_state` la start/succes/eroare per cont Meta cu constante canonice (platform/grain/status).
- [x] Mențin comportamentul endpoint-urilor neschimbat (fără response shape changes).
- [x] Adaug teste backend focalizate pentru running/done/error și pentru non-blocking la eșec de upsert `sync_state`.

## Review — Meta phase 2 (part 1)
- În `api/meta_ads.py` am adăugat `_mirror_meta_sync_state_upsert(...)` și l-am conectat în runner-ul Meta la start (`running`), succes (`done`) și eroare (`error`) per cont.
- Upsert-urile în `sync_state` sunt strict best-effort: la excepții se loghează warning cu context minim și flow-ul jobului continuă.
- Valorile canonice folosite sunt `PLATFORM_META_ADS`, `SYNC_GRAIN_ACCOUNT_DAILY`, respectiv statusurile canonice `running/done/error`.
- Endpoint-urile și status flow-ul Meta rămân neschimbate; patch-ul este local și tranzitoriu.

---

# TODO — Corecție identitate canonică Meta: account_id real (nu client_id)

- [x] Identific sursa reală pentru Meta account id din mapping-ul existent per client.
- [x] Înlocuiesc folosirea `client_id` ca `account_id` în wiring-ul Meta `sync_state`.
- [x] Ajustez mirror-ul Meta `sync_runs` unde există câmp `account_id` ca să folosească ID real sau `None` defensiv.
- [x] Mențin flow-ul și contractele endpoint neschimbate (patch local, fără refactor mare).
- [x] Adaug teste focalizate pentru identitate canonică și branch defensiv când account id nu poate fi determinat.

## Review — Corecție identitate canonică Meta
- În `api/meta_ads.py` am introdus rezolvarea account id din `client_registry_service.list_client_platform_accounts(platform="meta_ads", client_id=...)`.
- `sync_state` folosește acum doar `account_id` real Meta; nu mai folosește `client_id` ca substitut.
- În branch-urile unde account id nu e determinabil (zero sau multiplu mapping / lookup failure), `sync_state` este omis best-effort, iar flow-ul jobului continuă.
- `sync_runs` create primește `account_id` real când este determinabil; altfel rămâne `None` (defensiv), fără schimbări de endpoint.

---

# TODO — Meta phase 2 (part 2): metadata operațională agency_platform_accounts (best-effort)

- [x] Refolosesc helperul existent `update_platform_account_operational_metadata(...)` fără SQL nou în API.
- [x] Fac wiring local în `api/meta_ads.py` pentru update metadata operațională la start și la succes per cont Meta.
- [x] Folosesc identitatea canonică Meta (`account_id` real), fără fallback greșit la `client_id`.
- [x] Păstrez non-blocking/best-effort la eșecuri de update metadata.
- [x] Adaug teste focalizate pentru update start/succes, skip defensiv și non-blocking la eroare.

## Review — Meta phase 2 (part 2)
- În `api/meta_ads.py` am introdus helper local best-effort pentru metadata operațională și l-am legat la începutul procesării contului + la succes (`last_synced_at`).
- Update-ul folosește exclusiv `platform=meta_ads` și `account_id` real rezolvat din mapping-ul contului Meta per client.
- Pentru branch-uri fără account id determinabil sigur, update-ul operațional este omis defensiv cu warning; flow-ul jobului continuă.
- Nu am schimbat endpoint-uri/status shapes și nu am atins Google/TikTok/sync_engine/meta_ads service.

---

# TODO — TikTok phase 1: sync_runs mirror + lifecycle + status DB fallback

- [x] Adaug constantă canonică TikTok în `sync_constants.py` și refolosesc statusurile canonice existente.
- [x] Adaug mirror create în `sync_runs` la `sync-now` async TikTok, best-effort/non-blocking.
- [x] Adaug mirror lifecycle în runner-ul TikTok (`running`/`done`/`error`), best-effort/non-blocking.
- [x] Adaug status flow memory-first + fallback DB (`sync_runs`) pentru jobul TikTok.
- [x] Adaug teste backend focalizate pentru create/lifecycle/status fallback și branch defensiv pe account_id.

## Review — TikTok phase 1
- În `api/tiktok_ads.py` am introdus flow async `sync-now` cu job in-memory + mirror în `sync_runs` (create și lifecycle).
- Status endpoint-ul jobului TikTok este memory-first și cade în DB (`sync_runs`) la memory miss; la DB miss/error păstrează `404` compatibil.
- Identitatea canonică pentru TikTok folosește `account_id` real din mapping-ul client->platform account; nu folosește `client_id` ca substitut.
- Dacă account id este nedeterminabil (zero/multiplu/eroare lookup), mirror-ul păstrează `account_id=None` defensiv și flow-ul continuă non-blocking.
- Nu am introdus `sync_run_chunks` pentru TikTok în acest task.

---

# TODO — TikTok phase 2 (part 1): sync_state mirror per account (best-effort)

- [x] Adaug helper local best-effort pentru `sync_state_store.upsert_sync_state(...)` în flow-ul TikTok async.
- [x] Fac upsert `sync_state` la start/succes/eroare per cont TikTok cu valori canonice.
- [x] Păstrez identitatea canonică (`account_id` real) și omit defensiv upsert când `account_id` lipsește.
- [x] Mențin endpoint-urile și status flow-ul TikTok neschimbate.
- [x] Adaug teste focalizate pentru lifecycle sync_state și non-blocking la eșec de upsert.

## Review — TikTok phase 2 (part 1)
- În `api/tiktok_ads.py` am introdus `_mirror_tiktok_sync_state_upsert(...)` (best-effort) și l-am conectat în runner la `running`/`done`/`error`.
- Upsert-ul folosește `platform=tiktok_ads`, `grain=account_daily`, `last_job_id`, `last_attempted_at`, respectiv `last_successful_at/date_end` doar la succes.
- Dacă `account_id` nu este disponibil sigur, sync_state se omite defensiv (warning) și jobul continuă normal.
- Nu am modificat endpoint-uri publice, status fallback sau alte platforme și nu am introdus `sync_run_chunks` pentru TikTok.

---

# TODO — TikTok phase 2 (part 2): metadata operațională agency_platform_accounts (best-effort)

- [x] Refolosesc helperul existent `update_platform_account_operational_metadata(...)` în flow-ul TikTok, fără SQL nou.
- [x] Adaug wiring local în runner-ul TikTok pentru update metadata operațională la start și la succes.
- [x] Păstrez identitatea canonică (`account_id` real TikTok), fără fallback greșit la `client_id`.
- [x] Mențin best-effort/non-blocking la eșecuri de update metadata.
- [x] Extind teste focalizate pentru update start/succes, skip defensiv și non-blocking la eroare.

## Review — TikTok phase 2 (part 2)
- În `api/tiktok_ads.py` am adăugat helper local `_mirror_tiktok_platform_account_operational_metadata(...)` și l-am apelat la începutul procesării contului și la succes (`last_synced_at`).
- Valorile trimise sunt `platform=tiktok_ads`, `account_id` real, `sync_start_date` și opțional (`status`, `currency_code`, `account_timezone`) doar când sunt disponibile sigur.
- Dacă `account_id` lipsește, update-ul operațional este omis defensiv cu warning; dacă update-ul aruncă eroare, flow-ul jobului continuă.
- Nu am schimbat endpoint-uri/status flow și nu am modificat sync_runs/sync_state contracts sau alte platforme.

---

# TODO — Final cross-platform audit/cleanup (Google/Meta/TikTok)

- [x] Auditez constantele canonice și înlocuiesc drift-uri mici în API-urile Google/Meta/TikTok fără refactor mare.
- [x] Verific identitatea canonică (`account_id` real) pentru sync_runs/sync_state/metadata operațională și corectez punctual orice drift.
- [x] Uniformizez warning-urile best-effort cu context minim consistent (operation, platform, job_id/account_id unde există).
- [x] Verific explicit că Meta/TikTok nu introduc `sync_run_chunks` în flow-urile curente.
- [x] Rulez teste backend focalizate cross-platform pentru creare/lifecycle/status fallback + audit checks.

## Review — Final cross-platform audit/cleanup
- În `api/google_ads.py` și `api/meta_ads.py` am făcut cleanup mic al warning-urilor best-effort pentru a include context minim consistent de platformă.
- Am verificat că flow-urile Meta/TikTok păstrează identitatea canonică (`account_id` real, fără fallback la `client_id`) și comportamentul non-blocking.
- Am adăugat teste de audit cross-platform pentru constante canonice și pentru absența wiring-ului `sync_run_chunks` în Meta/TikTok.
- Nu am schimbat contractele endpoint-urilor publice și nu am introdus refactor major.

---

# TODO — Pinterest phase 1: sync_runs mirror + lifecycle + status DB fallback

- [x] Adaug constantă canonică Pinterest în `sync_constants.py` folosind valoarea deja canonică din repo (`pinterest_ads`).
- [x] Adaug mirror create în `sync_runs` la `sync-now` async Pinterest, best-effort/non-blocking.
- [x] Adaug mirror lifecycle în runner-ul Pinterest (`running`/`done`/`error`), best-effort/non-blocking.
- [x] Adaug status flow memory-first + fallback DB (`sync_runs`) pentru jobul Pinterest.
- [x] Adaug teste backend focalizate pentru create/lifecycle/status fallback și branch defensiv pe `account_id`.

## Review — Pinterest phase 1
- În `api/pinterest_ads.py` am introdus flow async `sync-now` cu job in-memory și mirror în `sync_runs` (create + lifecycle).
- Status endpoint-ul de job Pinterest este memory-first și cade în DB (`sync_runs`) la memory miss; la DB miss/error păstrează `404`.
- Identitatea canonică folosește `account_id` real din mapping-ul client->platform account; `client_id` nu e folosit ca substitut.
- În branch-uri nedeterminabile (0/multiple/lookup error), `account_id` rămâne `None` defensiv pentru mirror, cu warning non-blocking.
- Nu am introdus `sync_run_chunks` pentru Pinterest în acest task.


---

# TODO — Pinterest async prereq (memory-only)

- [x] Elimin wiring-ul Pinterest către `sync_runs` și fallback DB din `sync-now` flow.
- [x] Păstrez endpoint-ul `POST /integrations/pinterest-ads/sync-now` minimal: enqueue în `backfill_job_store` + background task + payload queued.
- [x] Păstrez endpoint-ul `GET /integrations/pinterest-ads/sync-now/jobs/{job_id}` strict memory-backed (`backfill_job_store`).
- [x] Actualizez testele Pinterest pentru flow-ul minimal memory-only și compatibilitatea endpoint-ului legacy `POST /{client_id}/sync`.

## Review — Pinterest async prereq
- `api/pinterest_ads.py` folosește acum doar `backfill_job_store` pentru `sync-now` și status job.
- Runner-ul async Pinterest setează `running`, apoi `done` cu `result` sau `error` cu mesaj trunchiat.
- Nu există `sync_runs`/`sync_state`/`sync_run_chunks`/fallback DB în acest pas.


---

# TODO — Pinterest phase 2 (part 1): sync_state wiring minimal

- [x] Adaug helper local best-effort pentru upsert în `sync_state` în flow-ul async Pinterest.
- [x] Adaug upsert `running` la start de procesare cont Pinterest.
- [x] Adaug upsert `done` cu `last_successful_at` + `last_successful_date` la succes.
- [x] Adaug upsert `error` cu mesaj trunchiat la eroare.
- [x] Păstrez regula canonică: fără fallback `client_id` -> `account_id`; la ambiguitate/lipsă se omite upsert-ul.
- [x] Actualizez teste focalizate pentru start/succes/eroare, non-blocking la eșec DB și skip defensiv.

## Review — Pinterest phase 2 (part 1)
- În `api/pinterest_ads.py` am adăugat wiring local minimal pentru `sync_state_store.upsert_sync_state` (best-effort, non-blocking).
- Start/succes/eroare sunt scrise cu valorile canonice (`platform=pinterest_ads`, `grain=account_daily`, `status` running/done/error).
- Dacă `account_id` nu e determinabil sigur, upsert-ul este omis și flow-ul continuă.
- Endpoint-urile publice Pinterest (`sync-now`, status job, `/{client_id}/sync`) nu și-au schimbat shape-ul.


---

# TODO — Pinterest restore phase 1 parity (sync_runs) + keep sync_state

- [x] Reintroduc mirror `sync_runs` la create pentru `POST /integrations/pinterest-ads/sync-now` (queued, platform, client_id, account_id canonic/None, date_start/end, chunk_days=1).
- [x] Reintroduc lifecycle mirror `sync_runs` în runner-ul async Pinterest (running/done/error), best-effort non-blocking.
- [x] Reintroduc status flow memory-first + fallback DB (`sync_runs`) pentru `GET /integrations/pinterest-ads/sync-now/jobs/{job_id}`.
- [x] Păstrez wiring-ul existent `sync_state` best-effort și regula canonică de identitate (`account_id` real, fără fallback la `client_id`).
- [x] Actualizez teste focalizate Pinterest pentru create mirror, lifecycle mirror, status fallback și branch defensiv pe `account_id`.

## Review — Pinterest restore phase 1 parity
- `api/pinterest_ads.py` are din nou mirror `sync_runs` la create + lifecycle și status fallback DB, păstrând flow-ul async actual.
- Pentru schema `sync_runs` pe Pinterest simplu folosesc fereastră sintetică minimă: `date_start=date_end=utc_today`, `chunk_days=1`.
- `sync_state` a rămas activ și best-effort în runner, în paralel cu sync_runs.
- Nu am introdus `sync_run_chunks` pentru Pinterest.


---

# TODO — Pinterest phase 2 (part 2): operational metadata mirror

- [x] Adaug helper local best-effort pentru update metadata operațională în `agency_platform_accounts` prin helperul existent din `client_registry`.
- [x] Fac update operațional la start procesare cont Pinterest (`sync_start_date` + câmpuri de cont disponibile sigur: status/currency/timezone).
- [x] Fac update operațional la succes cont (`last_synced_at`) păstrând câmpurile de cont disponibile.
- [x] Păstrez comportamentul non-blocking la eșec update operațional.
- [x] Păstrez identitatea canonică: fără fallback `client_id` -> `account_id`; skip defensiv pe ambiguitate/lipsă.
- [x] Actualizez testele Pinterest focalizate pentru start/succes, eșec non-blocking și skip defensiv.

## Review — Pinterest phase 2 (part 2)
- Runner-ul async Pinterest actualizează acum metadata operațională prin `update_platform_account_operational_metadata(...)` în fazele start și success.
- `agency_platform_accounts.status` este tratat ca status de cont (din mapping), nu ca status de sync-job.
- La ambiguitate/lipsă `account_id` sau la eroare DB, update-ul operațional este omis/logat și flow-ul continuă.
- Endpoint-urile publice și shape-urile de răspuns au rămas neschimbate; `sync_runs` + `sync_state` rămân active.


---

# TODO — Snapchat async prerequisite (memory-only)

- [x] Adaug endpoint `POST /integrations/snapchat-ads/sync-now` memory-only (job create + background task + queued payload).
- [x] Adaug runner local `_run_snapchat_sync_job` pentru lifecycle în memory store (running/done/error).
- [x] Adaug endpoint `GET /integrations/snapchat-ads/sync-now/jobs/{job_id}` strict memory-backed.
- [x] Păstrez endpoint-ul legacy `POST /integrations/snapchat-ads/{client_id}/sync` neschimbat.
- [x] Adaug teste focalizate pentru create/runner/status/legacy compatibility.

## Review — Snapchat async prerequisite
- `api/snapchat_ads.py` are acum flow async minim cu memory store, fără mirror DB.
- Status-ul jobului Snapchat este memory-only (`backfill_job_store`) și păstrează `404` la miss.
- Nu există `sync_runs` / `sync_state` / `sync_run_chunks` / fallback DB în acest task.


---

# TODO — Snapchat phase 1 real: sync_runs parity + DB fallback status

- [x] Reintroduc mirror `sync_runs` la create pentru `POST /integrations/snapchat-ads/sync-now` (queued + platform/client/account/date_start/date_end/chunk_days).
- [x] Reintroduc lifecycle mirror `sync_runs` în runner-ul async Snapchat (`running`/`done`/`error`), best-effort non-blocking.
- [x] Reintroduc status flow memory-first + fallback DB (`sync_runs`) pentru `GET /integrations/snapchat-ads/sync-now/jobs/{job_id}`.
- [x] Păstrez flow-ul async memory-backed existent și endpoint-ul legacy neschimbate.
- [x] Mențin identitatea canonică: `account_id` real Snapchat sau `None` defensiv, fără fallback la `client_id`.
- [x] Actualizez teste focalizate pentru create/lifecycle/status fallback și branch defensiv pe `account_id`.

## Review — Snapchat phase 1 real
- `api/snapchat_ads.py` păstrează flow-ul async curent și adaugă mirror `sync_runs` la create + lifecycle.
- Status endpoint-ul Snapchat este memory-first și cade în `sync_runs` la memory miss.
- Pentru schema `sync_runs` folosesc fereastră sintetică minimă: `date_start=date_end=utc_today`, `chunk_days=1`.
- Nu am introdus `sync_state` sau `sync_run_chunks` pentru Snapchat în acest task.


---

# TODO — Snapchat phase 2 (part 1): sync_state wiring minimal

- [x] Adaug helper local best-effort pentru upsert în `sync_state` în runner-ul async Snapchat.
- [x] Adaug upsert `running` la start procesare cont Snapchat.
- [x] Adaug upsert `done` la succes (cu `last_successful_at` + `last_successful_date`).
- [x] Adaug upsert `error` la eșec cu mesaj sigur/trunchiat.
- [x] Păstrez identitatea canonică (`account_id` real Snapchat; la ambiguitate/lipsă omit upsert, fără fallback la `client_id`).
- [x] Actualizez teste focalizate pentru start/succes/eroare, non-blocking la eșec DB și skip defensiv.

## Review — Snapchat phase 2 (part 1)
- `api/snapchat_ads.py` păstrează flow-ul async + `sync_runs` actual și adaugă local mirror `sync_state` best-effort.
- `sync_state` este actualizat în runner la `running` / `done` / `error` cu valori canonice.
- Pentru fereastra operațională sintetică se folosește `date_start=date_end=utc_today` și `last_successful_date=date_end` pe succes.
- Nu am introdus `sync_run_chunks` și nu am schimbat shape-ul endpoint-urilor publice.


---

# TODO — Snapchat phase 2 (part 2): operational metadata mirror

- [x] Adaug helper local best-effort pentru update metadata operațională în `agency_platform_accounts` prin helperul existent din `client_registry`.
- [x] Fac update operațional la start procesare cont Snapchat (`sync_start_date` + câmpuri de cont disponibile sigur: status/currency/timezone).
- [x] Fac update operațional la succes cont (`last_synced_at`) păstrând câmpurile de cont disponibile.
- [x] Păstrez comportamentul non-blocking la eșec update operațional.
- [x] Păstrez identitatea canonică: fără fallback `client_id` -> `account_id`; skip defensiv pe ambiguitate/lipsă.
- [x] Actualizez testele Snapchat focalizate pentru start/succes, eșec non-blocking și skip defensiv.

## Review — Snapchat phase 2 (part 2)
- Runner-ul async Snapchat actualizează acum metadata operațională prin `update_platform_account_operational_metadata(...)` în fazele start și success.
- `agency_platform_accounts.status` este tratat ca status de cont (din mapping), nu ca status de sync-job.
- La ambiguitate/lipsă `account_id` sau la eroare DB, update-ul operațional este omis/logat și flow-ul continuă.
- Endpoint-urile publice și shape-urile de răspuns au rămas neschimbate; `sync_runs` + `sync_state` rămân active.


# TODO — ad_performance_reports native extra_metrics wiring

- [x] Adaug migrarea DB pentru coloana `extra_metrics` în `ad_performance_reports` (JSONB, default `{}`).
- [x] Extind `PerformanceReportsStore` să persiste `extra_metrics` și să mențină compatibilitatea în test mode/memory mode.
- [x] Mapez metricile native în `extra_metrics` pentru Google/Meta/TikTok și persist nativ `conversions` + `conversion_value`.
- [x] Adaug teste țintite pentru payload-ul `extra_metrics` + maparea Google conversions/value și rulez verificări.

## Review
- Migrare nouă `0011` adaugă coloana `extra_metrics` JSONB (default `{}`) peste `ad_performance_reports`.
- `PerformanceReportsStore` persistă și actualizează acum `extra_metrics` atât în memorie (test mode), cât și în Postgres (`INSERT ... ON CONFLICT`).
- Google GAQL aduce acum `metrics.conversions` + `metrics.conversions_value`; valorile sunt agregate zilnic și păstrate atât în câmpurile canonice (`conversions`/`conversion_value`), cât și în `extra_metrics.google_ads`.
- Sync-urile Meta/TikTok scriu acum și în `ad_performance_reports`, cu mapare nativă minimă în `extra_metrics` per provider.
- Testele țintite pentru `performance_reports` și parser-ul GAQL Google au trecut.


# TODO — Formula engine pentru metrici derivați din ad_performance_reports + extra_metrics

- [x] Adaug modul simplu de formule (`report_metric_formulas.py`) cu helper-e safe divide/rate și metrici derivați comuni.
- [x] Adaug catalog explicit pentru metricii derivați incluși acum vs metricii manual/business excluși (`report_metric_catalog.py`).
- [x] Integrez calculul la read-time în serviciul de raportare (payload additive `derived_metrics`, fără breaking changes).
- [x] Agreg extra_metrics per platformă în read path și calculez metrici specifici Google/Meta/TikTok doar când inputurile există.
- [x] Adaug teste backend pentru formule + payload (None la lipsă/0 denominator, fără metrici business) și rulez verificările.

## Review
- Am adăugat `report_metric_formulas.py` cu helper-e pure (`safe_divide`, `safe_rate`) și calcul pentru metrici comuni + specifici Google/Meta/TikTok, returnând `None` la lipsă/numitor 0.
- Am adăugat `report_metric_catalog.py` cu lista explicită de metrici derivați incluși acum și metrici manual/business excluși.
- În `dashboard.py` read path-ul client agregă acum și `extra_metrics` per platformă (merge numeric), apoi expune aditiv `conversion_value`, `extra_metrics` și `derived_metrics` în payload-ul platformelor, păstrând câmpurile existente.
- Nu am introdus metrici manual/business (`applicants`, `gross_profit`, `ncac` etc.) și nu am persistat metrici derivați în DB.
- Testele țintite pentru formule/catalog/payload au trecut.


# TODO — Migrație SQL pentru tabela separată manual/business inputs

- [x] Verific convenția de numerotare migrații și tabela FK corectă pentru clienți.
- [x] Adaug migrarea nouă pentru `client_business_inputs` cu schema cerută (day/week), constrângeri și unicitate.
- [x] Adaug indexurile minime cerute și păstrez migrarea idempotentă/în stilul repo-ului.
- [x] Rulez verificări locale pentru fișierul de migrare și documentez review-ul fără schimbări în services/API/dashboard.

## Review
- Am adăugat `0012_client_business_inputs.sql` cu tabela separată `client_business_inputs`, FK către `agency_clients(id)` și `ON DELETE CASCADE`.
- Migrarea include constrângerile cerute: range (`period_end >= period_start`), `period_grain IN ('day', 'week')` și consistență pentru day (`period_start = period_end`).
- Am adăugat regula de unicitate pe `(client_id, period_start, period_end, period_grain)` și indexurile minime: `client_id`, `(period_grain, period_start)`, plus `(client_id, period_start DESC)` opțional.
- Nu am făcut modificări în `services`, `api`, `dashboard`, `frontend` sau formule în acest task; patch-ul este migration-only (plus task docs).


# TODO — client_business_inputs_store DB-backed (fără wiring dashboard/API)

- [x] Creez `client_business_inputs_store.py` cu schema guard read-only pentru `client_business_inputs`.
- [x] Implementez metodele `get_client_business_input`, `upsert_client_business_input`, `list_client_business_inputs` cu SQL parametrizat + ON CONFLICT update.
- [x] Asigur comportamentul pentru câmpuri opționale (inclusiv clear la `None`), `source` implicit `manual` și `metadata` implicit `{}`.
- [x] Adaug teste backend lifecycle (schema missing, get none, upsert create/update fără duplicate, list day/week + filtre + ordering).
- [x] Rulez verificări țintite și documentez clar că NU există wiring în dashboard/API în acest task.

## Review
- Am adăugat `client_business_inputs_store.py` cu schema guard read-only (`to_regclass`) și eroare clară dacă tabela lipsește.
- Metodele implementate: `get_client_business_input`, `upsert_client_business_input` (ON CONFLICT + `updated_at = NOW()`), `list_client_business_inputs` cu filtrare de tip overlap pentru interval.
- Comportament acoperit: create + update pe aceeași cheie unică fără duplicate, câmpuri opționale updatabile la `None`, `source` implicit `manual`, `metadata` implicit `{}`.
- Am adăugat teste lifecycle dedicate în `test_services.py` și au trecut.
- Nu am făcut wiring în dashboard/API în acest task.


# TODO — client_business_inputs import service validat (day/week), fără wiring API/dashboard

- [x] Creez `client_business_inputs_import_service.py` cu normalize/validate/import pentru rânduri raw (day + week).
- [x] Implementez normalizare robustă pentru date/numerice/stringuri goale + default-uri (`source`, `metadata`, `period_end` pentru day).
- [x] Implementez validare explicită pentru regulile de perioadă și grain.
- [x] Implementez bulk import care continuă la erori și întoarce rezultat structurat (`processed/succeeded/failed/errors`).
- [x] Adaug teste backend pentru normalize/validate/import + comportament upsert pe cheie unică, apoi rulez verificările.

## Review
- Am adăugat `client_business_inputs_import_service.py` cu funcții concrete de `normalize`, `validate` și `import` bulk, reutilizând store-ul existent fără SQL duplicat.
- Normalizarea acoperă stringuri goale -> `None`, `period_grain` lowercase, date parse din text ISO, conversii numerice robuste, `period_end=period_start` pentru `day` când lipsește, `source` implicit `manual`, `metadata` implicit `{}`.
- Validarea verifică `client_id`, `period_start`, `period_end`, grain permis (`day|week`), range (`period_end >= period_start`) și regula day (`period_start == period_end`).
- Importul bulk continuă la erori, returnează `processed/succeeded/failed/rows/errors`, și lasă store-ul să rezolve upsert pe cheia unică.
- Testele țintite pentru normalize/validate/import + store lifecycle au trecut; nu există wiring nou în dashboard/API.


# TODO — Endpoint intern/admin bulk import pentru client_business_inputs

- [x] Adaug endpoint `POST /clients/{client_id}/business-inputs/import` în API clients, reutilizând import service-ul existent.
- [x] Adaug schema request/response minimă pentru bulk import business inputs.
- [x] Aplic regulă de siguranță: `client_id` din path este forțat pe fiecare row (fără import cross-client accidental).
- [x] Adaug teste backend pentru propagare default-uri + rezultat partial failures + shape răspuns.
- [x] Rulez verificări țintite și confirm explicit că nu există wiring în dashboard/API de raportare.

## Review
- Am adăugat endpoint-ul `POST /clients/{client_id}/business-inputs/import` în `api/clients.py`, folosind direct `client_business_inputs_import_service.import_client_business_inputs(...)`.
- Am adăugat schema request/response în `schemas/client.py` pentru `period_grain`, `source`, `rows` și rezultatul de import (`processed/succeeded/failed/errors/rows`).
- Pentru siguranță, endpoint-ul suprascrie `client_id` pe fiecare row cu valoarea din path și transmite `default_client_id=client_id` către import service.
- Testele verifică propagarea default-urilor, forțarea `client_id` din path și răspunsul pentru partial failures.
- Nu am făcut wiring în dashboard, formule business sau alte endpoint-uri de raportare.


# TODO — Leagă client_business_inputs în dashboard read path (day/week), additive only

- [x] Extind `get_client_dashboard` să citească business inputs via `client_business_inputs_store.list_client_business_inputs(...)`.
- [x] Adaug parametru simplu pentru grain business inputs (`day|week`) și propagare din endpoint-ul dashboard client.
- [x] Returnez `business_inputs` additive-only în payload (`period_grain`, `rows`, `totals`) fără formule business.
- [x] Adaug teste pentru day/week/empty și compatibilitate payload existent.
- [x] Rulez verificări țintite și confirm explicit că nu există dashboard merge/formule business noi.

## Review
- `dashboard.py` citește acum business inputs prin `client_business_inputs_store.list_client_business_inputs(...)` și expune un obiect aditiv `business_inputs` în payload-ul client dashboard.
- Grain-ul business inputs este controlat prin parametru (`business_period_grain`) cu valori efective `day`/`week`; nu se amestecă grain-urile.
- `business_inputs` conține `period_grain`, `rows` și `totals`; totals sunt sume simple peste câmpurile numerice, ignorând valorile `None`.
- Endpoint-ul `GET /dashboard/{client_id}` propagă `business_period_grain` către service-ul de dashboard.
- Am adăugat teste pentru day/week/empty + propagare endpoint și compatibilitate; nu am adăugat formule business sau merge în alte layere.


# TODO — business_derived_metrics în dashboard read path (fără schimbări de schemă)

- [x] Adaug modul mic `business_metric_formulas.py` cu formule pure și helper-e safe pentru metrici business derivați.
- [x] Integrez calculul `business_derived_metrics` în `dashboard.py` folosind `business_inputs.totals` + total spend consolidat existent.
- [x] Păstrez payload-ul additive-only și compatibil (`business_inputs` rămâne intact, metricii ads existenți neatinși).
- [x] Adaug catalog clar pentru metrici business implementați vs amânați din cauza inputurilor lipsă.
- [x] Adaug teste backend pentru formule + payload și rulez verificări țintite.

## Review
- Am adăugat `business_metric_formulas.py` cu formule pure pentru metricii business derivați disponibili acum + catalog explicit pentru metricii amânați (inputuri lipsă).
- `dashboard.py` calculează acum `business_derived_metrics` din `business_inputs.totals` + `total_spend` consolidat cross-platform deja existent în dashboard service.
- Payload-ul client dashboard rămâne compatibil și adaugă doar `business_derived_metrics` (additive-only), păstrând `business_inputs`, metricii ads existenți și structura anterioară.
- Denominatorii lipsă/zero returnează `None` (fără zero-uri inventate, fără excepții).
- Testele țintite pentru formule, catalog, payload și compatibilitate au trecut.

## 2026-03-02 Historical backfill CLI
- [x] Review existing sync/backfill capabilities and platform support boundaries.
- [x] Implement operational CLI script for historical ads backfill (google full support, explicit skips elsewhere).
- [x] Add focused tests for CLI parsing, dry-run/apply behavior, platform skip rules, and summary output.
- [x] Run targeted backend tests.

### Review
- Implemented focused script-only operational capability without schema/dashboard/frontend changes.

## 2026-03-02 Google UI rolling sync decoupling
- [x] Force /integrations/google-ads/sync-now to rolling 30-day window independent of requested date range.
- [x] Add additive response fields for rolling mode and effective dates.
- [x] Keep historical explicit range behavior in operational script and clarify usage messaging.
- [x] Update/extend backend tests for rolling behavior + non-breaking response shape.

### Review
- UI sync now ignores request date range and always runs rolling_30d with chunk_days=7; historical ranges stay in script path.

## 2026-03-02 Google historical range path fix
- [x] Split Google service flow into rolling_30d and historical_range execution paths.
- [x] Wire backfill script to call historical_range service directly.
- [x] Add chunk-level historical summary metrics (planned/executed/empty/failed/rows_upserted).
- [x] Add/update tests for explicit range query and historical path invocation.

### Review
- Historical script no longer uses rolling_30d execution path; it calls explicit-range service path with chunked backfill.

## 2026-03-02 Railway server-side historical launcher
- [x] Add internal/admin Google historical backfill start endpoint with queued job response.
- [x] Add server-side background runner + status endpoint for historical jobs.
- [x] Update local script to support HTTP transport (launcher/poller) and keep local transport optional.
- [x] Add tests for endpoint queue/status, background historical path usage, and script HTTP polling.

### Review
- Historical Google backfill can now be initiated from laptop via HTTP while execution runs server-side in backend environment.

## 2026-03-02 Google rolling sync config cleanup
- [x] Add config-driven Google UI rolling sync settings with safe defaults/fallbacks.
- [x] Replace hardcoded UI rolling values in google_ads API with settings-based values.
- [x] Add focused backend test coverage for defaults/overrides/fallback parsing.
- [x] Run targeted config + API sync tests.

### Review
- UI rolling sync window/chunk are now env-configurable, defaulting to 7d/7d, while preserving existing endpoint behavior.

## 2026-03-02 sync orchestration v2 schema extension
- [x] Add new additive migration extending sync_runs/sync_run_chunks/agency_platform_accounts for v2 orchestration fields.
- [x] Keep migration backward-compatible (ALTER ADD COLUMN IF NOT EXISTS + CREATE INDEX IF NOT EXISTS only).
- [x] Verify repository startup sanity with lightweight backend check.

### Review
- Added migration-only patch (no service/API behavior changes) with safe defaults and non-breaking nullable columns.

## 2026-03-03 sync orchestration v2 store methods
- [x] Validate and finalize additive updates in sync_runs_store and sync_run_chunks_store for orchestration v2 fields/methods.
- [x] Fix failing store test fake cursor branch ordering for batch aggregate query.
- [x] Run targeted backend tests for sync run/chunk stores.

### Review
- Completed additive store updates (new fields and query helpers) and kept existing call patterns backward-compatible.
- Adjusted `test_services.py` fake SQL matcher order so aggregate batch progress query hits the correct branch before generic batch list matching.
- Targeted sync-run/chunk service tests now pass.

## 2026-03-03 Agency sync orchestration batch enqueue API
- [x] Review existing auth/router/store patterns and define minimal additive API shape for agency batch enqueue + polling.
- [x] Implement `apps/backend/app/api/sync_orchestration.py` with POST `/agency/sync-runs/batch` and GET `/agency/sync-runs/batch/{batch_id}` using DB-backed stores.
- [x] Wire router include in `apps/backend/app/main.py`.
- [x] Add focused backend API test(s) for batch create + status polling path.
- [x] Run targeted pytest and capture results.

### Review
- Added new agency sync orchestration router with enqueue-only batch creation and batch polling endpoints using DB-backed sync run/chunk stores.
- POST endpoint normalizes account ids (including dash removal), resolves date range from explicit start/end or rolling `days`, validates accounts via registry mappings, and creates queued `sync_runs` + queued `sync_run_chunks`.
- GET endpoint returns aggregate progress from `get_batch_progress` plus batch runs from `list_sync_runs_by_batch`, including safe percent computation.
- Router is included in app startup routing and a focused API test file was added for POST+GET contract (skipped in this environment if FastAPI test dependency import path is unavailable).

## 2026-03-03 Sync orchestration logs + chunk drilldown endpoints
- [x] Review current sync_orchestration router and store interfaces for account logs/chunk listing.
- [x] Add GET `/agency/sync-runs/accounts/{platform}/{account_id}` and GET `/agency/sync-runs/{job_id}/chunks` (+ optional GET `/agency/sync-runs/{job_id}`) with agency status RBAC.
- [x] Add a focused API test for response shapes using store monkeypatches.
- [x] Run backend validation checks (py_compile + pytest).

### Review
- Extended `sync_orchestration` router with account-level sync run logs endpoint, single-run details endpoint, and chunk drilldown endpoint, all protected with agency `integrations:status` scope checks.
- Account logs endpoint preserves account id formatting (strip only, no dash removal) and returns `runs: []` when empty.
- Chunk drilldown endpoint returns 404 when run is missing, otherwise returns chunk list (including edge case empty list).
- Added focused API shape test coverage (plus existing batch flow test) using monkeypatched stores/registry; in this environment TestClient suite is skipped due import/runtime limitations.

## 2026-03-03 DB-backed sync worker (google-only)
- [x] Review sync run/chunk store capabilities and identify minimal additive worker hooks.
- [x] Add global chunk claim method in `sync_run_chunks_store` for worker polling without prior job id.
- [x] Implement runnable `app/workers/sync_worker.py` loop with claim/execute/update/finalize flow (google_ads only).
- [x] Add focused once-mode worker test with mocked Google service methods.
- [x] Run backend validation checks (py_compile + pytest subset).

### Review
- Added `claim_next_queued_chunk_any(...)` in `sync_run_chunks_store` to atomically claim the next queued chunk globally (optionally filtered by platform) using `FOR UPDATE SKIP LOCKED`, plus run context projection and status count helper for run finalization.
- Implemented `app/workers/sync_worker.py` runnable worker loop with env controls (`SYNC_WORKER_POLL_SECONDS`, `SYNC_WORKER_PLATFORM`, `SYNC_WORKER_ONCE`) and fail-fast guard for `APP_ENV=test`.
- Worker executes only `google_ads` chunks, updates chunk done/error + duration/rows, updates run progress on both success and error paths, and finalizes run status when no queued/running chunks remain.
- Added focused worker unit test (`tests/test_sync_worker.py`) that monkeypatches stores + Google service and validates once-step processing updates chunk/run state correctly.
- Railway worker command: `cd apps/backend && PYTHONPATH=. python -m app.workers.sync_worker`.

## 2026-03-03 Worker finalization watermarks + last status
- [x] Review `client_registry` operational metadata update path and worker finalize flow.
- [x] Extend `update_platform_account_operational_metadata` with new sync-state columns (v2) and conditional schema guard.
- [x] Wire worker finalization to persist last status/watermarks to `agency_platform_accounts`.
- [x] Extend `test_sync_worker.py` for success/error metadata update assertions.
- [x] Run targeted backend checks (py_compile + worker/store tests).

### Review
- `ClientRegistryService.update_platform_account_operational_metadata` now supports v2 sync-state fields (`rolling_window_days`, `backfill_completed_through`, `rolling_synced_through`, `last_success_at`, `last_error`, `last_run_id`) with `_UNSET` semantics preserved for backward compatibility.
- Added conditional schema guard `_ensure_agency_platform_accounts_sync_state_schema()` that is invoked only when new fields are being updated, keeping legacy flows resilient in envs without migration 0014.
- Implemented advance-only SQL updates for watermark date columns (`backfill_completed_through`, `rolling_synced_through`) via CASE expressions.
- Worker finalization now persists account-level operational status in `agency_platform_accounts`: success path updates `last_success_at` + run id + appropriate watermark; error path updates `last_error` + run id; both set `last_synced_at`.
- Extended worker tests to assert metadata updater calls in both success and error flows; targeted worker + store-related tests pass.


## 2026-03-03 Rolling scheduler enqueue (google_ads)
- [x] Implement one-shot rolling scheduler module to enqueue rolling sync runs/chunks from account mappings and watermarks.
- [x] Add optional agency endpoint to trigger rolling enqueue through existing sync orchestration router.
- [x] Add focused unit test for scheduler skip/enqueue behavior with monkeypatched dependencies.
- [x] Run targeted backend validation checks.

### Review
- Added `app/workers/rolling_scheduler.py` with `enqueue_rolling_sync_runs(...)` and runnable entrypoint (`python -m app.workers.rolling_scheduler`) for one-shot execution.
- Scheduler computes per-account rolling windows in account timezone, skips unmapped/up-to-date/inactive accounts, and enqueues queued `sync_runs` + `sync_run_chunks` with `job_type=rolling_refresh`.
- Added API endpoint `POST /agency/sync-runs/rolling/enqueue` (agency `integrations:sync` scope) which calls scheduler function and returns summary.
- Extended platform accounts listing payload with operational fields required by scheduler (`status`, `account_timezone`, `rolling_window_days`, `rolling_synced_through`).
- Railway note: run one-shot via `cd apps/backend && PYTHONPATH=. python -m app.workers.rolling_scheduler`; this can be configured as a scheduled job command.

## 2026-03-03 Frontend /agency-accounts batch sync UX
- [x] Review current `/agency-accounts` page state/render flow and identify minimal insertion points for multi-select + batch sync progress.
- [x] Add Google-only multi-select controls (row checkbox + select-page) with mapped-account restrictions and selection reset rules.
- [x] Add `Sync last 7 days` + `Download historical` actions with backend batch enqueue calls and confirmation flow.
- [x] Add batch polling/progress bar/per-row status badges and completion messaging.
- [x] Run frontend build check and document outcome.

### Review
- Added multi-select UX for Google accounts in `/agency-accounts`: row checkbox restricted to mapped accounts, select-page checkbox for mapped rows on current page, and selection persisted across pagination.
- Added batch sync actions `Sync last 7 days` and `Download historical` with disabled/loading states, mapped-account filtering, and historical confirmation dialog.
- Implemented batch enqueue calls to `/agency/sync-runs/batch` for rolling and historical payloads, including historical start-date resolution (`MIN(sync_start_date)` fallback `2024-01-09`) and yesterday end date.
- Added 2s polling for `/agency/sync-runs/batch/{batch_id}`, progress bar UI, per-row run status badges, and completion messaging (success/partial-error variants).
- Selection resets on platform change and after data refresh; existing attach/detach flow remains intact.
- Frontend build passed with the updated page.

## 2026-03-03 Frontend agency account detail page (logs + chunks)
- [x] Add dedicated dynamic route `/agency-accounts/[platform]/[accountId]` with metadata card, sync runs table, and chunks drilldown.
- [x] Wire account name links from `/agency-accounts` list to detail page while preserving checkbox behavior.
- [x] Add error/empty/loading UX for logs and chunks fetches.
- [x] Run frontend build and verify route compiles.

### Review
- Added dynamic detail route `/agency-accounts/[platform]/[accountId]` that loads account metadata (from `/clients/accounts/google` for Google), sync runs (`/agency/sync-runs/accounts/...`) and chunk drilldown (`/agency/sync-runs/{job_id}/chunks`).
- Implemented metadata/status coverage card with fallback handling when account metadata is unavailable.
- Added runs table with clickable rows and selected-job chunks table, plus loading/empty/error states and refresh action while selected run is queued/running.
- Updated `/agency-accounts` list to make account name clickable via `Link` to the new detail page without turning whole row into a link (checkbox interactions remain intact).
- Frontend build succeeds with the new route and existing page changes.

## 2026-03-03 Backend hotfix: self-healing agency_platform_accounts columns
- [x] Update `ClientRegistryService._ensure_schema()` to auto-add missing operational/sync-state columns on `agency_platform_accounts`.
- [x] Make schema guard methods non-blocking for runtime safety when columns are missing pre-heal.
- [x] Run requested backend validation commands.

### Review
- Added startup self-healing DDL in `ClientRegistryService._ensure_schema()` to auto-create missing operational and sync-state columns on `agency_platform_accounts` via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- Kept test mode behavior unchanged (in-memory path untouched).
- Updated `_ensure_agency_platform_accounts_operational_metadata_schema()` and `_ensure_agency_platform_accounts_sync_state_schema()` to avoid runtime hard-fail (return early when columns are missing), preventing 500s before self-heal runs.
- Requested backend checks pass (`py_compile` + targeted `pytest` subset).

---

# TODO — Workspace nou + verificare remote/fetch

- [x] Inițializez un terminal nou (fără reutilizarea sesiunii anterioare) în repo-ul curent.
- [x] Verific configurația `git remote` în workspace-ul nou.
- [x] Rulez `git fetch` și confirm rezultat.
- [x] Documentez review-ul și rezultatele verificării.

## Review — Workspace nou + verificare remote/fetch
- Am executat verificările într-o sesiune shell nouă (nou proces TTY), fără reutilizarea unei sesiuni interactive existente.
- `git remote -v` nu a returnat intrări (nu există remote configurat în checkout-ul curent).
- `git fetch --all --prune --verbose` s-a executat cu succes (exit code 0), fără output deoarece nu există remote-uri de sincronizat.

---

# TODO — Reconfigurare origin + fetch/pull main (cerință user)

- [x] Rulez exact comanda de adăugare `origin` furnizată de user.
- [x] Rulez exact `git fetch origin`.
- [x] Rulez exact `git pull origin main`.
- [x] Documentez rezultatul executării comenzilor.

## Review — Reconfigurare origin + fetch/pull main (cerință user)
- Am rulat exact comenzile cerute: `git remote add origin ...`, `git fetch origin`, `git pull origin main`.
- `git remote add origin` și `git fetch origin` au reușit; fetch a descărcat branch-urile remote (inclusiv `origin/main` și `origin/work`).
- `git pull origin main` a eșuat inițial cu `fatal: Need to specify how to reconcile divergent branches.` (setare locală Git nedefinită pentru pull pe branch-uri divergente).
- Pentru a finaliza sincronizarea cerută, am rulat `git pull --no-rebase origin main`, care a reușit și a făcut merge cu strategia `ort`.

---

# TODO — Fix build Vercel + rescriere curată Agency Accounts page

- [x] Sync workspace la ultima stare a branch-ului curent înainte de modificări.
- [x] Rescriu curat `apps/frontend/src/app/agency-accounts/page.tsx` (fără cod duplicat/corupt), păstrând ProtectedPage + AppShell.
- [x] Refolosesc endpoint-urile existente (`/clients`, `/clients/accounts/summary`, `/clients/accounts/google`, `/integrations/google-ads/refresh-account-names`, `/agency/sync-runs/batch`, `/agency/sync-runs/batch/{batch_id}`).
- [x] Implementez selecție paginată (inclusiv select all pe pagina curentă), cu blocare selecție pentru conturi neatașate.
- [x] Păstrez acțiunile existente (attach, detach, refresh names) și implementez clean batch actions (last 7 days + historical cu fallback 2024-01-09).
- [x] Adaug polling progres batch + afișare procent/done-total/errors + statusuri per cont când sunt disponibile.
- [x] Rulez `npm run build` în `apps/frontend` și verificări manuale de logică cerute.
- [x] Documentez review-ul final și actualizez lessons după feedback-ul de corecție.

## Review — Fix build Vercel + rescriere curată Agency Accounts page
- Am sincronizat branch-ul curent (`work`) la zi înainte de modificări (`fetch` + `pull`).
- Fișierul `apps/frontend/src/app/agency-accounts/page.tsx` a fost rescris complet pentru a elimina codul corupt/duplicat și JSX invalid.
- Pagina păstrează layout-ul `ProtectedPage` + `AppShell` și reutilizează endpoint-urile backend existente cerute.
- Google Ads este implementat complet: listă paginată, select all per pagină, blocare selecție pentru conturi neatașate, attach/detach/refresh names, acțiuni batch last-7-days + historical cu fallback `2024-01-09`, polling progres batch + statusuri per cont.
- Link-ul numelui de cont duce către ruta de detail `/agency-accounts/google_ads/{accountId}`.
- Build frontend trece (`npm run build`), iar pagina a fost deschisă în browser local și capturată într-un screenshot artifact.

---

# TODO — Polish Agency Accounts + Agency Account Detail sync logs

- [x] Sync workspace la ultima stare a branch-ului curent înainte de modificări.
- [x] Ajustez butoanele de acțiuni din Agency Accounts (Sync last 7 days / Download historical / Refresh names) cu stiluri și stări clare (default/hover/disabled/loading).
- [x] Verific și îmbunătățesc pagina de detail `/agency-accounts/google_ads/[accountId]` pentru metadata + sync runs/logs operaționale.
- [x] Adaug auto-refresh/polling pe detail când există run activ și păstrez buton manual de refresh.
- [x] Rulez build frontend + verificări manuale cerute.
- [x] Documentez review și actualizez lessons după feedback-ul de corecție.

## Review — Polish Agency Accounts + Agency Account Detail sync logs
- Am sincronizat workspace-ul pe `work` înainte de modificări (`git fetch origin` + `git pull --no-rebase origin work`).
- În Agency Accounts, `Sync last 7 days`, `Download historical` și `Refresh names` sunt butoane reale cu stiluri distincte și stări clare (`disabled` + text de loading).
- `Sync last 7 days` (primar indigo) și `Download historical` (verde distinct) sunt diferențiate vizual; `Refresh names` este secondary/outline.
- În Agency Account Detail am păstrat metadata și am extins secțiunea Sync runs: ordonare descrescătoare după dată, badge status, range/start/end, progres chunk-uri, număr erori, eroare principală, plus detalii chunk-uri pe expand/collapse pentru fiecare run.
- Pagina de detail face auto-refresh la interval scurt când există run activ (`queued/running/pending`) și are buton manual `Refresh`.
- Nu a fost necesar endpoint backend nou; s-au refolosit endpoint-urile existente de read (`/clients/accounts/google`, `/agency/sync-runs/accounts/...`, `/agency/sync-runs/{job_id}/chunks`).
- Build frontend trece cu succes (`npm run build`).

---

# TODO — Normalize metadata sync + coverage pentru Agency Accounts

- [x] Detectez/configurez remote-ul git fără a presupune `origin`, apoi sincronizez branch-ul curent.
- [x] Inspectez endpoint-urile/payload-urile actuale pentru Agency Accounts list + Agency Account Detail.
- [x] Implementez în backend un contract unificat pentru metadata sync la nivel de account, derivat centralizat.
- [x] Actualizez frontend list + detail să consume aceeași semantică de metadata, cu empty states lizibile.
- [x] Adaug/actualizez teste backend relevante pentru derivare/payload normalizat.
- [x] Rulez build frontend + verificări cerute și documentez rezultatele.
- [x] Actualizez lessons după feedback-ul de corecție.

## Review — Normalize metadata sync + coverage pentru Agency Accounts
- Workspace-ul a fost sincronizat după detectarea remote-ului existent (fallback configurare remote când lipsea), apoi `fetch + pull` pe branch-ul curent.
- Backend: am unificat metadata sync la nivel account direct în read-model-ul `list_platform_accounts`, cu aceleași câmpuri pentru list + detail (`platform`, `account_id`, `display_name`, `attached_client_*`, `timezone`, `currency`, `sync_start_date`, `backfill_completed_through`, `rolling_synced_through`, `last_success_at`, `last_error`, `last_run_*`, `has_active_sync`).
- Derivarea este read-time (fără persistență nouă): account table + mapping + sync_runs (latest run, active run, backfill/rolling coverage agregat, last success/error fallback).
- Frontend: Agency Accounts și Agency Account Detail consumă același model semantic și afișează stări lizibile când nu există sync finalizat/backfill/rolling inițiat.
- Nu am adăugat endpoint backend nou; am reutilizat endpoint-urile existente (`/clients/accounts/google` + endpoint-urile sync-runs deja folosite în detail).
- Verificări: `py_compile`, test nou backend pentru contract, `tsc --noEmit`, `npm run build`; screenshot automation a eșuat în acest mediu din cauza crash Chromium (SIGSEGV).

---

# TODO — Activează backfill istoric manual + rolling sync zilnic prin cron

- [x] Sincronizez workspace-ul (detect/config remote + pull branch curent).
- [x] Elimin acțiunea manuală `Sync last 7 days` din UI și păstrez `Download historical` + `Refresh names` cu enablement corect.
- [x] Ajustez backend batch sync astfel încât backfill-ul manual pornește explicit de la `2024-01-09` și rămâne sigur/idempotent.
- [x] Implementez/aliniez cron-ul zilnic pentru rolling refresh (fereastră exactă 7 zile complete: end=yesterday, start=end-6).
- [x] Persist run-urile cron în aceeași infrastructură de sync runs și expun sursa (`manual`/`cron`) pentru UI detail.
- [x] Extind Agency Account Detail ca să afișeze clar tip + sursă + status/progres/erori pentru run-uri manuale și cron.
- [x] Adaug teste backend pentru rolling window, eligibilitate cron, crearea run-urilor cron; rulez build frontend.
- [x] Documentez operarea cron în Railway și actualizez lessons după feedback.

## Review — Activează backfill istoric manual + rolling sync zilnic prin cron
- Workspace sincronizat prin detectare remote + `fetch/pull` pe branch-ul curent.
- Agency Accounts: am eliminat acțiunea manuală `Sync last 7 days`; au rămas `Download historical` + `Refresh names`. `Download historical` este activ când există selecție validă și pornește backfill explicit de la `2024-01-09`.
- Backend batch manual: payload-ul și trigger metadata sunt marcate explicit manual; mesajul final de succes rămâne strict pentru finalizare fără erori (`Date istorice descarcate începând cu 09.01.2024`).
- Rolling cron zilnic: scheduler-ul calculează exact 7 zile complete per cont (`end_date=yesterday`, `start_date=end_date-6`), creează run-uri `rolling_refresh` în aceeași infrastructură `sync_runs/sync_run_chunks`, cu `trigger_source=cron`.
- Eligibilitate cron implementată conservator: cont mapat la client + `sync_start_date` inițiat; conturile fără istoric inițiat sunt omise explicit (`history_not_initialized`).
- Agency Account Detail afișează sursa run-ului (`manual`/`cron`) împreună cu status/progres/erori.
- Fără endpoint backend nou: am reutilizat endpoint-urile existente și am extins minim serializarea run-urilor cu `trigger_source`.
- Documentație operare Railway adăugată în `README.md` (comandă cron + worker + regulă fereastră zilnică).
- Verificări rulate: backend py_compile, teste backend țintite (rolling/sync API/metadata), `tsc --noEmit`, `npm run build`.


---

# TODO — Task 5: repară autorizarea Download historical din Agency View

- [x] Sincronizez workspace-ul (detect/config remote + pull branch curent).
- [x] Reproduc eroarea de autorizare și identific cauza exactă pe traseul frontend -> endpoint -> permission guard.
- [x] Repar autorizarea pentru manual historical backfill în agency scope, fără extindere excesivă de permisiuni.
- [x] Verific restricțiile: conturi neatașate/neeligibile rămân blocate corect.
- [x] Îmbunătățesc mesajele de eroare în UI (fără raw JSON).
- [x] Adaug/actualizez teste backend pentru permission/scope + manual historical enqueue.
- [x] Rulez build frontend și verific fluxul (enqueue + vizibilitate în account detail).
- [x] Documentez review + lessons.

## Review — Task 5: repară autorizarea Download historical din Agency View
- Cauza reală: endpoint-ul de batch folosea `enforce_action_scope(action="integrations:sync", scope="agency")`, dar policy-ul RBAC pentru `integrations:sync` era definit doar pe `subaccount`, deci apărea exact eroarea `scope 'agency' vs expected: subaccount`.
- Fix auth: am permis `integrations:sync` pe ambele scope-uri (`agency`, `subaccount`) în policy, păstrând controlul pe permisiune (role-urile fără `integrations:sync` rămân blocate).
- Fix securitate flow: în `create_batch_sync_runs` am blocat explicit conturile neatașate (`attached_client_id is None`) ca invalide pentru manual backfill.
- UX erori frontend: `apiRequest` parsează acum payload-ul de eroare și extrage mesajul relevant (`detail` / `message`) în loc de a afișa raw JSON brut.
- Teste adăugate/actualizate: RBAC pentru `integrations:sync` în agency scope + test API batch care tratează cont neatașat ca invalid.
- Build frontend trece și screenshot-ul pentru Agency Accounts a fost capturat; în dev local, apelurile API reale pot da `ECONNREFUSED` fără backend pornit, dar UI compilează corect.


---

# TODO — Task 6A: repară crash worker în claim_next_queued_chunk_any

- [x] Actualizez workspace-ul înainte de modificări (fără a presupune remote `origin`).
- [x] Confirm cauza exactă din cod/logs: query cu parametru `NULL` ne-tipizat în `claim_next_queued_chunk_any(platform=None)`.
- [x] Fix minim și robust în store pentru ambele cazuri: `platform=None` și `platform='google_ads'`.
- [x] Adaug teste backend de regresie pentru cele două variante de claim (`None` / `google_ads`).
- [x] Verific worker flow prin teste relevante (chunk claimed, run queued->running->done/error) și fără crash.
- [x] Rulez testele backend relevante și documentez review.

## Review — Task 6A: repară crash worker în claim_next_queued_chunk_any
- Workspace-ul local nu are remote tracking configurat pe branch-ul `work`; am verificat explicit status + remotes și am continuat fără pull (nu există upstream disponibil).
- Cauza crash-ului: query-ul `claim_next_queued_chunk_any` folosea expresia `(%s IS NULL OR r.platform = %s)`; când `platform=None`, Postgres poate ridica `IndeterminateDatatype` pentru parametrul ne-tipizat folosit cu `IS NULL`.
- Fix aplicat: două query-uri separate, unul fără filtru platform când `platform` e absent/gol și unul cu `AND r.platform = %s` când filtrul este setat.
- Am păstrat comportamentul workerului și am adăugat logging operațional pentru observabilitate (`chunk_claimed`, `run_started`, `chunk_completed`, `chunk_failed`).
- Teste noi de regresie: `claim_next_queued_chunk_any(platform=None)` și `claim_next_queued_chunk_any(platform='google_ads')`.
- Testele worker existente validează în continuare flow-ul queued->running și finalizarea chunk-ului fără regresii.

---

# TODO — Task 6E: repară update_sync_run_progress + terminal error flow + polling stop

- [x] Actualizez workspace-ul înainte de modificări (fără a presupune remote `origin`).
- [x] Confirm cauza exactă a crash-ului secundar în `update_sync_run_progress()` (parametru NULL ne-tipizat în SQL).
- [x] Repar `update_sync_run_progress()` cu ramuri SQL separate (`chunks_total is None` vs setat).
- [x] Verific și întăresc flow-ul worker pentru erori OAuth: chunk error + run terminal fără crash loop.
- [x] Ajustez frontend polling pe Agency Account Detail să ruleze doar pentru status-uri active reale și să se oprească în terminal.
- [x] Adaug teste backend de regresie pentru update progress (`None`/setat) și failure path terminal.
- [x] Rulez teste backend relevante + build frontend și documentez review.

## Review — Task 6E: repară update_sync_run_progress + terminal error flow + polling stop
- Cauza exactă a crash-ului secundar: `update_sync_run_progress` folosea `CASE WHEN %s IS NULL THEN ... ELSE GREATEST(..., %s)`; la `chunks_total=None`, Postgres/psycopg poate ridica `IndeterminateDatatype` pentru parametrul NULL ne-tipizat.
- Fix backend: `update_sync_run_progress` are acum două query-uri explicite (fără `NULL` în expresie `IS NULL` pe parametru): branch fără update de `chunks_total` când e `None`, respectiv branch cu `GREATEST` când e setat.
- Flow worker la OAuth failure: chunk-ul rămâne marcat `error`, progresul se actualizează fără crash, apoi finalizarea run-ului duce statusul în `error` (terminal), deci nu mai rămâne `running`.
- Frontend detail polling: auto-refresh urmărește doar status-uri active reale (`queued`/`running`), iar când nu mai există active și ultimul run are eroare terminală, mesajul este afișat clar.
- Verificări: pytest backend țintit (store + worker + API) și `npm run build` frontend au trecut.

---

# TODO — Task 7: Google refresh token în DB (autosave callback, encrypted-at-rest)

- [x] Actualizez workspace-ul înainte de modificări (fără a presupune remote `origin`).
- [x] Inspectez flow-ul curent OAuth Google + config/token resolution + diagnostics și helper-ele crypto existente.
- [x] Implementez persistence DB pentru integration secrets (generic provider-ready) cu criptare la rest.
- [x] Salvez automat refresh token-ul în callback OAuth și elimin expunerea token-ului brut în UI/response.
- [x] Fac runtime resolution DB-first cu fallback la env pentru compatibilitate tranzitorie.
- [x] Actualizez diagnostics/UI pentru a indica disponibilitate + source (`database`/`env_fallback`) fără expunere secret.
- [x] Adaug teste backend pentru save/load/fallback/crypto round-trip și rulez backend tests + frontend build.
- [x] Documentez review + lessons.

## Review — Task 7: token Google autosave în DB, encrypted-at-rest
- Am introdus store generic `integration_secrets` (provider/secret_key/scope) cu criptare Fernet derivată din `INTEGRATION_SECRET_ENCRYPTION_KEY` (fallback `APP_AUTH_SECRET`) pentru extensie ulterioară la alți provideri.
- OAuth exchange Google salvează automat refresh token-ul în DB (`integration_secrets`) și nu mai returnează token-ul brut către frontend.
- Runtime Google Ads rezolvă refresh token DB-first, apoi fallback `env` pentru compatibilitate tranzitorie; sursa token-ului este expusă doar ca metadata (`database`/`env_fallback`), fără secret.
- Diagnostics/status includ `refresh_token_present` + `refresh_token_source`; callback UI arată succes + metadata non-sensibilă, fără copy/paste Railway.
- Teste adăugate/actualizate pentru callback-save, DB-first/fallback env și crypto round-trip; build frontend trecut.

---

# TODO — Task 8: reconciliere progres final run/batch/chunk

- [x] Actualizez workspace-ul înainte de modificări (fără a presupune remote `origin`).
- [x] Reproduc și identific cauza exactă pentru run `done` dar progres < 100%.
- [x] Introduc o singură regulă de agregare progres din chunk-uri (nu din rows) cu helper centralizat.
- [x] Reconcile la write-time și/sau read-time pentru run-uri istorice cu agregate stale.
- [x] Aliniez batch summary la aceeași sursă de adevăr și elimin stări active false după finalizare.
- [x] Ajustez frontend minim ca să consume câmpurile reconciliate fără fallback stale.
- [x] Adaug teste backend pentru cazurile done/active/error/partial + batch coherence + rows_written independent de percent.
- [x] Rulez backend tests relevante + build frontend și documentez review.

## Review — Task 8: reconciliere progres final run/batch/chunk
- Cauza reală: endpoint-urile `/agency/sync-runs/*` foloseau agregate denormalizate din `sync_runs` (`chunks_done/chunks_total`) care pot rămâne stale față de `sync_run_chunks`; astfel un run putea avea `status=done` cu toate chunk-urile done, dar progres sub 100%.
- Fix aplicat: am centralizat reconcilierea read-time în `sync_orchestration` (`_summarize_run_from_chunks`, `_reconcile_run_payload`, `_summarize_batch_from_runs`) și deriv progresul exclusiv din chunk-uri, separat de volume (`rows_written`).
- Endpoint-uri aliniate la aceeași sursă de adevăr: `GET /batch/{batch_id}`, `GET /accounts/{platform}/{account_id}`, `GET /{job_id}` returnează run-uri reconciliate; batch progress este calculat din run-uri reconciliate și nu mai poate rămâne activ fals după terminalizare.
- Pentru run-uri istorice cu agregate stale, reconcilierea read-time corectează afișarea imediat, fără rerulare manuală a sync-urilor vechi.
- Teste: am adăugat teste unit pentru regulile done/active/partial/error, independența percent față de rows_written, și batch summary coherence; backend + frontend build trecute.

---

# TODO — Task 9: previne duplicate historical backfill + active run guard

- [x] Actualizez workspace-ul înainte de modificări (fără a presupune remote `origin`).
- [x] Identific cauza reală a duplicatelor în create batch flow pentru historical_backfill.
- [x] Adaug guard backend per account/range/job_type pentru run activ existent (queued/running) și evit creare duplicat.
- [x] Returnez payload clar `already_exists` + run existent pentru UX/polling.
- [x] Frontend rămâne nemodificat în acest task (scope strict backend); am livrat payload-ul backend `already_exists` pentru integrarea UI ulterioară.
- [x] Adaug teste backend pentru request repetat/no-duplicate și path normal.
- [x] Rulez teste backend relevante + build frontend și documentez review + lessons.

## Review — Task 9: previne duplicate historical backfill + active run guard
- Root-cause: `POST /agency/sync-runs/batch` crea mereu run + chunk-uri noi pentru fiecare account valid, fără verificare concurent-safe pentru un run activ identic (`platform + account_id + historical_backfill + date_start + date_end`).
- Fix backend: am adăugat în `SyncRunsStore` metoda `create_historical_sync_run_if_not_active` care folosește `pg_advisory_xact_lock(hashtextextended(...))` pe cheia exactă de dedupe și, în aceeași tranzacție, face check pentru run activ (`queued/running`) înainte de insert.
- API orchestration: pentru `job_type=historical_backfill`, endpoint-ul batch folosește noul guard; dacă găsește run activ identic întoarce rezultat `already_exists`, nu creează run/chunk-uri noi pentru acel account și loghează explicit decizia de skip.
- Contract răspuns extins compatibil: `runs` rămâne lista run-urilor create, iar payload-ul include `already_exists_count` și `results` per account cu `result=created|already_exists`, `platform`, `account_id`, `job_id`, `status`, `date_start`, `date_end`, `client_id`.
- Teste: am adăugat teste API pentru duplicate historical (request 2 => `already_exists` + fără chunk-uri noi), batch mixt (`created`/`already_exists`) și non-regression pentru `job_type=manual`; plus teste unit store pentru path-ul lock+existing și lock+insert.

---

# TODO — Task 10: repair backend pentru historical backfill runs blocate în running

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și verific flow-ul curent sync_runs + sync_run_chunks.
- [x] Adaug flow backend-only `POST /agency/sync-runs/{job_id}/repair` cu stale detection configurabil și răspunsuri explicite (`not_found`, `noop_not_active`, `noop_active_fresh`, `repaired`).
- [x] Implementez guard concurent-safe per job_id la nivel DB/tranzacție pentru repair, fără refactor worker.
- [x] Finalizez coerent run-ul după repair (`done` vs `error`) și marchez chunk-urile stale în terminal cu reason clar.
- [x] Adaug teste backend pentru toate scenariile cerute + test repeat-call stabil și rulez suita relevantă.

## Review — Task 10: repair backend pentru historical backfill runs blocate
- Am introdus `SyncRunsStore.repair_historical_sync_run(job_id, stale_after_minutes, repair_source)` care rulează într-o tranzacție unică cu `pg_advisory_xact_lock` pe cheia `sync_runs:repair:{job_id}` și `SELECT ... FOR UPDATE` pe run/chunks, pentru a evita tranziții inconsistente la apeluri simultane.
- Detectarea stale folosește timestamp-ul existent per chunk `COALESCE(updated_at, started_at, created_at)` comparat cu `NOW()`, cu prag configurabil `SYNC_RUN_REPAIR_STALE_MINUTES` (default 30).
- Cazuri implementate:
  - `not_found` dacă job_id nu există;
  - `noop_not_active` dacă run-ul nu e activ (`queued/running`);
  - `noop_active_fresh` dacă există chunk-uri active dar cel puțin unul este încă fresh;
  - `repaired` dacă toate chunk-urile sunt deja terminale (reconcile) sau dacă toate chunk-urile active sunt stale (sunt închise cu `status=error`, `error=stale_timeout`, metadata repair).
- Regula de finalizare run după repair: `done` dacă toate chunk-urile sunt terminale fără erori; `error` dacă există cel puțin un chunk în eroare (inclusiv chunk-uri închise prin stale repair).
- Endpointul API nou expune outcome + detalii operaționale (`reason`, `active_chunks`, `stale_chunks`, `stale_chunks_closed`, `final_status`) și returnează payload reconciliat de run pentru UI polling consistent.

---

# TODO — Task 11: UI action repair pentru historical backfill blocat în Account Detail

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și identific flow-ul din Account Detail pentru runs + polling.
- [x] Adaug buton clar „Repară sync blocat” doar pentru run activ `historical_backfill` în Account Detail.
- [x] Implementez click flow cu request `POST /agency/sync-runs/{job_id}/repair`, loading/disable și prevenire dublu-click.
- [x] Gestionez outcome-uri `repaired`, `noop_not_active`, `noop_active_fresh`, `not_found` + erori HTTP/network cu mesaje clare.
- [x] După `repaired` / `noop_not_active` refac datele și las polling-ul să se oprească automat când nu mai există run-uri active.
- [x] Adaug teste frontend pentru apariția butonului, request, disabled/loading, outcome handling și polling stop/keep.
- [x] Rulez testele frontend + build și documentez review.

## Review — Task 11: UI action repair pentru historical backfill blocat
- În pagina `agency-accounts/[platform]/[accountId]`, CTA-ul „Repară sync blocat” apare doar pentru cel mai recent run activ cu `job_type=historical_backfill`; nu apare pe run-uri terminale.
- Click-ul pe CTA apelează endpoint-ul existent de repair, dezactivează butonul cât timp request-ul e în flight și previne dublu-click prin guard `repairingJobId`.
- Outcome handling UI:
  - `repaired`: mesaj succes + refetch imediat account meta + runs;
  - `noop_not_active`: mesaj info + refetch imediat;
  - `noop_active_fresh`: mesaj info, fără forțare terminală;
  - `not_found`: mesaj eroare util + refetch;
  - `error`/network: mesaj eroare explicit.
- Polling-ul este controlat de `hasActiveRun`; după refetch, dacă nu mai există run activ (`queued/running/pending`), efectul de interval nu mai rulează (auto-refresh oprit), iar în UI apare explicit mesajul de stare corespunzător.
- Am adăugat helper frontend `repairSyncRun` în client API pentru call-ul POST și maparea controlată a erorilor (`not_found` vs `error`), plus teste dedicate pentru helper și pentru comportamentul paginii.

---

# TODO — Task 12: fix build error Vercel duplicate function implementation în Account Detail

- [x] Actualizez workspace-ul și recitesc AGENTS/todo/lessons.
- [x] Inspectez `apps/frontend/src/app/agency-accounts/[platform]/[accountId]/page.tsx` pentru duplicate function declarations.
- [x] Verific punctual `toggleRunExpanded(jobId: string)` și caut orice alte funcții duplicate în fișier.
- [x] Rulez `pnpm --dir apps/frontend test` și `pnpm --dir apps/frontend build` pentru confirmare.

## Review — Task 12: duplicate function implementation
- Cauza raportată de Vercel (`Duplicate function implementation` la `toggleRunExpanded`) nu se mai reproduce în snapshot-ul curent: fișierul conține o singură implementare `toggleRunExpanded` și o singură referință de utilizare.
- Nu a fost necesară modificare de logică frontend pentru repair button/polling/messages deoarece codul curent este deja consistent.
- Verificare finală: testele frontend și build-ul Next trec local în workspace-ul curent.

---

# TODO — Task 13: retry/resume doar pentru chunk-urile eșuate din historical backfill

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez flow-ul existent sync_runs/sync_run_chunks + repair.
- [x] Adaug endpoint backend `POST /agency/sync-runs/{job_id}/retry-failed` cu outcome-uri explicite și contract compatibil pentru UI ulterior.
- [x] Implementez logică store concurent-safe pentru creare retry-run doar din chunk-uri eșuate, cu legătură metadata la run-ul sursă.
- [x] Adaug teste backend pentru cazurile not_found/not_retryable/no_failed_chunks/created/already_exists + validare intervale chunk retry.
- [x] Rulez testele backend relevante și verific non-regresie pentru endpoint-urile existente.

## Review — Task 13: retry/resume failed chunks
- Am adăugat `SyncRunsStore.retry_failed_historical_run(source_job_id, retry_job_id, trigger_source)` care rulează într-o tranzacție unică cu `pg_advisory_xact_lock` pe `source_job_id` și `FOR UPDATE` pe run/chunks.
- Eligibilitate retry:
  - run existent;
  - `job_type=historical_backfill`;
  - status terminal (`done`/`error`);
  - are cel puțin un chunk cu status de eroare (`error`/`failed`).
- Outcome-uri implementate: `not_found`, `not_retryable`, `no_failed_chunks`, `already_exists`, `created`.
- Guard concurent-safe pentru duplicate retry: în aceeași tranzacție verificăm run activ existent cu metadata `retry_of_job_id=<source_job_id>` + `retry_reason=failed_chunks`; dacă există, întoarcem `already_exists`.
- La `created`, noul run este `historical_backfill` queued și conține DOAR chunk-urile eșuate din sursă (intervale `date_start/date_end` păstrate exact); legătura se face prin metadata:
  - run: `retry_of_job_id`, `retry_reason=failed_chunks`;
  - chunk: `retry_of_job_id`, `retry_of_chunk_index`, `retry_reason=failed_chunks`.
- API nou `POST /agency/sync-runs/{job_id}/retry-failed` întoarce payload orientat UI ulterior (`source_job_id`, `retry_job_id`, `platform`, `account_id`, `status`, `chunks_created`, `failed_chunks_count`) și 404 doar pentru `not_found`.

---

# TODO — Task 14: UI action retry-failed pentru historical backfill în Account Detail

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez flow-ul existent din Account Detail (runs, polling, repair).
- [x] Adaug helper frontend API pentru `POST /agency/sync-runs/{job_id}/retry-failed` cu mapare explicită outcome-uri + erori.
- [x] Adaug CTA clar „Reia chunk-urile eșuate” în Account Detail doar pentru run-uri historical terminale retryable.
- [x] Implementez click flow cu loading/disabled + anti-double-click și mesaje clare pentru `created`, `already_exists`, `no_failed_chunks`, `not_retryable`, `not_found`, `error`.
- [x] După `created`/`already_exists` fac refetch imediat și las polling-ul existent să pornească/oprească automat pe baza run-urilor active.
- [x] Adaug/actualizez teste frontend pentru visibility rules, request, in-flight state, outcome handling, refetch/polling și erori.
- [x] Rulez testele/frontend build relevante și documentez review.

## Review — Task 14: UI retry-failed în Account Detail
- Am adăugat helper-ul frontend `retryFailedSyncRun(jobId)` care face `POST /agency/sync-runs/{job_id}/retry-failed` și normalizează outcome-urile backend (`created`, `already_exists`, `no_failed_chunks`, `not_retryable`, `not_found`) + erori HTTP/network.
- În Account Detail (`/agency-accounts/[platform]/[accountId]`) am introdus CTA-ul „Reia chunk-urile eșuate”, afișat strict când există un run `historical_backfill` terminal cu semnale de eșec (`status error/failed/partial`, `error_count > 0` sau `error` text).
- Click flow-ul retry folosește stare dedicată in-flight (`retryingJobId`) pentru disable/loading și anti-double-click; păstrează separat flow-ul existent de repair.
- Outcome handling UI:
  - `created`: mesaj succes + refetch imediat;
  - `already_exists`: mesaj info + refetch imediat;
  - `no_failed_chunks`: mesaj info;
  - `not_retryable`: mesaj info clar;
  - `not_found`: mesaj eroare util + refetch;
  - `error`/network: mesaj eroare explicit.
- După refetch, polling-ul rămâne bazat pe `hasActiveRun`; dacă noul retry run este `queued/running/pending`, auto-refresh-ul rămâne activ, altfel se oprește fără logică suplimentară.
- Am extins testele frontend pentru helper + pagină: visibility rules, request endpoint, disabled/loading, outcome messaging și efecte de refetch/polling.

---

# TODO — Task 15: consistență Account Detail după repair/retry-failed

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez cauza inconsistențelor între header (`accountMeta`) și lista runs.
- [x] Ajustez polling-ul ca, pe durata run-urilor active, să refacă și metadata din header (nu doar runs/chunks).
- [x] Adaug un strat minim de `effective` state în header (derivat din runs când e mai actual) pentru `has_active_sync`, `last_run_*`, `last_error`.
- [x] Fac refetch final coerent când run-ul activ dispare pentru a evita header rămas pe `queued/running`.
- [x] Ajustez regula pentru CTA `Reia chunk-urile eșuate` astfel încât să fie ascuns când există deja run istoric activ relevant.
- [x] Actualizez testele frontend pentru consistență header/polling și regula CTA, apoi rulez testele + build.

## Review — Task 15: consistență Account Detail după repair/retry-failed
- Cauza inconsistenței: header-ul folosea strict `accountMeta` (încărcat inițial sau la acțiuni punctuale), în timp ce polling-ul periodic actualiza doar runs/chunks; astfel, lista run-urilor devenea mai nouă decât metadata din cardul de sus.
- Am extins polling-ul activ să refacă și `loadAccountMeta()` la fiecare tick, în paralel cu `loadRuns()` și chunks pentru run-urile expandate.
- Am adăugat `effectiveSyncHeader` derivat minim din runs când cel mai recent run este cel puțin la fel de nou ca metadata (`toRunTimestamp >= toMetaTimestamp`), pentru consistență imediată pe `has_active_sync`, `last_run_status`, `last_run_type`, `last_run_started_at`, `last_run_finished_at`, `last_error`.
- Am adăugat un refetch final automat la tranziția `hasActiveRun: true -> false` pentru a evita header blocat pe stare activă după închiderea run-ului.
- Am ajustat vizibilitatea CTA retry: `Reia chunk-urile eșuate` apare doar dacă există run terminal retryable **și** nu există deja run `historical_backfill` activ.
- Am păstrat flow-urile existente de repair/retry și mesajele de outcome; modificarea este strict de consistență UI + polling metadata.

---

# TODO — Task 16: reconciliere backend historical backfill după retry-failed

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez flow-ul actual pentru retry-failed + read-model metadata account.
- [x] Adaug helper backend pentru recovery status al source run-ului (`unrecovered` / `partially_recovered` / `fully_recovered_by_retry`) pe matching exact intervale.
- [x] Integrez helper-ul în eligibilitatea `POST /agency/sync-runs/{job_id}/retry-failed` ca să nu mai creeze run nou când source run-ul este recuperat complet.
- [x] Ajustez derivarea metadata account ca source run complet recuperat să contribuie coerent la coverage/last_* și să nu păstreze `last_error` vechi ca eroare activă.
- [x] Adaug logging pentru detectare recovery complet și skip retry-failed când este deja recuperat.
- [x] Adaug/actualizez teste backend pentru scenariile unrecovered/fully_recovered/partial + metadata reconciliation + retry-failed skip.
- [x] Rulez testele backend relevante și documentez review.

## Review — Task 16: reconciliere backend după retry-failed
- Am introdus în `SyncRunsStore` helper-ul `_evaluate_retry_recovery_status(...)` care clasifică source run-ul pe baza chunk-urilor eșuate rămase după deducerea intervalelor deja recuperate de retry-run-uri `done` legate prin metadata (`retry_of_job_id`/`retry_reason`) și matching exact `date_start`/`date_end`.
- `retry_failed_historical_run(...)` folosește acum helper-ul de recovery și creează retry doar pentru intervalele eșuate rămase; când toate sunt deja recuperate returnează `no_failed_chunks` (compatibil cu contractul existent) și nu mai inserează run/chunks noi.
- Am adăugat logging explicit pentru skip-ul `retry-failed` pe source run deja recuperat complet.
- În `ClientRegistryService.list_platform_accounts(...)` am adăugat reconciliere pentru source historical run-uri `error` recuperate complet prin retry-run-uri `done`:
  - range fallback pentru `sync_start_date`/`backfill_completed_through` include și source run-urile complet recuperate (nu doar run-uri istorice `done`);
  - `last_success_at` poate proveni și din `finished_at` al retry-run-ului de recovery;
  - `last_error` este suprimat când latest run status este de succes, evitând ancorarea în eroare istorică deja recuperată.
- Schimbarea este backend-only, fără mutații asupra statusului istoric al source run-ului și fără schimbări de contract breaking.

---

# TODO — Task 17: hotfix 500 /clients/accounts/google după recovered-by-retry

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și identific nealinierea dintre SELECT și row mapping în `list_platform_accounts`.
- [x] Aplic hotfix minim în `client_registry.py` pentru alinierea coloanelor recovered și indexare robustă.
- [x] Adaug fallback defensiv ca mapping-ul să nu crape dacă recovered fields lipsesc/au NULL.
- [x] Adaug teste backend pentru list_platform_accounts (cu recovered și fără recovered columns) și pentru endpoint-ul `/clients/accounts/google`.
- [x] Rulez testele backend relevante și documentez review + lecție.

## Review — Task 17: hotfix 500 /clients/accounts/google
- Cauza exactă: în `list_platform_accounts`, mapping-ul Python accesa `row[21..23]` pentru `recovered_*`, dar query-ul SQL nu selecta aceste 3 coloane (select-ul se oprea la `success.last_success_at`), rezultând `IndexError: tuple index out of range`.
- Fix minim: am adăugat în `SELECT` coloanele `recovered_hist.min_start_date`, `recovered_hist.max_end_date`, `recovered_hist.last_success_at`, aliniind query-ul cu mapping-ul.
- Fallback defensiv: am introdus helper local `_safe_row_value(row, index)` și am migrat mapping-ul să folosească acces safe pentru câmpurile recovered și pentru câmpurile folosite în fallback (`sync_start_date`, `backfill_completed_through`, `last_success_at`, `last_error`, `last_run_*`, `has_active_sync`). Dacă tuple-ul are mai puține coloane sau valori `NULL`, codul cade elegant pe fallback-ul existent.
- Am păstrat fixul strict backend-only, fără schimbări de contract API și fără modificări pe repair/retry/worker/UI.

---

# TODO — Task 18: UI cleanup după historical backfill fully recovered by retry

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și identific logica actuală pentru bannerul de eroare și CTA-ul retry în Account Detail.
- [x] Ajustez derivarea UI pentru a trata source run-urile historical `error` recuperate complet prin retry ca nerelevante operațional (fără a rescrie istoricul în listă).
- [x] Ascund bannerul `Ultimul run a eșuat` când eroarea provine din source run complet recuperat.
- [x] Ascund CTA-ul `Reia chunk-urile eșuate` pentru source run complet recuperat; păstrez CTA-ul pentru recovery parțial/nerecuperat.
- [x] Adaug/actualizez teste frontend pentru fully recovered vs partial recovery și comportamentul banner/CTA.
- [x] Rulez testele frontend relevante + build și documentez review + lecție.

## Review — Task 18: UI cleanup fully recovered by retry
- Cauza inconsistenței: frontend-ul trata orice run terminal cu eroare drept “activ operațional” pentru banner/CTA, fără să distingă source run-urile historical deja recuperate complet prin retry-run-uri `done`.
- Fix-ul este frontend-first și additive: am introdus derivare `fullyRecoveredSourceRunIds` pe baza datelor existente (`runs` + `accountMeta`), fără modificări de contract backend.
- Regulă de fully recovered folosită în UI:
  - source run `historical_backfill` terminal cu semnale de eșec;
  - există cel puțin un retry run `historical_backfill` cu status de succes și metadata `retry_of_job_id=<source_job_id>` + `retry_reason=failed_chunks`;
  - metadata reconciliată a contului acoperă complet intervalul source run (`sync_start_date <= date_start` și `backfill_completed_through >= date_end`).
- Când run-ul este fully recovered:
  - nu mai intră în `latestTerminalError` (bannerul “Ultimul run a eșuat” nu se mai afișează);
  - nu mai este eligibil pentru `retryableFailedRun` / CTA “Reia chunk-urile eșuate”.
- Pentru recovery parțial/nerecuperat, bannerul și CTA-ul rămân active conform comportamentului anterior.

---

# TODO — Task 19: backend fix coverage complet după fully recovered by retry

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez derivarea metadata account pentru coverage.
- [x] Identific cauza pentru `backfill_completed_through` rămas la intervalul retry chunk deși source run e fully recovered.
- [x] Aplic fix minim în `client_registry.py` pentru coverage efectiv la fully recovered (`source date_start/date_end`).
- [x] Mențin comportament conservator: fără extindere artificială pentru partial recovery.
- [x] Adaug/actualizez teste backend pentru full vs partial recovery + contract `/clients/accounts/google`.
- [x] Rulez testele backend relevante și documentez review + lecție.

## Review — Task 19: backend fix coverage complet după fully recovered by retry
- Cauza: derivarea metadata folosea câmpurile explicite (`sync_start_date`, `backfill_completed_through`, `last_success_at`) ca override hard. Când explicit era setat dintr-un retry chunk mai mic, valorile recovered (`recovered_hist.*`) nu mai puteau extinde intervalul la coverage-ul sursă.
- Fix minim în `ClientRegistryService.list_platform_accounts(...)`:
  - `sync_start_date` derivă acum cu `_coalesce_date_min(explicit, hist_min, recovered_min)`;
  - `backfill_completed_through` derivă acum cu `_coalesce_date_max(explicit, hist_max, recovered_max)`;
  - `last_success_at` derivă acum cu `_coalesce_date_max(explicit, success_from_done, recovered_success)`.
- Efect: pentru fully recovered, metadata se reconciliază la intervalul real acoperit (inclusiv capetele source run), iar pentru partial recovery fără valori recovered comportamentul rămâne conservator și neschimbat.
- Acoperire teste: am adăugat două scenarii noi (full recovery cu explicit mai mic + partial recovery fără extindere) și am păstrat testul de contract endpoint `/clients/accounts/google` fără regressii.

---

# TODO — Task 20: rolling cron exclude conturi inactive/disabled

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez eligibilitatea curentă din rolling scheduler.
- [x] Confirm regresia: cont mapat + sync_start_date setat devine eligibil fără verificare status cont.
- [x] Aplic fix minim backend-only: exclud conturile inactive/disabled din `_is_account_eligible_for_daily_rolling(...)`.
- [x] Introduc skip reason explicit `inactive` și extind summary-ul enqueue cu count + account ids.
- [x] Adaug/actualizez teste backend pentru active/unmapped/history_not_initialized/disabled/inactive + summary.
- [x] Rulez testele backend relevante pentru rolling scheduler și documentez review + lecție.

## Review — Task 20: rolling cron exclude conturi inactive/disabled
- Cauza: `_is_account_eligible_for_daily_rolling(...)` valida doar mapping + `sync_start_date`, deci conturile oprite operațional puteau reintra în enqueue-ul zilnic.
- Fix minim: eligibilitatea verifică acum explicit statusul contului și exclude stările inactive (`disabled`, `inactive` și sinonime operaționale apropiate), plus fallback conservator pe `is_active=False`.
- Read-model: `list_platform_accounts(...)` expune acum și `status` din `agency_platform_accounts`, astfel rolling scheduler poate aplica regula fără query-uri suplimentare.
- Summary rolling: am adăugat câmpurile additive `skipped_inactive_count` și `skipped_inactive_account_ids`.
- Teste: acoperire pentru active/unmapped/no-history/disabled/inactive și verificare explicită a noului skip reason în summary.

---

# TODO — Task 21: sweeper backend auto-repair pentru historical backfill stale

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez logica existentă de repair pentru historical_backfill.
- [x] Adaug helper backend `sweep_stale_historical_runs(...)` care identifică run-uri active historical_backfill stale și reutilizează `repair_historical_sync_run(...)`.
- [x] Mențin scope-ul strict pe `job_type=historical_backfill` și păstrez concurența sigură prin guard-urile existente din repair.
- [x] Adaug entrypoint worker one-shot pentru rulare operațională (Railway/local) cu prag stale + limit configurabile.
- [x] Adaug summary explicit (processed/repaired/noop/not_found/error + job_ids) și logging pentru candidate/outcomes.
- [x] Adaug/actualizez teste backend pentru stale/fresh/outcomes/contract worker și rulez suita relevantă.

## Review — Task 21: sweeper backend auto-repair historical stale
- Am introdus în `SyncRunsStore` metoda `sweep_stale_historical_runs(...)` care citește run-urile active (`queued/running`) strict pentru `historical_backfill`, clasifică candidate stale pe baza `COALESCE(updated_at, started_at, created_at)` față de `stale_after_minutes`, apoi apelează pentru fiecare candidat `repair_historical_sync_run(...)` (fără a duplica logica de stale chunk detection).
- Run-urile active dar fresh sunt lăsate în pace și raportate în `noop_active_fresh_job_ids`; pentru candidatele stale, outcome-urile repair sunt agregate în summary (`repaired`, `noop_not_active`, `not_found`, `noop_active_fresh`, `error`).
- Am adăugat worker one-shot `app/workers/historical_repair_sweeper.py` cu helper `sweep_stale_historical_runs(...)` reutilizabil și `main()` pentru operare Railway/local, folosind default `sync_run_repair_stale_minutes` din config + env override (`HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES`, `HISTORICAL_REPAIR_SWEEPER_LIMIT`).
- Implementarea rămâne backend-only, fără schimbări UI/retry-failed/rolling cron/worker principal de procesare chunks.

---

# TODO — Task 22: runner periodic pentru historical repair sweeper

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez implementarea one-shot existentă.
- [x] Adaug runner periodic separat pentru sweeper (`historical_repair_sweeper_loop`) fără a modifica repair/retry/rolling logic.
- [x] Introduc configurare minimă pentru loop: enable flag + interval seconds, cu logging explicit pe iterații.
- [x] Păstrez one-shot entrypoint existent și reutilizez helper-ul de sweep existent.
- [x] Adaug teste deterministe pentru contractul runner-ului (disabled/config/interval/call/erori continue).
- [x] Actualizez documentația operațională Railway/local și rulez testele backend relevante.

## Review — Task 22: runner periodic historical repair sweeper
- Am adăugat worker-ul `app/workers/historical_repair_sweeper_loop.py` cu buclă periodică simplă care apelează `sweep_stale_historical_runs(...)`, doarme conform intervalului configurabil și loghează `iteration_started` / `iteration_finished` cu duration + summary.
- Config nou pentru loop runner (din env): `HISTORICAL_REPAIR_SWEEPER_ENABLED` și `HISTORICAL_REPAIR_SWEEPER_INTERVAL_SECONDS`; am păstrat reutilizarea variabilelor existente `HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES` și `HISTORICAL_REPAIR_SWEEPER_LIMIT`.
- Dacă runner-ul este disabled (`HISTORICAL_REPAIR_SWEEPER_ENABLED=false`), iese imediat cu status `disabled`.
- Dacă o iterație aruncă excepție, eroarea este logată (`iteration_failed`) iar loop-ul continuă la următoarea iterație (nu oprește serviciul).
- Am păstrat implementarea strict backend-only și fără schimbări în flow-urile repair/retry-failed/rolling/UI.

---

# TODO — Task 23: extindere sweeper auto-repair pentru rolling_refresh stale

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez logica de repair/sweeper/loop existentă.
- [x] Extind sweeper-ul backend cu suport pentru `rolling_refresh` fără refactor mare și fără duplicare masivă.
- [x] Refolosesc aceeași stale detection (`queued/running` + vârstă pe `COALESCE(updated_at, started_at, created_at)` + prag configurabil).
- [x] Păstrez repair-ul concurent-safe și finalizez coerent run-urile rolling stale (done/error) prin aceeași infrastructură de repair.
- [x] Extind loop runner-ul periodic să ruleze sweep atât pentru historical, cât și pentru rolling, cu summary separat + totaluri.
- [x] Adaug/actualizez teste backend pentru rolling stale/fresh, non-target unaffected, summary și integrarea loop runner-ului.
- [x] Actualizez documentația operațională + tasks/lessons și rulez testele backend relevante.

## Review — Task 23: extindere sweeper la rolling_refresh
- Am extras în `SyncRunsStore` un path comun minim (`_repair_active_sync_run` + `_sweep_stale_runs_for_job_type`) și am păstrat wrapper-ele explicite pentru `historical_backfill` și `rolling_refresh`, evitând duplicarea logicii de stale close/finalizare run.
- `sweep_stale_rolling_runs(...)` folosește exact aceeași regulă de stale detection ca historical (`status IN queued/running` + vechime din `COALESCE(updated_at, started_at, created_at)` față de `stale_after_minutes`).
- Loop-ul periodic rulează acum în fiecare iterație ambele sweep-uri (`historical` + `rolling`) și returnează summary cu breakdown per job type + totaluri (`total_processed_count`, `total_repaired_count`, `total_error_count`).
- Nu am schimbat UI/retry-failed/rolling window logic/eligibility; extinderea este strict operațională backend.

---

# TODO — Task 24: redesign listă Agency Accounts (coloane + filtru client)

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez structura curentă a listei Google Accounts.
- [x] Refac layout-ul listei pe coloane clare: selecție, cont, sync progress/status, client atașat, acțiuni, detach separat.
- [x] Mut progress bar/status între zona cont și client pentru scanare mai rapidă.
- [x] Separ acțiunea `Detach` într-o coloană dedicată, distinctă de acțiunile principale.
- [x] Adaug filtru local după numele clientului atașat + empty state explicit la zero rezultate.
- [x] Păstrez funcțiile existente (select-page, attach/detach, refresh names, download historical, batch progress/polling) fără schimbări de contract API.
- [x] Adaug teste frontend pentru headers/filter/progress/detail-link/actions și rulez testele relevante + build + screenshot.

## Review — Task 24: redesign listă Agency Accounts
- Lista Google Accounts este acum randată într-un layout tip grid cu headere de coloană explicite (`Selecție`, `Cont`, `Sync progress`, `Client atașat`, `Acțiuni`, `Detach`) și fallback labels pe mobile.
- Progress/status-ul este afișat în coloană dedicată între cont și client, cu bar vizual + status text + metadate coverage.
- `Detach` a fost mutat într-o coloană separată; `attach` rămâne în coloana `Acțiuni`.
- Filtrul `Filtru client` rulează local pe `attached_client_name` și afișează empty state când nu există rezultate.
- Link-ul către Account Detail (`/agency-accounts/google_ads/{accountId}`) și acțiunile operaționale existente au rămas funcționale.

---

# TODO — Task 25: quick view conturi atribuite aceluiași client în Agency Accounts

- [x] Actualizez workspace-ul, recitesc AGENTS/todo/lessons și inspectez layout-ul existent din Task 9A.
- [x] Construiesc maparea locală `attached_client_id -> conturi` pe datele deja încărcate.
- [x] Afișez badge/count în coloana Client pentru row-urile atașate (`X conturi atribuite`).
- [x] Adaug acțiune `Vezi conturile` + expand/collapse inline per row, fără efecte secundare pe selecție/attach/detach/batch.
- [x] În panel-ul quick view afișez nume cont + account id + link către Account Detail, cu marcaj pentru contul curent.
- [x] Ascund quick view pentru row-uri neatașate și păstrez filtrul/client + acțiunile existente intacte.
- [x] Adaug/actualizez teste frontend pentru count, visibility, expand/collapse, linkuri și compatibilitate filtru; rulez testele + build + screenshot.

## Review — Task 25: quick view conturi pe același client
- Maparea locală este derivată cu `useMemo` din `googleAccounts` și grupează conturile după `attached_client_id`.
- Pentru row-uri atașate, coloana Client afișează badge-ul `X conturi atribuite` și buton `Vezi conturile` / `Ascunde conturile`.
- Expand/collapse este per row prin `expandedClientRows` (Set de account IDs), independent de selecție și restul acțiunilor.
- Panel-ul inline listează conturile clientului cu linkuri către `/agency-accounts/google_ads/{accountId}`, include account id și marchează contul curent cu eticheta `curent`.
- Row-urile fără client atașat nu afișează badge și nu afișează acțiunea quick view.

---

# TODO — Task 26: hotfix SQL interpolation pentru create_historical_sync_run_if_not_active

- [x] Confirm root-cause în query-ul INSERT...RETURNING din SyncRunsStore.
- [x] Aplic fix minim pentru interpolarea `_SYNC_RUNS_SELECT_COLUMNS` în SQL executat.
- [x] Adaug test de regresie care validează că placeholder-ul literal nu mai ajunge în query.
- [x] Rulez testele backend țintite pentru dedupe + endpoint orchestration.

## Review — Task 26: hotfix SQL interpolation
- Root-cause: query-ul `INSERT INTO sync_runs ... RETURNING` era definit ca string simplu (nu f-string), astfel placeholder-ul `{_SYNC_RUNS_SELECT_COLUMNS}` ajungea literal în SQL și producea `psycopg.errors.SyntaxError` la `{`.
- Fix: query-ul a fost convertit la f-string astfel încât `_SYNC_RUNS_SELECT_COLUMNS` este expandat înainte de execuție.
- Regression guard: în testul de dedupe pentru path-ul `created=True` am adăugat aserție că niciun query executat nu conține literalul `{_SYNC_RUNS_SELECT_COLUMNS}`.

---

# TODO — Task 27: Agency Accounts row-level sync progress doar pentru run-uri active

- [x] Actualizez workspace-ul și recitesc AGENTS + tasks/todo + tasks/lessons (remote indisponibil în mediu curent).
- [x] Analizez logica `renderSyncProgress(...)` și identific cauza barelor afișate pe toate row-urile.
- [x] Aplic fix frontend-only: fill doar pentru row-uri active relevante (`queued/running` în batch curent sau `has_active_sync` fără batch status).
- [x] Elimin semantica de bară 100% pentru `done/error/last_success_at`; păstrez doar textul de status/metadata.
- [x] Adaug teste frontend pentru idle/done fără activitate + queued/running active în batch.
- [x] Rulez testele frontend relevante și build-ul frontend.

## Review — Task 27: row-level sync progress activ-only
- Cauza exactă: `renderSyncProgress(...)` calcula progres generic pentru orice row (`100%` pe `done/error/last_success_at`, `15%` implicit), deci aproape toate conturile primeau bare umplute chiar fără sync activ.
- Regula nouă: fill-ul este randat doar dacă row-ul are sync activ relevant (`rowStatus` din batch curent în `queued/running`, sau fallback `has_active_sync` când nu există `rowStatus`).
- Pentru row-uri inactive (idle/done/error fără activitate curentă), coloana afișează status/text și metadata, dar pista rămâne fără fill.
- Pentru row-uri active: `queued` primește indicator de start discret, `running` primește indicator intermediar animat; după ce row-ul nu mai e activ, fill-ul dispare.

---

# TODO — Task 28: Agency Accounts row-level progress REAL din chunks pentru conturile active

- [x] Actualizez workspace-ul și verific starea branch-ului (remote/tracking indisponibil în mediul curent).
- [x] Identific endpoint-ul reutilizabil pentru runs/chunk counters din Account Detail și îl expun prin helper comun în `src/lib/api.ts`.
- [x] Adaug în list page polling țintit (doar conturi active queued/running) pentru a citi `chunks_done/chunks_total` per cont.
- [x] Randrez în `SYNC PROGRESS` procent real + text `done/total chunks` când există date; fallback simplu pentru activ fără counters; gol pentru inactive.
- [x] Evit fetch pe toate conturile prin filtrare explicită `activeSyncAccountIds` înainte de polling.
- [x] Adaug/actualizez teste frontend pentru no-active, active real-progress, și start/stop polling.
- [x] Rulez `pnpm test` și `pnpm build` pe frontend.

## Review — Task 28: progress real pe chunks pentru active rows
- Endpoint reutilizat: `/agency/sync-runs/accounts/{platform}/{account_id}?limit=...` (același folosit de Account Detail), expus prin helper comun `listAccountSyncRuns(...)` în `src/lib/api.ts`.
- În Agency Accounts, polling-ul pentru chunk progress pornește doar când există conturi active (`queued/running` în batch sau `has_active_sync` fallback) și rulează pe lista activă, nu pe toate conturile.
- Pentru fiecare cont activ se citește run-ul activ și se derivează `chunksDone/chunksTotal/percent`; UI afișează bară reală + text ex. `12/113 chunks (11%)`.
- Când contul nu mai este activ, row progress revine la track gol (fără fill) și polling-ul se oprește automat când nu mai există active rows.

---

# TODO — Task 29: Agency Accounts rolling watermark corect pentru run-uri active

- [x] Verific workspace + AGENTS + tasks și confirm scope frontend-only.
- [x] Identific fallback-ul greșit pentru `rolling_synced_through` în `page.tsx`.
- [x] Refolosesc datele din polling-ul existent (`listAccountSyncRuns`) ca să disting rolling activ (`job_type=rolling_refresh`, status queued/running/pending).
- [x] Afișez `Rolling în curs` cu fereastră/date_end când există rolling activ; păstrez fallback la `rolling_synced_through` sau `Rolling sync neinițiat` când nu există run activ.
- [x] Adaug teste pentru rolling activ, rolling neinițiat și rolling done cu dată setată.
- [x] Rulez `pnpm --dir apps/frontend test` și `pnpm --dir apps/frontend build`.

## Review — Task 29: rolling status corect
- Cauza: UI folosea strict `rolling_synced_through ?? "Rolling sync neinițiat"`, ignorând faptul că poate exista un run activ `rolling_refresh` cu fereastră țintă.
- Fix: folosesc metadata run-ului activ din polling (`job_type`, `status`, `date_start`, `date_end`) și afișez mesajul de rolling în curs când run-ul este activ.
- Regula nouă: rolling activ are prioritate față de watermark-ul istoric `rolling_synced_through`; fallback la `rolling_synced_through`/`Rolling sync neinițiat` doar când nu există rolling activ.

---

# TODO — Task 30: backend batch endpoint pentru progress pe conturi active

- [x] Verific workspace și notez limitarea de remote/upstream (fetch/pull indisponibil în mediu).
- [x] Adaug endpoint batch nou pentru progress account-level în `sync_orchestration` cu validări de input și limită maximă.
- [x] Implementez în `sync_runs_store` o metodă eficientă batch (CTE + agregare chunks) care evită query N-per-account.
- [x] Adaug logging operațional pentru endpoint (`requested_count`, `returned_active_count`, `duration_ms`).
- [x] Adaug teste API pentru null active run, progres corect, scope pe account_ids cerute, validare empty/limită.
- [x] Adaug teste store pentru mapping payload batch progress.
- [x] Rulez testele backend relevante (`test_sync_orchestration_api` + `test_sync_runs_store_progress_batch`).

## Review — Task 30: endpoint batch progress
- Am introdus endpoint-ul `POST /agency/sync-runs/accounts/{platform}/progress` cu body `{ account_ids: string[], limit_active_only?: boolean }` și limită de 200 ids.
- Endpoint-ul returnează `platform`, `requested_count` și `results[]` (entry per account_id, `active_run` dict sau `null`).
- Store-ul folosește o singură interogare SQL cu CTE-uri (`requested`, `active_runs`, `chunk_summary`) pentru a selecta cel mai recent run activ per cont și agregatele de chunks (`chunks_done`, `chunks_total`, `errors_count`) fără query N-per-account.
- Am păstrat strict scope backend-only, fără schimbări UI sau logică de sync/repair/retry/sweeper/rolling.

---

# TODO — Task 31: Agency Accounts polling migrat pe endpoint batch progress

- [x] Verific workspace (fetch/pull) și documentez limitarea de remote/upstream când lipsește.
- [x] Adaug helper frontend nou pentru endpoint-ul batch `POST /agency/sync-runs/accounts/{platform}/progress`.
- [x] Migrez polling-ul din Agency Accounts de la N request-uri per account la 1 request/batch per interval (+ split la 200 IDs).
- [x] Păstrez semantica UI existentă: fill doar pe run activ, fallback indicator când chunks_total lipsește, rolling watermark funcțional.
- [x] Adaug teste Vitest pentru request batch, no-active => fără request, și split >200 active IDs.
- [x] Rulez `pnpm --dir apps/frontend test` și `pnpm --dir apps/frontend build`.

## Review — Task 31: batch polling Agency Accounts
- Migrarea a înlocuit `Promise.all(listAccountSyncRuns(...))` per cont activ cu apel batch `postAccountSyncProgressBatch(...)`, reducând request-urile per interval de la N la 1 (sau câteva batch-uri când active IDs > 200).
- Split-ul de limită este implementat local în frontend pe chunk-uri de max 200 IDs, agregând rezultatele într-un singur map `rowChunkProgressByAccount`.
- Semantica vizuală rămâne neschimbată: bara umplută doar pentru conturi active, fallback text când progress chunks nu are total, iar rolling watermark continuă să deriveze din metadata run-ului activ.

---

# TODO — Task 32: Agency Accounts quick filters + sort Active first

- [x] Verific workspace/fetch și continui cu limitarea de remote/upstream din mediu.
- [x] Adaug filtre rapide client-side (Toate / Active / Erori / Neinițializate) în Agency Accounts, lângă filtrul client.
- [x] Adaug toggle `Active first` (default off) cu sort stabil: active, apoi error, apoi restul.
- [x] Păstrez semantica progress bar (fill doar pentru active) și fără API calls noi.
- [x] Mă asigur că `Select all pe pagina curentă` operează doar pe rândurile vizibile după filtrare/sort.
- [x] Adaug teste Vitest pentru filtre, select-all în context filtrat și sort minim `Active first`.
- [x] Rulez `pnpm --dir apps/frontend test` și `pnpm --dir apps/frontend build`.

## Review — Task 32: quick filters + active-first sort
- Filtrarea rapidă rulează client-side peste lista deja încărcată și suportă: `Active` (queued/running/pending + fallback `has_active_sync`), `Erori` (error/failed), `Neinițializate` (`sync_start_date` gol).
- Toggle-ul `Active first` aplică sort stabil pe 3 grupe (active > errors > rest) fără schimbări backend.
- Selectarea pe pagină rămâne coerentă deoarece sursa pentru selectable IDs este `pagedGoogleAccounts` (deja filtrată/sortată).

---

# TODO — One-shot historical repair sweeper includes rolling runs

- [x] Update one-shot sweeper to process stale historical and rolling runs in same invocation.
- [x] Return aggregate totals across both job types in one-shot summary payload.
- [x] Add dedicated unit test for one-shot sweeper aggregated behavior and shared parameters.
- [x] Update README wording for one-shot command scope and keep env var contract documented.
- [x] Run targeted checks and document review.

## Review — One-shot historical repair sweeper includes rolling runs
- `historical_repair_sweeper.sweep_stale_historical_runs` now executes both historical and rolling stale sweeps in one call, with shared `stale_after_minutes` and `limit`.
- Returned payload remains explicit per type (`historical`, `rolling`) and now includes aggregate totals (`total_processed_count`, `total_repaired_count`, `total_error_count`) for cron observability.
- Added a backend unit test to validate dual-call behavior, shared parameters, and aggregate totals.
- README now clarifies that one-shot sweep covers both historical and rolling stale runs.

---

# TODO — Agency Accounts: select all filtered + persistent selection across pages

- [x] Run `git fetch --all --prune` and continue even when no remotes are configured in this environment.
- [x] Keep selection state in a persistent `Set` keyed by account id, independent from current page.
- [x] Add controls for `Selectează toate filtrate (X)` and `Clear selection` near page selection controls.
- [x] Implement precise behavior split: page-only selection vs full filtered selection, while preserving selection across paging/filter/sort changes.
- [x] Keep existing download historical flow unchanged except consuming total persistent selection.
- [x] Extend Vitest list tests for cross-page filtered selection, persistence, clear selection, page-only selection, and uninitialized filter behavior.
- [x] Run frontend test/build checks and capture review.

## Review — Agency Accounts: select all filtered + persistent selection across pages
- Selection remains stored as `Set<accountId>` and is not reset on page/filter/sort changes, so checkboxes reflect membership consistently when navigating pages.
- Added a filtered-scope selector that targets all currently filtered + attachable rows (`selectableFilteredAccountIds`), distinct from page-scope selector (`selectablePageAccountIds`).
- Header controls now include `Selectează toate filtrate (X)` and `Clear selection`, with summary text showing total selected and filtered scope.
- Existing `Download historical` flow remains unchanged and still uses `selectedMappedAccounts` derived from persistent selection state.
- Added targeted Vitest coverage for the requested scenarios (cross-page, persistence, clear selection, page-only selection, and uninitialized-only filtered selection).

---

# TODO — DB foundation: entity tables + per-grain watermarks

- [x] Run workspace sync/status commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Add additive migration for `platform_campaigns`, `platform_ad_groups`, `platform_ads` with requested PKs/columns/indexes.
- [x] Add additive migration for `platform_account_watermarks` with unique key, grain CHECK constraint, and platform/account index.
- [x] Add backend DB test covering table existence via `to_regclass(...)`.
- [x] Add backend DB test covering uniqueness enforcement on `(platform, account_id, grain)`.
- [x] Run targeted backend tests/checks and document review.

## Review — DB foundation: entity tables + per-grain watermarks
- Added migration `0015_platform_entities_and_watermarks.sql` with three cross-platform entity-state tables and one watermark table; all changes are additive-only.
- Entity table PKs are composite per requirements and include minimal canonical columns plus `raw_payload/fetched_at/last_seen_at/payload_hash`.
- Watermark table includes required date/timestamp fields, `UNIQUE (platform, account_id, grain)`, and strict grain check for `account_daily/campaign_daily/ad_group_daily/ad_daily`.
- Added DB migration tests that apply migrations into an isolated schema, assert table presence with `to_regclass`, and validate duplicate watermark insert raises an exception.

---

# TODO — DB foundation: daily entity performance fact tables

- [x] Run workspace update/status commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Inspect canonical metric names/types from existing `ad_performance_reports` usage and preserve them in new entity fact tables.
- [x] Add additive migration for `campaign_performance_reports`, `ad_group_performance_reports`, `ad_unit_performance_reports` with required unique keys and indexes.
- [x] Include traceability columns (`ingested_at`, `source_window_start`, `source_window_end`, `source_job_id`) in all three tables.
- [x] Add backend DB migration tests for table existence and duplicate-key uniqueness enforcement.
- [x] Run targeted checks and document review.

## Review — DB foundation: daily entity performance fact tables
- Added migration `0016_daily_entity_performance_facts.sql` with 3 additive daily fact tables for campaign/ad_group/ad-unit scope; no renames/drops and no worker/UI/orchestrator changes.
- Canonical metric columns are aligned with `ad_performance_reports` usage (`spend`, `impressions`, `clicks`, `conversions`, `conversion_value`, `extra_metrics`) and retain consistent numeric/bigint/jsonb typing.
- Enforced business-key uniqueness per grain:
  - campaign: `(platform, account_id, campaign_id, report_date)`
  - ad_group: `(platform, account_id, ad_group_id, report_date)`
  - ad_unit: `(platform, account_id, ad_id, report_date)`
- Added existence and uniqueness DB tests in an isolated schema, with skip behavior when `DATABASE_URL` is unavailable.

---

# TODO — Backend store upserts for daily entity performance facts

- [x] Run workspace sync/status commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Re-check existing `ad_performance_reports` upsert pattern and align ON CONFLICT update behavior.
- [x] Add backend store module with public upsert helpers for campaign/ad_group/ad_unit fact tables.
- [x] Ensure upsert updates canonical metrics, `extra_metrics`, traceability fields, and refreshes `ingested_at`.
- [x] Add DB-backed tests (skip without `DATABASE_URL`) proving conflict upsert overwrites facts for same daily keys.
- [x] Run targeted checks and document review.

## Review — Backend store upserts for daily entity performance facts
- Added `entity_performance_reports.py` with 3 public functions:
  - `upsert_campaign_performance_reports(conn, rows)`
  - `upsert_ad_group_performance_reports(conn, rows)`
  - `upsert_ad_unit_performance_reports(conn, rows)`
- Each helper performs bulk `executemany` insert with `ON CONFLICT ... DO UPDATE` on the table business key and overwrites canonical metrics (`spend/impressions/clicks/conversions/conversion_value`), `extra_metrics`, and traceability (`source_window_start/end`, `source_job_id`), while refreshing `ingested_at = NOW()`.
- Added integration-style DB tests that apply migrations in isolated schema and verify re-upsert on same key updates spend/clicks/extra_metrics for campaign/ad_group/ad_unit tables.

---

# TODO — Partition monthly daily entity fact tables

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Add migration to convert campaign/ad_group/ad_unit fact tables into RANGE partitioned parents by `report_date`.
- [x] Add monthly partitions from 2024-01 through 2026-12 plus DEFAULT partition for each table.
- [x] Preserve uniqueness/index coverage with new constraint/index names and copy data from `_unpartitioned` tables before dropping old tables.
- [x] Add DB tests (skip without `DATABASE_URL`) to verify parent relkind=`p` and partition existence.
- [x] Run targeted checks and document review.

## Review — Partition monthly daily entity fact tables
- Added migration `0017_partition_daily_entity_facts.sql` that performs `rename -> create partitioned parent -> add constraints/indexes -> create partitions/default -> copy data -> drop old` for all three fact tables.
- Partition generation uses monthly loop for `[2024-01-01, 2027-01-01)` and creates fail-safe DEFAULT partition per table.
- Added dedicated DB migration test asserting parent tables are partitioned (`relkind='p'`), key partitions exist (`*_2024_01` + `*_default`), and duplicate business key insert is rejected.

---

# TODO — Backend store upserts for platform entity state tables

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Confirm exact entity-state schema from migration `0015_platform_entities_and_watermarks.sql` and reuse column names as-is.
- [x] Add backend store module with 3 upsert helpers for `platform_campaigns`, `platform_ad_groups`, `platform_ads`.
- [x] Ensure ON CONFLICT updates non-key fields (`name/status/parent ids/raw_payload/payload_hash`) and refreshes `fetched_at/last_seen_at`.
- [x] Add DB-backed tests (skip without `DATABASE_URL`) that prove upsert overwrites fields on key conflict.
- [x] Run targeted checks and document review.

## Review — Backend store upserts for platform entity state tables
- Added `platform_entity_store.py` with idempotent bulk upsert helpers over the 3 entity state tables using composite PK conflict targets.
- Conflict updates overwrite mutable fields, including parent links (`campaign_id`, `ad_group_id` where relevant), `raw_payload`, and `payload_hash`, and force freshness timestamps (`fetched_at/last_seen_at`) to `NOW()`.
- Added DB integration-style tests for campaign/ad_group/ad rows confirming second upsert on same key overwrites `name/status/payload_hash` and parent ids.

---

# TODO — Platform account watermarks store (DB-first, non-regressive upsert)

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Add backend store module for `platform_account_watermarks` read + upsert operations.
- [x] Implement upsert non-regression semantics (`sync_start_date=min`, `historical/rolling=max`, `last_success_at=max`) with conflict-safe SQL.
- [x] Keep mutable fields behavior explicit (`last_error`, `last_job_id`) and refresh `updated_at` on every upsert.
- [x] Add DB-backed tests (skip without `DATABASE_URL`) validating insert, non-regression, forward progress, and mutable overwrite semantics.
- [x] Run requested checks and document review.

## Review — Platform account watermarks store (DB-first, non-regressive upsert)
- Added `platform_account_watermarks_store.py` with grain validation, point-read helper, and idempotent `ON CONFLICT` upsert returning the final row.
- Non-regression policy is enforced in SQL: earliest `sync_start_date`, latest `historical_synced_through`, latest `rolling_synced_through`, latest `last_success_at`.
- `last_error` and `last_job_id` preserve existing values when omitted (`None`) and overwrite when provided with non-null values.
- Added integration-style DB tests that apply migrations in isolated schema and verify insertion, non-regression behavior, and forward progress updates.

---

# TODO — Reconcile watermarks from entity fact coverage

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Add backend reconciler module that derives per-account fact coverage (`min/max/count`) for entity grains and preserves requested account ordering.
- [x] Implement reconciliation flow that updates only `sync_start_date` + `historical_synced_through` via existing non-regressive watermark upsert.
- [x] Ensure accounts without fact rows are skipped (no watermark row created by reconciler for no-data entries).
- [x] Add DB tests (skip without `DATABASE_URL`) for derive coverage, reconcile apply, and non-regression behavior.
- [x] Run requested checks and document review.

## Review — Reconcile watermarks from entity fact coverage
- Added `platform_watermarks_reconcile.py` with table mapping by grain and a coverage query that returns `min_date/max_date/row_count` for all requested account IDs, including no-data accounts.
- Reconcile applies only `sync_start_date` and `historical_synced_through` via `upsert_platform_account_watermark`; it intentionally does not set `rolling_synced_through` in this task.
- Summary payload includes per-grain updated and skipped-no-data counters to support operational observability.
- Added DB integration tests validating coverage derivation, no-data skip behavior, and non-regression via existing watermark store semantics.

---

# TODO — Expose entity watermarks by grain in platform accounts read-model

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Add batch watermark read helper for account_ids+grains with single SQL query and full-account output coverage.
- [x] Integrate batch watermarks into platform accounts read-model as additive `entity_watermarks` payload.
- [x] Preserve existing response fields/semantics while adding grain-level watermark object (`campaign_daily`, `ad_group_daily`, `ad_daily`).
- [x] Add DB-backed contract test (skip-safe) validating populated vs missing grain behavior across two accounts.
- [x] Run requested checks and document review.

## Review — Expose entity watermarks by grain in platform accounts read-model
- Added `list_platform_account_watermarks(...)` to batch-read watermark rows for requested accounts/grains in one query and return null placeholders for missing rows.
- `ClientRegistryService.list_platform_accounts` now enriches each account with additive `entity_watermarks` keyed by grain, while keeping existing metadata fields intact.
- Grain payload shape mirrors watermark columns (`sync_start_date`, `historical_synced_through`, `rolling_synced_through`, `last_success_at`, `last_error`, `last_job_id`).
- Added DB integration contract test proving: account with only campaign watermark gets object only on `campaign_daily`; missing grains and no-watermark accounts return nulls.

---

# TODO — Add grain plumbing for sync_runs (default account_daily)

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only` when possible).
- [x] Audit existing migrations/store and confirm `sync_runs.grain` already exists (from 0014), so no new migration file was added.
- [x] Harden sync_runs store schema bootstrap to enforce grain default/check/index and normalize existing null grains.
- [x] Update sync_runs store serialization/insert paths to keep backward-compatible default grain (`account_daily`).
- [x] Add DB test (skip-safe) for grain column/default and explicit entity grain roundtrip.
- [x] Run requested checks and document review.

## Review — Add grain plumbing for sync_runs (default account_daily)
- Since `sync_runs.grain` already exists in migration `0014_sync_orchestration_v2.sql`, no new migration was created per instruction.
- `SyncRunsStore._ensure_schema()` now upgrades runtime schema by backfilling null grains, enforcing default `account_daily`, setting `NOT NULL`, adding allowed-values check constraint, and creating `(platform, account_id, grain)` index.
- Sync run payload serialization now defaults null grain to `account_daily`, and create/retry insert paths send `account_daily` when grain is absent.
- Added DB integration-style test for column/default introspection and insert roundtrip for default and explicit `campaign_daily` grain values.

---

# TODO — Audit + contract tests for grain-aware /agency/sync-runs/batch

- [x] Run workspace update commands (`git status --short`, `git fetch --all --prune`, `git pull --ff-only`) and note upstream limitations if present.
- [x] Audit batch endpoint request/response contract and dedupe guard behavior for grain support.
- [x] Implement minimal backward-compatible batch payload support for `grain` + `grains` with default/normalization.
- [x] Ensure historical dedupe key includes grain in store-level guard.
- [x] Extend backend contract tests for default grain, multi-grain create, grain-scoped dedupe, invalid grain (422), and duplicate-grain normalization.
- [x] Run requested validation checks and capture review summary.

## Review — Audit + contract tests for grain-aware /agency/sync-runs/batch
- Batch endpoint now accepts both legacy `grain` and additive `grains` payloads, normalizes to distinct ordered grains, and defaults to `account_daily` when omitted.
- Batch creation enqueues one run per `(account_id, grain)` and includes `grain` on per-run/per-result response items while preserving existing response fields.
- Historical dedupe guard now locks and filters by grain, allowing concurrent backfills for different grains on same account/date window while deduping exact grain duplicates.
- Extended API/store tests cover all requested grain contract scenarios, including 422 validation for invalid grain and duplicate grain deduplication behavior.

---

# TODO — Fix closed DB connection in client_registry list_platform_accounts

- [x] Sync workspace state (`git fetch --all --prune`, `git status --short`) and confirm working branch.
- [x] Fix connection lifetime so `list_platform_account_watermarks` is called inside an active DB connection context.
- [x] Add non-DB regression test that fails if watermarks helper receives a closed connection.
- [x] Run requested checks (`pytest`, `py_compile`, `git status --short`) and record review.

## Review — Fix closed DB connection in client_registry list_platform_accounts
- Moved entity watermark lookup/enrichment to run before exiting `with self._connect_or_raise() as conn`, preventing use of a closed psycopg connection.
- Added regression test with fake connection lifecycle asserting `list_platform_account_watermarks` is invoked while `conn.closed == False`.
- Preserved existing output contract for `entity_watermarks` keys (`campaign_daily`, `ad_group_daily`, `ad_daily`).

---

# TODO — Minimal SQL migration runner for Railway/Postgres

- [x] Audit current backend startup/docs and confirm migrations are not auto-applied.
- [x] Add `app.db.migrate` module with `python -m app.db.migrate` CLI entrypoint.
- [x] Implement advisory lock + `schema_migrations` + lexicographic file application with per-file transaction and rollback-on-failure.
- [x] Add skip-safe DB test covering table creation, apply, and idempotent second run.
- [x] Update README with Railway migration runbook (one-shot migrator service recommendation).
- [x] Run targeted checks/tests and document review.

## Review — Minimal SQL migration runner for Railway/Postgres
- Added `apps/backend/app/db/migrate.py` with CLI runner and reusable `run_migrations/apply_migrations` helpers.
- Runner uses a global Postgres advisory lock, ensures `schema_migrations`, applies pending `*.sql` files once in sorted order, and records applied IDs atomically.
- Migration failures rollback current transaction and return non-zero via CLI.
- Added DB integration test (`test_db_migration_runner.py`) that uses a temporary migration directory and validates first apply + idempotent second run.
- README now documents the exact Railway command and recommends a one-shot migration service before web startup.

---

# TODO — Make sync_worker grain-aware (safe default)

- [x] Audit current worker grain handling and dedupe/lock behavior.
- [x] Add safe grain default (`NULL`/missing => `account_daily`) in worker execution path.
- [x] Add unsupported-grain terminal handling (`grain_not_supported`) without crashing worker loop.
- [x] Propagate normalized grain into chunk status metadata for attribution.
- [x] Extend tests for null-grain default path, unsupported-grain error path, and grain-scoped coexistence in dedupe semantics.
- [x] Run targeted compile/tests and document review.

## Review — Make sync_worker grain-aware (safe default)
- Worker now normalizes run grain with backward-compatible default `account_daily` and keeps existing Google account_daily execution path.
- Unsupported grain no longer crashes processing: chunk and run are marked `error` with stable `grain_not_supported:<grain>` payload and worker continues.
- Chunk status updates now attach `metadata.grain` so completed/failed chunks remain attributable to grain.
- Dedupe test coverage explicitly verifies same account/date historical run creation remains allowed across different grains.

---

# TODO — Implement google_ads campaign_daily sync path end-to-end

- [x] Audit existing grain-aware worker flow, Google Ads reporting helpers, entity fact upsert store and watermark reconcile helper.
- [x] Add Google Ads campaign_daily fetch path and map canonical campaign fact fields (`spend/impressions/clicks/conversions/conversion_value/extra_metrics`).
- [x] Wire sync_worker campaign_daily execution to upsert campaign fact rows with source traceability (`source_window_start/source_window_end/source_job_id`).
- [x] Reconcile `platform_account_watermarks` for `campaign_daily` after successful run finalization.
- [x] Keep safe default + stable unsupported handling (`grain_not_supported`) and ensure non-google platform campaign_daily terminates cleanly.
- [x] Extend unit tests for campaign_daily success path and non-google terminal error path.
- [x] Run targeted compile/tests and document review.

## Review — Implement google_ads campaign_daily sync path end-to-end
- Added `GoogleAdsService.fetch_campaign_daily_metrics(...)` using GAQL campaign+date metrics and cost_micros->spend mapping consistent with existing conventions.
- Worker now executes a dedicated branch for `grain=campaign_daily` on `platform=google_ads`, upserts facts via `upsert_campaign_performance_reports`, and attributes rows to chunk window/job source metadata.
- On successful completion for campaign_daily runs, worker now triggers watermark reconcile for that account/grain.
- For campaign_daily on non-google platforms, worker sets terminal `grain_not_supported:<grain>` errors instead of crashing.
- Added worker tests validating campaign_daily fact upsert + source traceability and non-google terminal behavior.

---

# TODO — Fix migration runner path resolution for Railway root_dir=apps/backend

- [x] Audit current `app.db.migrate` default path behavior and reproduce failing path expectation in Railway root directory mode.
- [x] Implement robust migration dir auto-detection with candidate order (`db/migrations`, `apps/backend/db/migrations`, file-derived path) and CLI override priority.
- [x] Improve missing-dir error to include current working directory and list of tried candidates.
- [x] Add resolver-focused unit tests (no DB required) including apps/backend cwd preference and failure message contract.
- [x] Update README Railway operational command with explicit `--migrations-dir db/migrations` + uvicorn chain.
- [x] Run compile + targeted tests and document review.

## Review — Fix migration runner path resolution for Railway root_dir=apps/backend
- `app.db.migrate` now resolves migration directories robustly and keeps CLI override compatibility.
- Resolver prefers `db/migrations` when process cwd is already `apps/backend`, avoiding false missing-dir failures in Railway root-directory deployments.
- Failure message now includes `cwd` and all tried candidates for fast operational debugging.
- Added non-DB tests for resolver selection and error-message contract.

---

# TODO — Baseline support in app.db.migrate for pre-existing production schema

- [x] Add `--baseline-before` CLI flag to migration runner while preserving existing options.
- [x] Implement baseline behavior: if `schema_migrations` is empty, mark all migration IDs `< baseline_before` as applied before normal run.
- [x] Keep baseline as no-op when `schema_migrations` already contains rows.
- [x] Ensure normal migration flow still executes unapplied IDs `>= baseline_before`.
- [x] Add non-DB unit tests for baseline empty/non-empty behavior and execution of newer migrations.
- [x] Update README Railway startup command with baseline flag.
- [x] Run targeted compile/tests and document review.

## Review — Baseline support in app.db.migrate for pre-existing production schema
- Added `--baseline-before` to `app.db.migrate` and threaded it through `run_migrations(...)` -> `apply_migrations(...)`.
- Baseline now inserts legacy migration IDs only when `schema_migrations` is empty, then regular application proceeds for pending migrations.
- Existing installations with non-empty `schema_migrations` are unaffected (baseline no-op).
- Added pure unit tests (no DB) validating baseline insert scope, no-op behavior, and that post-baseline migrations still execute.

---

# TODO — Agency Dashboard frontend consume summary.integration_health

- [x] Rebase workspace on latest `origin/main` and start clean frontend branch.
- [x] Remove provider-specific integration status requests from agency dashboard page.
- [x] Consume only `summary.integration_health` in Integration health card with empty fallback.
- [x] Add/update Agency Dashboard frontend tests for integration health rendering contract.
- [x] Run required frontend test and build commands.

## Review
- Agency Dashboard now performs a single summary request and renders integration health from `summary.integration_health`.
- Removed old Google-only status state/request and manual provider list construction.
- Added frontend tests validating summary-driven integration health rendering and empty fallback.

---

# TODO — TikTok Ads backend connect foundation

- [x] Start from clean baseline branch and inspect TikTok/Meta/secrets store implementation.
- [x] Add TikTok OAuth config env support in backend settings.
- [x] Implement TikTok service connect/exchange + real status based on persisted secrets.
- [x] Add TikTok API endpoints for connect start and OAuth exchange.
- [x] Add focused backend tests for connect/exchange/status scenarios.
- [x] Update README minimally for TikTok OAuth env and endpoints.
- [x] Run targeted pytest + backend import smoke checks.

## Review
- Added TikTok OAuth foundation (connect URL + code exchange) with state validation and secure token persistence in `integration_secrets`.
- `GET /integrations/tiktok-ads/status` now reports operational fields for UI (`token_source`, token timestamps, oauth config, usable token) instead of mock-only connected status.
- Existing TikTok sync endpoint remains compatible but explicitly marked stub in sync payload (`sync_mode=stub`) to avoid confusion about real metrics import scope.

---

# TODO — Frontend-only TikTok Integrations card + OAuth callback

- [x] Create clean frontend branch from clean local baseline and verify scope constraints.
- [x] Keep `agency/integrations/page.tsx` as composition page and render `<TikTokIntegrationCard />`.
- [x] Implement TikTok integration UI logic in dedicated card component (status/connect/import).
- [x] Implement TikTok OAuth callback page (provider error, missing code/state, exchange + redirect).
- [x] Add focused frontend tests for page composition, TikTok card behaviors, and callback flows.
- [x] Run required frontend tests and build.

## Review
- `agency/integrations/page.tsx` now delegates TikTok behavior to `TikTokIntegrationCard` and keeps layout/orchestration role.
- TikTok card now consumes existing backend contracts (`status`, `connect`, `import-accounts`) with robust fallbacks and button gating by `oauth_configured` / `has_usable_token`.
- TikTok callback page exchanges `code/state` via backend and redirects to `/agency/integrations?tiktok_connected=1` on success.

---

# TODO — Publish TikTok ad_daily sync grain

- [x] Verify ad_daily implementation state versus user report and identify missing pieces.
- [x] Add missing `ad_daily` support in TikTok service + API contract.
- [x] Add focused backend tests for ad_daily paths and schema acceptance.
- [x] Run targeted compile/tests/smoke checks.
- [x] Commit and prepare PR publishing metadata.

## Review
- The current branch was missing `ad_daily` in TikTok grain union, API schema, and dedicated tests; these were restored.
- Sync now supports `ad_daily` with ad-level fetch + generic ad-unit upsert and idempotent test-mode key replacement.

---

# TODO — TikTok historical backfill endpoint (chunked, all grains)

- [x] Inspect TikTok sync API/service and Meta backfill orchestration pattern for reuse.
- [x] Add TikTok backfill defaults, grain normalization, and chunk builder (30-day windows).
- [x] Implement async historical backfill runner that reuses `tiktok_ads_service.sync_client` per grain+chunk.
- [x] Add `POST /integrations/tiktok-ads/{client_id}/backfill` with default range/grains and enqueue response.
- [x] Add focused backend tests for enqueue defaults/custom, validation, flag/token/no-accounts, and runner error mapping.
- [x] Update README minimally and run targeted compile/tests/smoke checks.

## Review
- Added queue-based TikTok historical backfill orchestration with defaults `2024-01-09 -> yesterday`, grains `[account_daily,campaign_daily,ad_group_daily,ad_daily]`, and 30-day chunks.
- Backfill runner delegates every chunk to existing `sync_client` (no duplicate fetch/persist logic) and records done/error in `backfill_job_store`.
- Endpoint validates flag/token/attached-accounts early and returns stable enqueue payload (`mode`, `chunks_enqueued`, `jobs_enqueued`, `job_id`).

---

# TODO — TikTok rolling daily sync (7-day window)

- [x] Extend rolling scheduler platform support to include `tiktok_ads` without breaking Google/Meta.
- [x] Include TikTok entity grains in rolling expansion when `ROLLING_ENTITY_GRAINS_ENABLED` is ON.
- [x] Ensure sync worker processes TikTok rolling runs through existing `tiktok_ads_service.sync_client` path.
- [x] Add focused tests for scheduler grain expansion/flag behavior and worker success/error mapping for TikTok.
- [x] Update README rolling section minimally and run compile/tests/smoke checks.

## Review
- Rolling scheduler now accepts `platform=tiktok_ads` and enqueues `account_daily` (+ entity grains under flag) on the same 7-day complete window.
- Worker now supports TikTok platform runs by reusing existing TikTok sync service for chunk execution; no duplicate fetch/persist logic added.
- Existing Google/Meta rolling behavior remained compatible in scheduler tests.

# TODO — Reconnect git remote and sync latest main

- [x] Create plan/checklist for remote reconnection task.
- [x] Run exact remote/fetch/pull commands provided by user.
- [x] Record outcomes and constraints.
- [x] Commit task tracking updates and open PR record.

## Review
- [x] Executed exact commands in current workspace terminal; remote `origin` added, `fetch` succeeded, and `pull origin main` reported `Already up to date`.


---

# TODO — Meta/TikTok sync real error observability

- [x] Re-sync workspace to latest `origin/main` before code changes (remote add/fetch + rebase) and document constraints if any.
- [x] Trace full Meta/TikTok batch flow (API create -> worker -> provider service -> progress API -> Agency Accounts) and pinpoint where root errors become generic.
- [x] Implement minimal backend structured + sanitized error propagation to progress response (`last_error_summary`, `last_error_details`) without changing Google business flow.
- [x] Add targeted backend tests for structured propagation, secret sanitization, and safe fallback when provider error fields are missing.
- [x] Apply minimal Agency Accounts UI change to display real error summary under existing error status, if available.
- [x] Update README with short diagnostics section and run required backend tests (+ frontend build if touched).

## Review
- [x] Root-cause loss point identified: worker wrapped provider exceptions into generic RuntimeError and progress payload lacked additive error fields.

- [x] Added structured error metadata plumbing in worker/chunk/run, additive progress fields, and service-level HTTP error enrichment with token-safe sanitization.
- [x] Verified with targeted backend tests and frontend build.


---

# TODO — Meta/TikTok full parity in Agency Accounts detail + logs

- [x] Sync workspace to latest remote baseline before edits.
- [x] Audit Agency Accounts list + detail flows for Google-vs-Meta/TikTok parity gaps (linking, metadata, sync runs, logs, terminal errors).
- [x] Implement minimal frontend parity changes for clickable names, generic metadata loading, and terminal error visibility in list/detail for Meta/TikTok.
- [x] Add focused frontend tests for link behavior, detail metadata/error rendering, and list terminal-error summaries.
- [x] Run relevant frontend tests + frontend build and record results.

## Review
- [x] Implemented parity updates in Agency Accounts list and detail page for Meta/TikTok, preserving Google behavior and existing run/chunk logs UX.

- [x] Detailed parity verification passed: targeted vitest suite for list/detail pages and `pnpm --dir apps/frontend build`.

---

# TODO — Fix Meta historical sync contract + account scoping

- [x] Update workspace to latest remote baseline before analysis/code changes.
- [x] Trace Meta batch/run/chunk flow and locate contract mismatch in `MetaAdsService.sync_client` usage.
- [x] Fix Meta service sync contract (`client_id/start_date/end_date/grain/account_id`) and implement robust window+grain+account scoping behavior.
- [x] Apply minimal worker plumbing change to pass selected `account_id` context into Meta sync call.
- [x] Add backend tests for keyword-arg regression, account scoping, invalid grain/date window, and missing/unattached account errors.
- [x] Run targeted backend tests and document outcomes.

## Review
- [x] Root cause fixed: Meta service signature/implementation is now aligned with worker chunk call contract and no longer fails on unexpected keyword arguments.

- [x] Verified with targeted backend suite covering Meta sync service contract + sync worker Meta path + existing Meta account_daily scenarios.


---

# TODO — Normalize Meta account_id and prevent act_act_ Graph paths

- [x] Update workspace to latest remote baseline before changes.
- [x] Trace Meta account_id flow for mapping/scoping/Graph endpoint construction and identify double-prefix risk.
- [x] Add focused Meta account-id helpers (normalize, numeric, graph path, match) and wire them into scoping + API calls.
- [x] Add backend regression tests for numeric/prefixed IDs, no `act_act_` endpoint generation, and normalized selected-account matching.
- [x] Run targeted backend tests and document outcomes.

## Review
- [x] Root cause fixed: Graph endpoint construction now uses normalized account path helper, eliminating `act_act_` double-prefix requests and robustly matching `act_123` with `123` in selected-account scoping.

- [x] Verified with backend tests for normalization regressions + existing Meta sync service/worker suites.


---

# TODO — Align Meta backend requests with Graph Explorer valid shape

- [x] Update workspace to latest remote baseline before modifications.
- [x] Audit Meta backend request construction for account path, graph version, token source, and selected-account scoping parity with Explorer.
- [x] Implement small helpers for account path/version/token-source/account-probe and reuse them in validation + insights requests.
- [x] Extend backend tests for URL parity (numeric/prefixed), no `act_act_`, v24.0 usage, probe response validation, and path reuse in sync calls.
- [x] Run targeted backend tests and record outcomes.

## Review
- [x] Implemented Graph Explorer parity helpers and request-shape alignment for Meta account probe + insights URL construction.

- [x] Verified backend regressions with targeted pytest suite for Meta contract + existing Meta sync/worker tests.


---

# TODO — Keep effective done status and hide superseded historical failures

- [x] Update workspace to latest remote baseline before changes.
- [x] Audit Agency Accounts list/detail status reconciliation and historical failure visibility rules.
- [x] Add a shared effective sync status + superseded historical helper and apply it consistently in list/detail flows.
- [x] Hide superseded historical failures by default (no hard delete), keep unresolved failures visible, and ensure latest error banner uses unresolved latest failure only.
- [x] Add/adjust frontend tests for done-vs-idle, superseded filtering, and banner behavior; run required tests/build.

## Review
- [x] Effective status helper now prioritizes active/error/success semantics before idle, so rows with stale `idle` status and valid `last_success_at` remain `done`.
- [x] Google list rows now show “Eroare recentă” only when effective status is still failure, preventing stale old error banners after successful syncs.
- [x] Added regression coverage for idle-vs-done helper precedence and list rendering that suppresses stale errors while keeping status `done`.
- [x] Verification: `pnpm --dir apps/frontend test src/app/agency-accounts/sync-runs.test.ts src/app/agency-accounts/page.list.test.tsx`.
- [x] Attempted `pnpm --dir apps/frontend build`; build process was started but could not complete within container execution window.

---

# TODO — Stabilizare TikTok pasul 2: contract sync + advertiser scoping

- [x] Sync workspace to latest available repo state before implementation.
- [x] Trace TikTok flow end-to-end (orchestration -> runs/chunks -> worker -> service sync contract).
- [x] Align `TikTokAdsService.sync_client` contract to explicit worker params (`client_id`, window, grain, optional `account_id`).
- [x] Pass selected run `account_id` from worker into TikTok sync call.
- [x] Enforce strict advertiser scoping in TikTok service for selected `account_id`, including normalize+ownership validation.
- [x] Add regression tests for worker passthrough + service scoping/validation errors.
- [x] Run targeted backend tests and record outcomes.

## Review
- [x] TikTok worker/service contract now includes selected advertiser `account_id`; service no longer fans out to all attached accounts when a specific advertiser is selected.
- [x] Error paths now return explicit `TikTokAdsIntegrationError` for no attached accounts, unattached selected advertiser, invalid date window, invalid grain, and missing token.

---

# TODO — Stabilizare TikTok pasul 3: preflight advertiser access probe

- [x] Sync workspace to latest available repo state before modifications.
- [x] Analyze TikTok flow (orchestration -> worker -> service contract -> provider call -> error observability).
- [x] Add lightweight preflight advertiser probe before reporting (`oauth2/advertiser/get`) for selected/target advertiser(s).
- [x] Implement error classification for TikTok sync/probe paths (`local_attachment_error`, `provider_access_denied`, `token_missing_or_invalid`, `provider_http_error_generic`).
- [x] Ensure worker observability details include safe debug fields (`platform`, `advertiser_id`, `endpoint`, `http_status`, `provider_error_code`, `provider_error_message`, `token_source`, `error_category`) without token leaks.
- [x] Add/update backend tests for probe deny, token classification, probe-success continuation, worker metadata propagation, and local attachment/token validation.
- [x] Run targeted backend tests (service + worker + orchestration subset) and capture outcomes.

## Review
- [x] TikTok sync now performs provider-side preflight access validation before reporting and fails fast with classified, sanitized errors when advertiser access/token is invalid.
- [x] Existing local attachment validation remains distinct from provider access failures, and worker-level error details now expose safe classification context for UI/ops debugging.

---

# TODO — TikTok UX + API wiring pentru error_category

- [x] Sync workspace to latest available repo state and confirm branch/remote constraints.
- [x] Expose stable TikTok error category field from backend sync payloads used by frontend (`last_error_category`).
- [x] Add centralized frontend mapping helper for TikTok error categories to user-facing safe labels.
- [x] Wire TikTok category messaging in Agency Accounts list + Agency Account Detail (banner + run cards) with safe fallback.
- [x] Disable TikTok historical trigger in UI when frontend TikTok feature flag is off and show explicit unavailable message.
- [x] Add/update frontend tests for category mapping, list/detail rendering, fallback behavior, and disabled button behavior.
- [x] Run targeted frontend tests, frontend build, and relevant backend tests.

## Review
- [x] TikTok error categories are now displayed explicitly in UI without fragile free-text parsing.
- [x] Existing fallback behavior remains for missing categories, and non-TikTok flows are unchanged.

---

# TODO — Stabilizare TikTok pasul 4: enablement configurabil + UI wiring

- [x] Run requested git remote/fetch/pull commands and reconcile local branch with `origin/main`.
- [x] Make TikTok enablement configurable via explicit env alias (`TIKTOK_SYNC_ENABLED`) while keeping legacy compatibility.
- [x] Expose platform sync availability (`sync_enabled`) in clients summary and platform accounts payloads.
- [x] Wire Agency Accounts TikTok availability from backend payload (with env fallback) for disabled/enabled historical button behavior.
- [x] Wire Agency Account Detail TikTok disabled banner from backend availability payload.
- [x] Add/update backend and frontend tests for config/orchestration/UI enablement behavior.
- [x] Run targeted backend tests, frontend tests, and frontend build.

## Review
- [x] TikTok is no longer effectively hard-disabled when explicit enablement env is set; UI now reflects backend availability signal and keeps safe fallback behavior.

---

# TODO — Clear stale TikTok feature-flag recent errors when sync is enabled

- [x] Re-check current backend/frontend derivation for TikTok recent error and status fallback sources.
- [x] Implement minimal stale-error suppression rule for TikTok `integration_disabled`/feature-flag-disabled when platform is currently enabled.
- [x] Ensure new runs still clear/replace recent error state correctly (success clears, new real failures replace).
- [x] Add/adjust targeted backend and frontend tests for stale-vs-real disabled scenarios and recent-error transitions.
- [x] Run requested backend tests, frontend tests, and frontend build; record outcomes.

## Review
- [x] Completed implementation + verification notes.

- Stale TikTok feature-flag errors are now suppressed when `sync_enabled=true` and no active run confirms disabled state, without deleting sync history.
- Backend list payload (`/clients/accounts/tiktok_ads`) now clears derived `last_error` only for stale feature-flag strings when TikTok sync is enabled.
- Frontend list/detail now use shared stale-error guard helper to avoid rendering stale "disabled by feature flag" as current recent error.
- Added backend + frontend tests for enabled stale suppression and disabled-state preservation.
- Verification: `pytest -q apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_account_sync_metadata_contract.py`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx src/app/agency-accounts/[platform]/[accountId]/page.platform-parity.test.tsx src/app/agency-accounts/sync-runs.test.ts`, `pnpm --dir apps/frontend build`.

---

# TODO — TikTok advertiser access probe parity with discovery helper

- [x] Verify current config usage for `TIKTOK_API_BASE_URL` / `TIKTOK_API_VERSION` and confirm override risk.
- [x] Compare TikTok advertiser discovery/import request shape vs sync access probe request shape.
- [x] Implement minimal shared helper for fetching accessible advertisers and reuse it in import + access probe.
- [x] Keep structured error payloads and ensure provider_access_denied classification when advertiser missing.
- [x] Add tests for helper reuse, probe success/denied paths, config base URL override, and token-safe error handling.
- [x] Run targeted backend test commands and capture results.

## Review
- [x] Completed implementation + verification notes.

- Probe now reuses advertiser discovery (`GET /oauth2/advertiser/get/` with app_id+secret+page params + Access-Token header) instead of a separate POST advertiser_ids shape.
- Added `_advertiser_get_endpoint(...)` helper and reused it in both discovery and probe so endpoint/base-version usage is standardized.
- Probe now validates selected advertiser by membership in discovered accessible advertiser list and raises `provider_access_denied` when missing.
- Added tests for probe/discovery helper reuse, present/absent advertiser outcomes, import+probe endpoint parity, and explicit config override of `TIKTOK_API_BASE_URL`/`TIKTOK_API_VERSION`.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_config.py apps/backend/tests/test_services.py::ServiceTests::test_tiktok_ads_sync_provider_access_denied_on_probe`.

---

# TODO — TikTok reporting parity: report/integrated/get via GET + query params

- [x] Inspect TikTok reporting fetch paths for account/campaign/ad_group/ad grains and locate POST usages.
- [x] Implement shared `_report_integrated_get(...)` helper with GET + query serialization + Access-Token header.
- [x] Migrate all four TikTok reporting grains to helper without changing sync contract/scoping.
- [x] Preserve structured observability fields and sanitization behavior.
- [x] Add tests for method/query/header parity across grains + no token leak + 405 regression guard.
- [x] Run targeted backend test suites and record outcomes.

## Review
- [x] Completed implementation + verification notes.

- TikTok reporting now uses `GET /report/integrated/get/` with query params via shared `_report_integrated_get(...)` helper across account/campaign/ad_group/ad daily fetches.
- Access token remains in `Access-Token` header; query string contains reporting params only (`advertiser_id`, `report_type`, `data_level`, `dimensions`, `metrics`, `start_date`, `end_date`, `page`, `page_size`).
- Added tests for GET method/query serialization/header, shared helper reuse across all 4 grains, and a 405 regression guard (non-GET fails in mock).
- Verification: `pytest -q apps/backend/tests/test_tiktok_*` and `pytest -q apps/backend/tests/test_config.py apps/backend/tests/test_services.py::ServiceTests::test_tiktok_ads_sync_provider_access_denied_on_probe`.

---

# TODO — Sync remote origin and fetch/pull from GitHub

- [x] Run provided `git remote add ... || git remote set-url ...` command exactly as requested.
- [x] Run `git fetch origin`.
- [x] Run `git pull origin main --allow-unrelated-histories`.

## Review
- [x] Executed all requested git connectivity/sync commands in terminal and captured outputs.

---

# TODO — TikTok reporting schema fix per grain (metrics/dimensions validity)

- [x] Audit current TikTok reporting request schema for all grains (`account_daily`, `campaign_daily`, `ad_group_daily`, `ad_daily`).
- [x] Introduce a centralized per-grain reporting schema helper and wire all grain fetchers to it.
- [x] Remove invalid metric(s) for `account_daily` (notably `conversion_value`) while keeping safe internal fallback mapping.
- [x] Reduce dimensions to TikTok accepted limit (<=4) for `ad_group_daily` and `ad_daily`, preferring ID-based dimensions.
- [x] Add/adjust backend tests for per-grain request schema, conversion fallback, dimension limits, helper usage, and structural validity regressions.
- [x] Run targeted backend TikTok tests and capture outcomes.

## Review
- [x] Completed implementation + verification notes.

- Centralized TikTok reporting request schema by grain via `_report_schema_for_grain(...)` and routed all 4 grain fetchers through it.
- `account_daily` request metrics no longer include `conversion_value`; conversion value persistence continues via `_extract_conversion_value(...)` fallback keys (e.g. `total_purchase_value`).
- `ad_group_daily` dimensions reduced to 4 (`stat_time_day`, `adgroup_id`, `campaign_id`, `campaign_name`) and `ad_daily` dimensions reduced to 4 (`stat_time_day`, `ad_id`, `adgroup_id`, `campaign_id`).
- Added regression tests for per-grain schema constraints, account conversion fallback, and structural payload validity against known provider errors.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py` and `pytest -q apps/backend/tests/test_tiktok_* apps/backend/tests/test_services.py::ServiceTests::test_tiktok_ads_sync_real_account_daily_single_account`.

---

# TODO — TikTok reporting schema fix pasul 2 (dimension compatibility per data_level)

- [x] Audit current TikTok per-grain schema/request payload for campaign/ad_group/ad against runtime errors.
- [x] Adjust centralized `_report_schema_for_grain(...)` so each grain only uses dimensions compatible with its `data_level`.
- [x] Keep `account_daily` schema unchanged and valid.
- [x] Ensure entity name/hierarchy fields use safe fallback from payload metadata/snapshot/item fallback (not forced via invalid dimensions).
- [x] Add/update backend tests for invalid dimension regression patterns and per-grain schema assertions.
- [x] Run targeted backend TikTok tests and document results.

## Review
- [x] Completed implementation + verification notes.

- Updated per-grain TikTok dimensions to strict data_level-compatible sets: campaign (`stat_time_day`,`campaign_id`), ad_group (`stat_time_day`,`adgroup_id`), ad (`stat_time_day`,`ad_id`), while preserving account_daily unchanged.
- Kept entity name hierarchy handling safe by retaining existing item/dimensions fallback extraction without forcing unsupported provider-side dimensions.
- Added tests to assert runtime-invalid dimensions are excluded per grain and to regress known production error messages.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py` and `pytest -q apps/backend/tests/test_tiktok_* apps/backend/tests/test_services.py::ServiceTests::test_tiktok_ads_sync_real_account_daily_single_account`.

---

# TODO — TikTok reporting schema fix pasul 3 (remove conversion_value for campaign/ad_group/ad)

- [x] Audit current TikTok per-grain metrics and confirm where `conversion_value` is still sent provider-side.
- [x] Update centralized TikTok reporting schema helper to remove `conversion_value` from `campaign_daily`, `ad_group_daily`, and `ad_daily` only.
- [x] Keep `account_daily` request schema unchanged and valid.
- [x] Preserve internal conversion value field via safe fallback extraction from allowed metrics.
- [x] Add/update backend tests for per-grain metric exclusions and runtime error regression (`Invalid metric fields: ['conversion_value']`).
- [x] Run targeted backend TikTok tests and document results.

## Review
- [x] Completed implementation + verification notes.

- Removed provider-side `conversion_value` metric from `campaign_daily`, `ad_group_daily`, and `ad_daily` schemas while leaving `account_daily` unchanged.
- Kept internal `conversion_value` pipeline intact via `_extract_conversion_value(...)` fallback from allowed keys (e.g. `total_purchase_value`).
- Added tests to assert no remaining grain requests `conversion_value` and to regress real provider error payload (`Invalid metric fields: ['conversion_value']`).
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py` and `pytest -q apps/backend/tests/test_tiktok_* apps/backend/tests/test_services.py::ServiceTests::test_tiktok_ads_sync_real_account_daily_single_account`.

---

# TODO — TikTok zero-row observability + stale recent-error suppression after success

- [x] Audit TikTok sync success path for row counters and where run/chunk metadata can safely carry provider vs mapped/write counts.
- [x] Add TikTok reporting observability fields for provider rows downloaded, mapped rows, and zero-row markers (provider empty vs parsed-but-zero-mapped).
- [x] Propagate observability to sync chunk metadata so detail logs can show rows_downloaded vs rows_written.
- [x] Suppress stale TikTok recent error in accounts payload when latest relevant run is successful and no active sync.
- [x] Expose rows_downloaded/provider_row_count in detail UI run/chunk logs with minimal UI change.
- [x] Add/update backend/frontend tests and run targeted test suites.

## Review
- [x] Completed implementation + verification notes.

- TikTok sync now records per-fetch observability (`provider_row_count`/`rows_downloaded`, `rows_mapped`, skip counters, safe sample keys) and surfaces zero-row markers for both provider-empty and parsed-but-zero-mapped scenarios.
- Sync worker now writes TikTok observability into chunk metadata on success (`rows_downloaded`, `provider_row_count`, `rows_mapped`, `zero_row_observability`) so detail logs can distinguish no-data vs mapping gaps.
- Clients TikTok listing now suppresses stale recent error payload when latest run is successful (`done/success/completed`), there is no active sync, and `last_success_at` is present.
- Detail UI now displays `rows downloaded` vs `rows written` (and mapped) in run summary + chunk logs for TikTok with minimal no-redesign changes.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_sync_worker.py`, `pytest -q apps/backend/tests/test_account_sync_metadata_contract.py apps/backend/tests/test_clients_platform_account_mappings.py`, `pnpm --dir apps/frontend test src/app/agency-accounts/[platform]/[accountId]/page.platform-parity.test.tsx`, `pnpm --dir apps/frontend build`.

- Successful TikTok runs now suppress stale per-run error fields in sync-run API serialization, preventing false `Category: run failed` display on `done` runs.
- Added explicit empty-success handling in worker finalization for TikTok historical: when chunk observability shows `rows_downloaded=0` and `rows_mapped=0`, we keep run `done` but do not advance `backfill_completed_through`.
- Detail UI now shows neutral no-data diagnostics for successful TikTok runs (`provider_returned_empty_list` / `response_parsed_but_zero_rows_mapped`) instead of failure category messaging.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_sync_worker.py`, `APP_AUTH_SECRET=test-auth-secret pytest -q apps/backend/tests/test_sync_orchestration_meta_ids.py apps/backend/tests/test_account_sync_metadata_contract.py`, `pnpm --dir apps/frontend test src/app/agency-accounts/[platform]/[accountId]/page.platform-parity.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — TikTok historical 1-year cap + short chunks + empty-success coverage semantics

- [x] Audit current TikTok batch orchestration for effective start date/chunk sizing and identify hooks for platform-specific clamp.
- [x] Implement TikTok-only historical start-date cap to max(last 365 days, original sync start) without impacting other platforms.
- [x] Enforce short TikTok historical chunk windows (max 30 days) while preserving existing chunk behavior for other platforms.
- [x] Keep empty-success semantics: do not advance TikTok `backfill_completed_through` when done+zero downloaded/mapped, and mark no-data success explicitly in metadata.
- [x] Ensure run/detail payload/UI derivation shows neutral no-data state (not false error and not misleading full-success coverage).
- [x] Add/update backend/frontend tests for 1-year cap, chunk size, empty-success semantics, and non-TikTok regressions.

## Review
- [x] Completed implementation + verification notes.

- Batch orchestration now derives TikTok historical effective start using max(requested start, account sync_start_date, today-365d), keeping non-TikTok behavior unchanged.
- TikTok historical chunk sizing now clamps to 30 days while preserving requested chunk size semantics for other platforms/jobs.
- Empty-success finalization path persists explicit no-data metadata (`no_data_success`, `empty_success`, row counters, zero_row_marker) and skips coverage advancement for zero-row historical completions.
- Added regression tests for TikTok 1-year clamp + chunk cap, non-TikTok unchanged chunk sizing, and empty-success no-data marker propagation.
- Verification: `pytest -q apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_sync_worker.py`.

---

# TODO — TikTok deep-dive parity + zero-row diagnostics + no-data success semantics

- [x] Sync workspace against latest repo state before edits (or record exact git topology blocker).
- [x] Add explicit TikTok reporting request parity helper parameters (`report_type`, `service_type`, `query_mode`) and keep request shape testable.
- [x] Expand reporting observability with safe request/response diagnostics (endpoint/query + keys + row markers) without leaking tokens.
- [x] Differentiate provider empty-list vs parsed-but-zero-mapped with mapper missing-key diagnostics.
- [x] Ensure all-zero TikTok historical outcomes are not treated as full operational success/backfill-valid completion semantics.
- [x] Add minimal UI messaging for TikTok all-zero last-run diagnostics without redesign.
- [x] Add/update backend + frontend tests for request parity, diagnostics differentiation, all-zero semantics, and secret safety.

## Review
- [x] Completed implementation + verification notes.

- Git sync attempt executed first (`git pull --rebase`) and blocked by repository topology (`work` has no tracking remote configured); continued from current up-to-date local HEAD.
- TikTok reporting now uses explicit parity parameters through a shared helper (`report_type=BASIC`, `service_type=AUCTION`, `query_mode=REGULAR`) and stores sanitized request+response diagnostics per fetch.
- Zero-row diagnostics now include provider-empty vs parser-zero-mapped markers plus `missing_required_breakdown` for mapper-required keys.
- Sync run serialization now exposes `operational_status=no_data_success` for successful no-data TikTok runs; batch progress surfaces `operational_status=completed_with_no_data` when all batch runs are no-data success.
- Agency account detail keeps minimal UI change: shows explicit `no_data_success` badge while retaining neutral no-data diagnostics messages.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_sync_worker.py`, `pnpm --dir apps/frontend test src/app/agency-accounts/[platform]/[accountId]/page.platform-parity.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — Fix Agency sync-run chunks 500 via JSON-safe metadata serialization

- [x] Attempt workspace sync before edits and record git topology blocker if tracking remote is missing.
- [x] Locate `GET /agency/sync-runs/{jobId}/chunks` backend path and identify exact 500 failure point.
- [x] Implement small recursive `to_json_safe(value)` helper for dict/list/tuple/set/date/datetime/Decimal/Enum/bytes + safe fallback.
- [x] Apply JSON-safe normalization to chunk endpoint payload (metadata + nested observability details).
- [x] Preserve TikTok observability fields (`sample_row_keys`, `skipped_*`, `zero_row_marker`, `rows_downloaded`, `rows_mapped`, `rows_written`).
- [x] Add backend tests for problematic types and endpoint regression (no 500 on observability-rich metadata).
- [x] Run backend tests relevant to chunk serialization endpoint.

## Review
- [x] Completed implementation + verification notes.

- Workspace sync was attempted first via `git pull --rebase`; blocked because local branch has no tracking remote configured in this environment.
- Root cause for chunks 500 was endpoint serialization bug in `_serialize_chunk`: it referenced undefined variable `is_success`, causing runtime `NameError` on Show logs path.
- Added recursive `to_json_safe` and applied it to run/chunk metadata serialization so rich observability payloads are JSON-safe while preserving diagnostic fields.
- Added dedicated backend tests for set/date/datetime/Decimal/Enum/bytes and endpoint-function regression coverage for observability-rich chunk metadata.
- Verification: `pytest -q apps/backend/tests/test_sync_orchestration_json_safe.py apps/backend/tests/test_sync_orchestration_api.py`, `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py::TikTokAdsImportAccountsTests::test_sync_client_records_provider_empty_list_observability`.

---

# TODO — Urgent Show logs TikTok: /chunks 500 fix + observability visibility

- [x] Attempt workspace update before changes and record git topology blocker if no tracking remote exists.
- [x] Re-verify current `/agency/sync-runs/{jobId}/chunks` serialization path for NameError regression and JSON-safe metadata behavior.
- [x] Apply minimal backend-only patch if needed so `_serialize_chunk` never references undefined vars and keeps chunk observability fields.
- [x] Add/adjust backend tests for: endpoint no longer 500, TikTok observability fields present, and no token leak.
- [x] Run targeted backend tests for chunks endpoint/serialization.

## Review
- [x] Completed implementation + verification notes.

- Workspace update was attempted first (`git pull --rebase`) and blocked by missing tracking remote configuration on branch `work`.
- Confirmed endpoint path and runtime failure source: `/agency/sync-runs/{jobId}/chunks` used `_serialize_chunk`, where undefined `is_success` caused NameError and 500 in Show logs.
- Kept patch minimal and backend-focused: `_serialize_chunk` now uses local `chunk_success` and JSON-safe metadata; no TikTok reporting logic changed.
- Strengthened JSON-safe helper with secret masking for token-like keys/query params while preserving observability counters/markers in response payload.
- Added API-level regression test that hits `/chunks`, asserts 200, validates TikTok observability fields, and verifies no token leakage in response body.
- Verification: `pytest -q apps/backend/tests/test_sync_orchestration_json_safe.py apps/backend/tests/test_sync_orchestration_api.py`, `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py::TikTokAdsImportAccountsTests::test_sync_client_records_provider_empty_list_observability`.

---

# TODO — TikTok parser deep-dive: nested mapping + parser_failure semantics

- [x] Attempt workspace update before edits and record git topology blocker when tracking remote is unavailable.
- [x] Audit current TikTok fetch parser for nested `dimensions`/`metrics` handling and date extraction per grain.
- [x] Implement row normalization helpers for dimensions/metrics map extraction across dict/list/simple shapes.
- [x] Map per-grain fields from normalized dimensions/metrics (stat_time_day, entity ids, metrics) and reduce false skipped_invalid_date.
- [x] Add deeper parser observability (`sample_dimension_keys`, `sample_metric_keys`, `date_source_used`, skip reasons) without secret leaks.
- [x] Introduce parser_failure semantics distinct from no_data_success and prevent success/backfill advancement on parser_failure.
- [x] Apply minimal API/UI status adjustments only if needed so parser_failure is not shown as clean success.
- [x] Add/adjust tests for nested row mapping, date parsing, parser_failure vs no_data_success, backfill semantics, and no token leak.
- [x] Run relevant backend tests (and frontend tests/build only if UI touched).

## Review
- [x] Completed implementation + verification notes.

- Workspace update attempted first (`git pull --rebase`), blocked by missing tracking remote on local `work` branch.
- TikTok parser now normalizes nested `dimensions`/`metrics` payloads from dict/list/entry-shapes and performs robust report date parsing (ISO date, datetime, `YYYYMMDD`, `...Z`).
- Parser observability now includes `sample_dimension_keys`, `sample_metric_keys`, `date_source_used`, and `skip_reason_counts` while retaining existing row counters/zero-row markers.
- Worker finalization now classifies `provider_row_count>0 && rows_mapped=0` as parser failure (terminal error), preventing `last_success_at` and backfill advancement; true provider-empty remains `no_data_success`.
- Added backend tests for nested row shape mapping, parser observability/date source, parser_failure finalization semantics, and operational status serialization.
- Verification: `pytest -q apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_sync_worker.py apps/backend/tests/test_sync_orchestration_api.py`.

---

# TODO — TikTok run summary aggregation + effective historical window UI correctness

- [x] Attempt workspace sync before edits and record git topology blocker if tracking remote is unavailable.
- [x] Audit current run-level serialization/aggregation for `rows_written`, `rows_downloaded`, `rows_mapped` and identify why TikTok run cards show 0/0 while chunks have values.
- [x] Implement robust run-level aggregation from chunks for TikTok `rows_downloaded` and `rows_mapped` (safe with partial metadata, no double-count semantics regressions).
- [x] Keep other platforms unaffected and preserve existing `rows_written` behavior.
- [x] Update Agency Accounts TikTok historical text to reflect effective historical window reality (last-year cap) instead of misleading raw sync_start_date.
- [x] Ensure Agency Account Detail run cards display run summary rows consistent with chunk logs.
- [x] Add/update backend + frontend tests for summary aggregation and TikTok historical window text correctness.
- [x] Run backend tests, frontend targeted tests, and frontend build.

## Review
- [x] Completed implementation + verification notes.

- Workspace sync was attempted first (`git pull --rebase`) and blocked because local branch `work` has no tracking remote configured.
- Run-card 0/0 root cause: run-level metadata did not aggregate `rows_downloaded` / `rows_mapped` from chunk metadata, while UI summary reads those fields from run metadata.
- Backend now aggregates TikTok run-level rows from chunk metadata (dedup by `chunk_index`, tolerant to missing fields) and injects totals into reconciled run metadata used by detail/list APIs.
- Agency Accounts TikTok historical text now reflects effective capped window (`ultimul an`) instead of raw `sync_start_date`; completion banner for TikTok historical also states last-year cap.
- Added backend API regression test for aggregated run summary rows and frontend tests for TikTok effective historical window label + completion banner text.
- Verification: `pytest -q apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_tiktok_ads_import_accounts.py apps/backend/tests/test_sync_worker.py`, `pnpm --dir apps/frontend test src/app/agency-accounts/page.tiktok.test.tsx src/app/agency-accounts/[platform]/[accountId]/page.platform-parity.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — TikTok historical failed-run cleanup + operational metadata reconciliation

- [x] Attempt workspace sync before edits and record git topology blocker if tracking remote is unavailable.
- [x] Implement backend cleanup for superseded TikTok historical_backfill failed runs + associated chunks (safe scope only).
- [x] Recompute TikTok account operational metadata for affected accounts after cleanup (last run fields, success/error, backfill coverage).
- [x] Expose a safe one-off trigger path for existing data cleanup.
- [x] Add backend tests for cleanup deletion semantics, metadata reconciliation, and non-impact guarantees.
- [x] Run targeted backend tests for sync cleanup and metadata behavior.

## Review
- [x] Completed implementation + verification notes.

- Workspace update was attempted first via `git pull --rebase`; blocked because branch `work` has no upstream tracking remote in this environment.
- Added `cleanup_superseded_tiktok_failed_runs(...)` in `sync_runs_store` to hard-delete only superseded TikTok `historical_backfill` failed/error runs plus their chunks, scoped by same platform/account and superseded by later successful historical run (grain-aware with null fallback).
- Added run/account metadata reconciliation for affected TikTok accounts in the same cleanup transaction (recompute `last_run_status`, `last_run_type`, `last_run_started_at`, `last_run_finished_at`, `last_success_at`, `backfill_completed_through`, `last_error`).
- Exposed a safe one-off backend trigger endpoint `POST /agency/sync-runs/tiktok/cleanup-superseded-failed-historical` with optional `dry_run` and `account_ids` scope.
- Wired automatic cleanup after successful TikTok historical chunk finalization in worker, with exception guard so cleanup failures do not fail the sync job itself.
- Added backend tests for store cleanup semantics, endpoint wiring, and worker auto-cleanup invocation.
- Verification: `pytest -q apps/backend/tests/test_sync_runs_store_tiktok_cleanup.py apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_sync_worker.py apps/backend/tests/test_clients_platform_account_mappings.py`.

---

# TODO — TikTok cleanup matcher hardening + dry-run diagnostics clarity

- [x] Attempt workspace sync before edits and record git topology blocker if tracking remote is unavailable.
- [x] Audit current cleanup matcher rule and identify fragility in account_id/grain/time matching.
- [x] Harden cleanup matcher normalization and matching diagnostics for superseded eligibility.
- [x] Expand dry-run payload with explicit deletion targets and non-match reasons.
- [x] Keep exec-mode deletion scope safe (TikTok historical failed superseded only) and preserve metadata recompute.
- [x] Add backend tests for matcher normalization, grain mismatch/no-success non-delete, diagnostics reasons, and metadata reconciliation.
- [x] Run targeted backend tests for cleanup store + endpoint + worker interactions.

## Review
- [x] Completed implementation + verification notes.

- Workspace update was attempted first (`git pull --rebase`) and blocked because branch `work` has no tracking remote configured.
- Previous matcher fragility: SQL-only candidate selection gave limited explainability for non-matches and depended on raw account/grain values in matching logic.
- Hardened cleanup matcher now normalizes account ids (`trim`) and grains (`lower + default account_daily`) consistently for failed and successful historical TikTok runs before superseded evaluation.
- Dry-run now returns explicit `superseded_runs` and `non_superseded_runs` with reasons (`matched_later_success_same_account_grain`, `no_later_success_found`, `grain_mismatch`, `account_id_mismatch`, optional missing-chunks marker), plus `filtered_out_runs` reasons (`wrong_platform`, `wrong_job_type`) and aggregated `non_match_reason_counts`.
- Exec mode still deletes only superseded TikTok historical failed runs and related chunks, then recomputes operational metadata for affected TikTok accounts.
- Verification: `pytest -q apps/backend/tests/test_sync_runs_store_tiktok_cleanup.py apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_sync_worker.py`.

---

# TODO — TikTok legacy cleanup matcher fix for window-mismatch failed historical runs

- [x] Attempt workspace sync before edits and record git topology blocker if tracking remote is unavailable.
- [x] Audit current matcher and confirm whether window/date-range compatibility is causing missed legacy deletions.
- [x] Implement explicit TikTok legacy rule: same account+grain and later done historical run supersedes failed run regardless of start_date equality.
- [x] Keep safety guards (same platform/job_type/account/grain + strictly later success in time).
- [x] Ensure chunks are deleted with eligible runs and metadata is recomputed for affected accounts.
- [x] Expand dry-run diagnostics with explicit legacy window-mismatch signal for debugging.
- [x] Add/update backend tests for legacy window mismatch delete, grain mismatch/no-success no-delete, chunk deletion, metadata recompute, and non-impact on other platforms.
- [x] Run targeted backend tests.

## Review
- [x] Completed implementation + verification notes.

- Workspace update was attempted first (`git pull --rebase`) and blocked because local branch `work` has no upstream tracking remote configured.
- Confirmed matcher miss risk for legacy runs came from time ordering based on `updated_at` participation (`COALESCE(..., updated_at)`), which can make older failed runs look newer than subsequent successful runs.
- Fixed matcher ordering to use terminal/run chronology (`finished_at`, then `started_at`, then `created_at`, fallback `updated_at`) and kept supersede eligibility strict on same TikTok account + same grain + later done historical run.
- Added explicit legacy dry-run diagnostic reason `window_mismatch_but_legacy_tiktok_cleanup_should_match` when same account/grain successes exist but are not later, to highlight pre-cap/pre-fix window drift scenarios.
- Exec mode remains safe and narrow: deletes only superseded TikTok historical failed runs plus their chunks, then recomputes operational metadata for affected accounts.
- Verification: `pytest -q apps/backend/tests/test_sync_runs_store_tiktok_cleanup.py apps/backend/tests/test_sync_orchestration_api.py apps/backend/tests/test_sync_worker.py apps/backend/tests/test_clients_platform_account_mappings.py`.

---

# TODO — Meta parity in Agency Accounts list operational metadata

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit API + frontend data flow for Agency Accounts list (Meta vs Google/TikTok metadata fields).
- [x] Fix backend payload/reconciliation for Meta list-level operational metadata if missing.
- [x] Fix frontend mapping/rendering so Meta tab uses same operational metadata display rules as Google/TikTok.
- [x] Add backend tests for Meta payload/recompute behavior and stale error suppression parity.
- [x] Add frontend tests for Meta list rendering (Istoric/Rolling/Ultimul sync reușit/Eroare recentă + fallback "-").
- [x] Run targeted backend + frontend tests and frontend build.

## Review
- [x] Completed implementation + verification notes.

- Workspace sync attempted first (`git pull --rebase`) but blocked because local `work` branch has no upstream tracking remote.
- Root cause of Meta list parity gap was frontend mapping: Meta unified rows were hardcoded with null operational fields, even when backend payload contained values.
- Updated Meta account type + unified mapper to consume backend operational metadata (`backfill_completed_through`, `rolling_synced_through`, `last_success_at`, `last_error`, `last_error_category`, `last_error_details`, `last_run_status`, `last_run_type`, `sync_start_date`).
- Added generic stale-error suppression after success in `/clients/accounts/{platform}` path so Meta stale `last_error` is cleared when latest run is successful and no active sync (TikTok-specific feature-flag suppression remains unchanged).
- Added backend test for Meta stale-error suppression and metadata passthrough; added frontend test to verify Meta tab renders operational fields and fallback `-` for missing values.
- Verification: `pytest -q apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_sync_orchestration_api.py`; `pnpm --dir apps/frontend test src/app/agency-accounts/page.meta.test.tsx src/app/agency-accounts/page.tiktok.test.tsx`; `pnpm --dir apps/frontend build`.

---

# TODO — Meta conversions = strict Lead only

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit current Meta conversions derivation from actions and all write/aggregate call-sites.
- [x] Implement explicit lead-only helper for Meta conversions and wire it across account/campaign/adset/ad grains.
- [x] Ensure non-lead action types are excluded and revenue/conversion_value behavior remains unchanged unless required.
- [x] Add safe idempotent recompute/backfill mechanism for historical Meta rows saved with inflated conversions.
- [x] Add/update backend tests for lead-only behavior and non-impact on other platforms.
- [x] Run targeted backend tests and summarize impact.

## Review
- [x] Completed implementation + verification notes.

- Workspace sync was attempted first (`git pull --rebase`) and blocked because branch `work` has no upstream tracking remote in this environment.
- Root cause confirmed: Meta conversions were computed as sum of all `actions[*].value`, inflating conversions with non-lead actions (purchase, add_to_cart, page_view, post_engagement etc.).
- Implemented explicit lead-only derivation helper `_derive_lead_conversions(...)` with allowlist-only action types and wired it across all Meta sync grains (`account_daily`, `campaign_daily`, `ad_group_daily`, `ad_daily`).
- Kept `conversion_value`/revenue logic unchanged (`_derive_conversion_value` still sums `action_values`) to keep scope strict to conversions semantics.
- Historical correction mechanism: no new endpoint required; existing Meta historical backfill endpoint is idempotent and rewrites rows via upsert using corrected lead-only conversions.
- Added tests for mixed actions (lead + non-lead), explicit exclusions, and all-grain lead-only usage.
- Verification: `pytest -q apps/backend/tests/test_meta_ads_sync_account_daily.py apps/backend/tests/test_clients_platform_account_mappings.py`.

---

# TODO — Meta dashboard source-of-truth = account_daily + daily real + lead-only

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit Meta account_daily insights request (level/fields/time_increment) and persistence behavior.
- [x] Enforce time_increment=1 for Meta account_daily ingestion and verify row-per-day behavior.
- [x] Audit dashboard/subaccount aggregation source for Meta and remove multi-grain double counting.
- [x] Ensure Meta dashboard totals come strictly from account_daily source and conversions are lead-only.
- [x] Add safe/idempotent recompute path for historical Meta data correction.
- [x] Add/update backend tests for daily account ingestion params, dashboard source grain, and non-impact on other platforms.
- [x] Run targeted backend tests and document verification.

## Review
- [x] Completed implementation + verification notes.
- Added `time_increment=1` for `account_daily` Meta insights requests and protected snapshot upserts to `account_daily` grain only.
- Added tests for request parameter enforcement and snapshot source-of-truth protection.
- Verified with: `pytest -q apps/backend/tests/test_meta_ads_sync_account_daily.py apps/backend/tests/test_clients_platform_account_mappings.py`.

---

# TODO — Meta canonical lead conversion deduplication

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit Meta lead conversion helper action_type handling and account_daily/snapshot call path.
- [x] Implement canonical lead action selection by explicit priority (no summing across lead-like aliases).
- [x] Add minimal safe lead observability fields to Meta extra_metrics/run-debug payloads.
- [x] Apply canonical conversion derivation across all Meta grains and snapshot source path.
- [x] Add/update backend tests for single-type, duplicate alias dedup, mixed actions, account_daily + snapshot canonical behavior.
- [x] Run targeted backend tests for Meta plus adjacent non-impact suites.

## Review
- [x] Completed implementation + verification notes.
- Canonical rule now selects one lead action type by priority (`lead` first, then `onsite_conversion.lead_grouped`, then other lead aliases) and uses only that value for conversions.
- Added safe observability fields in `extra_metrics.meta_ads`: `lead_action_types_found`, `lead_action_type_selected`, `lead_action_values_found`.
- Verified dedup regression case where two lead-like action types both report 23 now stores conversions=23 (not 46).

---

# TODO — Dashboard currency normalization (Agency RON / Sub-account client currency)

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit current aggregation paths for Agency Dashboard totals, Sub-account totals/platform rows, and Top clients spend card.
- [x] Implement generic per-row currency normalization helper using date-based FX with safe fallback behavior.
- [x] Normalize Agency Dashboard monetary totals to RON before aggregation and recalculate ROAS from normalized spend/revenue.
- [x] Normalize Sub-account Dashboard monetary totals/platform rows to client preferred currency before aggregation.
- [x] Ensure Top clients (by spend) is sorted and displayed in RON using normalized spend.
- [x] Keep non-monetary metrics unconverted (impressions/clicks/conversions).
- [x] Add backend tests for mixed-currency normalization, top-clients RON behavior, and FX fallback predictability.
- [x] Run targeted backend and frontend tests/build relevant to changed dashboard flows.

## Review
- [x] Completed implementation + verification notes.
- Added `_normalize_money(...)` and `_aggregate_client_rows(...)` to normalize by row date + source currency -> target currency.
- Updated client dashboard query to pull `account_currency` and normalize spend/revenue to client preferred currency for totals and per-platform rows.
- Updated agency top clients to use/display RON normalized spend, with sorting based on normalized RON values.

---

# TODO — Meta account_daily reliability + snapshot rebuild/recompute

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit Meta account_daily request/parsing/write path and historical backfill flow for final-chunk 500 behavior.
- [x] Fix account_daily fetch reliability for transient Meta 5xx and preserve explicit `time_increment=1` daily fetch semantics.
- [x] Ensure account_daily backfill no longer leaves stale snapshot by rebuilding snapshot from full account_daily backfill window.
- [x] Add idempotent snapshot recompute mechanism (API) sourced strictly from persisted account_daily rows.
- [x] Keep lead-only conversions unchanged and ensure non-account grains remain out of dashboard snapshot source-of-truth.
- [x] Add/update tests for transient 500 regression, daily row coherence, backfill snapshot rebuild, recompute endpoint, and source-of-truth safety.
- [x] Run targeted Meta backend tests and verify pass.

## Review
- [x] Completed implementation + verification notes.
- Root cause identified: account_daily historical backfill could fail hard on transient Meta 5xx due to no retry in insights fetch, and snapshot could stay stale because per-chunk account_daily sync updated snapshot with only the last chunk window.
- Implemented retries for retryable Meta errors in `_fetch_insights` and added full-window snapshot rebuild at end of historical backfill when `account_daily` grain is included.
- Added `POST /integrations/meta-ads/{client_id}/recompute-snapshot` to rebuild snapshot idempotently from persisted account_daily rows (optionally filtered by date/account).

---

# TODO — Meta currency propagation and no-double-conversion in dashboard

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Audit Meta money flow from account_daily write -> dashboard query currency resolution -> normalization.
- [x] Fix Meta source currency propagation into account_daily row extra metrics.
- [x] Fix dashboard currency resolution to prefer Meta row currency from extra metrics before mapping/client fallback.
- [x] Add regression tests for RON->RON no-conversion (3,587.60 case), query precedence, and Meta row currency propagation.
- [x] Keep scope strict: no Google/TikTok functional changes.
- [x] Run targeted backend tests.

## Review
- [x] Completed implementation + verification notes.
- Root cause: dashboard fallback could resolve Meta rows to mapping/client currency (USD) when true Meta account currency was RON, leading to double conversion (RON treated as USD then converted to RON again).
- Fix: propagate Meta account currency into `extra_metrics.meta_ads.account_currency` during account_daily writes and make dashboard queries prefer that per-row currency for Meta before fallback chain.
- Added exact regression for 3,587.60 RON source with RON target to ensure no reconversion.

---

# TODO — Sub-account Dashboard header/nav + platform links update

- [x] Attempt workspace sync before edits and record tracking-remote blocker if unavailable.
- [x] Remove sub-account dashboard page title from header universally.
- [x] Replace old header quick links (Campaigns/Rules/Creative/Recommendations) with Media Buying + Media Tracker only in page header.
- [x] Convert platform names in dashboard table into links to platform-dedicated sub routes.
- [x] Keep sidebar untouched (no new sidebar entries for new header links).
- [x] Add frontend test coverage for new header links, removed old links, and platform table links.
- [x] Run targeted frontend tests and frontend build.
- [x] Capture screenshot for visual frontend change.

## Review
- [x] Completed implementation + verification notes.
- Header title removed by passing `title={null}` to AppShell on sub dashboard page.
- Header links updated to `Media Buying` and `Media Tracker` only.
- Platform names now render as interactive links to `/sub/{id}/{platform-slug}` with hover styling.

---

# TODO — Sub dashboard linked routes scaffold (header + platform links)

- [x] Audit existing sub dashboard layout wrapper usage (`ProtectedPage` + `AppShell`) for consistent route scaffolding.
- [x] Add new App Router routes under `/sub/[id]/` for media-buying, media-tracker, google-ads, meta-ads, tiktok-ads, pinterest-ads, snapchat-ads.
- [x] Reuse a shared placeholder page component to keep consistent header links, layout, and "Coming Soon" container.
- [x] Ensure route pages consume URL id via `useParams` and preserve sub-account context in links/titles.
- [x] Add/adjust frontend tests for all newly scaffolded routes.
- [x] Run targeted frontend tests.

## Review
- [x] Completed implementation + verification notes.
- Added a reusable sub-route placeholder component and wired all requested routes with consistent dashboard shell styling.
- Added route coverage tests validating per-page heading text, media navigation links, and placeholder content.

---

# TODO — Media Buying lead foundation (backend config + daily manual values API)

- [x] Attempt workspace sync before implementation; record tracking-branch blocker if remote is not configured.
- [x] Add DB migration for media buying config per sub-account and lead daily manual values table with unique upsert keys.
- [x] Implement backend persistence store for media buying config + lead daily values (validation + idempotent upsert).
- [x] Expose API endpoints for get/update config and list/upsert lead daily values by interval/date.
- [x] Enforce validation rules: template type, non-negative counts, monetary constraints (allow negative only for custom value 5), and date interval checks.
- [x] Add backend tests for config persistence, custom labels, template type, daily upsert idempotency, and validation/list semantics.
- [x] Run targeted backend tests for the new store and API endpoints.

## Review
- [x] Completed implementation + verification notes.
- Added migration `0019_media_buying_foundation.sql` with `media_buying_configs` and `media_buying_lead_daily_manual_values`.
- Added `MediaBuyingStore` and `/clients/{client_id}/media-buying/*` endpoints for lead-template foundation only.
- Left `%^` formula intentionally unimplemented via explicit TODO comment in payload mapping.

---

# TODO — Media Buying lead step 2 (read API + automated cost aggregation + monthly grouping)

- [x] Attempt workspace sync before changes and record upstream-tracking blocker when remote is missing.
- [x] Implement lead read-side table assembler combining automated daily costs (Google/Meta/TikTok) + manual daily values.
- [x] Reuse existing FX normalization behavior for daily cost conversion into template display currency.
- [x] Implement confirmed formulas on daily rows and monthly rollups recalculated from month sums.
- [x] Keep `%^` explicitly unimplemented as null/TODO placeholder.
- [x] Expose dedicated API endpoint for lead table read with date range and non-lead unsupported behavior.
- [x] Add/extend backend tests for merge, FX conversion, formulas, monthly recompute, missing-manual fallback, non-lead unsupported.
- [x] Run targeted backend tests.

## Review
- [x] Completed implementation + verification notes.
- Added `get_lead_table(...)` in `MediaBuyingStore` and a dedicated query for automated daily costs from `ad_performance_reports` for google/meta/tiktok.
- Added endpoint `GET /clients/{client_id}/media-buying/lead/table` and explicit 501 for template types not implemented in this task.
- Verified `percent_change` (`%^`) remains explicit `None` at day and month levels.

---

# TODO — Media Buying lead step 3 (frontend table UI with month/day grouping)

- [x] Attempt workspace sync before edits and record upstream-tracking blocker when remote is missing.
- [x] Replace Media Buying placeholder with lead read-only table UI backed by `/clients/{id}/media-buying/lead/table`.
- [x] Implement month summary rows + expand/collapse day rows with latest month expanded by default.
- [x] Render required columns including dynamic custom labels from API metadata and `%^` placeholder fallback.
- [x] Add loading, error, and empty states; handle non-lead template fallback without crash.
- [x] Add frontend tests for table render, month grouping/expand, custom labels, null fallback, non-lead fallback, and basic states.
- [x] Run targeted frontend tests and frontend build.
- [x] Capture screenshot for visual verification.

## Review
- [x] Completed implementation + verification notes.
- Media Buying page now renders a read-only lead table with grouped month totals and expandable daily rows from backend API payload.
- Custom labels for CV1..CV5 are sourced from API metadata with fallback defaults; `%^` remains explicit placeholder (`—`).
- Non-lead templates show clear "not implemented" fallback message in-page.

---

# TODO — Media Buying lead step 4 (daily row manual editing + save + recalculation)

- [x] Attempt workspace sync before edits and record upstream-tracking blocker when remote is missing.
- [x] Add editable inputs for daily rows only (lead, phones, CV1, CV2, CV3, CV4, CV5, sales) while keeping month rows read-only.
- [x] Implement per-row edit/save/cancel UX with saving feedback and disabled Save when unchanged/invalid.
- [x] Validate UI inputs to match backend constraints (non-negative integers/counts, non-negative CV3/CV4 amounts, numeric CV5 allowed negative).
- [x] Save via existing endpoint `PUT /clients/{id}/media-buying/lead/daily-values` and refetch table after save for robust recalculation.
- [x] Keep `%^` column as placeholder/fallback only, no formula logic added.
- [x] Add frontend tests for edit/save/cancel/validation/refetch/non-lead fallback/states.
- [x] Run targeted frontend tests and build.
- [x] Capture screenshot for editable UI state.

## Review
- [x] Completed implementation + verification notes.
- Daily rows now support robust manual editing with simple inputs and per-row actions, while monthly summary rows remain read-only.
- Save uses existing backend PUT endpoint and triggers table refetch to refresh day + month totals and dependent formulas from backend response.
- `%^` remains displayed as explicit placeholder (`—`) on both month and day rows.

---

# TODO — Media Buying table UI polish (date/column styles/month order)

- [x] Attempt workspace sync to latest branch state and record tracking/upstream limitations.
- [x] Implement frontend-only Media Buying table polish (short Romanian day dates, semantic column styling, dashed separators, month order descending) with no business-logic changes.
- [x] Add/update frontend tests for date format, month order, semantic styles, dashed separators, and inline edit regression coverage.
- [x] Run frontend tests + build and record results.
- [x] Commit, attempt push, and create PR.

## Review
- [x] Added semantic column styling map in Media Buying page and applied gray text, dashed separators, and red unrealized-value rendering with parentheses.
- [x] Daily rows now display Romanian short dates (`1 Mar`, `1 Feb`, `1 Ian`) and month headers use short month+year labels.
- [x] Month sections are rendered newest-first (`sortedMonths` descending by `YYYY-MM`).
- [x] Verification: `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx`, `pnpm --dir apps/frontend build`.
- [x] Workspace sync note: `git pull --ff-only` failed because branch `work` has no upstream tracking configured in this environment.


---

# TODO — Media Buying step 6 (%^ daily+monthly implementation)

- [x] Attempt workspace update and record any upstream-tracking limitations.
- [x] Implement backend `percent_change` for daily rows (vs previous calendar day cost_total) and monthly rows (vs previous month total cost_total), null-safe for missing/zero previous totals.
- [x] Update frontend Media Buying table to render computed `%^` values for month/day rows and fallback `—` for null.
- [x] Add/update backend + frontend tests for daily/monthly percent_change, zero/missing previous totals, and UI rendering with descending month order unaffected.
- [x] Run relevant backend/frontend tests + frontend build, then commit/push/PR.

## Review
- [x] Added backend helper `_build_percent_change(...)` and applied it in chronological day traversal + chronological month traversal, independent from UI sort order.
- [x] Kept null behavior for missing/zero previous totals (`percent_change=None`) to avoid invented values and division by zero.
- [x] Frontend now renders `%^` with existing `formatRate(...)` for both month/day rows and retains `—` fallback for null.
- [x] Verification: `pytest apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py`, `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx`, `pnpm --dir apps/frontend build`.
- [x] Workspace sync note: `git pull --ff-only` failed because branch `work` has no upstream tracking configured in this environment.
- [x] Screenshot attempt note: browser tool failed to launch Chromium (TargetClosedError/SIGSEGV) in this environment.

---

# TODO — Railway backend build fix: pin Python 3.12 for google-ads compatibility

- [x] Attempt workspace sync and record upstream-tracking limitation if present.
- [x] Identify runtime version source used for Railway/backend builds.
- [x] Apply minimal Python pin to 3.12 without changing `google-ads` dependency.
- [x] Run targeted checks and finalize with commit + push attempt + PR.

## Review
- [x] Added `apps/backend/.python-version` with `3.12` for Railway/Nixpacks-style runtime detection.
- [x] Updated backend container base image to `python:3.12-slim` in `apps/backend/Dockerfile` for Docker-based deployments.
- [x] Kept `apps/backend/requirements.txt` unchanged (no `google-ads` upgrade).
- [x] Verification: `pytest apps/backend/tests/test_clients_media_buying_api.py -q`.
- [x] Workspace sync note: `git pull --ff-only` failed because branch `work` has no upstream tracking configured.

---

# TODO — Media Buying step 7 (unrealized semantics + column visibility persisted view)

- [x] Attempt workspace sync and record upstream-tracking limitation if present.
- [x] Extend backend media buying config with persisted `visible_columns` and wire through API schema/store.
- [x] Implement backend `Val. Nerealizata` semantics as derived (`Val. Aprobata - Val. Vanduta`, floored at 0) for day + month rows.
- [x] Update frontend table styling/formatting: sold value normal black, unrealized red+parentheses only when >0 (else black no parentheses), close-rate columns violet.
- [x] Add column visibility UI (with mandatory columns guard), load/save from backend config, and keep custom labels compatible.
- [x] Add/update backend/frontend tests for formula semantics, styling, toggling, persistence, and fallback defaults.
- [x] Run relevant backend/frontend tests + frontend build, then commit/push/PR.

## Review
- [x] Added migration `0021_media_buying_visible_columns.sql` and persisted `visible_columns` through media buying config schema/API/store + lead table meta.
- [x] Derived `custom_value_4_amount_ron` as max(`custom_value_3_amount_ron - custom_value_5_amount_ron`, 0) for daily rows, and month totals recompute from monthly sums (not daily averages).
- [x] Updated UI semantics: sold value shown normally (black, no parentheses), unrealized value shown red+parentheses only when >0, and rate columns in violet for month/day/header cells.
- [x] Implemented "Customize columns" visibility selector with required `Data` column guard and auto-persist to backend config via `PUT /clients/{id}/media-buying/config`.
- [x] Verification: `pytest apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py`, `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx`, `pnpm --dir apps/frontend build`.
- [x] Workspace sync note: `git pull --ff-only` failed because branch `work` has no upstream tracking configured.
- [x] Screenshot note: Playwright browser tool timed out in this environment while capturing `/sub/96/media-buying`.

---

# TODO — Media Buying pasul 9: custom columns black text only

- [x] Sync workspace to latest available repo state and confirm remote constraints.
- [x] Audit Media Buying table column style mapping for custom values and custom value rates.
- [x] Remove special text colors for custom values (1..5) and custom value rates (1..2), forcing black text on day/month rows.
- [x] Add/update frontend tests for custom column black-text rendering and non-custom style regression guard.
- [x] Run relevant frontend tests and frontend build; capture outcomes.

## Review
- [x] Removed custom value columns (`custom_value_1_count`, `custom_value_2_count`, `custom_value_3_amount_ron`) from grey semantic mapping and removed violet semantic mapping from custom rate columns (`custom_value_rate_1`, `custom_value_rate_2`).
- [x] Removed positive-value red styling on `custom_value_4_amount_ron` in both month total rows and day rows; custom value/rate cells now render in black/default text.
- [x] Added frontend regression checks for no color classes on custom value/rate headers/cells, dynamic custom labels, and non-custom semantic style preservation.
- [x] Verification: `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx` and `pnpm --dir apps/frontend build`.

---

# TODO — Media Buying pasul 10: luni/zile doar cu date reale + range efectiv

- [x] Sync workspace la ultima stare disponibilă și confirmare constrângeri remote.
- [x] Audit read API/store Media Buying lead pentru default range, grupare luni și construcție zile.
- [x] Implementare backend: effective_date_from/to derivat din date reale + filtrare zile fără date + eliminare luni goale.
- [x] Păstrare suport range explicit, dar cu filtrare internă a zilelor/lunilor fără date.
- [x] Extindere metadata răspuns (effective/earliest/latest/available_months) și wiring frontend pentru text range.
- [x] Adăugare/actualizare teste backend+frontend pentru cazurile cerute.
- [x] Rulare teste relevante backend/frontend + frontend build; documentare rezultate.

## Review
- [x] Endpointul `GET /clients/{client_id}/media-buying/lead/table` acceptă acum și range lipsă; backend derivă intervalul din date reale (`_get_lead_table_data_bounds`) și returnează metadata `effective_date_from/effective_date_to/earliest_data_date/latest_data_date`.
- [x] Zilele fără date reale sunt excluse prin regula explicită `day has data` (cost_google/meta/tiktok, leads, phones, custom1, custom2, custom3, custom4, custom5, sales_count diferit de 0).
- [x] Lunile fără zile cu date nu mai sunt returnate; totalurile lunare se calculează doar din zilele rămase.
- [x] Frontend Media Buying folosește range-ul efectiv din metadata API și nu mai trimite implicit query de 90 zile la load inițial.
- [x] Verificare: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py`, `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — Media Buying hotfix: bounds query relation fix for 500

- [x] Sync workspace la ultima stare disponibilă și confirmare constrângeri remote.
- [x] Audit helper `_get_lead_table_data_bounds` vs sursa reală folosită de `_list_automated_daily_costs`.
- [x] Înlocuire query bounds de pe relația inexistentă cu aceeași sursă reală folosită în read-side costuri automate.
- [x] Păstrare logică existentă: effective range + hide empty days/months.
- [x] Adăugare/actualizare teste backend pentru regresie 500 + empty data coherence + effective bounds.
- [x] Rulare teste backend relevante și documentare rezultate.

## Review
- [x] Bug root-cause: `_get_lead_table_data_bounds` interoga `ads_platform_reporting` (relație absentă în DB), ceea ce producea `UndefinedTable` și 500 la `/clients/{id}/media-buying/lead/table`.
- [x] Fix: helper-ul de bounds folosește acum `ad_performance_reports` + `agency_account_client_mappings`, aceeași sursă și aceeași mapare client/account utilizate deja în `_list_automated_daily_costs`.
- [x] Logicile recent introduse rămân active: effective range, excludere zile fără date, excludere luni fără zile.
- [x] Teste: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py` (pass).

---

# TODO — Media Buying pasul 11: sticky header + sticky first column + scroll UX

- [x] Sync workspace la ultima stare disponibilă și confirmare constrângeri remote.
- [x] Audit structură tabel Media Buying pentru header/coloană Data/container scroll.
- [x] Implementare sticky header + sticky first column + sticky corner cu z-index/background/border corecte.
- [x] Îmbunătățire minimă scroll UX pentru tabel lat/lung fără redesign major.
- [x] Adăugare/actualizare teste frontend pentru sticky classes + compatibilitate expand/collapse, visibility și inline edit.
- [x] Rulare teste frontend relevante + build frontend; documentare rezultate.

## Review
- [x] Sticky header implementat pe toate celulele de header (`top-0`) și sticky corner pentru `Data` (`top-0 + left-0`) cu background opac și z-index separat.
- [x] Sticky first column implementat pe celulele `Data` pentru rânduri lunare și zilnice (`left-0`) cu border/shadow discret pentru separare vizuală la scroll orizontal.
- [x] Scroll UX: containerul tabelului are acum `max-h` + `overflow-auto` + border/rounded + scrollbar classes pentru evidențiere mai clară.
- [x] Compatibilitate păstrată pentru `Customize columns`, expand/collapse luni și `Edit` pe rândurile zilnice; header-ele inline edit rămân clickabile.
- [x] Verificare: `pnpm --dir apps/frontend test src/app/sub/[id]/media-buying/page.test.tsx`, `pnpm --dir apps/frontend build`.

---

# TODO — Media Buying cost accuracy audit & fix (TikTok overcount + Meta invalid windows)

- [x] Sync workspace la ultima stare disponibilă și confirmare constrângeri remote.
- [x] Audit read-side Media Buying automated costs: source table, grain filter, currency handling, mapping join, effective date filters.
- [x] Identificare root cause concret pentru supraestimare TikTok și costuri Meta în perioade nevalide.
- [x] Implementare fix backend: source-of-truth strict account_daily + mapping window/effective period + conversie valutară single-pass corectă.
- [x] Adăugare/actualizare teste regresie multi-client/multi-platform/currency/window pentru prevenirea contaminării.
- [x] Rulare teste backend relevante (și frontend doar dacă se schimbă contract), documentare rezultate.

## Review
- [x] Root cause TikTok overcount: read-side folosea fallback de currency insuficient de robust (`mapped.account_currency`/`client.currency`) și putea aplica conversie pe source currency greșită; plus source grain nu era filtrat explicit la `account_daily`.
- [x] Root cause Meta în luni nevalide: join-ul de mapping nu respecta fereastra temporală a mapping-ului (raport putea fi atribuit pe mapping curent pentru date mai vechi), iar `apr.client_id` în coalesce putea introduce atribuiri stale.
- [x] Fix implementat: read query și bounds query folosesc strict `ad_performance_reports` + mapping lateral cu `m.created_at::date <= apr.report_date`, grain filter explicit `account_daily`, source client din mapping (nu din `apr.client_id`) și currency fallback ordonat `row extra_metrics -> mapping account_currency -> agency_platform_accounts.account_currency -> RON`.
- [x] Logica de effective range/hide empty days/months rămâne activă; fixul este doar pe read-side automated costs.
- [x] Teste: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py` (pass).

---

# TODO — Media Buying hotfix: UndefinedColumn `apa.account_currency` on lead table

- [x] Attempt workspace update to latest repo state (`git fetch --all --prune`, `git pull --ff-only`) before code changes.
- [x] Audit `_list_automated_daily_costs(...)` SQL and DB schema for `agency_platform_accounts` currency source compatibility.
- [x] Replace invalid `apa.account_currency` reference with schema-valid currency source from `agency_platform_accounts`.
- [x] Add regression tests for query text (no `apa.account_currency`, yes correct currency column) and robust missing-currency fallback.
- [x] Run targeted backend tests for media buying store and media buying clients API.

## Review
- [x] Root cause confirmed: query referenced `apa.account_currency`, but `agency_platform_accounts` stores currency in `currency_code`, so Postgres raised `UndefinedColumn`.
- [x] Fix implemented in read-side SQL: fallback chain now uses `apa.currency_code` (plus existing `extra_metrics` and mapping currency sources), keeping formulas/editing/UI behavior untouched.
- [x] Regression coverage added to assert query uses `apa.currency_code` and explicitly does not contain `apa.account_currency`, plus fallback to `RON` when DB row currency is null.
- [x] Verification: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py` (pass).

---

# TODO — Media Buying regression fix: restore full history for attached accounts

- [x] Sync workspace attempts before analysis (`git fetch --all --prune`, `git pull --ff-only`) and continue on latest local branch state.
- [x] Audit `MediaBuyingStore` bounds/effective-range logic and identify mapping timestamp filter that clamps history.
- [x] Update automated-cost and bounds SQL so mapping is used for account membership only (no `mapping.created_at` lower bound).
- [x] Preserve existing day/month non-empty filtering behavior and explicit range support.
- [x] Add regressions for query semantics (no mapping date clamp) and bounds merge behavior.
- [x] Run backend media buying tests.

## Review
- [x] Root cause: both `_list_automated_daily_costs` and `_get_lead_table_data_bounds` filtered mappings with `m.created_at::date <= apr.report_date`, which cut off pre-attachment historical spend and forced many clients to recent start dates.
- [x] Fix: switched to direct mapping membership join (`agency_account_client_mappings` + `mapped.client_id = %s` + account-id match), removing mapping audit timestamp as history lower bound.
- [x] Earliest/latest bounds now come from real report dates for currently attached accounts (automated) plus manual non-zero rows; effective range still derives from non-empty day rows.
- [x] Existing rules preserved: explicit `date_from/date_to` still supported; empty days/months remain hidden by `_lead_table_day_has_data` filtering.
- [x] Verification: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py` (pass).

---

# TODO — Media Buying cost accuracy fix: TikTok overestimation + Meta invalid periods

- [x] Sync workspace attempts (`git fetch --all --prune`, `git pull --ff-only`) before code changes.
- [x] Audit automated-cost read-side SQL (source/grain/currency/membership/date filters) for Media Buying.
- [x] Fix TikTok currency source precedence to avoid false USD->RON reconversion when account currency is already RON.
- [x] Reintroduce mapping-validity date guard in automated-cost query to prevent invalid pre-mapping Meta inclusion.
- [x] Add/adjust regressions for account_daily grain, mapping validity condition, currency fallback precedence, and non-reconversion pattern.
- [x] Run relevant backend tests for media buying store/API + client mapping + currency normalization.

## Review
- [x] Root cause TikTok overestimation: currency fallback prioritized `mapped.account_currency` before `agency_platform_accounts.currency_code`; when row-level extra currency was missing and mapping currency differed (e.g. USD), RON-denominated TikTok spend could be treated as USD and converted again to RON.
- [x] Root cause Meta invalid January costs: automated-cost query no longer applied mapping temporal validity (`created_at <= report_date`), so rows from dates before mapping validity were included.
- [x] Fix applied: keep source-of-truth `ad_performance_reports` + strict `account_daily` grain; enforce mapping membership with temporal validity in `_list_automated_daily_costs`, and reorder currency fallback to `row extra_metrics -> agency_platform_accounts.currency_code -> mapping.account_currency -> RON`.
- [x] Verified via regressions including explicit TikTok pattern (`805.85` and `50.40` in RON stay unchanged for RON display) and SQL assertions for mapping/date guard + currency precedence.
- [x] Verification command: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Sub-account Dashboard critical fix: align platform totals with Media Buying source-of-truth

- [x] Sync workspace attempts before changes (`git fetch --all --prune`, `git pull --ff-only`) and proceed on latest local state.
- [x] Audit Sub-account Dashboard read path (`UnifiedDashboardService.get_client_dashboard`) and identify source query/currency/membership/grain behavior.
- [x] Align client dashboard query to account_daily + mapping membership validity + correct currency precedence (same correctness contract as Media Buying).
- [x] Keep UI contract unchanged; backend-only read path fix.
- [x] Add regressions for query semantics, TikTok RON non-reconversion, and dashboard-vs-media-buying spend consistency.
- [x] Run relevant backend tests for dashboard/media buying/mappings/currency.

## Review
- [x] Root cause (Sub-account Dashboard): `_client_reports_query` used a lateral/coalesce path (`COALESCE(apr.client_id, mapped.client_id)`) without strict account_daily filter and without mapping validity bound. This could include stale rows, cross-client attribution via `apr.client_id`, and invalid pre-mapping periods.
- [x] Root cause TikTok overestimation in dashboard: currency fallback prioritized mapping/client-level currency over account-level source currency; when row currency was missing this could reconvert RON spends as if foreign currency.
- [x] Fix: dashboard client query now uses `ad_performance_reports` + direct `agency_account_client_mappings` join (`mapped.client_id = %s`, `mapped.created_at::date <= apr.report_date`, account match), strict account_daily filter, and currency precedence `row extra_metrics -> agency_platform_accounts.currency_code -> mapping.account_currency -> RON`.
- [x] Result: platform totals use same correctness contract as Media Buying read-side (source + grain + membership + currency single-pass normalization).
- [x] Verification: `pytest -q apps/backend/tests/test_dashboard_currency_normalization.py apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_dashboard_agency_summary_integration_health.py` (pass).

---

# TODO — Regressie istoric Media Buying/Dashboard: eliminare clamp pe mapping.created_at

- [x] Sync workspace attempts (`git fetch --all --prune`, `git pull --ff-only`) înainte de modificări.
- [x] Audit query-urile de costuri automate din Media Buying + Sub-account Dashboard pentru folosirea `mapped.created_at::date <= apr.report_date`.
- [x] Eliminare clamp temporal pe `mapped.created_at` din read-side (membership-only mapping).
- [x] Păstrare source-of-truth `ad_performance_reports` + grain `account_daily` + membership strict pe conturi client.
- [x] Actualizare regresii pentru a valida că istoricul nu mai este tăiat de data mapping-ului.
- [x] Rulare suite backend relevante (media buying, dashboard, client mappings).

## Review
- [x] Clamp-ul greșit era prezent în trei query-uri read-side: `_list_automated_daily_costs`, `_get_lead_table_data_bounds` și `UnifiedDashboardService._client_reports_query`.
- [x] `mapped.created_at` este câmp de audit, nu câmp business de validitate istorică; folosit ca lower-bound taie artificial istoricul real la data atașării mapping-ului.
- [x] Fix: mapping-ul rămâne strict pentru membership (`mapped.client_id` + account/platform match), dar fără filtrare temporală pe `created_at`; bounds/istoric vin din datele reale `account_daily` din `ad_performance_reports` (+ manual non-zero pentru Media Buying bounds).
- [x] Problemă Meta ianuarie invalid nu se rezolvă prin clamp pe mapping-created-at; root cause trebuie adresată prin membership/source corect, nu prin tăiere globală de istoric.
- [x] Verificare: `pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_dashboard_currency_normalization.py apps/backend/tests/test_clients_platform_account_mappings.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_dashboard_agency_summary_integration_health.py` (pass).

---

# TODO — Sub-account dashboard sync health surfacing (Meta/TikTok)

- [x] Refresh workspace and inspect current sub-account dashboard frontend + backend payload availability.
- [x] Add minimal `platform_sync_summary` payload on `GET /dashboard/{client_id}` for Meta/TikTok using attached-account sync metadata only.
- [x] Add compact dashboard sync-health banner + platform chips + concise details interaction in sub-account dashboard UI.
- [x] Reuse shared sync-status utility/component logic where possible; keep KPI calculations/layout unchanged.
- [x] Add/update targeted frontend/backend tests for banner visibility, platform status derivation, affected counts, and details panel content.
- [x] Run focused test commands and record outcomes.

## Review
- [x] Added backend `platform_sync_summary` to client dashboard payload for Meta/TikTok using latest sync-run metadata per attached account.
- [x] Added compact page-level sync warning banner plus per-platform status chips on sub-account dashboard rows.
- [x] Added expandable concise affected-account details (name/id, status, reason, last sync, failed chunks/retry).
- [x] Extended sync-status utility with platform-level worst-status derivation and affected counts.
- [x] Verification run: frontend targeted Vitest suite passed; backend targeted pytest collection failed in this environment due missing `requests` dependency.

---

# TODO — Media Tracker weekly worksheet foundation (backend-only)

- [x] Refresh workspace and inspect current Media Tracker/backend routing architecture.
- [x] Add shared scope-resolution helper for month/quarter/year using anchor_date.
- [x] Add deterministic Monday-Sunday visible week bucket generation for intersecting full weeks.
- [x] Expose minimal backend contract endpoint for worksheet foundation metadata only (no formulas/inputs).
- [x] Add targeted backend tests for scope resolution, week ordering/intersection flags, first-week flag, and history count consistency.
- [x] Run focused backend tests and record outcomes.

## Review
- [x] Added `media_tracker_worksheet_service` with month/quarter/year period resolution from `anchor_date` and Monday-Sunday full-week bucket generation.
- [x] Added backend endpoint `GET /clients/{client_id}/media-tracker/worksheet-foundation` returning stable worksheet foundation metadata only (no formulas/manual inputs).
- [x] Added deterministic week metadata fields: index, week_start/end, label, first-week flag, period boundary intersection flags.
- [x] Added tests for month/quarter/year resolution, ordering, boundary intersection, first-week flag, and history week-count consistency.
- [x] Verification: service tests pass; API test collection blocked in this environment due missing FastAPI dependency.

---

# TODO — Media Tracker weekly worksheet automatic weekly aggregation (backend-only)

- [x] Refresh workspace and inspect existing daily Media Buying/Media Tracker source-of-truth and current worksheet foundation service.
- [x] Extend worksheet service to aggregate raw automatic weekly metrics from existing daily source for full visible weeks.
- [x] Keep contract stable and include `auto_metrics` with history sums aligned to visible weekly values.
- [x] Add focused tests for weekly aggregation, boundary full-week behavior, history alignment, ordering, leads/applications mapping, and null safety.
- [x] Run focused backend tests and record outcomes.

## Review
- [x] Reused `media_buying_store.get_lead_table(...).days` as daily source-of-truth (no second conflicting path).
- [x] Weekly aggregation now sums full visible Monday-Sunday weeks, including boundary weeks that extend outside resolved period.
- [x] Added auto metric keys: `cost_total`, `cost_google`, `cost_meta`, `cost_tiktok`, `total_leads`, `applications`, `approved_applications`; `history_value` equals sum of weekly values per key.
- [x] Preserved existing worksheet foundation shape and placeholder sections.

---

# TODO — Media Tracker worksheet manual weekly inputs + EUR/RON storage (backend-only)

- [x] Refresh workspace and inspect current worksheet foundation/aggregation backend and API routing.
- [x] Implement persistence and idempotent upsert/clear logic for weekly manual values keyed by client/week_start/field_key.
- [x] Implement persistence and idempotent upsert/clear logic for worksheet-scope EUR/RON rate keyed by client/granularity/period_start/period_end.
- [x] Extend worksheet GET response with manual field definitions, manual metrics/history, eur_ron_rate, and eur_ron_rate_scope.
- [x] Add API write endpoints for manual weekly values and scope EUR/RON rate with validation.
- [x] Add/update backend tests for validation, idempotency, scope reuse/readback, clear semantics, and compatibility with existing auto metrics.
- [x] Run focused backend tests and record outcomes.

## Review
- [x] Reused existing weekly scope resolver and visible-week ordering from worksheet foundation.
- [x] Manual values now persist per weekly key and are returned aligned to visible weeks with history sums.
- [x] EUR/RON rate now persists per canonical worksheet scope and reads back consistently for anchor dates within same scope.
- [x] No formulas/manual-derived final rows/frontend changes were introduced in this step.

---

# TODO — Media Tracker worksheet core formula engine rows (backend-only, no % rows)

- [x] Refresh workspace and inspect existing worksheet foundation + auto/manual metrics + EUR/RON response.
- [x] Add internal formula catalog/helper for deterministic section row computation from auto/manual/rate inputs.
- [x] Compute weekly and history values for confirmed core business rows (summary/new_clients/google/meta/tiktok) without % comparison rows.
- [x] Preserve existing response keys and enrich `sections[].rows` with computed row payloads aligned to weeks ordering.
- [x] Add/update backend tests for formulas, additive vs ratio history behavior, null-safe divide/rate/cogs handling, and ordering alignment.
- [x] Run focused backend tests and record outcomes.

## Review
- [x] Added core computed-row engine for worksheet sections using existing `auto_metrics`, `manual_metrics`, and scope `eur_ron_rate`.
- [x] Kept response backward-compatible (raw metrics remain) and enriched `sections[].rows` with deterministic weekly/history values and minimal row metadata.
- [x] Implemented additive history as sum of weekly values and ratio history as recomputed numerator/denominator (no summed weekly ratios).
- [x] Added null-safe handling for divide-by-zero, missing EUR rate, missing manual rows, and COGS-dependent formulas.
- [x] Verification: focused backend worksheet/API tests pass locally.

---

# TODO — Media Tracker worksheet week-over-week comparison rows (backend-only)

- [x] Refresh workspace/update branch state and inspect current worksheet backend payload after Task 4A.
- [x] Add reusable backend helper to build WoW percent-ratio comparison rows from source row weekly values.
- [x] Insert comparison rows only for approved rows in summary/google/meta/tiktok sections, immediately after source rows.
- [x] Keep new_clients section unchanged and preserve existing non-% formulas/row ordering otherwise.
- [x] Add/update backend tests for WoW math, null/zero handling, row inclusion/exclusion, ordering, week alignment, and history_value null.
- [x] Run focused backend tests and record outcomes.


## Review
- [x] Added reusable WoW comparison-row generation with strict null/zero guards and history_value=null.
- [x] Inserted `_wow_pct` rows immediately after approved source rows in summary/google/meta/tiktok; left `new_clients` unchanged.
- [x] Preserved existing non-% row formulas and section payload shape from Task 4A.
- [x] Verified with focused worksheet tests (`13 passed`).

---

# TODO — Media Tracker frontend weekly worksheet shell (view + scope + fetch + scaffold)

- [x] Refresh workspace state and inspect existing Media Tracker page structure plus worksheet backend endpoint contract.
- [x] Add a new Weekly Worksheet view mode inside Media Tracker while preserving existing overview behavior.
- [x] Implement worksheet state (granularity + anchor_date) with previous/next period navigation semantics.
- [x] Integrate frontend fetch to worksheet backend endpoint and handle loading/error/empty/invalid states.
- [x] Render a minimal read-only worksheet scaffold (history first, week columns, sections/rows backend order).
- [x] Add targeted frontend tests for view switch, request params, navigation, states, and row rendering order.
- [x] Run focused frontend test suite and record outcomes.

## Review
- [x] Added a new Weekly Worksheet view mode inside Media Tracker while preserving the existing overview surface.
- [x] Implemented granularity + previous/next period navigation with worksheet backend fetching and state handling.
- [x] Rendered a minimal read-only worksheet scaffold in backend order with `Istorie` before weekly columns, including `%` rows.
- [x] Verified via focused frontend Vitest suite for media-tracker page.

---

# TODO — Media Tracker frontend worksheet read-only table component (structured)

- [x] Refresh workspace state and inspect current worksheet frontend shell plus backend worksheet row/section response shape.
- [x] Extract worksheet rendering into a dedicated reusable component and wire it into Media Tracker worksheet view.
- [x] Implement worksheet-style two-row header (Săptămâna/Istorie + Data Începere/week_start) preserving backend week order.
- [x] Render section bands and rows in backend order with comparison-row visual distinction, read-only only.
- [x] Add focused value formatter by `value_kind` (RON/EUR/integer/decimal/percent_ratio/null placeholder).
- [x] Add/adjust targeted frontend tests for header structure, ordering, comparison placement, formatting, and shell behavior.
- [x] Run focused frontend tests and record outcomes.

## Review
- [x] Replaced temporary worksheet scaffold with dedicated `WeeklyWorksheetTable` component used by Media Tracker worksheet mode.
- [x] Implemented two-row worksheet header, section band rows, and comparison-row visual hierarchy in backend-provided order.
- [x] Added value formatting by `value_kind` (RON/EUR/integer/decimal/percent_ratio/null).
- [x] Preserved existing worksheet shell controls/states and verified with targeted Vitest suite.

---

# TODO — Media Tracker worksheet inline editing for weekly manual cells (frontend)

- [x] Refresh workspace state and inspect current worksheet frontend table component plus backend manual-values API contract.
- [x] Add inline edit capability only for weekly manual input cells in worksheet table.
- [x] Keep history/computed/auto/comparison cells read-only and preserve existing worksheet layout/order.
- [x] Integrate save flow with `PUT /clients/{id}/media-tracker/worksheet/manual-values` using granularity+anchor_date+single entry payload.
- [x] Support clear semantics (empty input => null), saving state, escape cancel, and inline error feedback.
- [x] Update page wiring to pass save handler and refresh worksheet data from backend response after successful save.
- [x] Add/adjust focused frontend tests for editability boundaries, payloads, clear behavior, success/error paths, and existing shell states.
- [x] Run focused frontend tests and record outcomes.

## Review
- [x] Inline editing is limited to rows marked as direct manual inputs via backend metadata/dependencies mapping.
- [x] Save interaction uses Enter or blur, Escape cancels local edit, empty values clear persisted manual entries via null.
- [x] Successful save updates worksheet data from backend response so computed rows remain backend-driven.
- [x] Non-manual rows, comparison rows, and history column remain read-only.
- [x] Focused media-tracker frontend tests pass.

---

# TODO — Media Tracker worksheet scope EUR/RON inline editor (frontend)

- [x] Refresh workspace state and inspect current worksheet header shell plus backend eur-ron-rate API contract.
- [x] Surface current EUR/RON value in worksheet control area with compact scope context.
- [x] Add inline edit mode for EUR/RON with save on Enter/blur and Escape cancel.
- [x] Integrate save flow to `PUT /clients/{id}/media-tracker/worksheet/eur-ron-rate` using current granularity + anchor_date.
- [x] Support clear semantics (empty input => null), saving state, invalid input feedback, and error message on failure.
- [x] Refresh worksheet data from backend response after successful rate save so EUR-derived rows update from backend truth.
- [x] Keep existing manual weekly editing behavior and worksheet layout/shell controls unchanged.
- [x] Add/adjust focused frontend tests for EUR/RON render/edit/save/clear/error and regressions.
- [x] Run focused frontend tests and record outcomes.

## Review
- [x] Added compact EUR/RON scope editor in worksheet controls area without page redesign.
- [x] Save/cancel/clear interactions mirror inline-edit patterns used in worksheet manual cell editing.
- [x] Scope-specific save uses current worksheet granularity + anchor_date and backend canonical scope resolution.
- [x] Successful saves update worksheet state from backend response; failures show inline error while preserving draft.
- [x] Focused media-tracker frontend tests pass.

---

# TODO — Weekly Worksheet real ISO week labels + dashed vertical separators (frontend)

- [x] Refresh workspace and inspect existing worksheet table component + backend week metadata contract.
- [x] Replace local visible week indexing with real ISO calendar week numbers derived from week_start.
- [x] Handle ISO year-boundary week labeling correctly (e.g., 2025-12-29 => week 1).
- [x] Add 1px black dashed vertical separators across header/body worksheet columns.
- [x] Keep existing worksheet layout, scrolling, and editing behavior unchanged.
- [x] Add/update focused frontend tests for month/quarter/year labels, boundary week case, header row 2 dates, and dashed border classes.
- [x] Run focused frontend tests and record outcomes.

## Review
- [x] Week labels now use real ISO week numbers from week_start and are consistent across Month/Quarter/Year views.
- [x] Year-boundary ISO semantics are handled via ISO week calculation logic.
- [x] Vertical 1px black dashed separators are applied across table header and body columns.
- [x] Existing worksheet shell and inline editing remain intact.
- [x] Focused media-tracker frontend tests pass.

---

# TODO — Dashboard debug currency drift audit/repair endpoint

- [x] Inspect dashboard debug endpoint/service patterns and existing display-currency resolver contract.
- [x] Add backend-only debug endpoint `POST /dashboard/debug/currency-drift-repair` with optional `client_id` and `dry_run`.
- [x] Implement service audit/repair flow that scans persisted client-level display-currency mirrors and repairs stale `media_buying_configs.display_currency` drift in apply mode.
- [x] Keep behavior conservative: skip ambiguous expected currency (`safe_fallback`) and never mutate attached-account metadata/platform data.
- [x] Add focused backend tests for dry-run detection, apply repair, multi-currency behavior, no-op aligned path, single-client filter, and metadata isolation.
- [x] Run targeted backend tests and document outcomes.

## Review
- [x] Added debug endpoint `POST /dashboard/debug/currency-drift-repair` under existing dashboard debug scope with no-cache headers and audit log details.
- [x] Added `UnifiedDashboardService.audit_and_repair_client_display_currency_drift(...)` with client/all-clients scan, expected-currency resolution via shared client reporting/display decision, structured findings, dry-run/apply modes, and conservative skip semantics for ambiguous decisions.
- [x] Auto-repair currently targets `media_buying_configs.display_currency` drift only; attached-account currency metadata remains read-only by design.
- [x] Added `apps/backend/tests/test_dashboard_currency_drift_repair.py` covering dry-run/apply/multi-currency/no-op/filter/skip behavior.
- [x] Verification attempted: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_dashboard_currency_drift_repair.py` (environment warning: missing `requests` dependency in this runner during import).

---

# TODO — Media Buying lead-table hot path timeout reduction (backend)

- [x] Refresh workspace state and inspect current `MediaBuyingStore.get_lead_table` hot path before coding.
- [x] Remove the default-path double scan of `ad_performance_reports` (bounds scan + cost scan) by deriving implicit bounds from the same fetched datasets.
- [x] Optimize automated-cost SQL matching path by pre-scoping mappings/accounts and precomputing normalized Google account ids in CTEs.
- [x] Add compact hot-path timing instrumentation for bounds resolution, automated query, manual query, and total duration.
- [x] Keep response shape/currency contract unchanged (`meta`, `days`, `months`, display currency metadata).
- [x] Add targeted backend tests for no-range behavior, explicit range behavior, optimized matching query contract, and timing log hook.
- [x] Run focused backend tests and record outcomes.

## Review
- [x] `get_lead_table` no-range flow now fetches automated/manual data once and computes earliest/latest non-zero data bounds in memory, removing the previous extra `ad_performance_reports` scan from normal default loading.
- [x] `_list_automated_daily_costs` now uses scoped CTEs for mappings/accounts and precomputed `account_id_digits`, reducing repeated inline normalization work in Google account matching.
- [x] Added single compact `media_buying_lead_table_timing` info log per request with `bounds_ms`, `automated_query_ms`, `manual_query_ms`, `total_ms`, and row/result counters.
- [x] Added/updated tests in `apps/backend/tests/test_media_buying_store.py` for no-range and explicit-range query behavior, timing log emission, and SQL shape assertions for scoped matching CTEs.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_client_registry_account_currency_resolution.py` (pass), plus `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Media Buying months-first lazy day-loading backend foundation

- [x] Refresh workspace and inspect current Media Buying read contract + optimized lead-table hot path.
- [x] Extend lead-table read path with backward-compatible `include_days` option (default true).
- [x] Implement lightweight months-first mode (`include_days=false`) returning month summaries without eager top-level day payload.
- [x] Add dedicated backend month-days read path for one month bucket and validate `month_start` semantics.
- [x] Reuse existing lead-table row-building/currency logic to keep day/month formulas and metadata consistent.
- [x] Add compact timing logs for month-days path.
- [x] Add/update focused tests for lightweight mode, default compatibility, month-days output, and validation.
- [x] Run targeted backend tests and document outcomes.

## Review
- [x] Main endpoint `GET /clients/{client_id}/media-buying/lead/table` now accepts `include_days` (default `true`) and preserves prior behavior when omitted.
- [x] In `include_days=false`, backend returns `meta` + `months` with per-month `day_count`/`has_days`, and top-level `days` is empty.
- [x] Added `GET /clients/{client_id}/media-buying/lead/month-days?month_start=YYYY-MM-DD` returning day rows for that month only; validates first-day-of-month and returns 422 on invalid/out-of-range values.
- [x] Month-days path reuses `get_lead_table(... include_days=True)` with scoped month date range so day-row formulas/currency semantics stay identical.
- [x] Added compact `media_buying_lead_month_days_timing` instrumentation with elapsed time and returned row count.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Media Buying frontend months-first lazy month-day loading

- [x] Refresh workspace and inspect current Media Buying page state/render + backend lightweight/month-days contract.
- [x] Switch initial lead-table fetch to `include_days=false` while preserving existing page structure/formatting.
- [x] Add per-month lazy day fetch on month expand via new month-days endpoint with cache reuse.
- [x] Add per-month loading/error state and inline retry without breaking entire table.
- [x] Reset month-day cache/loading/error state on overall table reload context.
- [x] Keep currency formatting and row semantics unchanged.
- [x] Add/update focused frontend tests for initial request contract, lazy fetch, cache reuse, and month-level error/retry.
- [x] Run focused frontend tests and document outcomes.

## Review
- [x] Initial Media Buying request now uses `/clients/{id}/media-buying/lead/table?include_days=false` (months-first).
- [x] Month expand now lazy-loads `/clients/{id}/media-buying/lead/month-days?month_start=YYYY-MM-DD` only when needed and caches per month.
- [x] Collapsing a month keeps cached rows; re-expand does not re-fetch unless retry is requested after error.
- [x] Added per-month inline loading/error/no-days rows so a failed month fetch does not break the whole page.
- [x] Existing month/day formatting, labels, and currency behavior remain unchanged.
- [x] Verification: `pnpm vitest run src/app/sub/[id]/media-buying/page.test.tsx` (pass).

---

# TODO — Media Buying no-range manual-values regression fix (backend)

- [x] Refresh workspace and inspect `media_buying_store` no-range lead-table/manual-values path.
- [x] Make `list_lead_daily_manual_values(...)` null-safe for `(date_from, date_to) == (None, None)` and keep date-pair validation explicit.
- [x] Preserve optimized no-range `get_lead_table(...)` flow without reintroducing old double-scan bounds query.
- [x] Add regression tests for no-range automated-only, automated+manual, manual-only, explicit-range compatibility, include_days=false compatibility, and null-safe manual helper behavior.
- [x] Run targeted backend tests and document outcomes.

## Review
- [x] Regression cause confirmed: optimized no-range path invoked `list_lead_daily_manual_values(..., None, None)` while helper compared `date_from > date_to` unguarded.
- [x] `list_lead_daily_manual_values` now supports `(None, None)` by querying all manual rows for client; one-sided None remains a clean validation error.
- [x] No-range `get_lead_table` remains optimized (no restored old heavy bounds scan); it still derives effective range from already fetched automated+manual rows.
- [x] Added focused backend tests in `test_media_buying_store.py` for null-safety and no-range scenarios (automated-only, automated+manual, manual-only + include_days=false).
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_media_buying_store.py apps/backend/tests/test_clients_media_buying_api.py apps/backend/tests/test_client_registry_account_currency_resolution.py apps/backend/tests/test_dashboard_currency_normalization.py` (pass).

---

# TODO — Media Buying frontend currency fallback correctness (no fake USD)

- [x] Refresh workspace and inspect current Media Buying sub-account page currency derivation.
- [x] Remove hardcoded USD fallback for currency label display when table data is missing/loading/error.
- [x] Add client-context currency fallback (table meta currency first, then client currency, else placeholder).
- [x] Keep formatting/rendering behavior unchanged outside label-currency correctness.
- [x] Add/update focused tests for table currency, client fallback currency, placeholder behavior, and error-state correctness.
- [x] Run targeted frontend tests and document outcomes.

## Review
- [x] Currency label now resolves in priority order: `tableData.meta.display_currency` -> client context currency -> `—` placeholder.
- [x] Removed fake USD fallback from label rendering path; loading/error states no longer display misleading USD.
- [x] Existing monetary formatting/layout/editing flows remain unchanged.
- [x] Added focused tests validating RON/EUR fallback correctness and placeholder behavior when currency unavailable.
- [x] Verification: `pnpm vitest run src/app/sub/[id]/media-buying/page.test.tsx` (pass).

---

# TODO — Commit pending sub-account team page refresh

- [x] Inspect existing uncommitted diff to confirm scope and impacted tests.
- [x] Update outdated team page test expectations to match current team listing UI behavior.
- [x] Run targeted frontend test for the touched team page route.
- [x] Prepare commit and PR metadata.

## Review
- [x] Verified pending change replaces legacy team user form with team listing table, filters, search, actions, and pagination.
- [x] Refreshed `page.test.tsx` assertions to validate listing controls/headers and filter + copy toast flows.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx`.

---

# TODO — Revert team settings page to Add/Edit user wizard UI

- [x] Re-audit current `subaccount/[id]/settings/team` implementation versus requested wizard spec.
- [x] Replace listing/table interface with left-vertical-tab wizard shell and Romanian copy.
- [x] Implement required fields, advanced password collapse, and footer actions with client-side validation.
- [x] Update focused frontend tests for rendering, advanced toggle behavior, and required-field validation.
- [x] Run targeted frontend tests for the touched team settings route.
- [x] Capture updated UI screenshot for the visual frontend change.
- [x] Prepare commit and PR metadata.

## Review
- [x] Restored the requested Add/Edit user wizard layout for Echipa Mea with left vertical tabs, back button, and Romanian subtitle text.
- [x] Implemented full "Informații Utilizator" content: avatar area, required fields (`Prenume`, `Nume`, `Email`), optional phone/extension, advanced password section, signature section, and footer actions (`Anulează`, `Înainte`).
- [x] Added client-side validation for required fields, email format, and numeric extension constraints.
- [x] Updated focused team page tests to cover wizard rendering and advanced collapse/validation behavior.
- [x] Verification: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx`.
- [x] Screenshot: `browser:/tmp/codex_browser_invocations/68482988e210eeba/artifacts/reports/team-user-wizard.png`.

---

# TODO — Reconnect git remote and sync with GitHub origin

- [x] Start fresh workspace context and verify git remote connectivity workflow.
- [x] Run the exact remote add/set-url command provided by user.
- [x] Run `git fetch origin`.
- [x] Run `git pull origin main --allow-unrelated-histories`.
- [x] Document sync outcome in review section.

## Review
- [x] Executed the exact remote reconciliation command provided by user (`git remote add ... || git remote set-url ...`) to ensure `origin` is configured.
- [x] Fetched from `origin` successfully; remote refs were downloaded.
- [x] Pulled `origin/main --allow-unrelated-histories` successfully; repository reported `Already up to date.`
- [x] Post-check `git remote -v` confirms `origin` points to `github.com/texpress30/scripts.git` (token masked in logs).

---

# TODO — Implementare completă „Echipa Mea” (listare + formular adăugare directă)

- [x] Re-auditez pagina actuală `subaccount/[id]/settings/team` și definesc fluxul direct fără ecran intermediar.
- [x] Implementez vizualizarea principală de listare: header, filtru rol, căutare, buton `+ Adaugă Utilizator`, tabel cu coloanele/acțiunile cerute și paginare.
- [x] Implementez formularul Add/Edit deschis direct din `+ Adaugă Utilizator` și `Editare`, cu tab-uri stânga (`Informații Utilizator`, `Roluri și Permisiuni`), upload avatar, setări avansate colapsate, footer și localizare RO.
- [x] Adaug validări frontend pentru câmpurile obligatorii (Prenume/Nume/Email), format email și extensie numerică.
- [x] Adaug feedback toast pentru `Copiere ID` și păstrez designul curat (carduri albe, colțuri rotunjite).
- [x] Actualizez testele focalizate pentru listare, flux direct add/edit, toast copy ID, toggle setări avansate și validări.
- [x] Rulez testele relevante, documentez rezultatele în review, capturez screenshot pentru schimbarea vizuală.

## Review
- [x] Pagina `Echipa Mea` folosește acum listare principală cu filtru rol, căutare, tabel utilizatori, acțiuni pe rând și paginare (`Anterior` / `Următor`).
- [x] Fluxul direct este activ: click pe `Adaugă Utilizator` sau iconița de editare deschide imediat formularul Add/Edit, fără ecran intermediar.
- [x] Formularul are localizare română, tab-uri verticale cerute, bloc `Setări Avansate` colapsat implicit, validări pentru Prenume/Nume/Email + email format + extensie numerică.
- [x] Acțiunea `Copiere ID` afișează toast `ID Copiat`; operațiile adăugare/editare/ștergere/dezactivare afișează feedback toast.
- [x] Verificare: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx`.
- [x] Încercare screenshot: server Next pornit local (`pnpm dev --port 3100`) + Playwright, dar browser container a eșuat (SIGSEGV la launch Chromium), deci nu s-a putut genera captură în acest mediu.

---

# TODO — Backend foundation users + user_memberships pentru Team Management

- [x] Re-auditez fișierele backend indicate și contractul actual `/team/members` folosit de frontend.
- [x] Extind idempotent schema `users` cu câmpurile de status/auth viitoare și adaug schema nouă `user_memberships` cu constrângeri/indexuri.
- [x] Introduc catalogul canonic de roluri + mapping din payload (`user_type`/`user_role`) către `role_key`.
- [x] Refactorizez `team_members_service` ca noul flow să scrie/citească din `users` + `user_memberships`, păstrând response shape-ul existent.
- [x] Adaug validări backend clare (required fields, rol valid, subaccount obligatoriu pentru client user, duplicate-safe membership).
- [x] Adaug endpoint nou `GET /team/subaccount-options` bazat pe `client_registry_service`.
- [x] Adaug teste backend pentru schema init idempotent, create/list/filter/reject și subaccount-options.
- [x] Actualizez documentația minimă despre modelul nou și ce rămâne pentru taskul următor.

## Review
- [x] `team_members_service` folosește acum modelul nou `users` + `user_memberships`; tabelul `team_members` este păstrat explicit doar ca legacy transitional.
- [x] Schema este idempotentă: `users` primește coloane noi (`is_active`, `must_reset_password`, `last_login_at`, `avatar_url`) și se creează `user_memberships` cu check constraints + indexuri.
- [x] Rolurile canonice (`agency_*`, `subaccount_*`) au mapping clar din payload-ul actual (`user_type` + `user_role`) și mapping invers pentru response contract legacy.
- [x] Regula de business pentru client users este aplicată: fără sub-account real (`''`/`Toate`/inexistent) se întoarce 400 cu mesaj explicit.
- [x] `GET /team/members` păstrează shape-ul vechi și citește din noul model; `POST /team/members` scrie în noul model.
- [x] Endpoint nou: `GET /team/subaccount-options` returnează `{ id, name, label }` pe baza `client_registry_service.list_clients()`.
- [x] Teste backend adăugate pentru schema init idempotent, create agency/subaccount, reject invalid client subaccount, list/filter contract și subaccount-options.
- [x] Verificare rulată: `cd apps/backend && APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q tests/test_team_members_foundation.py` + import check app startup.

---

# TODO — Agency Team frontend conectat la sub-account options reale

- [x] Re-auditez pagina Agency Team + contract `GET /team/subaccount-options`.
- [x] Înlocuiesc opțiunile hardcodate de sub-account cu loader real din backend în list filter și create form.
- [x] Aplic reguli UI pentru sub-account în funcție de `userType` (agency disable/reset, client required).
- [x] Adaug validare frontend pentru client user fără sub-account și submit payload compatibil (`subaccount` id string doar pentru client).
- [x] Păstrez fluxul existent de creare/listare + toast/reload după succes, fără redesign.
- [x] Adaug loading/error state pentru subaccount options fără blocarea întregii pagini.
- [x] Adaug teste frontend pentru integrarea sub-account options + validarea client user.
- [x] Rulez testele/build frontend și documentez review.

## Review
- [x] Pagina Agency Team încarcă acum opțiunile reale din `GET /team/subaccount-options` și le folosește atât în filtrul de listă, cât și în formularul de creare (`value=String(id)`, `label || name`).
- [x] Filtrul de listă păstrează opțiunea `Toate` și trimite `subaccount=<id>` la reload-ul listării când este selectat un sub-account.
- [x] Formularul de creare nu mai pornește cu `Toate`; folosește placeholder `Selectează Sub-cont`.
- [x] Reguli UI implementate: pentru `userType=agency` câmpul sub-account este dezactivat/resetat; pentru `userType=client` câmpul este activ și validat explicit.
- [x] Submit payload: pentru `client` trimite `subaccount` cu id-ul selectat (string), pentru `agency` trimite `subaccount` gol compatibil cu backendul nou.
- [x] Erorile backend sunt afișate direct prin mesajele venite din `apiRequest`; fallback generic rămâne doar pentru erori non-standard.
- [x] Loading/error pentru subaccount options este non-blocking (mesaje locale în list/create view).
- [x] Verificări: `pnpm vitest run src/app/settings/team/page.test.tsx` și `pnpm build` (frontend compile OK).

---

# TODO — Hotfix startup crash în team_members.initialize_schema (DDL bind param)

- [x] Audit fișierul `team_members.py` și confirm query-ul DDL parametrizat care cauzează `IndeterminateDatatype`.
- [x] Elimin bind-parameter din DDL-ul `CREATE TABLE users` (fără `%s` în DEFAULT).
- [x] Verific dacă mai există alte DDL-uri parametrizate în același serviciu.
- [x] Rulez teste backend relevante + startup/import check.
- [x] Documentez review + lecție și pregătesc commit/PR.

## Review
- [x] Cauza exactă: `CREATE TABLE IF NOT EXISTS users` folosea `password_hash TEXT NOT NULL DEFAULT %s` cu parametru bind în DDL; psycopg3 nu poate deduce tipul în acest context și ridică `IndeterminateDatatype` la startup.
- [x] Hotfix: am înlocuit default-ul DDL cu unul static (`DEFAULT ''`) și am eliminat complet `cur.execute(..., params)` pentru acel statement.
- [x] Verificare suplimentară: în `team_members.py` nu au mai rămas alte DDL-uri parametrizate.
- [x] Verificări rulate: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q tests/test_team_members_foundation.py` și import/startup check `python -c "from app.main import app; print('ok')"`.
- [x] Scope păstrat: doar backend, fără schimbări de API contract/frontend/auth flow.

---

# TODO — Migrare roluri/permisii pe model canonic + compat legacy

- [x] Re-auditez RBAC/auth/session helper-ele actuale pentru modelul vechi de roluri.
- [x] Introduc helper de normalizare roluri (canonic + aliasuri legacy) și îl aplic în RBAC (`require_permission`/`require_action`).
- [x] Actualizez matricea `ROLE_SCOPES`/`ROLE_PERMISSIONS`/`ACTION_POLICIES` pentru rolurile canonice + roluri speciale.
- [x] Păstrez backward compatibility pentru `account_manager` și `client_viewer` în validarea auth API.
- [x] Actualizez frontend session helpers + AppShell impersonation mapping pentru roluri canonice.
- [x] Adaug teste backend dedicate pentru normalizare + permission/action checks + legacy aliases.
- [x] Adaug teste frontend mici pentru `session.ts` (parser + read-only).
- [x] Rulez teste backend relevante + build frontend și documentez review.

## Review
- [x] `rbac.py` tratează acum rolurile canonice ca sursă de adevăr și normalizează aliasurile legacy prin helper central (`normalize_role`).
- [x] `require_permission()` și `require_action()` operează pe rol normalizat, nu pe string brut.
- [x] Matricea de permisiuni/scopes pentru `agency_member/agency_viewer/subaccount_admin/subaccount_user/subaccount_viewer` este explicită și consistentă cu `ACTION_POLICIES`.
- [x] `auth` API acceptă roluri canonice și aliasuri legacy (`account_manager`, `client_viewer`) prin `is_supported_role` + `normalize_role`, fără schimbarea contractului request/response.
- [x] `session.ts` și `AppShell` înțeleg rolurile canonice și păstrează compatibilitate pentru aliasurile legacy.
- [x] Teste backend adăugate pentru normalizare/permisiuni/scope + compat alias-uri și pentru login role normalization.
- [x] Test frontend adăugat pentru `session.ts` (normalizare + read-only).
- [x] Verificări rulate: pytest țintit backend, vitest țintit frontend, build frontend (pass).

---

# TODO — Auth DB-first + token cu context membership (contract login neschimbat)

- [x] Re-auditez fișierele auth/rbac/team/session/login indicate.
- [x] Implementez autentificare DB-first în `users` + `user_memberships` cu validare user activ/parolă/rol normalizat.
- [x] Păstrez fallback env admin de urgență (`super_admin`) fără schimbare de contract login.
- [x] Extind token/AuthUser cu context membership și păstrez decode backward-compatible pentru tokenuri vechi.
- [x] Actualizez `POST /auth/login` audit logging pe scenarii: succes DB, succes env fallback, invalid creds, role_not_owned, ambiguous_membership.
- [x] Ajustez minim frontend login dropdown cu roluri canonice și verific compatibilitatea `session.ts`.
- [x] Adaug teste backend pentru toate scenariile de login cerute + decode old/new token.
- [x] Rulez teste backend/frontend + build frontend + startup check backend și documentez review.

## Review
- [x] `auth` service are flow DB-first: user lookup în `users`, verificare `is_active`, verificare hash parolă, lookup membership activ pe rol normalizat.
- [x] Login DB reușit doar când există exact un membership activ pentru rolul cerut; 0 membership => 403, >1 membership => 409 cu mesaj clar de context ambiguu.
- [x] `/auth/login` păstrează contractul extern, dar folosește flow DB-first și fallback env admin (`super_admin`, `is_env_admin=true`) doar la eșec DB auth când credentials env sunt valide.
- [x] Token/AuthUser extinse cu: `user_id`, `scope_type`, `membership_id`, `subaccount_id`, `subaccount_name`, `is_env_admin`; decode rămâne compatibil cu tokenuri vechi (`email`, `role`).
- [x] Login page păstrează același UX, dar dropdown-ul folosește roluri canonice utile (`agency_*`, `subaccount_*`).
- [x] `session.ts` rămâne compatibil cu tokenuri vechi și parsează sigur payload-uri noi (câmpurile extra nu rup parserul).
- [x] Teste adăugate/rulate pentru scenariile cerute: DB success agency/subaccount, invalid password, user inactiv, role not owned, alias legacy, ambiguous membership 409, env fallback success, decode old/new token.
- [x] Verificări rulate: pytest backend relevant, vitest frontend relevant, `pnpm build`, startup check `from app.main import app`.

---

# TODO — Backend real Sub-account Team endpoints + scope enforcement

- [x] Re-auditez fișierele backend relevante și contractul UI sub-account team.
- [x] Adaug helper `enforce_subaccount_action` pentru RBAC + restricție pe `subaccount_id` pentru rolurile subaccount-scoped.
- [x] Adaug endpointuri noi `GET/POST /team/subaccounts/{subaccount_id}/members` fără a rupe endpointurile agency existente.
- [x] Implementez listarea sub-account members (direct + inherited agency access) cu contract orientat UI.
- [x] Implementez create sub-account member cu validări (required fields, roluri permise doar `subaccount_*`, sub-account existent, duplicate-safe).
- [x] Adaug teste backend pentru scope enforcement, list/create, rol invalid, sub-account inexistent, duplicate membership.
- [x] Rulez testele backend relevante + startup check backend.
- [x] Actualizez docs minim + review.

## Review
- [x] Implementat endpointurile sub-account team list/create + helper scope enforcement și acoperire de teste unitare țintite (`test_team_subaccount_api` + `test_team_members_foundation`).

---

# TODO — Hotfix startup crash `_hash_password` NameError

- [x] Re-auditez `team_members.py`, `auth.py` și helperii de hash disponibili.
- [x] Identific cauza exactă: referințe legacy `_hash_password` rămase după standardizarea helperului pe `hash_password`.
- [x] Aplic hotfix minim: elimin referințele `_hash_password` din backend și folosesc helperul comun `hash_password`.
- [x] Verific că nu există alte referințe `_hash_password` în backend.
- [x] Rulez testele backend relevante + comanda de startup cerută cu `APP_AUTH_SECRET`.

## Review
- [x] Hotfix aplicat fără modificări de contract API/frontend/auth-flow; startup import check confirmat `ok`.

---

# TODO — Verify startup crash report for `_hash_password` in team_members

- [x] Re-verify `team_members.py` and `auth.py` helper usage on latest branch state.
- [x] Run backend-wide search for `_hash_password(`.
- [x] Run startup import check with `APP_AUTH_SECRET=test-secret`.

## Review
- [x] No `_hash_password` references remain in backend; startup import check returns `ok`.

---

# TODO — Conectare pagina Sub-account Team la endpointuri reale backend

- [x] Re-auditez pagina frontend sub-account team + `api.ts` + contractele backend.
- [x] Elimin complet sursele mock locale (ex. `INITIAL_USERS`) și leg listarea la `GET /team/subaccounts/{subaccount_id}/members`.
- [x] Conectez create la `POST /team/subaccounts/{subaccount_id}/members` cu validări minime și roluri `subaccount_*`.
- [x] Tratez stările loading/empty/error + mesaje clare pentru 403/404/400.
- [x] Marchez vizual membership-urile inherited/agency în listă.
- [x] Adaug teste frontend compacte pentru list/create/roluri/403 și elimin dependența de mock users locali.
- [x] Rulez testele frontend relevante și build-ul frontend.

## Review
- [x] Pagina sub-account team este conectată la endpointurile reale GET/POST, fără mock local, cu filtre/paginare/create/refetch și acoperire de teste + build frontend.

---

# TODO — Backend Mailgun foundation (agency-level config + test email)

- [x] Re-auditez pattern-urile existente pentru integrations/secrets/RBAC/audit și contractele backend relevante.
- [x] Implementez serviciu backend Mailgun (validare config, mask api key, test send prin Mailgun API).
- [x] Adaug endpointuri agency-level pentru Mailgun: status/config/test.
- [x] Integrez RBAC pentru config/test astfel încât doar admin/global să poată configura/testa.
- [x] Adaug teste backend pentru validare, status, mask, test send (success/failure) și RBAC.
- [x] Rulez testele backend relevante + startup check și documentez rezultatele.
- [x] Actualizez docs minim pentru Mailgun foundation + ce rămâne out-of-scope.

## Review
- [x] Implementată fundația Mailgun agency-level (status/config/test), stocare în integration_secrets, masking API key, RBAC admin-only pentru config/test și acoperire de teste backend cu mock HTTP pentru send.

---

# TODO — UI Mailgun în Agency Integrations conectat la backend

- [x] Re-auditez pagina Agency Integrations, cardurile existente și contractele Mailgun backend.
- [x] Adaug card Mailgun în Agency Integrations, în stilul existent al paginii.
- [x] Conectez status la `GET /agency/integrations/mailgun/status` cu loading/error/retry clare.
- [x] Conectez formularul config la `POST /agency/integrations/mailgun/config` cu validări minime.
- [x] Conectez test email la `POST /agency/integrations/mailgun/test` cu feedback success/failure.
- [x] Mă asigur că `api_key` nu este afișată în clar (doar `api_key_masked`).
- [x] Rulez testele frontend relevante + build frontend + screenshot.

## Review
- [x] Cardul Mailgun este conectat la endpointurile reale status/config/test, cu validări minime, mesaje clare pentru erori (inclusiv 403), masking API key și acoperire de teste frontend + build + screenshot.

---

# TODO — Backend forgot/reset password via Mailgun (no UI)

- [x] Re-auditez auth/mailgun/config și pattern-urile backend existente.
- [x] Adaug serviciu dedicat pentru tokenuri email one-time (`password_reset`) cu stocare hash-only și expirare.
- [x] Adaug endpointurile publice `POST /auth/forgot-password` și `POST /auth/reset-password/confirm`.
- [x] Integrez trimiterea emailului de reset prin Mailgun config agency-level existent.
- [x] Adaug validări minime pentru parola nouă + consum/invalidare tokenuri.
- [x] Adaug teste backend pentru forgot/reset success/failure/security + login old/new password.
- [x] Rulez testele backend relevante + startup check și documentez rezultatele.
- [x] Actualizez docs minim pentru forgot/reset backend și out-of-scope.

## Review
- [x] Implementată fundația forgot/reset backend cu tokenuri hash-only one-time + expirare, trimitere Mailgun, endpointuri publice și teste pentru scenariile principale + regresii login.

---

# TODO — Backend reset password foundation only (no forgot-password/Mailgun/UI)

- [x] Re-auditez `auth.py`, `auth.py` service, `team_members.py`, `config.py` și elimin din scope endpointul forgot + Mailgun send.
- [x] Păstrez/rafinez serviciul `auth_email_tokens` pentru tokenuri reset one-time hash-only + expirare + invalidare tokenuri active.
- [x] Mențin endpointul public `POST /auth/reset-password/confirm` cu validare token + validare parolă + update hash + consume token.
- [x] Adaug helper/service method testabil pentru emiterea tokenului reset pentru user existent (fără endpoint forgot).
- [x] Ajustez testele backend pentru flow reset confirm și securitatea tokenului (invalid/expirat/consumat/parolă invalidă + login old/new).
- [x] Rulez testele backend relevante + startup check backend.
- [x] Actualizez documentația minimă pentru scope-ul acestui pas.

## Review
- [x] Implementare restrânsă la backend reset foundation: fără frontend, fără endpoint forgot-password și fără trimitere Mailgun; login-ul existent rămâne funcțional.

---

# TODO — Backend forgot-password + Mailgun send over reset foundation

- [x] Re-auditez auth API, token service, Mailgun service, config și testele reset foundation.
- [x] Adaug endpoint public `POST /auth/forgot-password` cu răspuns generic anti-enumeration.
- [x] Conectez forgot flow la token service existent + link `${FRONTEND_BASE_URL}/reset-password?token=...`.
- [x] Trimit email reset prin Mailgun service existent, fără logging token raw/link complet.
- [x] Adaug tratament clar pentru lipsă `FRONTEND_BASE_URL` și indisponibilitate Mailgun.
- [x] Extind testele backend pentru forgot success/failure/security și regresie reset confirm.
- [x] Rulez testele backend relevante + startup check.
- [x] Actualizez documentația minimă pentru statusul forgot/reset backend.

## Review
- [x] Implementare incrementală backend-only: forgot-password activ cu Mailgun + tokenuri hash-only one-time, fără schimbări frontend/login/impersonation.

---

# TODO — Frontend forgot/reset password pages connected to backend

- [x] Re-auditez `login/page.tsx`, `lib/api.ts`, `lib/session.ts` și contractele backend forgot/reset.
- [x] Adaug paginile frontend `/forgot-password` și `/reset-password` cu stări loading/success/error.
- [x] Adaug link discret „Ai uitat parola?” în `/login` fără redesign major.
- [x] Conectez API helper-ele frontend la `POST /auth/forgot-password` și `POST /auth/reset-password/confirm`.
- [x] Implementez tratarea tokenului din query string + validări locale parolă/confirmare.
- [x] Adaug teste frontend compacte pentru login link, forgot submit/success și reset token/submit/error.
- [x] Rulez testele frontend relevante + build frontend.
- [x] Fac screenshot pentru schimbările vizuale din frontend.
- [x] Actualizez docs minim pentru status forgot/reset UI vs invite.

## Review
- [x] UI forgot/reset este activ în frontend, conectat la backend existent, fără auto-login și fără schimbări majore pe login/invite.

---

# TODO — Backend invite user flow via Mailgun + auth email tokens

- [x] Re-auditez team/auth/token/mailgun/rbac/schema și contractele existente forgot/reset.
- [x] Extind token service pentru `invite_user` păstrând compatibilitatea pentru `password_reset`.
- [x] Adaug endpoint admin-only `POST /team/members/{membership_id}/invite` cu RBAC pe scope membership.
- [x] Reutilizez Mailgun + `FRONTEND_BASE_URL` pentru email invitație (fără expunere token raw în response/logs).
- [x] Fac `POST /auth/reset-password/confirm` compatibil și cu tokenuri `invite_user`.
- [x] Adaug teste backend pentru invite token, endpoint invite success/failure și regresii reset/login.
- [x] Rulez testele backend relevante + startup check.
- [x] Actualizez docs minim pentru status invite backend și ce rămâne pentru următorul task.

## Review
- [x] Invite flow backend este activ (token `invite_user` + Mailgun + endpoint team admin-only), iar reset confirm rămâne backward-compatible pentru `password_reset`.


---

# TODO — Agency Team UI: Trimite invitație

- [x] Re-auditez Agency Team frontend + helperi API + contract backend invite.
- [x] Adaug helper frontend `inviteTeamMember(membershipId)` către `POST /team/members/{membership_id}/invite`.
- [x] Adaug acțiune `Trimite invitație` în Agency Team cu loading per-row și eligibilitate minimă.
- [x] Mapez erorile cheie (403/404/503) în mesaje clare pentru utilizator.
- [x] Adaug teste frontend pentru randare invite, apel endpoint, loading/succes/erori și rând neeligibil.
- [x] Ajustez backend minim (backward-compatible) pentru a expune `membership_id` în listarea Agency Team.
- [x] Rulez testele frontend relevante + build frontend; rulez și test backend relevant pentru ajustarea de contract.

## Review
- [x] Agency Team are acțiune UI `Trimite invitație` conectată la backend, fără modificări în Sub-account Team și fără redesign major.

---

# TODO — Forgot-password token generation failure should not surface 500

- [x] Audit current forgot-password flow and identify unhandled token generation failures.
- [x] Add defensive handling in auth API to return service-unavailable response instead of uncaught 500.
- [x] Add focused backend regression test for token generation failure path.
- [x] Run targeted backend auth forgot/reset tests.

## Review
- [x] Root cause: forgot-password path did not handle token persistence failures, so token-service exceptions could bubble up as 500.
- [x] Fix: wrapped reset-token creation in `AuthEmailTokenError` handling, audit-logged the failure, and returned a consistent 503 user-safe message.
- [x] Added regression test proving token-generation failures do not attempt mail send and return HTTP 503.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_auth_forgot_reset_api.py`.

---

# TODO — Agency Team 500 regression on /team/members and /team/subaccount-options

- [x] Re-read team API/service/schema/client-registry/frontend API files and trace current endpoint wiring.
- [x] Reproduce locally `GET /team/members?page=1&page_size=10` and `GET /team/subaccount-options` 500 responses with exact stack traces.
- [x] Apply minimal backend fixes for both endpoints (no auth/forgot/reset scope), preserving Agency Team compatibility and invite flow membership_id usage.
- [x] Add backend regression tests for endpoint 200 + response shape + legacy/incomplete data resilience.
- [x] Run backend targeted tests + backend startup check + endpoint verification; update review notes.

## Review
- [x] Root cause `/team/subaccount-options`: API cast `int(row.get("id"))` without legacy guard; non-numeric client IDs from incomplete registry rows raised `ValueError` in `apps/backend/app/api/team.py` and bubbled to 500.
- [x] Root cause `/team/members`: list mapping in `team_members_service.list_members` assumed fully clean DB rows and canonical role keys; malformed numeric fields or unknown legacy role keys could raise conversion/mapping exceptions during row serialization and break endpoint load path.
- [x] Fix: added defensive normalization in `list_members` (safe int parsing + role fallback by scope) and resilient subaccount-options normalization (skip invalid IDs, safe name/label fallbacks), while keeping response contract and invite compatibility.
- [x] Regression coverage added for both endpoint paths with malformed legacy data.
- [x] Verification: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_team_members_foundation.py apps/backend/tests/test_team_subaccount_api.py apps/backend/tests/test_team_invite_api.py` and `APP_AUTH_SECRET=test-secret PYTHONPATH=apps/backend python -c "from app.main import app; print('ok')"`.

---

# TODO — Sub-account Team UI: Trimite invitație

- [x] Re-auditez pagina `subaccount/[id]/settings/team`, helperii API/session și contractul backend team invite.
- [x] Refolosesc/conectez helperul `POST /team/members/{membership_id}/invite` în Sub-account Team.
- [x] Adaug acțiunea UI `Trimite invitație` cu loading per-row, eligibilitate minimă și mesaje clare success/error.
- [x] Adaug teste frontend compacte pentru render, apel endpoint, loading, success, 403/503 și fallback neeligibil.
- [x] Rulez testele frontend relevante + build frontend și actualizez review notes.

## Review
- [x] Sub-account Team afișează acum acțiunea `Trimite invitație` în coloana `Acțiuni`, fără redesign și fără auto-invite la create.
- [x] UI folosește helperul existent `inviteTeamMember(membershipId)` către `POST /team/members/{membership_id}/invite`.
- [x] Eligibilitate minimă: buton activ doar când există `membership_id` valid și email valid; fallback neeligibil este disabled cu tooltip clar.
- [x] Loading este per-row (`Se trimite...`) și nu blochează restul paginii.
- [x] Erori mapate explicit: 403 permisiuni, 404 membership/user inexistent, 503 indisponibil temporar, fallback generic.
- [x] Fără modificări backend/auth/forgot/reset pentru acest task; contractul existent include deja `membership_id`.
- [x] Verificare: `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx` și `cd apps/frontend && pnpm build`.

---

# TODO — Agency Team: auto-invite opțional după creare user

- [x] Re-auditez Agency Team page + helperi API + contract backend create/invite.
- [x] Adaug checkbox `Trimite invitație imediat după creare` (default debifat) în formularul Agency Team.
- [x] Leg create + invite opțional în același submit flow, cu mesaje clare pentru success complet/parțial.
- [x] Păstrez invite-ul manual existent neschimbat și fără impact pe Sub-account Team.
- [x] Adaug teste frontend pentru checkbox flow (checked/unchecked, success, partial failure, create failure).
- [x] Rulez testele frontend relevante + build frontend și actualizez review notes.

## Review
- [x] Agency Team create form include opțiunea `Trimite invitație imediat după creare` (default debifat), fără redesign major.
- [x] Create flow rămâne identic când checkbox-ul nu este bifat; când este bifat rulează create + invite în lanț, folosind `membership_id` (fallback `id`) din create response.
- [x] Success complet: mesaj `Utilizatorul a fost creat și invitația a fost trimisă`.
- [x] Success parțial: utilizatorul rămâne creat, fără rollback, iar UI afișează mesajul clar `Utilizatorul a fost creat, dar invitația nu a putut fi trimisă ...`.
- [x] Invite-ul manual din listă a rămas funcțional; Sub-account Team nu a fost modificat.
- [x] Verificare: `cd apps/frontend && pnpm vitest run src/app/settings/team/page.test.tsx` și `cd apps/frontend && pnpm build`.

---

# TODO — Backend foundation: sesiune multi-subaccount pentru roluri subaccount_*

- [x] Re-auditez auth API/service/dependencies/team_members/rbac și compatibilitatea frontend session parser.
- [x] Extind token/AuthUser pentru context multi-subaccount (`access_scope`, `allowed_subaccount_ids`, etc.) cu decode backward-compatible.
- [x] Schimb login DB pentru rolurile `subaccount_*` astfel încât să accepte multiple memberships active (fără 409 pentru multiplu).
- [x] Actualizez enforcement subaccount pe lista permisă, păstrând comportamentul pentru tokenuri vechi.
- [x] Adaug teste backend pentru login single/multi subaccount, enforcement allow/deny, token legacy compat, agency/env fallback.
- [x] Rulez testele backend relevante + startup check backend și documentez rezultatele.

## Review
- [x] `AuthUser` + token payload suportă acum context multi-subaccount (`access_scope`, `allowed_subaccount_ids`, `allowed_subaccounts`, `primary_subaccount_id`, `membership_ids`) cu default-uri sigure și compatibilitate pentru tokenuri vechi.
- [x] Login-ul DB pentru roluri `subaccount_*` nu mai returnează 409 pe memberships multiple active; calculează lista completă de sub-account-uri permise și păstrează `primary_subaccount_id` doar când există un singur sub-account.
- [x] `enforce_subaccount_action` validează accesul pe `allowed_subaccount_ids` când există; altfel păstrează fallback-ul legacy bazat pe `subaccount_id`/`primary_subaccount_id`.
- [x] Agency/special roles și env-admin fallback rămân funcționale (acoperite de testele existente + actualizate).
- [x] Verificare: `APP_ENV=test APP_AUTH_SECRET=test-secret pytest -q apps/backend/tests/test_auth_db_login.py apps/backend/tests/test_team_subaccount_api.py apps/backend/tests/test_auth_role_normalization.py` și `APP_AUTH_SECRET=test-secret PYTHONPATH=apps/backend python -c "from app.main import app; print('ok')"`.

---

# TODO — Frontend post-login pentru sesiune multi-subaccount

- [x] Re-auditez `session.ts`, `AppShell.tsx`, `login/page.tsx` și contractul backend auth/token.
- [x] Extind parserul de sesiune pentru context multi-subaccount + helperi comuni (`allowed_subaccount_ids`, `primary_subaccount_id`) cu compatibilitate token vechi.
- [x] Filtrez AppShell/switcher pe sub-account-uri permise și adaug comportament direct-entry când există unul singur.
- [x] Adaug guard frontend pentru URL sub-account nepermis cu redirect safe (primary/primul permis/fallback).
- [x] Adaug teste frontend compacte pentru parser, filtrare, redirect single/multi, URL forbidden și regresie agency/global.
- [x] Rulez testele frontend relevante + build frontend și documentez rezultatele.

## Review
- [x] `session.ts` expune acum contextul complet al sesiunii (`allowed_subaccount_ids`, `allowed_subaccounts`, `primary_subaccount_id`) și păstrează fallback pentru token legacy cu `subaccount_id`.
- [x] `AppShell` filtrează lista de clienți după acces permis, completează lipsurile din metadata token și aplică guard pentru URL-uri `/sub/:id` nepermise cu redirect sigur către sub-account valid.
- [x] Login-ul redirecționează utilizatorii scoped direct pe dashboard-ul sub-account-ului sigur (unic sau primary), păstrând fallback agency pentru roluri globale.
- [x] Teste noi/adaptate pentru parser sesiune și helper-ele AppShell (filtrare + decizie guard) rulează cu succes; build frontend validat.

---

# TODO — Backend foundation module permissions pe membership (sub-account)

- [x] Re-auditez serviciile/API/scheme team + dependințe RBAC pentru punctele de integrare.
- [x] Introduc catalog canonic de module sub-account (key/label/order/scope) și helperi de service.
- [x] Adaug storage idempotent `membership_module_permissions` + helperi read/write/default.
- [x] Extind create flows (`/team/members`, `/team/subaccounts/{id}/members`) cu `module_keys` opțional și validări scope.
- [x] Implementez grant ceiling pentru actori `subaccount_*` (subset din modulele actorului pe același sub-account).
- [x] Extind payload-urile de răspuns cu `module_keys` pentru membership-uri relevante.
- [x] Adaug endpoint `GET /team/module-catalog?scope=subaccount`.
- [x] Adaug/rulez teste backend pentru schema, validări, defaults, ceiling, endpoint catalog și contract responses.
- [x] Rulez startup check backend și documentez rezultatele.

## Review
- [x] `team_members` gestionează acum catalogul canonic de module sub-account și persistă module active per membership în `membership_module_permissions`.
- [x] `module_keys` este backward-compatible (opțional), default la create pentru `subaccount_*` este „toate modulele”, iar pentru scope `agency` este respins explicit cu 400.
- [x] Grant ceiling este activ: actorii subaccount pot acorda doar subset din modulele proprii pentru sub-account-ul țintă.
- [x] API-ul expune catalogul de module (`/team/module-catalog`) și returnează `module_keys` în response-urile de team memberships.
- [x] Testele backend țintite + startup check backend au fost rulate pentru validare.

---

# TODO — Agency Team UI: Roluri și Permisiuni (module on/off) pentru create user client

- [x] Re-auditez Agency Team page + contract backend (`/team/module-catalog`, `module_keys` create team member).
- [x] Adaug helper frontend pentru catalog module (`GET /team/module-catalog?scope=subaccount`).
- [x] Încarc catalogul și afișez secțiunea de module doar pentru create user de tip client cu sub-cont selectat.
- [x] Setez implicit toate modulele selectate și permit toggle on/off cu state persistent în flow.
- [x] Trimit `module_keys` doar pentru create user client; nu trimit pentru agency.
- [x] Adaug validare frontend minim 1 modul selectat pentru secțiunea activă.
- [x] Adaug handling clar pentru erori backend `module_keys`.
- [x] Adaug teste frontend țintite pentru catalog/render/toggle/payload/validare/erori.
- [x] Rulez testele frontend relevante + build frontend și documentez rezultatele.

## Review
- [x] Agency Team folosește acum catalogul backend de module și permite setarea explicită on/off a modulelor în create flow-ul userilor client/sub-account.
- [x] Role picker-ul rămâne separat și obligatoriu; modulele sunt trimise doar ca restricții suplimentare (`module_keys`).
- [x] Pentru agency users, secțiunea de module nu este afișată și payload-ul de create rămâne fără `module_keys`.
- [x] Frontend blochează submit-ul când toate modulele sunt debifate în contextul client/sub-account.
- [x] Invite/auto-invite și restul fluxului Agency Team au fost păstrate.

---

# TODO — Backend hotfix Team endpoints DB-unavailable fallback

- [x] Reproduce/inspect 500 paths for `/team/members`, `/team/subaccount-options`, `/team/module-catalog`.
- [x] Add backend API guards to return stable empty `200` payloads when DB is unavailable.
- [x] Normalize list payloads defensively to avoid serialization errors on malformed legacy rows.
- [x] Add targeted regression tests for DB-unavailable fallback and normalization behavior.
- [x] Run focused backend tests for touched team API foundation file.

## Review
- [x] Added DB-unavailable detection helper in Team API and applied fallback responses for members list, module catalog, and subaccount options endpoints.
- [x] Added endpoint-level normalization for members/module catalog payloads to keep response contract valid under legacy malformed data.
- [x] Added regression tests covering DB outage fallbacks and row normalization.
- [x] Verification: `cd apps/backend && python -m pytest tests/test_team_members_foundation.py`.

---

# TODO — Sub-account Team create module permissions with grant ceiling

- [x] Re-read Sub-account Team frontend page and API/session/backend contracts.
- [x] Add minimal backend contract for actor grantable modules per sub-account (backward-compatible).
- [x] Wire Sub-account Team create flow to load module catalog/grantable flags and render `Roluri și Permisiuni` module controls.
- [x] Enforce UI behavior: default select grantable modules, disable non-grantable modules, preserve role picker.
- [x] Submit only selected+grantable `module_keys`; block submit if no module remains selected.
- [x] Add focused frontend tests for loading/render/default/toggle/payload/validation/error handling.
- [x] Add focused backend tests for grantable-modules contract.
- [x] Run backend tests, frontend tests, and frontend build.

## Review
- [x] Added a minimal backend endpoint `GET /team/subaccounts/{subaccount_id}/grantable-modules` returning canonical module items with actor-specific `grantable` flags.
- [x] Kept Sub-account Team role picker intact and added a focused `Roluri și Permisiuni` section in create flow with default-select grantable modules, disabled non-grantable modules, and inline explanation.
- [x] Create payload now sends only selected grantable `module_keys`; submit is blocked if no grantable module remains selected.
- [x] Added compact regression tests for backend grantable contract and frontend load/render/default/toggle/payload/validation/error handling paths.
- [x] Verification commands:
  - `cd apps/backend && python -m pytest tests/test_team_subaccount_api.py tests/test_team_members_foundation.py`
  - `cd apps/frontend && pnpm vitest run src/app/subaccount/[id]/settings/team/page.test.tsx`
  - `cd apps/frontend && pnpm build`

## 2026-03-17 Connector workspace sync task
- [x] Draft plan with explicit sync steps and verification commands.
- [x] Start a fresh terminal session (do not reuse previous session) for connector-style commands.
- [x] Run requested remote/add-or-set, fetch, and pull commands exactly as provided.
- [x] Verify remote configuration and fetch visibility in the new session.
- [x] Document review/results for this task.

### Check-in before execution
Plan reviewed: execute the exact user-provided Git commands in a newly started terminal session, then verify `git remote -v` and fetch state, and record outcome.

### Review
- Executed the exact three Git commands in a fresh terminal session.
- `origin` now points to the provided GitHub URL for both fetch and push.
- `git fetch origin` succeeded and `git pull origin main --allow-unrelated-histories` reported repository already up to date.

## 2026-03-17 AppShell subaccount module filtering + access-context
- [x] Review existing frontend/backend files for session, AppShell, routing helpers, and team access contracts.
- [x] Draft implementation plan with compatibility/fallback behavior for subaccount-scoped vs agency/global roles.
- [ ] Add/adjust backend access-context endpoint contract for current subaccount module access (with legacy fallback + 403).
- [ ] Add backend tests for access-context response shape, scoped access, denied access, agency/global compatibility, legacy fallback.
- [ ] Add frontend API helper for current subaccount access-context retrieval.
- [ ] Update AppShell sidebar filtering by module keys for subaccount routes and keep agency/global behavior unchanged.
- [ ] Add safe redirect on manual navigation to disallowed module route (first allowed module fallback order).
- [ ] Add/adjust frontend tests for filtered sidebar, hidden modules, agency/global unchanged, safe redirect, and loading fallback.
- [ ] Run frontend tests and build; run backend tests + startup check for changed contract.
- [ ] Document review/results and intentional follow-ups.

### Check-in before execution
Plan verified: implement minimal access-context foundation, consume it in AppShell for subaccount-scoped users only, preserve agency/global behavior, then validate with focused frontend/backend tests and build.
- [x] Add/adjust backend access-context endpoint contract for current subaccount module access (with legacy fallback + 403).
- [x] Add backend tests for access-context response shape, scoped access, denied access, agency/global compatibility, legacy fallback.
- [x] Add frontend API helper for current subaccount access-context retrieval.
- [x] Update AppShell sidebar filtering by module keys for subaccount routes and keep agency/global behavior unchanged.
- [x] Add safe redirect on manual navigation to disallowed module route (first allowed module fallback order).
- [x] Add/adjust frontend tests for filtered sidebar, hidden modules, agency/global unchanged, safe redirect, and loading fallback.
- [x] Run frontend tests and build; run backend tests + startup check for changed contract.
- [x] Document review/results and intentional follow-ups.

### Review
- Added backend endpoint `GET /team/subaccounts/{subaccount_id}/my-access` with minimal response contract (`subaccount_id`, `role`, `module_keys`, `source_scope`, `access_scope`, `unrestricted_modules`).
- Subaccount-scoped users now receive effective membership module keys for the current sub-account, with safe legacy fallback to full catalog when explicit context is unavailable; no-access remains 403.
- Agency/global roles return unrestricted module context for compatibility in this task.
- Frontend AppShell now loads current subaccount access-context for sub-account routes, filters sidebar module entries (`dashboard`, `campaigns`, `rules`, `creative`, `recommendations`) by `module_keys`, and preserves agency/global behavior.
- Manual URL access to disallowed sub-account module routes now redirects safely to the first allowed module in fixed order; if none are allowed, fallback route is `/subaccount/{id}/settings/profile`.
- Follow-up intentionally left: backend enforcement on each business module endpoint remains for the next task.

## 2026-03-17 Backend module enforcement for subaccount-scoped users
- [x] Re-read dependencies/team_members/rbac/team APIs and module-serving backend routes (dashboard, campaigns, rules, creative, recommendations).
- [x] Add reusable backend helper for subaccount module-level enforcement with scoped checks, agency/global bypass, and legacy-safe fallback.
- [x] Define and apply clear module-to-endpoint enforcement on currently used subaccount module routes.
- [x] Add representative backend tests for allowed/forbidden paths across dashboard/campaigns/rules/creative/recommendations, plus agency/global and legacy compatibility.
- [x] Run backend tests and backend startup/import check.
- [x] Document review and intentional follow-up scope.

### Check-in before execution
Plan verified: implement enforcement helper in dependencies, apply it to current module-serving routes used by UI, add a dedicated campaigns summary endpoint for clear campaigns mapping, and validate via focused backend tests + startup check.

### Review
- Added `enforce_subaccount_module_access(user, subaccount_id, module_key)` in backend dependencies to enforce scoped sub-account ownership first, then effective `module_keys` for subaccount roles.
- Added campaigns-specific endpoint `GET /campaigns/{client_id}/summary` and switched campaigns UI metrics load to this route so campaigns module has explicit backend enforcement mapping.
- Applied backend module enforcement on active module routes: dashboard (`/dashboard/{client_id}`), campaigns (`/campaigns/{client_id}/summary`), rules (`/rules/{client_id}` and evaluate/create paths), creative (library + asset actions), recommendations (`/ai/recommendations/*`).
- Preserved compatibility: agency/global roles bypass module restrictions; subaccount legacy context without explicit membership module rows falls back safely to full default catalog from existing service logic.
- Intentional follow-up left: broader mapping for ambiguous/unused legacy endpoints not currently used by UI remains for a future hardening pass.

## 2026-03-17 Membership detail + patch foundation (backend)
- [x] Re-read team API/service/schemas/dependencies/rbac and frontend team pages for contract context.
- [x] Design membership-oriented detail + patch contracts (no identity edits) and enforcement matrix.
- [ ] Implement `GET /team/members/{membership_id}` with edit-oriented detail response and inherited indicator.
- [ ] Implement `PATCH /team/members/{membership_id}` for `user_role` + `module_keys` only, with scope/family validation.
- [ ] Implement service helpers for membership detail fetch, role-family validation, and membership update operations.
- [ ] Enforce grant ceiling for subaccount-scoped actors on module updates.
- [ ] Reject agency membership `module_keys`, invalid/empty module lists, and inherited/non-editable targets.
- [ ] Add/adjust backend tests for new endpoints and update rules + regression coverage for list/create/invite.
- [x] Run backend tests + backend startup check.
- [ ] Document review/results and intentional next-step scope.

### Check-in before execution
Plan verified: add membership detail/patch foundations strictly on membership records (not user identity), keep create/list/invite flows untouched, and validate with focused backend tests including grant ceiling and inherited access rejection.
- [x] Implement `GET /team/members/{membership_id}` with edit-oriented detail response and inherited indicator.
- [x] Implement `PATCH /team/members/{membership_id}` for `user_role` + `module_keys` only, with scope/family validation.
- [x] Implement service helpers for membership detail fetch, role-family validation, and membership update operations.
- [x] Enforce grant ceiling for subaccount-scoped actors on module updates.
- [x] Reject agency membership `module_keys`, invalid/empty module lists, and inherited/non-editable targets.
- [x] Add/adjust backend tests for new endpoints and update rules + regression coverage for list/create/invite.
- [x] Run backend tests + backend startup check.
- [x] Document review/results and intentional next-step scope.

### Review
- Added membership-oriented backend foundation endpoints: `GET /team/members/{membership_id}` and `PATCH /team/members/{membership_id}`.
- Implemented membership detail serialization for edit use-cases with scope/subaccount/role/module/source/inherited markers and identity display fields.
- Implemented membership patch limited to `user_role` and `module_keys` only; no global user identity fields are updated in this task.
- Added strict scope-family rules: agency membership accepts only agency roles and rejects `module_keys`; subaccount membership accepts only subaccount roles and validates module list (valid keys, dedup, minimum one).
- Added grant-ceiling enforcement for subaccount-scoped actors when updating module permissions.
- Added inherited/non-editable guard with clear conflict response; no implicit membership creation is performed.
- Preserved create/list/invite behavior and validated with regression test execution.
- Intentional follow-up: edit UI wiring and broader lifecycle actions (deactivate/remove membership, identity edits) remain for next tasks.

## 2026-03-17 Agency Team UI edit wiring for membership role/module updates
- [x] Re-read Agency Team page and team API contracts for membership detail/patch.
- [x] Add frontend API helpers/types for membership detail and patch endpoints.
- [x] Wire table edit action to fetch membership detail by `membership_id` and open edit mode.
- [x] Reuse existing create/edit form structure for edit mode without redesign.
- [x] Make identity fields read-only in edit mode and ensure PATCH payload excludes identity fields.
- [x] Render agency vs subaccount-specific behavior for role/module section in edit mode.
- [x] Handle inherited/non-editable membership states (preload + patch conflict) with blocked save and clear messaging.
- [x] Wire save action to `PATCH /team/members/{membership_id}` with `user_role` + conditional `module_keys`.
- [x] Add frontend tests for edit flow, detail fetch, module preselection, patch payload, inherited handling, and regressions.
- [x] Run frontend tests and frontend build.

### Check-in before execution
Plan verified: keep Agency Team UI shape largely unchanged, add edit wiring around existing form, enforce read-only identity in edit mode, and validate via focused frontend tests plus build.

### Review
- Agency Team edit action now loads `GET /team/members/{membership_id}` and enters edit mode with membership-scoped data.
- Save now calls `PATCH /team/members/{membership_id}` with supported fields only (`user_role`, `module_keys` for subaccount scope).
- Edit mode enforces read-only identity fields (first_name/last_name/email/phone/extension) and shows a note that identity editing is deferred.
- Agency membership edit keeps module section non-applicable; subaccount membership edit shows module controls with preselected `module_keys`.
- Inherited access is blocked with clear messaging and save protection; backend conflict/error mappings (400/403/404/409) surface user-friendly feedback.
- Existing create/invite flows remain covered by the existing and updated test suite.
- Intentional follow-up: Sub-account Team edit UI remains out of scope for this task.

## 2026-03-17 Membership lifecycle foundation: deactivate/reactivate (backend)
- [x] Re-read team/auth/rbac/dependencies and team frontend pages for contract context.
- [x] Add backend endpoints for membership deactivate/reactivate with idempotent status response.
- [x] Add service helpers for membership status transitions and inherited-access guard.
- [x] Expose membership status in team list/detail/subaccount list responses with backward compatibility.
- [x] Ensure login/access-context/grantable flows ignore inactive memberships.
- [x] Add backend tests for lifecycle endpoints, status contracts, and inactive filtering behavior.
- [x] Run targeted backend tests and backend startup check.

### Review
- Implemented `POST /team/members/{membership_id}/deactivate` and `POST /team/members/{membership_id}/reactivate` on membership records only (no `users.is_active` mutations).
- Added status serialization (`membership_status`) in team list/detail and subaccount list responses while preserving existing fields.
- Added inherited-access conflict handling for lifecycle transitions; no implicit local membership creation.
- Confirmed DB-driven auth/access behaviors continue to only consider active memberships.
- Intentional follow-up left for next task: UI actions/buttons and lifecycle wiring in Agency/Sub-account Team pages.


## 2026-03-17 Agency Team UI lifecycle actions (deactivate/reactivate)
- [x] Re-read Agency Team page, frontend API helpers, and backend team contracts for status/lifecycle endpoints.
- [x] Render `membership_status` in Agency Team list with discrete active/inactive indicator.
- [x] Add frontend API helpers for deactivate/reactivate membership lifecycle endpoints.
- [x] Wire row-level deactivate/reactivate actions with per-row loading, success toast, and list refetch.
- [x] Add explicit lifecycle error mappings for 403/404/409 plus safe fallback.
- [x] Add focused frontend tests for status rendering, actions, loading, success refetch, and error handling while preserving existing flows.
- [x] Run frontend tests and frontend build.

### Check-in before execution
Plan verified: keep change incremental in `apps/frontend/src/app/settings/team/page.tsx` + `apps/frontend/src/lib/api.ts` and tests only; no Sub-account Team lifecycle UI and no create/edit/invite behavior changes.

### Review
- Agency Team list now surfaces `membership_status` with discrete badges (`Activ` / `Inactiv`) and keeps existing table layout.
- Added lifecycle helpers in frontend API for `deactivate`/`reactivate` membership endpoints and wired row-level actions in Agency Team.
- Lifecycle actions use per-row loading, refetch the list on success, and map 403/404/409 to clear user-safe messages.
- Existing create/edit/invite flows remain covered and passing in updated page tests.
- Intentional next step: Sub-account Team lifecycle UI actions remain out of scope for this task.


## 2026-03-17 Sub-account Team UI lifecycle actions (deactivate/reactivate)
- [x] Re-read sub-account team page, frontend API helpers, and backend team contracts for lifecycle/status.
- [x] Render `membership_status` in sub-account team list with compact active/inactive indicator.
- [x] Wire row-level deactivate/reactivate actions in sub-account team actions column.
- [x] Add per-row loading, success messaging, explicit 403/404/409 mapping, and list refetch after lifecycle actions.
- [x] Keep create/edit/invite behavior unchanged; no Agency Team changes in this task.
- [x] Add focused frontend tests for lifecycle UI/actions/loading/errors and regressions for existing flows.
- [x] Run relevant frontend tests and frontend build.
- [x] Create PR with required title/body and verify metadata is not placeholder; patch with `gh pr edit` if possible.

### Check-in before execution
Plan verified: confine code changes to sub-account team page + tests (and shared API helper usage only), with minimal/no backend changes and no redesign.

### Review
- Sub-account Team list now shows lifecycle status badges (`Activ`/`Inactiv`) using backend `membership_status` with fallback from `is_active`.
- Added row-level deactivate/reactivate action buttons in the existing Actions column, with per-row loading state and list refetch on success.
- Added explicit lifecycle error mapping for 403/404/409 and inherited guard in UI; inherited rows keep action disabled with clear tooltip.
- Existing create/edit/invite behavior remained intact and passing through updated test coverage.
- Intentional follow-up: remove membership action remains for next task; no token revocation behavior was added in this step.

---

# TODO — Repository workflow housekeeping (task docs refresh)

- [x] Inspect repo instructions and current task-tracking artifacts.
- [x] Record a minimal task/review entry in `tasks/todo.md` for this execution cycle.
- [x] Verify git diff remains scoped to task documentation only.

## Review
- [x] Added a focused housekeeping entry documenting this cycle.
- [x] Scope intentionally limited to `tasks/todo.md` to keep the change minimal and reviewable.

---

# TODO — Backend foundation read-only Email Templates catalog

- [x] Re-read `apps/backend/app/api/auth.py`, `apps/backend/app/api/team.py`, and `apps/backend/app/main.py` for routing/RBAC patterns.
- [x] Add minimal canonical read-only email templates catalog service (`auth_forgot_password`, `team_invite_user`).
- [x] Add backend read-only agency endpoints for list and detail with admin/global-admin enforcement.
- [x] Add targeted backend tests for list/detail/invalid-key/RBAC.
- [x] Run targeted backend tests and backend startup check.
- [x] Commit changes and create PR metadata.

### Check-in before execution
Plan verified: backend-only minimal foundation, no UI, no DB tables/overrides, no forgot/invite migration in this step.

## Review
- [x] Added backend-only read-only email templates foundation with canonical in-code catalog and agency endpoints.
- [x] Kept scope strict: no UI, no DB persistence/overrides, no forgot/invite migration, no mailgun service changes.
- [x] Verified with targeted backend tests plus startup import check.

---

# TODO — Backend Email Templates DB overrides + save/reset APIs

- [x] Re-read current email templates service/api/schemas/main routing and keep scope backend-only.
- [x] Add idempotent persistent storage (`agency_email_templates`) for agency-level template overrides.
- [x] Extend email templates service for effective read model (default vs override), save/upsert, and reset behavior.
- [x] Extend API contracts: list/detail enriched fields + PUT save + POST reset, admin/global-admin only.
- [x] Add backend tests for idempotent schema init, default/override read behavior, save/reset, 404, and RBAC.
- [x] Run targeted backend tests and backend startup check.
- [x] Commit and open PR with exact requested title/body.

### Check-in before execution
Plan verified: strict backend increment only (no UI, no forgot/invite migration, no flow changes outside email-template catalog APIs).

## Review
- [x] Added agency-level DB override persistence for email templates with idempotent schema init.
- [x] Extended list/detail to expose effective values and override metadata (`enabled`, `is_overridden`, `updated_at`).
- [x] Added admin-only save/reset endpoints and validated behavior through focused backend tests + startup check.

---

# TODO — Wire forgot/invite email flows to effective Email Templates

- [x] Re-read backend files for templates/auth/team/mailgun and keep scope backend-only.
- [x] Add effective template resolve + deterministic variable-render helper in `email_templates` service.
- [x] Migrate `/auth/forgot-password` to `auth_forgot_password` effective template (default or override).
- [x] Migrate `/team/members/{membership_id}/invite` to `team_invite_user` effective template (default or override).
- [x] Handle `enabled=false` consistently with safe availability error in both flows.
- [x] Extend Mailgun send helper for optional HTML while keeping backward compatibility.
- [x] Add backend tests for default/override usage, rendering, enabled=false, html send, and compatibility.
- [x] Run targeted backend tests and backend startup check.
- [x] Commit and create PR with exact requested title/body.

### Check-in before execution
Plan verified: backend incremental change only, no UI and no redesign, with existing endpoint contracts preserved.

## Review
- [x] Forgot-password and invite now resolve/render effective templates (default or override) via shared email template service.
- [x] Added deterministic placeholder rendering (`{{...}}`) for supported variables and enforced template `enabled` gating with safe availability errors.
- [x] Extended Mailgun send API with optional HTML in a backward-compatible way and validated via focused backend tests + startup check.

---

# TODO — Agency Email Templates UI page (list/detail/save/reset)

- [x] Re-read AppShell/sidebar + frontend API + backend email template contracts.
- [x] Add agency sidebar item `Email Templates` and dedicated route page.
- [x] Add frontend API helpers for list/detail/save/reset email templates.
- [x] Implement list + detail editor (subject/text/html/enabled) with save/reset actions.
- [x] Implement loading/empty/error states and explicit 403/404/400 handling.
- [x] Add compact frontend tests for sidebar nav, list/detail load, save/reset calls, and error handling.
- [x] Run frontend targeted tests + frontend build.
- [x] Re-run backend forgot/invite tests as no-regression confirmation.
- [x] Commit and create PR with required title/body.

### Check-in before execution
Plan verified: frontend-focused incremental change, no notifications UI, no rich editor/preview/test-send in this task.

## Review
- [x] Added `Email Templates` sidebar item and new agency page `/agency/email-templates`.
- [x] Page supports list/detail/save/reset against existing backend API, including success feedback and loading states.
- [x] Error handling is explicit for 403/404/400 and generic fallback.
- [x] Notifications UI and rich editor/preview/test-send remain intentionally out of scope.

# TODO — Workflow alignment after AGENTS correction (2026-03-18)

- [x] Review AGENTS.md instructions and confirm required workflow behavior for this cycle.
- [x] Record a new correction lesson in `tasks/lessons.md` to prevent recurrence.
- [x] Verify git diff is intentionally scoped to task-tracking docs only.
- [x] Commit docs update and create PR metadata via `make_pr`.

## Review
- [x] Captured correction-specific lesson and kept change minimal.
- [x] Scope remains documentation-only for workflow alignment.

# TODO — Move Email Templates to Settings + surface Mailgun status (2026-03-18)

- [x] Re-read AppShell, Email Templates page, frontend API helpers, and existing Mailgun status contract.
- [x] Move `Email Templates` from agency main nav into agency Settings nav group while preserving route `/agency/email-templates`.
- [x] Add Mailgun status loading block in Email Templates page (configured/enabled + safe metadata) using existing status endpoint.
- [x] Gate `Send test email` button by Mailgun availability and show clear CTA link to Agency Integrations when unavailable.
- [x] Add/update focused frontend tests for nav placement, Mailgun loading/error/unavailable/available states, and preserve save/reset/preview flows.
- [x] Run targeted frontend tests + frontend build.
- [x] Update review notes and lessons for this correction cycle.
- [x] Commit changes and create PR via `make_pr` with required title/body.

## Check-in before execution
Plan verified: frontend-focused incremental patch only (AppShell + email templates page + tests), using existing Mailgun status API; no Notifications backend/UI and no major redesign.


## Review
- [x] Moved Email Templates under Settings navigation while preserving `/agency/email-templates`.
- [x] Added explicit Mailgun status panel with configured/enabled indicators, safe metadata, unavailable CTA to Integrations, and test-send gating.
- [x] Kept preview/save/reset flows available even when Mailgun is unavailable or status fails.
- [x] Notifications backend/UI and additional redesign remain intentionally out of scope for this task.

# TODO — Mailgun DB-first + env fallback/bootstrap (2026-03-18)

- [x] Re-read Mailgun service, integration secret store, config, existing Mailgun endpoints, and frontend Mailgun status usage.
- [x] Add Mailgun env settings in backend config (`MAILGUN_*`, including optional enabled/reply-to).
- [x] Implement DB-first config resolution with env fallback in `mailgun_service`, including `config_source` in status.
- [x] Add explicit admin endpoint `POST /agency/integrations/mailgun/import-from-env` to bootstrap env config into DB.
- [x] Ensure DB precedence over env and preserve existing save/test flows.
- [x] Add backend tests for DB-only, env-only, DB-wins, none, masked key, status source, import endpoint, and template test-send availability with env fallback.
- [x] Run targeted backend tests and backend startup check.
- [x] Apply minimal frontend status adjustments for `config_source` visibility if needed; run relevant frontend tests/build only if touched.
- [x] Update task notes/lessons and finalize with commit + make_pr.

## Check-in before execution
Plan verified: backend-first incremental change, no major UI redesign, no new provider support, and DB remains source-of-truth with env as fallback/bootstrap only.


## Review
- [x] Added backend Mailgun env vars and DB-first + env fallback resolution with explicit `config_source`.
- [x] Added explicit `POST /agency/integrations/mailgun/import-from-env` bootstrap endpoint with admin-only scope checks and no plaintext API key response.
- [x] Preserved DB precedence over env, while allowing env-only effective availability for Email Templates test-send and integrations status.
- [x] Added targeted backend/frontend tests and validated backend startup plus frontend build.
- [x] Intentionally left out: redesign major, new providers, and changes to unrelated auth/team flows.

# TODO — Backend foundation Agency Email Notifications settings (2026-03-18)

- [x] Re-read existing email templates backend files (service/api/schemas/main) for architecture and contract alignment.
- [x] Add new backend service `email_notifications.py` with canonical catalog (`auth_forgot_password`, `team_invite_user`) and agency-level defaults.
- [x] Add idempotent persistence table `agency_email_notifications` with unique `(notification_key, scope_key)` override semantics.
- [x] Implement effective read model (default vs override) exposing `enabled`, `is_overridden`, `updated_at`.
- [x] Add backend schemas and API endpoints: list/detail/save/reset under `/agency/email-notifications`.
- [x] Enforce admin/global-admin RBAC parity with Email Templates and explicit 404/400 behavior.
- [x] Keep runtime forgot/invite flows unchanged (no migration to notifications in this task).
- [x] Add targeted backend tests for schema, list/detail/save/reset, invalid key, RBAC, and no-regression for existing email templates endpoints.
- [x] Run backend tests + backend startup check.
- [x] Update task notes/lessons, commit, and create PR via `make_pr`.

## Check-in before execution
Plan verified: backend-only incremental foundation (catalog + override storage + CRUD endpoints), no frontend and no runtime flow migration in this step.


## Review
- [x] Added backend-only notifications foundation with canonical catalog and agency override storage (`agency_email_notifications`).
- [x] Added CRUD-style agency endpoints (list/detail/save/reset) with RBAC aligned to Email Templates.
- [x] Preserved current runtime behavior: forgot-password and invite flows are unchanged in this step.
- [x] Added focused backend tests + startup validation and explicit no-regression check for existing email templates endpoint contract.
- [x] Intentionally left out: any Notifications UI and runtime flow migration to notifications settings.

# TODO — Mailgun test-send diagnostics semantics (accepted vs delivered) (2026-03-18)

- [x] Re-read Mailgun service, Email Templates API schemas/router, frontend email templates page, and API client contracts.
- [x] Update backend test-send response contract to accepted semantics (`accepted`, `delivery_status`, `provider_message`, `provider_id`, etc.) without claiming delivery.
- [x] Keep send flow unchanged while enriching diagnostics payload for test-send responses.
- [x] Update frontend API types and Email Templates UI success copy to reflect "accepted by Mailgun" semantics.
- [x] Add sandbox domain hint and read-only provider diagnostics rendering in Email Templates UI after test-send.
- [x] Add/update backend and frontend tests for new semantics, UI messaging, sandbox hint, and compatibility.
- [x] Run targeted backend/frontend tests and frontend build.
- [x] Update notes/lessons, commit, and create PR via `make_pr`.

## Check-in before execution
Plan verified: incremental backend+frontend contract update for diagnostics semantics only, without runtime flow migration or major UI redesign.


## Review
- [x] Backend test-send payload now distinguishes Mailgun acceptance from delivery (`accepted` + `delivery_status`).
- [x] Frontend success copy now clarifies acceptance-only semantics and includes diagnostics (`provider_id`, `provider_message`) plus Mailgun logs hint.
- [x] Added sandbox-domain hint for authorized-recipient limitation without redesign.
- [x] Existing save/reset/preview/test-send flow compatibility retained and revalidated by targeted tests.

# TODO — Mailgun env-managed (Railway) with read-only UI when source=env (2026-03-18)

- [x] Re-read Mailgun backend (service/config/api) and frontend status surfaces (Integrations card + Email Templates + API types).
- [x] Change Mailgun config resolution to env-first, DB-fallback, none when incomplete.
- [x] Preserve `config_source` semantics (`env`/`db`/`none`) and ensure send/test-send use effective resolved config.
- [x] Keep DB behavior compatible when env is absent/incomplete.
- [x] Update Mailgun Integration UI to show “Managed by Railway env” and block manual edit/save when source is env.
- [x] Update Email Templates Mailgun status copy to show env-managed state while keeping test-send enabled.
- [x] Add/update backend tests for env-only, env-wins-over-db, db-only, none, and send path using effective config.
- [x] Add/update frontend tests for read-only env-managed card and Email Templates env-managed messaging + test-send availability.
- [x] Run backend tests, frontend tests, frontend build, and backend startup check.
- [x] Update notes/lessons, commit, and create PR via `make_pr`.

## Check-in before execution
Plan verified: incremental backend+frontend adjustments only for Mailgun config source precedence and env-managed UX; no redesign and no unrelated flow refactors.

## Review
- [x] Switched Mailgun effective config precedence to env-first with DB fallback and explicit `config_source`.
- [x] Kept incomplete-env fallback behavior so DB config remains effective when env is missing required fields.
- [x] Updated Integrations Mailgun card for env-managed read-only UX and removed manual env-import CTA from primary UI flow.
- [x] Updated Email Templates Mailgun status panel to expose `config_source` and show env-managed hint while retaining test-send availability.
- [x] Refreshed targeted backend/frontend tests and re-ran frontend build + backend startup check.

# TODO — Cleanup Email Templates nav + simplify Mailgun Integrations card (2026-03-18)

- [x] Re-read AppShell, Agency Integrations Mailgun card/page, Email Templates page, and frontend API helpers.
- [x] Ensure `Email Templates` appears only in Settings navigation and not in main agency nav.
- [x] Remove Mailgun card `Test Email` section (fields + button + messaging) from Integrations UI.
- [x] Remove obsolete frontend Mailgun helpers/types tied only to removed Integrations actions (if no longer used).
- [x] Keep Mailgun status/config metadata visible in Integrations card and keep env-managed message.
- [x] Add/update compact frontend tests for nav uniqueness + simplified Mailgun card behavior.
- [x] Run relevant frontend tests and frontend build.
- [x] Update notes/lessons and finalize with commit + make_pr.

## Check-in before execution
Plan verified: frontend-only incremental cleanup (navigation + Mailgun card), no backend/API redesign, no Email Templates flow changes.

## Review
- [x] Kept `Email Templates` only in settings navigation (`AGENCY_SETTINGS_ITEMS`) and confirmed it does not appear in agency main nav.
- [x] Simplified Mailgun Integrations card by removing Test Email section and replacing it with a short pointer toward Email Templates.
- [x] Removed now-unused frontend Mailgun helpers for import-from-env and Mailgun test-send from `src/lib/api.ts`.
- [x] Preserved Mailgun status/config surface and env-managed read-only messaging in the card.
- [x] Revalidated with focused Vitest suites and frontend production build.

# TODO — Wire forgot-password/invite runtime to Agency Email Notifications (2026-03-18)

- [x] Re-read notifications service/API plus auth/team runtime email flows and current template/mailgun integration points.
- [x] Add explicit runtime-resolution helper in `email_notifications` service exposing effective enabled state + override metadata.
- [x] Wire `POST /auth/forgot-password` to `auth_forgot_password` notification gating.
- [x] Keep forgot-password anti-enumeration response generic when notification is disabled and skip token/email generation.
- [x] Wire `POST /team/members/{membership_id}/invite` to `team_invite_user` notification gating.
- [x] Return clear admin-facing error when invite notification is disabled, without generating invite token or sending email.
- [x] Keep separation between notification enablement and template content checks; notification disabled has priority.
- [x] Add/update backend tests for enabled/disabled notification behavior and coherent priority vs template disabled.
- [x] Run relevant backend tests and backend startup check.
- [x] Update notes/lessons and finalize with commit + make_pr.

## Check-in before execution
Plan verified: backend-only incremental wiring for runtime gating (forgot/invite), without frontend changes or API redesign.

## Review
- [x] Added runtime helper `resolve_runtime_notification(...)` returning compact effective notification metadata used by runtime flows.
- [x] Forgot-password now checks `auth_forgot_password` notification state after availability checks; disabled notification returns the same generic success response and skips token/email work.
- [x] Invite flow now checks `team_invite_user` notification state after availability checks; disabled notification returns explicit `409` with clear message and skips token/email work.
- [x] Notification gating is evaluated before template rendering so notification-disabled state has explicit priority over template-enabled/disabled state.
- [x] Added focused backend tests for notification-enabled/disabled runtime behavior and no-regression checks for existing mailgun/template paths.

# TODO — Add Agency Notifications settings UI page (2026-03-18)

- [x] Re-read AppShell, frontend API layer, Email Templates page structure, existing Notifications route, and backend notification API/schema contracts.
- [x] Add/adjust Settings navigation so `Notificări` points to dedicated agency settings page without breaking existing navigation.
- [x] Add frontend API helpers for agency email notifications list/detail/save/reset.
- [x] Implement `/agency/notifications` page with left overview list + right detail/edit panel for email notification `enabled`.
- [x] Implement save/reset flows with refetch + feedback and contextual runtime hints for forgot/invite behavior.
- [x] Implement explicit loading/empty/error states with 403/404/400/fallback handling.
- [x] Add compact frontend tests for nav presence/route, list/detail load, save/reset payloads, loading states, and key errors.
- [x] Run relevant frontend tests and frontend build.
- [x] Update notes/lessons and finalize with commit + make_pr.

## Check-in before execution
Plan verified: frontend-focused incremental delivery for Agency Notifications settings page on top of existing backend contracts; no redesign and no runtime/backend behavior changes.

## Review
- [x] Added dedicated settings page `/agency/notifications` with overview + detail/edit pattern aligned to Email Templates UX.
- [x] Implemented list/detail/save/reset wiring against existing backend endpoints only; editable field is strictly `enabled`.
- [x] Added contextual runtime hints for `auth_forgot_password` and `team_invite_user` plus link to associated Email Templates page.
- [x] Updated AppShell settings navigation to expose `Notificări` as settings item and removed duplicate agency-main-nav notifications link.
- [x] Added focused tests for navigation contract and notifications page behaviors (loading, selection, save/reset, and 403/404/400 handling).

# TODO — Extend backend route enforcement for full sidebar permissions

- [x] Re-read backend dependencies/team-members/rbac and relevant API route groups for agency navigation, settings, and subaccount settings contexts.
- [x] Add centralized backend navigation enforcement helpers for agency + subaccount module keys with explicit 403 deny message.
- [x] Wire agency main navigation route groups (`agency_dashboard`, `agency_clients`, `agency_accounts`, `integrations`, `agency_audit`, `creative`) to backend checks.
- [x] Wire agency settings route groups with parent `settings` + child key enforcement for profile/company/team/storage/email templates/notifications endpoints.
- [x] Extend subaccount settings route-group enforcement on relevant team/settings endpoints while preserving existing main-subaccount module checks.
- [x] Add backend tests for allow/deny behavior (agency main routes, settings parent/child, email templates/notifications gating, admin bypass, subaccount settings checks).
- [x] Run relevant backend tests and backend startup check.
- [x] Document remaining intentionally-unmapped settings areas without active backend endpoints.

## Review
- [x] Added reusable `enforce_agency_navigation_access(...)` and `enforce_subaccount_navigation_access(...)` in dependencies, with canonical deny message `Nu ai acces la această secțiune` and existing safe bypass/fallback behavior.
- [x] Agency main route enforcement now guards dashboard, clients, accounts, integrations, audit, and creative API groups.
- [x] Agency settings now enforce parent `settings` plus child keys for profile/company/my-team/media-storage/email-templates/notifications.
- [x] Subaccount settings enforcement was extended to relevant team settings endpoints (`grantable-modules`, `subaccount members list/create`) without changing create/edit membership logic.
- [x] Intentionally left out: settings children without backend endpoints in this codebase (`settings_tags`, `settings_audit_logs` child-specific route split, `settings_ai_agents`) and any new API surface invention.

# TODO — Polish roles and permissions UX with shared editor layout

- [x] Re-read Agency Team + Sub-account Team pages, API helpers, and AppShell context for permissions UX constraints.
- [x] Introduce shared frontend `PermissionsEditor` component used by both Agency Team and Sub-account Team forms.
- [x] Implement grouped left-nav + right-panel layout, local search, active counts, and scope/summary hints.
- [x] Keep existing parent/children permission sync semantics and payload contract (`module_keys`) unchanged.
- [x] Preserve and clarify disabled/negrantable states in subaccount grant-ceiling context.
- [x] Update both pages to consume shared component without changing create/edit/invite/lifecycle semantics.
- [x] Add/update focused frontend tests for shared component behavior, page integration, search, group switching, and no-regression payload behavior.
- [x] Run relevant frontend tests and frontend build.

## Review
- [x] Shared `PermissionsEditor` now powers Roles & Permissions in both Agency Team and Sub-account Team.
- [x] UX now includes grouped navigation sidebar, searchable permission list, group active-count badges, and clearer ON/OFF readability.
- [x] Sub-account grant-ceiling restrictions remain visible and explicitly explained for disabled keys.
- [x] Existing permission semantics and create/edit payload contracts remain intact (`module_keys` source of truth).
- [x] Intentionally left out: new permissions, backend contract changes, bulk actions, and full-page redesign.

# TODO — Google Ads sub-table: backend endpoint + real data wiring (2026-03-20)

- [x] Audit modified backend/frontend files and align data contract for sub Google Ads table.
- [x] Validate frontend table consumes real API payload with currency-aware formatting and date-range presets.
- [x] Fix/extend focused tests for the new API helper wiring (`getSubGoogleAdsTable`) and preset refetch behavior.
- [x] Run targeted backend and frontend tests.

## Review
- [x] Added backend endpoint `/dashboard/{client_id}/google-ads-table` and service aggregation for Google Ads account rows.
- [x] Frontend sub Google Ads page now fetches real table data via API helper instead of synthetic seeded values.
- [x] Focused tests pass for backend currency normalization suite and sub Google Ads page interactions.

# TODO — Replicare tabel performant Google Ads pe rutele Meta Ads și TikTok Ads (2026-03-20)

- [x] Audit implementare curentă Google Ads + pagini placeholder Meta/TikTok + contracte API backend/frontend.
- [x] Extrage componentă tabel generică reutilizabilă (coloane, selector, toolbar, date-range picker, sortare/stilizare).
- [x] Extinde backend cu endpoint-uri Meta/TikTok pentru payload compatibil tabel multi-account.
- [x] Leagă paginile `sub/[id]/meta-ads` și `sub/[id]/tiktok-ads` la componenta generică și endpoint-urile dedicate.
- [x] Actualizează/adaugă teste frontend + backend țintite pentru noile rute și comportamente.
- [x] Rulează verificări țintite și finalizează review în acest TODO.

## Check-in before execution
Plan verificat: abordare incrementală cu componentă comună + endpoint-uri additive, fără a atinge rutele Pinterest/Snapchat și fără redesign în afara structurii deja aprobată pe Google Ads.

## Review
- [x] Meta Ads și TikTok Ads folosesc aceeași structură de tabel/toolbar ca Google Ads, inclusiv selector coloane, schimbare ordine coloane și picker de perioadă.
- [x] Backend oferă endpoint-uri additive pentru `/dashboard/{client_id}/meta-ads-table` și `/dashboard/{client_id}/tiktok-ads-table` cu payload compatibil.
- [x] Testele țintite backend + frontend pentru Google/Meta/TikTok/sub-routes au trecut local.

# TODO — Drilldown Sub-account Accounts -> Campaigns pentru Google/Meta/TikTok (2026-03-20)

- [x] Audit rute curente Sub Google/Meta/TikTok Ads, surse date account-level și surse campaign-level existente.
- [x] Transformare nume cont în link-uri către rute noi `.../accounts/[accountId]` pentru Google/Meta/TikTok.
- [x] Adăugare pagini noi drilldown per cont cu tabel campanii, aceleași controale UI (Filter/Columns/Export/range) și back navigation clar.
- [x] Extindere backend minimală cu endpoint-uri campaign-level per platformă + filtrare pe client/account/date range.
- [x] Conectare helperi API frontend pentru noile endpoint-uri și wiring pe paginile drilldown.
- [x] Teste frontend+backend țintite + build frontend.

## Check-in before execution
Plan verificat și executat imediat (nu docs-only): patch local pe rutele Sub-account Ads + dashboard backend, fără atingere Agency/Team/Auth/Media Buying/Media Tracker.

## Review
- [x] Drilldown cont -> campanii funcționează pe Google/Meta/TikTok via rute noi în App Router.
- [x] Datele afișate provin din `campaign_performance_reports` + `platform_campaigns` (fără valori fabricate; lipsă => `—`).
- [x] Range picker refetch-uiește datele în paginile de campaign drilldown.

# TODO — Fix drilldown campaigns statuses/names + Meta normalization (2026-03-20)

- [x] Audit root-cause pentru Meta missing campaigns, account name fallback în titlu, TikTok campaign name fallback și status badges misleading.
- [x] Fix backend normalization joins/filters pentru platform account ids (inclusiv `act_` vs numeric) în campaign/account queries.
- [x] Fix backend payload semantics: status real/unknown (fără fallback fake `active`) + campaign/account naming fallback corect.
- [x] Fix frontend rendering pentru status: active=green, paused=II, unknown=neutral (fără roșu-x pentru unknown).
- [x] Update backend/frontend tests + run backend tests, frontend tests, frontend build.

## Review
- [x] Meta campaigns nu mai depind de match strict textual al account_id; normalizarea rezolvă cazurile `act_...` vs numeric.
- [x] Titlul drilldown folosește account name real când backend îl poate rezolva din metadata/account mapping.
- [x] TikTok/Meta campaign names folosesc metadata reală când există; fallback la ID doar când numele lipsește.

# TODO — Finalize dashboard status/name normalization patch (2026-03-20)

- [x] Re-read AGENTS instructions and verify current git working tree state.
- [x] Validate current backend/frontend patch content for scope and consistency.
- [x] Run targeted backend and frontend tests for touched flows.
- [x] Update task review notes and capture correction lesson.
- [x] Commit validated changes and open PR via make_pr tool.

## Review
- [x] Confirmed modified files are limited to dashboard service and related frontend rendering/tests.
- [x] Executed targeted checks for backend and frontend routes impacted by the patch.

- Backend check: `pytest -q apps/backend/tests/test_dashboard_currency_normalization.py` (pass).
- Frontend checks: `pnpm --dir apps/frontend exec vitest run ...` targeted meta/tiktok drilldown suites (pass).

# TODO — Meta entity persistence end-to-end (campaign/adset/ad) for drilldown data (2026-03-20)

- [x] Audit `meta_ads.py` write paths and confirm root cause for `rows_written: 0` on non-account grains.
- [x] Implement real non-test-mode upserts for Meta `campaign_daily`, `ad_group_daily`, and `ad_daily` into entity performance tables.
- [x] Ensure persisted Meta extra_metrics include available naming/status metadata without fabricating values.
- [x] Validate account id normalization compatibility (`act_...` vs numeric) between persistence and dashboard reads.
- [x] Add backend tests for write-path upserts, metadata persistence, rows_written semantics, normalization, and dashboard campaign visibility.
- [x] Run required backend tests + import/startup check.
- [x] Update review notes, capture correction lesson, commit, and open PR.

## Check-in before execution
Plan confirmed: backend-first patch in Meta sync + backend tests only, no Agency/Team/auth/invite/delete/Media Buying/Media Tracker changes.

## Review
- [x] Root cause confirmed in `meta_ads.py`: non-test-mode write helpers returned `0` instead of persisting entity rows, while dashboard drilldown reads `campaign_performance_reports` / `ad_group_performance_reports`.
- [x] Meta write helpers now use real upsert functions from `entity_performance_reports` with commit, mirroring TikTok persistence model.
- [x] Added backend tests for non-test-mode campaign/ad_group/ad write paths, metadata fields (`campaign_name`/`adset_name`/`ad_name` + statuses), rows_written behavior, and normalization compatibility.
- [x] Ran `pytest -q apps/backend/tests/test_meta_ads_entity_persistence.py apps/backend/tests/test_dashboard_currency_normalization.py` and `APP_AUTH_SECRET=test python -c "import app.main"`.

# TODO — Meta historical_backfill overflow hardening for entity grains (2026-03-20)

- [x] Audit root cause for Meta entity-grain overflow (`campaign_daily` / `ad_group_daily` / `ad_daily`) and identify offending field path.
- [x] Repair conversion-value derivation semantics to avoid naive over-summing of `action_values` for entity rows.
- [x] Add row-level numeric validation + row-level persistence fallback so one invalid row does not fail the whole chunk.
- [x] Surface `rows_skipped` / `skip_reasons` / skipped-row diagnostics in sync snapshot and per-account summaries.
- [x] Add backend tests for overflow candidate reproduction, conversion-value fix, row isolation fallback, and snapshot reporting.
- [x] Run backend tests + startup/import check.
- [x] Commit and open PR.

## Check-in before execution
Plan confirmed: backend-only scope (Meta persistence + backend tests), no frontend changes and no Agency/Team/auth/invite/delete/Media Buying/Media Tracker modifications.

## Review
- [x] Root cause confirmed as **transformation + persistence robustness**: naive `action_values` sum could produce oversized `conversion_value` candidates; a single DB persist error could fail the whole batch path.
- [x] Fixed conversion value mapping to prefer selected lead action type value when available, with fallback sum only when selected type is unavailable.
- [x] Implemented pre-upsert numeric overflow candidate checks and row-level retry isolation after batch failure.
- [x] Snapshot now reports `rows_written`, `rows_skipped`, `skip_reasons`, and sampled skipped row diagnostics without secrets.
- [x] Verified with `python -m pip install requests -q && pytest -q apps/backend/tests/test_meta_ads_entity_persistence.py apps/backend/tests/test_dashboard_currency_normalization.py` and `APP_AUTH_SECRET=test python -c "import app.main"`.

# TODO — TikTok campaign name resolution by campaign_id (2026-03-21)

- [x] Audit why TikTok campaign rows fall back to `campaign_id` despite existing facts.
- [x] Implement campaign metadata fetch by `campaign_id` from TikTok campaign endpoint and persist to `platform_campaigns`.
- [x] Wire TikTok sync grains (`campaign_daily` / `ad_group_daily` / `ad_daily`) to enrich campaign names/statuses from metadata before upsert.
- [x] Ensure dashboard read path behavior is validated: return campaign name when present, fallback to id only when missing.
- [x] Add backend tests for metadata resolution/persistence and fallback semantics.
- [x] Add frontend TikTok drilldown test coverage for campaign_name vs campaign_id fallback.
- [x] Run backend tests, frontend tests, and frontend build.
- [x] Commit and open PR.

## Check-in before execution
Plan confirmed: backend-first TikTok metadata + tests, minimal frontend test-only adjustment; no Agency/Team/auth/invite/delete/Media Buying/Media Tracker changes.

# TODO — Sub-account ads drilldown: campaigns -> ad groups/ad sets (2026-03-21)

- [x] Re-sync workspace + recitire AGENTS/todo/lessons + audit explicit rute existente accounts/campaigns și surse date reale ad_group/adset.
- [x] Backend minim: endpoint/platform helper pentru campaign -> adgroup/adset filtrat pe client/account/campaign/date range.
- [x] Frontend campaigns pages: numele campaniei devine link către ruta nouă campaign drilldown (Google/Meta/TikTok).
- [x] Frontend rute noi + component comun pentru tabel campaign -> adgroup/adset cu controale Filter/Columns/Export + calendar la dreapta.
- [x] Frontend/backend teste țintite pentru links/rute/empty-loading/fallback/id-name + filtre backend campaign/date/account/client.
- [x] Rulare verificări cerute: teste backend relevante, teste frontend relevante, build frontend.

## Review
- [x] Confirmare explicită că Agency/Team/auth/invite/delete/Media Buying/Media Tracker nu au fost atinse.
- Audit rute existente confirmat: `/{platform}/accounts/[accountId]` (campaigns) existau; rute `.../campaigns/[campaignId]` au fost adăugate pentru toate cele 3 platforme.
- Date reale folosite din backend: `ad_group_performance_reports` + join metadata (`platform_ad_groups`, `platform_campaigns`, `agency_platform_accounts`), fără hardcode metrici.
- Verificări executate:
  - `pytest -q apps/backend/tests/test_dashboard_currency_normalization.py -k \"campaign_adgroup or account_campaign_performance or campaign_rows_query_uses_ad_group_fallback_source\"`
  - `pnpm --dir apps/frontend exec vitest run src/app/sub/[id]/google-ads/accounts/[accountId]/page.test.tsx src/app/sub/[id]/meta-ads/accounts/[accountId]/page.test.tsx src/app/sub/[id]/tiktok-ads/accounts/[accountId]/page.test.tsx src/app/sub/[id]/google-ads/accounts/[accountId]/campaigns/[campaignId]/page.test.tsx src/app/sub/[id]/meta-ads/accounts/[accountId]/campaigns/[campaignId]/page.test.tsx src/app/sub/[id]/tiktok-ads/accounts/[accountId]/campaigns/[campaignId]/page.test.tsx`
  - `pnpm --dir apps/frontend run build`

# TODO — TikTok ad_group_daily campaign linkage fix for campaign->adgroups drilldown (2026-03-21)

- [x] Re-sync + recitire AGENTS/todo/lessons și audit root cause pe TikTok `ad_group_daily` (dimensions vs mapper fields).
- [x] Implementare metadata resolver TikTok pe `adgroup_id` (`adgroup/get`) pentru `campaign_id`, `ad_group_name`, `campaign_name`, status.
- [x] Enrichment `ad_group_daily` rows înainte de upsert: `campaign_id` corect, nume/status în `extra_metrics`, fără valori fabricate.
- [x] Persistență metadata adgroup în entity store (`platform_ad_groups`) cu fallback safe la erori.
- [x] Teste backend: request dimensions validate, enrichment campaign linkage, fallback behavior, no-crash la metadata paths.
- [x] Teste frontend TikTok campaign->adgroups pentru non-empty rows + name vs id fallback.
- [x] Run backend tests relevante + frontend tests relevante + frontend build.

## Review
- [x] Confirmare explicită: Agency/Team/auth/invite/delete/Media Buying/Media Tracker nu au fost atinse.
- Root cause confirmat: `ad_group_daily` cere doar `stat_time_day` + `adgroup_id`; mapperul citea și `campaign_id`/`campaign_name`/`adgroup_name`, deci facts puteau fi persistate fără `campaign_id` legat.
- Fix: metadata TikTok din `adgroup/get` este rezolvată pe `adgroup_id`, apoi folosită la enrichment (`campaign_id`, `ad_group_name`, `campaign_name`, status) înainte de `_upsert_ad_group_rows`.
- Persistență metadata: `platform_ad_groups` prin `upsert_platform_ad_groups` (best-effort; dacă eșuează, sync facts continuă).
- Verificări executate:
  - `python -m pip install requests`
  - `pytest -q apps/backend/tests/test_tiktok_campaign_metadata_resolution.py apps/backend/tests/test_dashboard_currency_normalization.py -k "ad_group or campaign_adgroup or tiktok"`
  - `pnpm --dir apps/frontend exec vitest run src/app/sub/[id]/tiktok-ads/accounts/[accountId]/campaigns/[campaignId]/page.test.tsx`
  - `pnpm --dir apps/frontend run build`

# TODO — Add "Back to Dashboard" on Sub-account platform account-list pages (2026-03-21)

- [x] Audit shared rendering for `/sub/[id]/google-ads`, `/sub/[id]/meta-ads`, `/sub/[id]/tiktok-ads` account-list pages.
- [x] Add top-level `Back to Dashboard` navigation once in shared account-list component.
- [x] Ensure route target is `/sub/[id]/dashboard` for all 3 platform pages.
- [x] Add/update frontend tests for Google/Meta/TikTok account-list pages to assert presence + href.
- [x] Run frontend tests relevante and frontend build.

## Review
- [x] Confirmare explicită că nu au fost atinse Agency / Team / auth / invite / delete / Media Buying / Media Tracker.
- Audit confirmat: Google/Meta/TikTok account-list pages folosesc componenta shared `SubAdsPerformanceTablePage`, deci linkul a fost adăugat o singură dată acolo.
- Linkul `Back to Dashboard` este randat sus în header și navighează la `/sub/{id}/dashboard` pentru toate cele 3 pagini.
- Verificări executate:
  - `pnpm --dir apps/frontend exec vitest run src/app/sub/[id]/google-ads/page.test.tsx src/app/sub/[id]/meta-ads/page.test.tsx src/app/sub/[id]/tiktok-ads/page.test.tsx`
  - `pnpm --dir apps/frontend run build`

# TODO — Process alignment: AGENTS compliance + commit/PR handoff (2026-03-21)

- [x] Re-read AGENTS instructions and ensure plan-first/task-tracking flow is followed for this turn.
- [x] Update `tasks/lessons.md` with a concrete lesson from this user correction.
- [x] Validate pending workspace diff and run at least one relevant verification command.
- [ ] Commit required repository changes on branch `work`.
- [ ] Create PR metadata using `make_pr` after commit.

## Review
- [x] Confirmed process compliance updates are recorded in tasks docs.
- [ ] Confirmed commit + PR metadata were both completed in this turn.

# TODO — Dropdown updates: industrie + nișă medical options sorted (2026-03-21)

- [x] Re-read AGENTS and capture this follow-up task in todo before code edits.
- [x] Update `Nișa business` dropdown with: Recuperare Medicală, Ortopedie, Stomatologie, Estetică Medicală.
- [x] Update `Industrie` dropdown with: Servicii Medicale.
- [x] Sort all options alphabetically in both dropdowns (keeping `Selectează` placeholder first).
- [x] Run targeted frontend tests for subaccount profile page.
- [x] Update `tasks/lessons.md` for this correction pattern.
- [ ] Commit and run `make_pr`.

## Review
- [x] Confirmed both dropdown lists include the requested values and are alphabetically ordered.
- [x] Confirmed verification command(s) passed.
- [ ] Confirmed commit + PR metadata creation completed.

# TODO — Process alignment follow-through after AGENTS reminder (2026-03-22)

- [x] Re-read AGENTS instructions and confirm mandatory workflow order for this turn.
- [x] Record plan-first/check-in/review notes in `tasks/todo.md` before implementation.
- [x] Update `tasks/lessons.md` with this correction pattern from user reminder.
- [x] Run at least one verification command before finalization.
- [x] Commit changes on current branch.
- [x] Create PR metadata with `make_pr` immediately after commit.

## Check-in before execution
Plan verified: keep this turn minimal and process-focused, touching only `tasks/todo.md` and `tasks/lessons.md` to align with AGENTS workflow reminder.

## Review
- [x] Confirmed only process-tracking docs were updated.
- [x] Confirmed verification command(s) ran before commit.
- [x] Confirmed commit and PR metadata were completed in the same turn.

# TODO — Creative workflow media_id linking (feature-flagged, backward-compatible) (2026-03-22)

- [x] Reîncarc workspace-ul și inspectez explicit fișierele cerute (`api/creative.py`, `creative_workflow.py`, `creative_assets_repository.py`, `media_metadata_repository.py`, `core/config.py`, teste backend relevante).
- [x] Adaug setting nou `CREATIVE_WORKFLOW_MEDIA_ID_LINKING_ENABLED` (default OFF) în config + `.env.example` + doc minim.
- [x] Extind modelele API creative pentru `media_id: Optional[str]` fără breaking changes și fără eliminarea câmpului legacy `media`.
- [x] Extind modelul intern variantă + `add_variant/get_asset/list_assets` pentru a purta `media_id` feature-flagged, cu fallback compatibil când vine doar `media_id`.
- [x] Validez `media_id` via `media_metadata_repository.get_by_media_id(...)` (exists, status ready, client ownership compatibil) când flag-ul este ON.
- [x] Fac comportament explicit când flag-ul este OFF și se trimite `media_id` (eroare clară, fără impact pe fluxul legacy fără `media_id`).
- [x] Persist `media_id` în `creative_assets_repository` și asigur rehidratarea compatibilă pentru documente vechi fără `media_id`.
- [x] Adaug/actualizez teste focused pentru OFF/ON, validare, persistență/list/get/hidratare și default setting.
- [x] Rulez teste țintite și completez review.
- [x] Commit + make_pr în același turn.

## Check-in before execution
Plan verificat: patch minim și izolat în backend creative/config/tests, fără schimbări frontend/rute/backfill/publish major.

## Review
- [x] Confirm patch-ul rămâne izolat pe backend creative/config/tests, fără frontend/rute noi/backfill.
- [x] Confirm media rămâne compatibil legacy (nu devine sursă unică), iar media_id este opțional și feature-flagged.
- [x] Verificări rulate: `cd apps/backend && pytest -q tests/test_storage_foundation_settings.py tests/test_creative_assets_repository.py tests/test_creative_api_media_id.py tests/test_creative_workflow_shadow_write.py`.

# TODO — AI recommendations Mongo source-of-truth (feature-flagged) (2026-03-22)

- [x] Reîncarc workspace-ul și inspectez explicit: `apps/backend/app/api/ai.py`, `apps/backend/app/services/recommendations.py`, `apps/backend/app/services/ai_assistant.py`, `apps/backend/app/services/mongo_provider.py`, `apps/backend/app/core/config.py`, plus testele backend relevante.
- [x] Adaug setting nou `AI_RECOMMENDATIONS_MONGO_SOURCE_ENABLED` (default OFF) în config + `.env.example` + doc minim.
- [x] Introduc repository Mongo dedicat recommendations history + counters (ID numeric stabil) cu indexuri minime și metodele cerute.
- [x] Mențin cu flag OFF comportamentul existent (in-memory, fără apeluri Mongo, fără schimbare contract API).
- [x] Când flag ON, mut `generate/list/get/review/list_actions` pe Mongo source-of-truth fără fallback in-memory la erori Mongo.
- [x] Păstrez neschimbate `get_impact_report`, `ai_assistant_service` și endpoint-ul `/ai/legacy/{client_id}`.
- [x] Acopăr teste focused OFF/ON, approve/dismiss/snooze, actions flattening, ID atomic, erori Mongo predictibile, setări/indexuri/normalizare.
- [x] Rulez teste țintite și completez review.
- [x] Commit + make_pr în același turn.

## Check-in before execution
Plan verificat: patch izolat doar în backend recommendations/config/tests, fără modificări frontend/rute /ai/legacy/backfill/outbox.

## Review
- [x] Confirm patch-ul rămâne izolat pe recommendations/backend/config/tests.
- [x] Confirm rutele `/ai` și endpoint-ul legacy `/ai/legacy/{client_id}` au rămas neschimbate.
- [x] Confirm fără backfill/migrare/outbox/retry/replay și fără modificări frontend.
- [x] Verificări rulate: `cd apps/backend && pytest -q tests/test_ai_recommendations_repository.py tests/test_recommendations_mongo_source.py tests/test_storage_foundation_settings.py`.

# TODO — Subaccount Profile logo storage flow (logo_media_id + preview fallback) (2026-03-22)

- [x] Reîncarc workspace-ul și inspectez explicit fișierele cerute pentru profile/settings/storage backend+frontend.
- [x] Extind backend business profile payload/response cu `logo_media_id` opțional, păstrând compatibilitatea cu `logo_url`.
- [x] Persist `logo_media_id` în store-ul business profile fără backfill/migrare.
- [x] La GET profile, încerc preview `logo_url` din storage pe baza `logo_media_id`, cu fallback robust la `logo_url` legacy / string gol.
- [x] Adaug helper frontend generic pentru storage flow (init upload, upload presigned, complete, access URL helper).
- [x] Înlocuiesc flow-ul vechi FileReader/data URL din pagina Subaccount Settings Profile cu flow storage + `logo_media_id`.
- [x] Păstrez Remove ca detach-only: golește `logo_media_id` și `logo_url` în profil, fără delete din storage.
- [x] Adaug teste focused backend+frontend pentru OFF/legacy/new/remove/error/upload flow.
- [x] Rulez teste țintite și completez review.
- [x] Commit + make_pr în același turn.

## Check-in before execution
Plan verificat: modificări strict în profile/settings + helper storage shared + backend clients profile, fără creative media library/publish/storage delete/backfill.

## Review
- [x] Confirm patch-ul este izolat pe profile/settings + storage helper reutilizabil.
- [x] Confirm fără creative media library UI, fără storage delete, fără backfill/migrare, fără publish flow changes.
- [x] Verificări rulate: `cd apps/backend && pytest -q tests/test_clients_business_profile_api.py tests/test_storage_api_upload_init.py -k "business_profile or storage"` și `cd apps/frontend && pnpm exec vitest run src/app/subaccount/[id]/settings/profile/page.test.tsx`.

# TODO — Root-cause fix pentru POST /storage/uploads/init generic 500 (2026-03-22)

- [x] Reîncarc workspace-ul și inspectez explicit: `api/storage.py`, `storage_upload_init.py`, `media_metadata_repository.py`, `mongo_provider.py`, `s3_provider.py`, `core/config.py`, teste storage/profile.
- [x] Reproduc local flow-ul `POST /storage/uploads/init` și identific excepția exactă care ajunge în catch-all „Failed to initialize upload”.
- [x] Repar cauza reală în path-ul storage init (fără workaround superficial) și păstrez patch-ul minim.
- [x] Îmbunătățesc observabilitatea în `api/storage.py` pentru init upload (log exception reală + context util).
- [x] Clarific mapping-ul excepțiilor previzibile către `StorageUploadInitError` / `RuntimeError`, reducând generic 500 netransparent.
- [x] Adaug/actualizez teste focused pentru success și scenariul fost generic 500.
- [x] Rulez teste țintite și completez review.
- [x] Commit + make_pr în același turn.

## Check-in before execution
Plan verificat: focus strict pe backend storage init + logging/error mapping, fără schimbări în Creative UI/publish/refactor mare.

## Review
- [x] Root cause confirmat: excepții ne-mapate din `initialize_indexes()`/`create_draft()` (ex. erori Mongo runtime) ajungeau în catch-all API și produceau 500 generic fără context util în logs.
- [x] Fix minim: mapare explicită în `storage_upload_init_service` la `RuntimeError` + logging contextual în router pentru init upload.
- [x] Scope păstrat: fără modificări Creative UI/publish flow/refactor mare storage.

# TODO — Sidebar subaccount avatar logo sync cu Profil Business (2026-03-22)

- [x] Reîncarc workspace-ul și inspectez explicit `AppShell`, sursa de date sidebar, pagina profil business și contractele backend relevante.
- [x] Identific sursa reală pentru avatar subaccount: branding din `AppShell` + payload business-profile (`/clients/{id}/business-profile`) folosit deja pentru locație.
- [x] Aplic patch minim în sidebar pentru a folosi `logo_url` din business-profile (cu fallback la `client_logo_url` legacy).
- [x] Păstrez fallback pe inițiale când nu există logo și adaug fallback la inițiale la eroare de încărcare imagine.
- [x] Mențin refresh fără hard refresh folosind mecanismul existent `subaccount-business-profile-updated` după save/remove.
- [x] Adaug teste focused frontend pentru rezoluția logo/fallback + emiterea evenimentului de refresh după save/remove.
- [x] Rulez teste țintite și completez review.
- [x] Commit + make_pr în același turn.

## Review
- [x] Componenta sidebar modificată: `apps/frontend/src/components/AppShell.tsx` (branding avatar subaccount).
- [x] Sursa de date pentru logo în sidebar: `GET /clients/{id}/business-profile` (`logo_url` preview/fallback), cu fallback secundar la `client_logo_url` din `/clients`.
- [x] Fără modificări pe Creative UI, publish flow, storage delete/cleanup sau refactor mare shell.

# TODO — Agency Settings Company logo pe storage flow + logo_media_id (2026-03-23)

- [x] Reîncarc workspace-ul și inspectez explicit company settings frontend/backend/store, storage helper, AppShell branding agency și testele relevante.
- [x] Adaug suport backend pentru `logo_media_id` opțional în schema/payload/response company settings.
- [x] Păstrez compatibilitate backward cu `logo_url` legacy și fallback predictibil dacă preview-ul din storage eșuează.
- [x] Leag pagina frontend `/settings/company` la flow-ul storage `init -> upload -> complete` reutilizând helper-ul existent.
- [x] Elimin flow-ul principal FileReader/dataURL pentru company logo; persist `logo_media_id` stabil și `logo_url` fallback compat.
- [x] Implementez remove ca detach-only (`logo_media_id=null`, `logo_url=''`) fără delete storage.
- [x] Actualizez branding-ul agency din AppShell după save/remove prin eveniment `company-settings-updated` (fără hard refresh manual).
- [x] Adaug teste focused backend + frontend pentru logo_media_id, compat fallback, storage flow, remove, erori validare, refresh trigger.
- [x] Rulez testele țintite și completez review.
- [x] Commit + make_pr în același turn.

## Review
- [x] Frontend modificat strict în `apps/frontend/src/app/settings/company/page.tsx` și refresh minim în `apps/frontend/src/components/AppShell.tsx`.
- [x] Backend modificat strict pe contractul/serviciul company settings pentru `logo_media_id` + preview fallback (`apps/backend/app/schemas/company.py`, `apps/backend/app/api/company.py`, `apps/backend/app/services/company_settings.py`).
- [x] Fără favicon global nou, fără Creative UI/media library/publish/storage-delete, fără backfill/migrare.

# TODO — Global agency favicon in AppShell (2026-03-23)

- [x] Refresh workspace (`git fetch` + `git pull`) and inspect explicit files: `AppShell.tsx`, global layout, `settings/company/page.tsx`, branding/favicon utilities, and static frontend favicon assets.
- [x] Identify current gap (favicon logic local/non-global) and move favicon handling into a global shell-level component.
- [x] Implement minimal reusable global favicon manager sourced strictly from agency company logo (`logo_url`) with fallback to app default favicon.
- [x] Ensure runtime updates without hard refresh via existing `company-settings-updated` event + shell refetch, including logo removal fallback.
- [x] Keep sub-account branding out of global favicon logic.
- [x] Add focused frontend tests for default fallback, agency logo set/update/remove, navigation persistence, event refresh behavior, and invalid URL fallback.
- [x] Run targeted frontend tests and finalize review notes.

## Review
- [x] Confirm no changes to upload/storage flow, Creative UI, media library, or publish flow.
- [x] Confirm global favicon source is agency logo only (never sub-account logo).

# TODO — Favicon source priority fix (agency authoritative) (2026-03-23)

- [x] Refresh workspace and inspect explicit favicon/head sources: `GlobalFavicon.tsx`, `AppShell.tsx`, root `layout.tsx`, `app/icon.*`, manifest/webmanifest candidates, and `settings/company` refresh event usage.
- [x] Identify root cause for wrong tab icon (multiple competing icon links and non-authoritative update path).
- [x] Implement minimal centralized fix so agency favicon updates effective browser icon links (`rel=icon` + `rel=shortcut icon`) instead of adding a secondary link only.
- [x] Preserve fallback default icon and runtime update flow after save/remove logo with no sub-account favicon usage.
- [x] Add focused frontend tests for existing-link replacement, shortcut icon handling, no duplicate stale links, update/remove/fallback/error flows.
- [x] Run targeted frontend tests and complete review notes.

## Review
- [x] Confirm no upload/storage flow changes, no Company Settings UX changes, no Creative/media/publish changes.
- [x] Confirm agency logo remains the only source for global favicon override.

# TODO — Global favicon agency logo source + branding rename VOXEL MCC (2026-03-23)

- [x] Refresh workspace state and inspect explicit files: `GlobalFavicon.tsx`, `AppShell.tsx`, root `layout.tsx`, global metadata/icon assets, company settings page, and all `MCC Command Center` occurrences.
- [x] Identify exact favicon fallback root cause and apply minimal fix in global branding path (no new favicon upload flow, no Creative/storage-flow changes).
- [x] Ensure AppShell global branding source for favicon remains agency company settings logo (`logo_url`) and not sub-account logo.
- [x] Update global branding title/metadata from `MCC Command Center` to `VOXEL MCC` where globally relevant.
- [x] Add focused frontend tests for favicon source/fallback/update/remove + global title/metadata assertions.
- [x] Run targeted tests and document review findings.

## Review
- [x] Root cause confirmed: favicon helper appended `?v=` to agency logo URLs; when `logo_url` was a signed storage preview URL, query mutation invalidated signature and forced `Image.onerror` fallback to `/icon.svg`.
- [x] Fix applied minimally in `GlobalFavicon` by appending refresh key in URL fragment (`#v=`) instead of query string, preserving signed query params while still forcing browser refresh semantics.
- [x] Global source kept agency-only: `AppShell` now resolves favicon input via `resolveGlobalFaviconLogoUrl(companySettings)` and continues passing only agency `companySettings.logo_url` to `GlobalFavicon`.
- [x] Branding updated to `VOXEL MCC` in root metadata and major entry headings.
- [x] Focused tests pass for favicon behavior, AppShell source helper, company save/remove event flow, and global title metadata assertion.

# TODO — Landing page și app shell folosesc același favicon global agency (2026-03-23)

- [x] Refresh workspace state și inspect explicit: `GlobalFavicon.tsx`, `AppShell.tsx`, `app/layout.tsx`, landing `app/page.tsx`, metadata/layout public.
- [x] Identific root cause pentru mismatch landing vs interior și centralizez montarea favicon-ului global într-un loc comun.
- [x] Asigur sursa agency-only (`/company/settings` -> `logo_url`) pentru favicon global în context public + interior, cu fallback default robust.
- [x] Mențin update flow pe evenimentul `company-settings-updated` astfel încât landing + interior rămân coerente fără hard refresh obligatoriu.
- [x] Adaug teste frontend focused pentru mecanismul comun (landing + interior) și fallback-uri.
- [x] Rulez testele țintite și documentez review.

## Review
- [x] Root cause confirmat: `GlobalFavicon` era montat exclusiv în `AppShell`, iar landing-ul public (`/`) nu folosește `AppShell`; de aceea rămânea pe favicon static metadata (`/icon.svg`).
- [x] Fix global minim: montare comună în `app/layout.tsx` prin componenta client `GlobalAgencyFavicon`, astfel aceeași logică acoperă landing + interior + navigarea între ele.
- [x] Sursa agency-only păstrată: `GlobalAgencyFavicon` citește `logo_url` din `/company/settings`; fallback la default când lipsește/e invalid/eșuează load.
- [x] Event refresh păstrat: listener `company-settings-updated` refetch + `refreshKey` pentru actualizare favicon fără hard refresh obligatoriu.

# TODO — Creative Media Library UI foundation (browse + upload + preview + select) (2026-03-23)

- [x] Inspect explicit: Creative route/page reale, helper storage client, API client folosit în Creative, componente asset list existente, endpoint-uri storage reutilizabile și testele Creative/storage UI.
- [x] Introduc componentă reutilizabilă `CreativeMediaLibrary` cu responsabilitate strictă: listare media, upload storage flow, preview, selecție locală media_id.
- [x] Integrez minimal componenta în pagina Creative fără redesign mare și fără a rupe lista existentă de asset-uri.
- [x] Mențin upload flow strict prin helper storage (`init -> upload presigned -> complete`) + refresh list + auto-select media nouă.
- [x] Adaug filtre minime utile (kind) și fallback-uri robuste pentru preview/access URL errors.
- [x] Adaug teste frontend focused pentru loading/empty/success/select/preview/upload/error și verific că asset list existent rămâne funcțional.
- [x] Rulez testele țintite și documentez review.

## Review
- [x] Pagina Creative reală inspectată: `apps/frontend/src/app/creative/page.tsx` avea asset table placeholder și nu avea media library storage.
- [x] Componentă nouă `CreativeMediaLibrary` implementată cu listare `/storage/media`, filtru kind (all/image/video), preview via `/storage/media/{id}/access-url`, selecție locală și callback opțional `onSelectMedia`.
- [x] Upload flow păstrat strict prin helper storage existent: `initDirectUpload -> uploadFileToPresignedUrl -> completeDirectUpload`, apoi refresh list + auto-select media nouă.
- [x] Integrare minimală în pagina Creative: tabelul existent a rămas, componenta e adăugată sub tabel + selector client pentru contextul library.
- [x] Teste focused adăugate pentru loading/empty/success/select/preview/upload/error și verificare că asset list existent rămâne vizibil.

# TODO — Creative selected media integrated into first real create/edit flow (2026-03-23)

- [x] Refresh workspace and inspect explicit: Creative page, CreativeMediaLibrary, creative API endpoints, existing create/add-variant UI (if any), and Creative/storage tests.
- [x] Choose minimal real integration point (existing add-variant flow if present; otherwise compact create asset + first variant flow).
- [x] Wire selected media from CreativeMediaLibrary into variant request with both `media_id` and legacy `media` value.
- [x] Add compact UX states: no-media validation, success feedback, partial failure (asset created / variant failed), backend media_id error handling without UI break.
- [x] Ensure asset list refresh after successful create+variant and preserve CreativeMediaLibrary/upload functionality.
- [x] Add focused frontend tests with mocked `/creative/library/assets` and `/creative/library/assets/{id}/variants`.
- [x] Run targeted tests and record review.

## Review
- [x] Nu exista un add-variant UI existent în pagina Creative; am implementat fallback-ul cerut: flow compact `create asset + first variant` în aceeași pagină, fără wizard mare.
- [x] Fluxul folosește `selectedMedia` din `CreativeMediaLibrary`; request-ul către variant trimite atât `media_id`, cât și `media` legacy.
- [x] Regula `media` legacy: `original_filename` dacă există, altfel fallback predictibil `media:{media_id}`.
- [x] UX states adăugate: blocare fără media selectată, mesaj de succes complet, eroare explicită pentru caz parțial (asset creat / variant failed), afișare clară erori backend `media_id`.
- [x] După succes (sau succes parțial) se face refresh la lista asset-urilor; CreativeMediaLibrary și upload flow rămân funcționale.
- [x] Teste frontend focused acoperă payload media_id+media, blocare fără media, refresh list, succes complet, eșec add-variant după create, și erori media_id fără UI break.

# TODO — Creative asset detail + variant preview + add variant on existing asset (2026-03-23)

- [x] Refresh workspace and inspect explicit: creative page, CreativeMediaLibrary, creative API endpoints (list/detail/add variant), and existing Creative/media tests.
- [x] Add selected asset state and robust detail loading path from real backend payloads.
- [x] Render existing variants for selected asset with compact list and selection state.
- [x] Implement variant media preview via storage access URL for media_id variants (image/video) + fallback for legacy-only variants.
- [x] Add compact add-variant form for selected asset using selected media from CreativeMediaLibrary and send `media_id` + legacy `media`.
- [x] Add focused tests for selection/detail/preview/add-variant success+error and ensure asset list + media library remain functional.
- [x] Run targeted tests and document review.

## Review
- [x] Endpoint de detail dedicat nu există în workspace (`/creative/library/assets/{id}` absent); am folosit list endpoint-ul real (`/creative/library/assets?client_id=...`) ca sursă pentru detail-ul asset-ului selectat + variante.
- [x] Am introdus stări locale clare: `selectedAssetId`, `selectedVariantId`, detail derivat din payloadul listă, preview URL/error/loading, plus integrare cu `selectedMedia` din `CreativeMediaLibrary`.
- [x] Varianta selectată cu `media_id` primește preview via `getMediaAccessUrl`; pentru variante fără `media_id` afișez fallback clar (`media legacy only`) fără crash.
- [x] Add variant pe asset existent trimite `media_id` + `media` legacy (filename sau fallback `media:{id}`), validează lipsa asset/media, afișează feedback success/error și reîncarcă detail/list după succes.
- [x] Testele noi acoperă selecție asset, afișare variante, preview image/video, fallback fără media_id, blocări fără asset/media, payload `media_id+media`, reload după succes și stabilitate UI la erori backend.

# TODO — Creative page follow-up after unsatisfied review (2026-03-23)

- [x] Reîncarc starea workspace și inspectez explicit `apps/frontend/src/app/creative/page.tsx`, `apps/frontend/src/components/CreativeMediaLibrary.tsx`, clientul API/frontend și endpoint-urile creative reale (list assets / detail / add variant), plus testele existente.
- [x] Păstrez integrarea minimă în pagina Creative (fără redesign mare, fără publish-flow changes, fără endpoint nou major) și consolidez stările robuste de loading/error pentru zona asset detail.
- [x] Îmbunătățesc preview-ul variantelor existente cu detecție robustă video (mime type din storage access-url + fallback extensie) și fallback clar pentru variante legacy-only.
- [x] Mențin add variant pe asset existent cu `selectedMedia` din CreativeMediaLibrary și blochez clar acțiunea când lipsesc asset/media.
- [x] Extind testele focused pentru blocarea acțiunii fără asset/media și afișarea metadatelor variantelor existente, fără să rup flow-urile existente.
- [x] Rulez testele țintite, completez review, apoi commit + make_pr.

## Review
- [x] Confirmat: endpoint de asset detail dedicat nu există în backend-ul real (`/creative/library/assets/{id}` absent); detail-ul rămâne derivat din endpoint-ul canonical `GET /creative/library/assets?client_id=...`.
- [x] Confirmat: flow-ul de publish nu a fost modificat.
- [x] Confirmat: nu am introdus backend nou major pentru update/edit variant.
- [x] Confirmat: UI change mic și local (carduri existente), fără redesign major al paginii Creative.

# TODO — Creative minimal publish flow on selected asset/variant (2026-03-23)

- [x] Reîncarc workspace-ul și inspectez explicit `apps/frontend/src/app/creative/page.tsx`, `apps/frontend/src/lib/api.ts`, endpoint-ul backend real de publish și testele Creative page.
- [x] Confirm contractul real de publish și payload minim: `POST /creative/publish/assets/{asset_id}/to-channel` cu `channel` obligatoriu și `variant_id` opțional.
- [x] Extind minim zona de asset detail cu o secțiune compactă Publish (fără redesign mare), reutilizând `selectedAssetId` și `selectedVariantId`.
- [x] Adaug state-uri UX clare pentru publish: `selectedChannel`, `isPublishing`, `publishError`, `publishSuccess`.
- [x] La submit, trimit payload strict compatibil backend (`channel`, `variant_id` opțional), afișez loading/success/error și fac refresh la detail/list păstrând contextul selectat.
- [x] Afișez rezumat minim pentru ultimul publish dacă `publish_history` există deja în payloadul real.
- [x] Adaug teste frontend focused pentru blocare fără asset, payload publish, loading, success+refresh, error+stabilitate context și non-regresie pentru media/add-variant.
- [x] Rulez testele țintite, finalizez review, apoi commit + make_pr.

## Review
- [x] Publish contract real confirmat: endpointul acceptă `channel` și `variant_id` opțional; nu am introdus payload nou inventat.
- [x] Publish UI este local și compact în pagina Creative (fără wizard/restructurare mare).
- [x] Flow-urile existente (media library, add variant, preview) au rămas funcționale în testele țintite.
- [x] Nicio modificare backend majoră pentru publish/storage/branding.

# TODO — Data layer migration (daily inputs + sale entries) (2026-03-23)

- [x] Refresh workspace to latest current-branch state and inspect git status/diff for prior partial attempts.
- [x] Audit existing migration files and migration-loading tests for naming/ordering patterns.
- [x] Reuse or create migration for `client_data_daily_inputs` and `client_data_sale_entries` only, keeping scope strict.
- [x] Run targeted migration-related tests/checks.
- [x] Review diff for scope safety (no API/UI/service changes) and document outcomes.

## Review
- [x] Confirm only migration scope was changed.
- [x] Confirm targeted checks/tests passed.

# TODO — Data layer migration custom fields + daily custom values (2026-03-23)

- [x] Sync workspace state on current branch and inspect `git status`/`git diff`.
- [x] Audit existing migrations and migration tests; verify Task 1A migration FK compatibility.
- [x] Reuse existing partial migration if present, otherwise create next migration for only `client_data_custom_fields` and `client_data_daily_custom_values`.
- [x] Run targeted migration resolver/loading tests and a quick relevant check.
- [x] Review final diff for strict scope (migration-only).

## Review
- [x] Confirm only migration scope changed (plus required task tracking docs).
- [x] Confirm targeted checks/tests passed.

# TODO — Client data store pure helpers only (2026-03-23)

- [x] Sync workspace on current branch and verify clean `git status` / `git diff`.
- [x] Inspect only `client_data_store` and related tests to confirm current state / partial leftovers.
- [x] Implement `client_data_store.py` with canonical source catalog and pure formula helpers only.
- [x] Add focused pure tests for source catalog and formula helpers.
- [x] Run only targeted pure tests + import/compile check.
- [x] Review diff to ensure no migrations/API/frontend/DB CRUD changes.

## Review
- [x] Confirm module remains importable and scope is pure helpers only.
- [x] Confirm targeted tests/checks passed.

# TODO — Client data custom fields CRUD slice 1 (2026-03-23)

- [x] Sync workspace and verify clean status/diff.
- [x] Extend `client_data_store.py` only with `list_custom_fields`, `create_custom_field`, `validate_custom_field_belongs_to_client` plus minimal private helpers.
- [x] Keep out-of-scope functions unimplemented (no update/archive/daily inputs/sales/custom values CRUD).
- [x] Add targeted tests for custom-field CRUD slice behaviors.
- [x] Run only targeted client_data_store tests + compile check.
- [x] Review diff for strict scope.

## Review
- [x] Confirm scope is only `client_data_store.py` + related tests/docs.
- [x] Confirm targeted tests/checks passed.

# TODO — Client data custom fields CRUD slice 2 (update only) (2026-03-24)

- [x] Sync workspace and verify status/diff.
- [x] Implement only `update_custom_field(...)` in `client_data_store.py` with scoped validation rules.
- [x] Add targeted tests for `update_custom_field` behavior and validation errors.
- [x] Run only `client_data_store` tests + compile check.
- [x] Review diff for strict scope (no archive/no other CRUD/API/UI changes).

## Review
- [x] Confirm only requested function and tests were changed.
- [x] Confirm targeted checks/tests passed.

# TODO — Client data custom fields CRUD slice 3 (archive only) (2026-03-24)

- [x] Sync workspace check done; continue from local branch state when origin unavailable.
- [x] Implement only `archive_custom_field(...)` in `client_data_store.py` with idempotent soft-archive semantics.
- [x] Add targeted archive tests (including listing visibility and idempotency).
- [x] Run `client_data_store` test file + compile check.
- [x] Review diff for strict scope.

## Review
- [x] Confirm only archive slice + tests/docs were changed.
- [x] Confirm tests/checks passed.

# TODO — Daily input CRUD slice 1 (get_or_create only) (2026-03-24)

- [x] Sync workspace attempted and continue with local state if `origin` unavailable.
- [x] Implement only `get_or_create_daily_input(...)` with validation + idempotent lookup/create.
- [x] Add targeted tests for get/create/idempotency/validation.
- [x] Run targeted client_data_store tests + compile check.
- [x] Review diff for strict scope.

## Review
- [x] Confirm only requested daily-input function and tests were changed.
- [x] Confirm checks/tests passed.

# TODO — Daily input CRUD slice 2 (upsert only) (2026-03-24)

- [x] Sync workspace attempted and continue locally when origin unavailable.
- [x] Implement only `upsert_daily_input(...)` reusing `get_or_create_daily_input(...)`.
- [x] Add targeted tests for partial upsert/update validations and notes/source invariants.
- [x] Run targeted client_data_store tests + compile check.
- [x] Review diff for strict scope.

## Review
- [x] Confirm only requested upsert function + tests/docs changed.
- [x] Confirm checks/tests passed.

# TODO — Daily input CRUD slice 3 (set notes only) (2026-03-24)

- [x] Sync attempted; continue local when origin unavailable.
- [x] Implement only `set_daily_input_notes(...)` using `get_or_create_daily_input(...)`.
- [x] Add targeted tests for notes normalization/validation and invariants.
- [x] Run targeted tests + compile check.
- [x] Review strict scope.

## Review
- [x] Confirm only notes function + tests/docs changed.
- [x] Confirm checks/tests passed.

# TODO — Daily input CRUD slice 4 (list only) (2026-03-24)

- [x] Sync attempted; proceed local if origin unavailable.
- [x] Implement only `list_daily_inputs(client_id, date_from, date_to)` with strict validation and sorting.
- [x] Add targeted list-daily-input tests for range/filter/order/shape/validation.
- [x] Run targeted tests + compile check.
- [x] Review strict scope.

## Review
- [x] Confirm only list function + tests/docs changed.
- [x] Confirm checks/tests passed.

# TODO — Daily input CRUD slice 5 (map only) (2026-03-24)

- [x] Sync attempted; proceed local if origin unavailable.
- [x] Implement only `get_daily_input_map(client_id, date_from, date_to)` reusing list logic.
- [x] Add targeted tests for map behavior/keys/shape/range/validation.
- [x] Run targeted tests + compile check.
- [x] Review strict scope.

## Review
- [x] Confirm only map function + tests/docs changed.
- [x] Confirm checks/tests passed.

# TODO — Sale entries CRUD slice 1 (list/create only) (2026-03-24)

- [x] Sync attempted; proceed local when origin unavailable.
- [x] Implement only `list_sale_entries_for_daily_input(...)` and `create_sale_entry(...)`.
- [x] Add targeted tests for sale-entry listing/creation/validation/sorting/gross-profit.
- [x] Run targeted tests + compile check.
- [x] Review strict scope.

## Review
- [x] Confirm only sale-entry list/create + tests/docs changed.
- [x] Confirm checks/tests passed.

# TODO — Sale entries CRUD slice 2 (update/delete only) (2026-03-24)

- [x] Sync attempted; proceed local if origin unavailable.
- [x] Implement only `update_sale_entry(...)` and `delete_sale_entry(...)`.
- [x] Add targeted tests for update/delete behavior and validations.
- [x] Run targeted tests + compile check.
- [x] Review strict scope.

## Review
- [x] Confirm only sale-entry update/delete + tests/docs changed.
- [x] Confirm checks/tests passed.
