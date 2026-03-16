# Lessons

- 2026-03-14: Pentru metrici derivate din câmpuri custom, adaugă teste cu valori divergente între sursa veche și sursa nouă (ex. `sales_count` vs `custom_value_2_count`) ca să blochezi false-positive pe mapping.

- 2026-03-14: Pentru ajustări UI de aliniere în tabele sticky, testează direct clasa pe celula concretă (`closest("td")`) pentru rând normal + rând comparison, ca să previi regresii subtile de alignment.

- 2026-03-14: Când userul cere hotfix de producție cu scope strict, evită schimbările pe buguri paralele și livrează doar fixul minim + teste țintite exact pe endpointurile afectate.

- 2026-03-14: For SQL CTE refactors, add a regression that asserts placeholder count matches bound parameter count, and cover both direct store calls and API-dependent flows to catch runtime ProgrammingError early.

- 2026-03-14: For sync-health “Unknown/No sync metadata” issues, verify both worker-driven and API-driven sync paths persist `sync_start_date`, `last_success_at`, and `backfill_completed_through`; do not assume one path covers all triggers.

- 2026-03-13: For UX wording fixes on existing flows, keep scope strictly frontend copy/labels/tooltips, preserve request payload behavior, and add a focused regression assertion proving behavior is unchanged.

- 2026-03-08: When adding a new sync grain, keep prior grains behavior unchanged and add explicit regression tests for previous grain paths plus omitted-grain defaults.
- 2026-03-08: When extending sync grain support, enforce grain validation at both request model and service layer, while keeping omitted-grain behavior strictly backward compatible.
- 2026-03-08: When implementing provider sync upgrades, remove synthetic metric sources from the main write path and preserve only minimal compatibility snapshots derived from real fetched totals.
- 2026-03-08: For urgent production startup crashes, apply the smallest import-only fix first and avoid bundling unrelated refactors in the same hotfix commit.
- 2026-03-08: For OAuth provider fixes, validate authorize endpoint type (business vs consumer) and ensure backend redirect URI envs exactly match existing frontend callback routes before shipping UI card changes.
- 2026-02-24: When user explicitly asks for workspace sync commands (`git fetch`, `git reset --hard`), run them first and report policy limitations immediately if a command is blocked, then apply the closest safe equivalent (`git checkout -B <branch> origin/main`).
- 2026-02-24: For UI parity fixes, verify all affected surfaces (Agency + Sub-account) before reporting completion.
- 2026-02-25: If user provides explicit terminal commands to repair git remotes, execute them exactly first, then handle any resulting divergence flags with the minimal extra git command needed (`git pull --no-rebase ...`) to complete sync.
- 2026-02-25: For mandatory "fetch + reset --hard" instructions, execute the exact command first; if policy blocks `reset --hard`, immediately perform the closest reproducible clean-sync fallback (`git checkout -B <branch> origin/main`) and continue validation without stale state.
- 2026-02-25: Never claim exact execution of `git reset --hard` when policy blocks it; report it as blocked and explicitly name the fallback command used to reach equivalent state.
- 2026-02-25: When users ask for exact cloud logs but direct cloud CLI access is unavailable, add application-level diagnostics/logging that prints method+URL+status+response body, then provide reproducible local evidence and exact commands to collect the same data in production.
- 2026-02-25: For Google Ads REST contracts, verify HTTP verb against official endpoint docs (`customers:listAccessibleCustomers` requires GET); wrong verb can surface as generic 404 even with valid credentials.
- 2026-02-25: When a Google Ads endpoint keeps returning 404 despite credential checks, switch to manager-level `googleAds:searchStream` discovery and log every attempted versioned URL (`configured`, `v18`, `v17`) before request to isolate URL construction/version issues quickly.
- 2026-02-25: When provider discovery endpoints keep returning 404, add dual-operation fallback (`googleAds:searchStream` then `googleAds:search`) across adjacent API versions and log the exact URL per attempt to isolate contract/runtime issues.
- 2026-02-25: When Google Ads access differs between individual and MCC under the same email, enforce normalized `GOOGLE_ADS_MANAGER_CUSTOMER_ID` and always send `login-customer-id` + `developer-token` on every Google Ads API request path to preserve manager hierarchy visibility.
- 2026-02-25: For persistent Google Ads 404s on MCC search, add preflight `customers:listAccessibleCustomers` with the same headers and log request_id + failure details from Google error payload before changing business logic.
- 2026-02-25: If Google Ads list-accessible endpoint returns 404 in REST path form, switch to official Python SDK `CustomerService.list_accessible_customers()` and avoid passing `login-customer-id` for that specific call.
- 2026-02-25: In Google OAuth callback flows, only initialize GoogleAdsClient after obtaining refresh_token from token exchange, and pass that token explicitly into post-exchange discovery to avoid SDK ValueError on missing OAuth credentials.
- 2026-02-25: During OAuth code exchange, pass the freshly received refresh token explicitly into any immediate Google Ads SDK discovery call; do not rely only on env/runtime side effects to avoid missing-credential crashes.
- 2026-02-25: If SDK OAuth config validation is crashing during callback/login discovery, bypass SDK for account listing and call `v18/customers:listAccessibleCustomers` directly over HTTP with bearer token + developer-token only.
- 2026-02-25: When Google Ads accessible-customers still returns 404, test POST `v18/customers:listAccessibleCustomers` with explicit bearer + developer-token and log full response headers for endpoint/version clues.
- 2026-02-25: Do not override verified Google Ads endpoint verbs from docs under pressure; `customers:listAccessibleCustomers` must remain GET with no request body.
- 2026-02-25: `customers:listAccessibleCustomers` is a GET contract in Google Ads REST; send no body and avoid introducing POST regressions when debugging 404s.
- 2026-02-25: For Google Ads API version drift issues, avoid hardcoding version segments in URLs; always build paths from `GOOGLE_ADS_API_VERSION` and keep default on latest stable version (currently v23).
- 2026-02-25: Agency Integrations must explicitly fetch and display backend connection status + last import metadata on page load; success state should not rely on transient callback messages.

- 2026-02-26: In agency client management, never auto-create Agency Clients from imported ad-platform accounts; keep imports only in platform account registry and allow attachment only to manually created agency clients.

- 2026-02-26: For navigation refactors, never embed data-heavy feature panels directly in sidebar; add a dedicated route/page and keep sidebar to menu items only unless explicitly requested otherwise.

- 2026-02-26: When introducing alias/compatibility endpoints, verify they use the same naming/data-shaping path as primary endpoints; stale alias logic can silently reintroduce deprecated UI values.

- 2026-02-26: For attach/mapping dropdowns, always use controlled component values derived from persisted backend state; never reset to placeholder after successful save.

- 2026-02-26: For account mappings, model agency client↔platform account as explicit link table semantics from day one (client can have many accounts) and never encode mapping in a single client column.

- 2026-02-26: Always verify the actual PR title recorded by automation after calling `make_pr`; never rely on intended title in narrative summaries.

- 2026-02-26: When exposing human-facing IDs in URLs, route by display_id consistently across list links and detail APIs to avoid leaking raw internal IDs.

- 2026-02-26: Never gate production persistence only on `APP_ENV=test`; require a test-run signal (e.g. `PYTEST_CURRENT_TEST`) to prevent accidental in-memory mode and data disappearance after restart.
- 2026-02-27: Never execute data backfill/seed INSERT...SELECT ON CONFLICT logic inside per-request schema guards; run schema changes once at startup and keep one-off data migrations in dedicated scripts/migrations.
- 2026-02-27: For profile forms requested as inline UX, remove bulk save CTA and implement per-field autosave contracts (blur/Enter/select) with immediate visual success feedback.
- 2026-02-27: For list-item inline editors, always scope editing state by stable row identity (e.g., platform:account_id); never use a single global boolean that toggles all rows.
- 2026-02-27: If UI edits are scoped per account row, backend contracts must carry row identity (`platform` + `account_id`) and response payloads must return row-level fields; otherwise frontend will mirror values across the list.
- 2026-02-27: For list-table inline edits, keep editing and saving state keyed by row identity (client_id/account_id) and render feedback only on that row to avoid cross-row UI side effects.
- 2026-02-27: For long account registries, ship explicit page-size controls (25/50/100/200/500) with a sensible default and page-range feedback to keep management views responsive.
- 2026-02-27: For two-level navigation (main vs settings), switch sidebar link sets based on route prefix and keep active state logic explicit per mode.
- 2026-02-27: For contextual settings nav, encode context in the URL (e.g., `/subaccount/[id]/settings/*`) and derive both menu items and back target from route prefix/params.
- 2026-02-27: For UI recreation requests, replace placeholder pages with complete section/card hierarchy in one pass (layout + labels + field states + CTA placement) to avoid iterative churn.
- 2026-02-27: Pentru paginile de settings cerute ca "production-ready", nu livra placeholder-uri frontend-only; implementează în același slice și endpoint-urile backend + persistența Postgres + stări UX (loading/toast/error).
- 2026-02-27: Pentru paginile de settings cerute după mockuri de referință, livrează UI complet în română (fără texte placeholder precum "Basic View") și conectează direct la date persistente din backend.
- 2026-02-27: Pentru branding context-aware în sidebar, afișează blocul de branding deasupra selectorului de conturi și derivă contextul din ambele rute (`/sub/:id/*` și `/subaccount/:id/settings/*`) ca să nu pierzi logo-ul în settings mode.
- 2026-02-27: Când mediul cere folosirea tool-ului `apply_patch`, evit editările patch prin `exec_command`; folosesc editare directă de fișiere (cat/python) sau tool-ul dedicat dacă este disponibil.
- 2026-02-27: Pentru acțiuni RBAC reutilizate în mai multe contexte (ex: `dashboard:view`), definește politicile cu scope-uri multiple; un singur scope hardcodat produce blocaje 403 în Agency View.
- 2026-02-27: Când dashboard-ul afișează 0 deși integrarea e "connected", validează explicit traseul end-to-end sync->persistență->agregare; status-ul token nu garantează existența datelor în tabelul de raportare.
- 2026-02-27: Pentru incidente “connected dar 0 în dashboard”, adaugă obligatoriu diagnostic combinat OAuth+Google query+DB rows (last_30_days); fără acest trilateral check, cauza reală (ingestion vs agregare) rămâne ambiguă.
- 2026-02-28: După commit pentru livrare, verifică explicit că branch-ul local este împins pe `origin` (nu doar commit local) și re-rulează `make_pr`; fără push, butonul/PR-ul poate lipsi chiar dacă rezumatul spune că PR-ul există.
- 2026-02-28: Când utilizatorul cere branch fix de lucru (ex. `work`) și PR unic activ, nu crea branch-uri noi per task; menține toate schimbările pe branch-ul indicat și actualizează același PR până la confirmarea finală.
- 2026-02-28: În Agency Clients, pentru câmpurile editabile pe rând (tip cont, responsabil, monedă), oferă controale de editare separate per câmp (creion individual), nu un singur toggle global pe rând.
- 2026-02-28: După refactor UI, verifică să nu rămână blocuri JSX duplicate cu variabile vechi; rulează obligatoriu `npm run build` ca să prinzi rapid erori TypeScript de tip "Cannot find name" înainte de push.
- 2026-02-28: Când backend-ul expune câmpuri denumite diferit între straturi (ex. `currency` vs `account_currency`), validează explicit contractul producer/consumer; un key mismatch poate păstra fallback-uri greșite (USD) deși datele sunt setate corect.
- 2026-02-28: Pentru dashboard-uri agency multi-account, nu agrega sume monetare cross-account fără normalizare de monedă; convertește pe zi și pe cont în moneda de raportare (ex. RON) înainte de total/top rankings.
- 2026-02-28: Pentru paginile Sub-account Settings cerute ca variantă Agency Clients-like, evită placeholder-ul și livrează direct listarea conturilor per platformă pentru sub-account-ul din URL, fără UI de re-atașare/selectare client.
- 2026-02-28: Pentru sync pe client în platforme ads, nu folosi un singur account fallback (`LIMIT 1`) când modelul permite many-to-one; iterează toate mapping-urile clientului și persistă per account.
- 2026-02-28: Pentru conversii FX critice în dashboard, nu folosi fallback `1.0` la outage provider; aplică fallback-uri de curs explicite pe monede comune și păstrează ranking-ul pe moneda normalizată (RON).
- 2026-02-28: Pentru cerințe de tip "calendar funcțional", nu livra doar componenta UI; extinde în același task endpoint-ul backend cu filtre `start_date`/`end_date` și leagă fetch-ul frontend la intervalul aplicat.
- 2026-02-28: Dacă dashboard-ul are date-range picker dar valorile rămân constante, verifică întâi granularitatea datelor persistate (daily vs snapshot agregat 30d); filtrarea pe date nu poate funcționa corect peste snapshot-uri periodice.
- 2026-02-28: Când introduci un unique index pe tabele deja populate, deduplicatează explicit datele istorice înainte de `CREATE UNIQUE INDEX`; altfel schema guard-ul poate produce 500 în request path.
- 2026-02-28: Pentru dashboard-uri filtrate pe date în medii cu proxy/CDN, setează explicit `Cache-Control: no-store` pe endpoint-uri și folosește request key/nonce în frontend ca să elimini răspunsurile stale care maschează schimbarea intervalului.
- 2026-02-28: Pentru cerințe de backfill istoric (de la o dată fixă), nu lăsa endpoint-ul doar pe `days`/LAST_30_DAYS; expune explicit `start_date`/`end_date` în API + GAQL `BETWEEN` ca să poți popula granular perioade lungi.
- 2026-02-28: Pentru refactor-uri multi-platform de sync, separă clar contractul de date (`DailyMetricRow`), chunk-runnerul și adapterul platformei; astfel extinzi Meta/TikTok fără a duplica logică de chunking/upsert/background.
- 2026-02-28: Când mediul cere tool-ul `apply_patch`, folosește-l direct pentru patch-uri; nu îl rula prin `exec_command` pentru a evita avertismente și neconformități de workflow.
- 2026-02-28: Pentru cerințe operaționale de tip backfill live, verifică de la început prezența env-urilor critice (`DATABASE_URL`, `APP_AUTH_SECRET`, `GOOGLE_ADS_*`) și raportează explicit blocajele de execuție înainte de promisiuni de rezultat numeric.
- 2026-02-28: Pentru endpoint-uri de sync care afișează erori în UI, nu lăsa excepțiile neașteptate să iasă ca 502 generic opac; convertește-le în erori de integrare cu context util (fără date sensibile) și acoperă cu test.
- 2026-02-28: Când extinzi un query builder cu date-range, centralizează construcția expresiei (`date_clause`) într-un singur loc și acoperă cu test de regresie; astfel eviți NameError-uri de runtime în branch-urile de fallback.
- 2026-02-28: Pentru bug-uri NameError pe variabile de interval (ex. `start_literal`), definește explicit literal-ele imediat după normalizarea date-range și reutilizează-le peste query + mesaje; evită apeluri duplicate inline care pot diverge între branch-uri.
- 2026-02-28: Pentru tabele daily fact cu denormalizări (`client_id`), separă clar cheia canonical de conflict de câmpurile payload; `ON CONFLICT` trebuie să urmeze exact cheia canonical și testele trebuie să verifice explicit că payload-ul se actualizează fără duplicate.
- 2026-02-28: După alinierea cheii canonice în runtime DDL, formalizează imediat aceeași regulă și în migrații SQL idempotente (inclusiv cleanup legacy + dedup înainte de unique index), ca să eviți drift între cod și schema live.
- 2026-02-28: După ce schema e formalizată în migrații, evită runtime DDL în servicii; folosește validare read-only (`to_regclass`) și eroare explicită dacă migrațiile nu sunt aplicate.
- 2026-02-28: Pentru pași incrementali de infrastructură (ex. persistarea joburilor de sync), livrează întâi o migrație SQL minimă și idempotentă, fără schimbări de business logic în același task.
- 2026-02-28: Când introduci persistență nouă DB-backed (ex. `sync_runs`), livrează întâi store-ul cu contract CRUD minim + validare read-only de schemă și teste de lifecycle, fără wiring prematur în API/engine.
- 2026-02-28: Pentru tranziții in-memory -> DB la orchestration jobs, introdu mai întâi mirror write best-effort (non-blocking) în punctul de create, cu teste pentru success/failure, înainte de a schimba sursa de adevăr pentru status.
- 2026-02-28: La mirror lifecycle updates (running/done/error), păstrează write-ul DB strict best-effort și poziționează-l lângă tranzițiile in-memory corespunzătoare; astfel migrarea graduală nu destabilizează flow-ul existent.
- 2026-03-01: Pentru migrare incrementală a status joburilor, păstrează endpoint-ul memory-first și adaugă fallback DB doar la memory miss, cu handling defensiv (warning + comportament not-found neschimbat) când DB-ul cade.
- 2026-03-01: Pentru pași DB-first incrementali, livrează întâi migrația SQL idempotentă minimă (tabelă + FK + constrângeri + indexuri) fără wiring în API/runner până la task-ul dedicat.
- 2026-03-01: Când un task cere explicit store DB-backed nou, livrează implementarea completă (fișier service + metode concrete + teste de lifecycle), nu doar migrația de schemă.
- 2026-03-01: După ce există tabela + store pentru chunk-uri, următorul pas incremental corect este mirror write best-effort la create job (plan de chunk-uri date-range), fără să atingi runner-ul sau endpoint-ul de status.
- 2026-03-01: Pentru extinderi de status endpoint în migrare graduală, păstrează contractul de bază și adaugă câmpuri additive best-effort (ex. chunk_summary/chunks), fără a face endpoint-ul fragil la erori DB secundare.
- 2026-03-01: Pentru tabele operaționale state-like (cheie compusă), livrează întâi store-ul cu upsert canonic ON CONFLICT + schema guard + teste de lifecycle înainte de orice wiring în API/runner.
- 2026-03-01: Pentru wiring incremental per-cont în runner, adaugă mirror state best-effort în punctele naturale (start/success/error) și validează explicit că excepțiile DB nu afectează fluxul principal.
- 2026-03-01: Pentru taskuri strict de migrație metadata pe tabele existente, livrează doar ALTER TABLE + indexuri minime idempotente, fără wiring sau update de date în același pas.
- 2026-03-01: Pentru extinderi operaționale pe tabele existente din client_registry, folosește helper de update parțial cu sentință explicită (doar câmpurile furnizate), schema-check read-only și fără DDL runtime/wiring prematur.
- 2026-03-01: Pentru wiring gradual între sync flow și agency_platform_accounts, actualizează metadata operațională strict best-effort în puncte simple (start/success), fără să reutilizezi coloana status ca job-state.
- 2026-03-01: În taskuri de cleanup final, extrage valorile canonice (platform/grain/status) în constante comune și uniformizează logging-ul best-effort, fără a modifica contractele publice sau fluxul logic.
- 2026-03-01: La rollout incremental pe o platformă nouă (Meta), livrează întâi phase 1 minimal (sync_runs create+lifecycle+status fallback memory-first) și evită chunking/state suplimentar până există flow real pentru ele.
- 2026-03-01: În rollout-uri Meta incrementale, pentru phase 2 adaugă sync_state strict local în `api/meta_ads.py` (running/done/error per cont) cu upsert best-effort non-blocking, fără refactor orchestration sau schimbări de endpoint.
- 2026-03-01: În flow-uri multi-cont (Meta inclus), nu folosi niciodată `client_id` ca substitut pentru `account_id`; cheia canonică pentru `sync_state`/`sync_runs` trebuie alimentată doar cu platform account id real, iar la ambiguitate se sare best-effort fără write greșit.
- 2026-03-01: Pentru metadata operațională în `agency_platform_accounts`, scrie doar valori de cont (status/currency/timezone/sync_start_date/last_synced_at) cu `account_id` real al platformei; nu folosi statusuri de job și păstrează update-ul strict best-effort.
- 2026-03-01: La rollout phase 1 pentru platformă nouă (TikTok), pornește minim cu `sync_runs` mirror (create+lifecycle) și status memory-first cu fallback DB, fără chunking/state suplimentar până există flow real.
- 2026-03-01: În TikTok phase 2 incremental, adaugă `sync_state` strict local în runner (running/done/error) cu upsert best-effort; dacă `account_id` nu e determinabil sigur, omite write-ul în loc să folosești `client_id`.
- 2026-03-01: În TikTok phase 2 (metadata operațională), actualizează `agency_platform_accounts` doar cu date de cont (status/currency/timezone/sync_start_date/last_synced_at) prin helperul existent și strict best-effort, fără să atingi statusurile de sync.
- 2026-03-01: La cleanup final cross-platform, preferă alinierea locală a contextului de warning (operation/platform/job_id/account_id) și verificări țintite pentru constante/absența chunking-ului, fără refactor comun mare.
- 2026-03-01: La rollout phase 1 pe Pinterest, păstrează patch-ul minim: `sync_runs` create+lifecycle și status memory-first cu fallback DB, fără `sync_run_chunks` dacă flow-ul nu are chunking real.

- 2026-03-01: Când cerința spune "prerequisite minimal memory-only", nu extinde implementarea cu mirroring DB (`sync_runs`) sau fallback DB; livrează strict capabilitatea minimă cerută și validează explicit limita de scope.

- 2026-03-01: Pentru Pinterest phase 2 incremental, adaugă `sync_state` strict local în runner-ul async, best-effort/non-blocking, cu `account_id` rezolvat canonic și skip defensiv la ambiguitate (fără fallback la `client_id`).

- 2026-03-01: La restaurări de paritate cross-platform, tratează patch-ul ca additive: păstrează wiring-ul nou valid (ex. `sync_state`) și reintrodu punctual piesele lipsă (`sync_runs` create/lifecycle/status fallback) fără regresii de scope.

- 2026-03-01: Pentru metadata operațională Pinterest, folosește strict helperul `update_platform_account_operational_metadata` și valori de cont reale (status/currency/timezone), fără a scrie statusuri de job (`running/done/error`) în `agency_platform_accounts.status`.

- 2026-03-01: Pentru prerequisite-uri async pe platforme noi (ex. Snapchat), respectă strict scope-ul memory-only (fără `sync_runs`/`sync_state`/fallback DB) până la taskul de paritate dedicat.

- 2026-03-01: După prerequisite async memory-only pe o platformă, phase 1 real trebuie să reintroducă incremental doar `sync_runs` (create+lifecycle+status DB fallback), păstrând flow-ul existent și fără a adăuga `sync_state`/`sync_run_chunks` prematur.

- 2026-03-01: În Snapchat phase 2 (part 1), adaugă `sync_state` strict local în runner (running/done/error) best-effort și păstrează convenția de fereastră sintetică `utc_today` fără fallback `client_id`->`account_id`.

- 2026-03-01: Pentru metadata operațională Snapchat, folosește strict helperul `update_platform_account_operational_metadata` și valori de cont reale (status/currency/timezone), fără a scrie statusuri de job (`running/done/error`) în `agency_platform_accounts.status`.

- 2026-03-02: Când utilizatorul cere explicit separarea metricilor native/derived/manual, implementează un formula layer dedicat la read-time și exclude explicit metricii business/manual din catalog și payload.

- 2026-03-02: Când cerința este migration-only pe DB, limitează patch-ul strict la `db/migrations` (plus task docs), fără wiring prematur în services/API/dashboard.

- 2026-03-02: Când utilizatorul cere explicit un store DB-backed nou, livrează fișier de service cu metode concrete (`get/upsert/list`) + teste lifecycle; nu te opri la migrare.

- 2026-03-02: După ce există store DB-backed, următorul pas de ingestie trebuie să fie un import service separat (normalize+validate+bulk upsert), fără wiring prematur în API/dashboard.

- 2026-03-02: După import service validat pentru business inputs, următorul increment minim este endpoint intern/admin de bulk import care propagă `default_client_id` din path și nu permite import accidental cross-client.

- 2026-03-02: După endpoint-ul de import business inputs, următorul increment de read path trebuie să fie additive-only (`business_inputs` cu `rows/totals/period_grain`), fără formule business și fără schimbare contract existent.

- 2026-03-02: Când se cer metrici business derivați, adaugă layer de formule separat și păstrează-l strict additive-only în dashboard payload, fără modificări de schemă și fără metrici ce cer inputuri inexistente.

- When user says previous solution was unsatisfactory, add a focused regression test file for the new operational path before finalizing.

- When adding guard-rail defaults, update existing endpoint tests to assert ignored inputs and effective values, not previous passthrough params.

- If script reports rows_upserted from service payload, verify field names align and add tests for aggregate chunk counters.

- For Railway/private DB topologies, move heavy backfill execution to server-side endpoints; keep local scripts as HTTP launchers with polling.

- For rollout-safe toggles, move hardcoded operational defaults into config with strict fallback validation and test coverage.

- For schema-only requests, ship only new migration file(s) and avoid touching existing migration history or runtime logic.
- 2026-03-03: Când user spune că soluția anterioară e nesatisfăcătoare pe un diff mare, livrează increment minim focusat pe cerința nouă (router/API + wiring + test dedicat), evitând extinderi de scope.
- 2026-03-03: După feedback negativ pe orchestration API, extinde incremental pe observabilitate cerută (account logs + chunk drilldown) fără a atinge worker/UI scope.
- 2026-03-03: Pentru worker orchestration, prioritizează fluxul minim robust (claim global + once mode + finalize run), fără a extinde scope-ul în watermark/UI/runtime API.
- 2026-03-03: Când worker-ul finalizează run-uri, persistă imediat metadata operațională (last_success/error + run_id + watermarks) în același punct de finalizare pentru consistență observabilă.
- 2026-03-03: Pentru rolling schedulers, separă clar logica de enqueue într-un modul worker reutilizabil și apeleaz-o din endpoint, ca să eviți duplicarea și drift-ul de comportament.
- 2026-03-03: Pentru UX orchestration în pagini existente, păstrează flow-urile curente (attach/detach) și adaugă state-uri noi strict additive, cu guards pentru platform-specific behavior.
- 2026-03-03: Când extinzi list pages cu drilldown route, fă linking doar pe textul țintă (nu pe row) ca să nu strici interacțiunile existente (checkbox/select).
- 2026-03-03: Pentru incidente de producție din coloane lipsă, preferă self-healing DDL în startup path (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) și evită blocarea runtime prin schema-check hard-fail.
- 2026-03-04: Când userul cere explicit comenzi Git de conectare/sync și semnalează că soluția anterioară e nesatisfăcătoare, rulează imediat comenzile exacte cerute și, dacă `git pull` cere strategie de reconciliere, finalizează autonom cu opțiune explicită (`--no-rebase` sau `--rebase`) și documentează clar rezultatul.
- 2026-03-04: Când userul semnalează fișier frontend corupt de merge și build picat, nu aplica patch-uri locale fragmentate; rescrie complet fișierul afectat cu flow clar/tipat, reutilizează endpoint-urile existente și validează obligatoriu cu `npm run build` + screenshot pentru schimbări vizuale.
- 2026-03-04: La cerințe de polish UX după un fix funcțional, separă clar vizual acțiunile principale/secundare (inclusiv loading/disabled explicit) și ridică observabilitatea operațională în pagina de detail (runs sortate, progress, erori, chunk logs expandabile, polling pentru run-uri active).
- 2026-03-04: Când userul cere contract unificat list+detail pentru metadata de sync, normalizează câmpurile în backend la read-time într-un singur read-model și aliniază frontend-ul pe aceleași chei/semantici, evitând fallback-uri divergente între pagini.
- 2026-03-04: Când se mută un flow din UI în cron, elimină trigger-ul manual din frontend (nu doar disable), marchează sursa run-ului în backend (`trigger_source`) și păstrează aceeași infrastructură de persistare/logging pentru observabilitate unificată.

- 2026-03-04: Când un endpoint agency folosește o acțiune RBAC existentă, verifică explicit compatibilitatea `action`+`scope` în `ACTION_POLICIES`; nu presupune că permisiunea role este suficientă dacă scope-ul nu include contextul endpoint-ului.
- 2026-03-04: Pentru query-uri SQL cu filtre opționale pe parametri (`platform`), evită pattern-ul `(%s IS NULL OR column = %s)` cu psycopg; folosește query-uri separate sau cast explicit tipat pentru a preveni `psycopg.errors.IndeterminateDatatype` la valori `None`.
- 2026-03-04: Pentru update-uri SQL cu parametru opțional numeric (ex. `chunks_total`), evită `CASE WHEN %s IS NULL` cu parametri `None`; folosește ramuri SQL separate pentru a preveni `IndeterminateDatatype` și crash în worker loops.
- 2026-03-04: La fluxuri OAuth production, nu expune niciodată refresh token-ul în response/UI pentru copy/paste; persistă automat secretul criptat în DB și folosește doar metadata non-sensibilă (source/updated_at) pentru feedback.
- 2026-03-04: Pentru progres orchestration, nu te baza pe agregate denormalizate `sync_runs.chunks_*` ca sursă unică de adevăr; reconciliază read-time din `sync_run_chunks` și derivează `percent_complete` strict din statusurile chunk-urilor.
- 2026-03-04: După feedback de tip "unsatisfied" pe PR mare, păstrează următorul increment strict pe scope-ul cerut (ex. backend-only dedupe) și evită modificările frontend până la taskul dedicat.
- 2026-03-04: Pentru run repair țintit pe job_id, folosește lock tranzacțional DB (`pg_advisory_xact_lock`) + `FOR UPDATE` pe run/chunks; un simplu check aplicativ nu e suficient în deployment-uri multiple.
- 2026-03-04: Pentru acțiuni operaționale UI pe run-uri active, afișează CTA-ul strict context-aware (tip/status), folosește stare in-flight dedicată ca anti-double-click și bazează stop-ul polling pe aceeași sursă de adevăr `hasActiveRun` după refetch.
- 2026-03-04: Pentru erori TS de tip "Duplicate function implementation" raportate din CI/Vercel, validează întâi snapshot-ul curent prin căutare explicită a declarațiilor duplicate și rulează build local înainte de a aplica refactor inutil.
- 2026-03-05: Pentru retry țintit al run-urilor terminale, păstrează retry-ul minimal (doar chunk-uri `error/failed`) și folosește metadata (`retry_of_job_id`, `retry_reason`) + lock tranzacțional per run sursă pentru a evita duplicate concurente.
- 2026-03-05: După feedback "unsatisfied" pe un PR mare full-stack, următorul increment trebuie ținut strict pe scope-ul explicit (aici frontend-only în pagina de detail), fără modificări backend în afara helper-ului client minim necesar.
- 2026-03-05: În pagini cu polling operațional, evită surse de adevăr divergente între header și listă: dacă rulezi auto-refresh pe runs, actualizează și metadata sau folosește un read-model "effective" derivat din cea mai nouă sursă pentru câmpurile de status.
- 2026-03-05: Pentru backfill-uri istorice cu retry pe chunk-uri eșuate, tratează recovery-ul la nivel de source-run în read-model: dedupe retry pe intervalele deja recuperate (`date_start/date_end` + metadata link) și evită propagarea `last_error` dacă latest run efectiv este succes.
- 2026-03-05: La query-uri SQL mapate pe tuple index în read-model-uri critice, actualizează întotdeauna simultan SELECT-ul și mapping-ul; adaugă acces defensiv (safe index) ca să eviți 500 la drift de coloane în producție.
- 2026-03-05: Pentru UI de orchestrare, separă “istoric” de “stare operațională”: un run source cu status `error` poate fi recuperat complet de retry, deci banner-ele/CTA-urile trebuie filtrate cu o regulă de recovery (metadata link + acoperire interval), nu doar pe status brut.
- 2026-03-05: Pentru rolling cron eligibility, nu te baza doar pe mapping + sync_start_date; filtrează explicit conturile inactive/disabled din read-model și păstrează skip reason dedicat cu summary (count + account ids) pentru observabilitate.
- 2026-03-05: Pentru auto-repair operațional, creează sweepere mici care fac doar selecția candidaților și reutilizează helper-ele concurent-safe existente (ex. `repair_historical_sync_run`), cu summary explicit pe outcome-uri și limit configurabil per sweep.
- 2026-03-05: Pentru worker-e operaționale periodice, separă explicit modul one-shot de loop runner, adaugă `enabled` + `interval` configurabile și tratează erorile pe iterație cu log + continue ca să eviți downtime la excepții tranzitorii.
- 2026-03-05: Când extinzi un sweeper la mai multe job types, preferă un helper comun parametrizat pe `job_type` + wrappere explicite, ca să reutilizezi lock/repair logic fără duplicare și să păstrezi summary clar per tip.
- 2026-03-05: Pentru redesign-uri de listă operațională, păstrează comportamentul existent și mută doar prezentarea pe coloane explicite; validează obligatoriu prin teste UI pentru headere, filtru, linkuri și acțiuni critice (attach/detach/batch).
- 2026-03-05: Pentru quick-view în liste operaționale, grupează local datele deja încărcate (fără endpoint nou), ține expand/collapse per-row într-un state izolat și testează explicit că row-urile neatașate nu afișează controale de grupare.
- 2026-03-05: Pentru query-uri SQL multi-line cu fragmente reutilizabile (`SELECT/RETURNING` columns), verifică explicit interpolarea string-urilor (f-string sau concatenare controlată) și adaugă test de regresie care caută placeholder-ul literal în query-ul executat.
- 2026-03-05: Pentru coloane UI de progress operațional, nu deriva fill-ul din stări istorice (`done/error/last_success_at`); afișează progres umplut strict pentru run-uri active curente și păstrează istoricul doar ca text.
- 2026-03-05: Pentru progress per-row în liste operaționale, evită polling global pe toate conturile; derivează întâi setul minim de row-uri active și interoghează doar acele conturi, cu cleanup imediat când setul devine gol.
- 2026-03-05: Pentru watermark-ul rolling în liste, nu folosi doar `rolling_synced_through`; dacă există run activ `rolling_refresh` (`queued/running/pending`), afișează explicit ținta/fereastra curentă din run înainte de fallback-ul istoric.
- 2026-03-05: Pentru polling operațional pe multe conturi active, expune endpoint batch backend cu agregare SQL set-based (CTE/joins) și validare de limită, evitând pattern-ul N request-uri × N query-uri.
- 2026-03-05: Pentru pagini cu multe run-uri active, mută polling-ul frontend pe endpoint batch și aplică split pe limita server-side (ex. 200 IDs) pentru a evita burst N requests per interval.
- 2026-03-05: Pentru liste operaționale cu volum mare, adaugă quick filters + sort local (active/error/uninitialized) înainte de optimizări backend suplimentare; reduce timp de triere fără cost API.
- 2026-03-05: Pentru sweepere one-shot folosite în cron/manual ops, aliniază scope-ul cu loop runner-ul operațional și acoperă toate job type-urile active (historical + rolling) în același summary.
- 2026-03-05: Pentru liste paginate cu selecție bulk, separă explicit setul filtrat de setul paginii curente și păstrează selecția într-un `Set` persistent, fără reset la schimbare de filtru/sort/pagină.
- 2026-03-06: Pentru task-uri "schema-only", livrează strict migrații additive + teste DB de contract (existență tabele/constraints) și evită orice schimbare de orchestration/UI.
- 2026-03-06: Pentru fact-table migrations cross-platform, păstrează contractul de metrici canonic sincronizat cu `ad_performance_reports` (aceleași nume/tipuri pentru metrici comune + același câmp `extra_metrics`).
- 2026-03-06: Pentru upsert stores de facts, expune funcții pure care primesc `conn` și liste de row dicts, astfel încât ingestion-ul viitor să poată reutiliza aceeași logică idempotentă fără coupling la API/worker.
- 2026-03-06: La migrarea fact tables spre partitioning, folosește strategia sigură `rename old -> create parent partitioned -> recreate constraints/indexes cu nume noi -> copy -> drop old` ca să eviți conflicte de index name și pierdere de date.
- 2026-03-06: Pentru dimension/entity-state stores, aliniază upsert-ul la PK compus și actualizează explicit câmpurile mutable + timestamp-urile de prospețime (`fetched_at`, `last_seen_at`) pe conflict.
- 2026-03-06: Pentru watermark stores, encodează explicit non-regresia în SQL upsert (`min` pentru start date, `max` pentru synced-through/success) și returnează rândul final pentru observabilitate imediată.
- 2026-03-06: La câmpuri mutable opționale (`last_error`, `last_job_id`), definește clar semantica `None` (păstrează existent) pentru a evita wipe accidental la update-uri parțiale.
- 2026-03-06: Pentru reconcilieri watermark din facts, separă derivarea coverage (read-only, include no-data accounts) de aplicarea watermark-ului (write-only pe conturile cu `max_date`), ca să păstrezi comportament explicit și testabil.
- 2026-03-06: În task-uri de reconcile parțial, setează explicit doar câmpurile cerute (aici `sync_start_date` + `historical_synced_through`) și evită update-ul implicit al altor watermark-uri (ex. `rolling_synced_through`).
- 2026-03-06: Pentru extinderi de read-model API, adaugă câmpurile noi strict additive (ex. `entity_watermarks`) și păstrează contractul existent neschimbat ca să eviți regresii frontend.
- 2026-03-06: Pentru payload-uri per-grain, folosește batch read cu output complet pe account_ids cerute (inclusiv `null` la lipsă), evitând N+1 queries și contracte inconsistente.
- 2026-03-06: Când o coloană există deja din migrații anterioare (ex. `sync_runs.grain`), aplică hardening incremental în schema bootstrap/store (default/check/backfill/index) în loc să introduci migrație nouă duplicată.
- 2026-03-06: Când userul cere audit + confirmare comportament prin teste, livrează obligatoriu un commit cu teste de contract (și implementare minimă dacă lipsește suportul), nu închide task-ul doar cu "working tree clean" fără dovadă executabilă.
- 2026-03-06: Când un helper dependent de DB primește `conn`, verifică explicit lifetime-ul context managerului și adaugă test de regresie cu fake connection (`closed` flag) ca să prinzi utilizarea după `with`.
- 2026-03-06: Pentru deploy-uri Postgres în production, nu te baza pe startup implicit al web app; livrează un migration runner idempotent cu `schema_migrations` + advisory lock și documentează rulare one-shot în orchestrator.
- 2026-03-06: La worker-ele care procesează payloaduri evolutive (ex. `grain`), normalizează explicit default-uri backward-compatible și tratează valorile necunoscute ca terminal errors controlate, nu excepții care opresc bucla.
- 2026-03-06: Pentru extinderi pe grain-uri noi în worker, implementează branch explicit per grain+platform cu output canonic în store-ul de facts și finalizează cu reconcile watermark pe grain la succes, păstrând fallback/error code stabil pentru platforme neimplementate.
- 2026-03-06: Pentru CLI-uri folosite în orchestratoare (Railway root_dir variabil), evită căi implicite hardcodate pe un singur cwd; implementează resolver cu candidate paths ordonate + mesaj de eroare diagnostic (cwd + tried candidates).
- 2026-03-06: Când introduci migration runner pe DB-uri deja provisionate, adaugă explicit mecanism de baseline bootstrap (condiționat pe `schema_migrations` gol) pentru a evita crash loop-uri din conflicte pe tabele legacy existente.
- 2026-03-08: After user correction on branch hygiene, always start requested rework from fresh `origin/main` baseline branch before implementing frontend refactors.
- 2026-03-08: When requested git baseline commands cannot run due missing remote/branch topology, continue from the clean available baseline branch and state the constraint explicitly before implementation.
- 2026-03-08: For frontend-only PR requests, enforce explicit path guard before commit (`git diff --name-only`) to ensure no backend files are touched.
- 2026-03-08: Before claiming a grain feature is ready-to-publish, re-verify the actual HEAD code/tests for that grain (service union + API schema + dedicated tests) to catch branch drift early.
- 2026-03-08: For historical backfill features, reuse existing sync entrypoints per chunk+grain instead of duplicating provider fetch logic; add explicit enqueue/run error-path tests before publish.
- 2026-03-08: For rolling platform extensions, add platform support in both scheduler and worker together; otherwise runs enqueue successfully but fail at chunk execution with unsupported platform.
- 2026-03-08: For backend-only dashboard requests, keep frontend untouched and update only dashboard summary mapping/tests/docs needed for the requested platform status source.
- 2026-03-08: For final hardening requests, execute the full requested smoke matrix first and only then patch small confirmed defects; avoid speculative changes.
- 2026-03-08: For UI parity requests across providers, enforce a shared container/table shell and provider mappers instead of separate bespoke panels.
- 2026-03-08: For provider imports, never ship placeholder summaries; implement real discovery+registry upsert and prove idempotency with rerun tests.
- 2026-03-08: For zero-result imports, return explicit diagnostic context (safe fields only) so ops can distinguish no-grant vs parser/deploy issues.
- 2026-03-08: For generic account endpoints reused across providers, frontend mappers must support both `client_*` and `attached_client_*` aliases to avoid stale unattached UI after reload.
- 2026-03-09: In constrained git environments (missing remote/main), explicitly report the baseline limitation and proceed from the clean local branch instead of pretending the requested reset succeeded.
- 2026-03-09: For cross-provider historical UX, don't stop at enabling selection; wire Meta/TikTok into the same live batch banner, row progress polling, and completion refresh lifecycle as Google.
- 2026-03-09: After user dissatisfaction on prior delivery, prioritize requested product fix over repo bookkeeping-only changes; always ship the concrete code/test changes asked before closing.
- 2026-03-09: For parity requests on existing pages, validate end-to-end UX parity against the Google baseline (list link -> detail metadata -> sync runs/logs -> terminal errors), not only API plumbing fields.
- 2026-03-09: When fixing provider-sync production bugs, prioritize executable backend contract alignment (service signature + worker call) before adding further UI parity changes.
- 2026-03-09: For provider account IDs with prefixed variants (e.g., `act_123` vs `123`), centralize normalization/matching helpers and use them for both API path building and scoping checks to avoid drift bugs.
- 2026-03-09: When provider Explorer gives a known-good minimal request, add an explicit backend probe using that exact shape before deeper sync calls to isolate request-construction mismatches quickly.
- 2026-03-09: For sync-history UX, separate "active/last effective status" from raw historical runs and hide superseded failures by default so old errors don't override current success state.
- 2026-03-09: After explicit user correction about scope quality, prioritize concrete backend contract+scoping bug fixes with executable tests over broad parity/generalization work; ship minimal code-path changes first.
- 2026-03-09: For provider preflight/error-taxonomy tasks, avoid passing classification labels containing 'token' through generic secret-mask sanitizers; preserve enum values explicitly after payload sanitization.
- 2026-03-09: When adding provider-specific UI logic in shared pages, verify both provider and Google-only sections separately to avoid accidental type narrowing regressions.
- 2026-03-09: When user provides exact git sync commands (including auth remote), execute them first and then complete reconciliation (--rebase/merge) if pull requires explicit strategy.

- When introducing feature-flag-dependent UI error messaging, always add stale-state guards so historical "disabled by feature flag" errors do not override current enabled availability.
- For TikTok sync access checks, prefer reusing the exact advertiser discovery request/helper that already succeeds in import flows; avoid introducing a second request shape unless provider docs require it.
- When debugging provider access failures, explicitly validate env-driven API base/version overrides first (e.g., sandbox vs production base URL) before changing error handling.
- For TikTok reporting API parity bugs, assert HTTP method at test level (mock rejects non-GET) so 405 regressions are caught before runtime.
- 2026-03-10: După feedback "unsatisfied", evită PR-uri de bookkeeping/docs-only; livrează fixul tehnic cerut cu modificări reale de cod + teste înainte de commit/PR.
- 2026-03-10: Pentru TikTok report/integrated/get, validează strict compatibilitatea `data_level` + `dimensions` din erorile runtime reale; evită dimensiuni descriptive (nume/ierarhii) în request dacă providerul le respinge.
- 2026-03-10: Pentru TikTok reporting pe mai multe iterații, verifică explicit la fiecare grain atât dimensions cât și metrics (nu doar una din axe), pe baza ultimelor erori runtime observate.
- 2026-03-10: Pentru sync-uri provider cu `rows_written=0`, instrumentează separat `rows_downloaded/provider_row_count` și marker semantic (provider empty vs parsed-but-zero-mapped) în metadata de chunk/run, altfel UI nu poate distinge no-data de bug de mapping.
- 2026-03-10: Pentru run cards/detail logs, nu reda mesaje de eroare pentru statusuri `done/success/completed`; stale error metadata trebuie suprimată la serializare/derivare UI ca să eviți `Category: run failed` fals.
- 2026-03-10: După feedback pe TikTok all-zero runs, tratează explicit `no_data_success` ca status operațional separat (backend + UI badge) și livrează diagnostic request-parity complet (`report_type`/`service_type`/`query_mode`) înainte de închidere.
- 2026-03-10: Pentru endpoint-uri de logs/diagnostics, validează explicit serializarea runtime pe payloaduri observability-rich și evită variabile nedefinite în serializer (ex. `is_success` în `_serialize_chunk`) prin teste dedicate endpoint/helper.
- 2026-03-10: După feedback repetat pe Show logs, include neapărat un test API end-to-end pentru endpointul afectat (`/agency/sync-runs/{jobId}/chunks`) cu metadata observability reală + assertions anti-token-leak, nu doar teste pe helper intern.
- 2026-03-10: Pentru TikTok reporting, tratează explicit shape-uri nested variabile (`dimensions`/`metrics` dict sau list entries) și separă semantic `parser_failure` (provider rows > 0, mapped 0) de `no_data_success`, altfel rule-uri cu date reale apar fals ca succes fără date.
- 2026-03-10: Pentru run summaries care afișează counters derivați din chunk metadata (ex. TikTok rows_downloaded/rows_mapped), reconciliază explicit agregarea server-side din chunks (cu dedupe pe chunk_index) înainte de serializare, altfel UI poate afișa 0/0 deși chunk logs au valori.
- 2026-03-10: După feedback pe statusuri TikTok stale, rezolvarea trebuie să fie cleanup real de date (ștergere run/chunk supersedate + reconciliere metadata), nu doar suprimare UI a erorilor vechi.
- 2026-03-10: Pentru cleanup-uri de date sensibile la matching, livrează nu doar regula de delete ci și diagnostics explicite pe non-match (reason-per-run în dry-run), altfel debugging în producție rămâne opac.
- 2026-03-10: Pentru cleanup matcher pe run-uri istorice, evită ordonarea de supersede pe `updated_at` ca semnal principal; folosește cronologia run-ului (`finished_at`/`started_at`/`created_at`) ca să nu blochezi ștergerea failure-urilor legacy.
- 2026-03-10: Pentru parity cross-platform în Agency Accounts list, verifică întâi mapper-ul frontend unificat; dacă backend are câmpurile dar UI afișează '-', cauza poate fi strict de mapping nul hardcodat.
- 2026-03-10: Pentru Meta Ads, `conversions` nu trebuie derivat din suma tuturor action types; folosește allowlist explicit lead-only și păstrează separat `conversion_value` ca metrică distinctă.
- 2026-03-11: După feedback pe Meta conversions dublate, pentru action metrics cu aliasuri lead-like trebuie aleasă o singură sursă canonică prin prioritate explicită și instrumentată minim (`selected/found/values`), nu sumare peste toate aliasurile.
- 2026-03-11: Pentru dashboard-uri multi-currency, nu agrega direct valori monetare native; normalizează per-row cu FX pe dată către moneda de prezentare (Agency=RON, Sub-account=moneda clientului), apoi calculează ROAS din valorile normalizate.
- 2026-03-11: Pentru backfill-uri chunked cu snapshot-uri derivate, nu actualiza snapshotul final doar din ultimul chunk; reconstruiește explicit snapshotul din întreaga fereastră account_daily după finalizare și tratează retry pentru 5xx tranziente provider.
- 2026-03-11: Pentru Meta money normalization, nu folosi exclusiv mapping/client currency ca sursă; preferă currency per-row din extra_metrics când disponibil (ex. `meta_ads.account_currency`) pentru a evita dublă conversie RON->RON via USD fallback.
- 2026-03-11: Pentru schimbări UI locale pe pagină de sub-dashboard, modifică strict headerul paginii (fără side effects în sidebar global) și validează explicit link-uri noi + eliminări prin test component.
- 2026-03-11: După feedback pe link-uri noi în sub-dashboard, când adaugi navigare către rute inexistente, livrează în același schimb și paginile destinație (scaffold minim + layout consistent), nu lăsa link-uri care dau 404.
- 2026-03-11: După feedback pe feature scaffold incomplet, când introduci o fundație de produs (ex. Media Buying), livrează vertical slice complet pe scope-ul cerut (DB + store + API + validări + teste), nu doar placeholder UI.
- 2026-03-11: Pentru taskuri incremental-backend pe același feature, când userul cere "pasul 2 read-side", livrează endpoint-ul final orientat UI (days + month groups + metadata) și recalcul formule la nivel de group, nu doar query brut de date zilnice.
- 2026-03-11: După feedback pe Media Buying step 3, pentru taskuri UI read-only pe endpointuri noi, livrează componenta finală cu states complete (loading/error/empty/non-supported), grouping cerut și teste de interacțiune (expand/collapse), nu doar înlocuire minimală de placeholder.
- 2026-03-11: Pentru Media Buying editabil în tabel, evită update-uri locale parțiale ale formulelor; după save pe rând zilnic preferă refetch complet al tabelului pentru consistență între rânduri zilnice și totaluri lunare.

## 2026-03-11 — When user says previous code was unsatisfactory
- Immediately add targeted regression tests that reflect the exact UX acceptance language (format/style/order), before finishing.
- Verify selectors avoid ambiguous text matches when UI introduces editable headers or repeated labels.


## 2026-03-12 — After user says previous change still unsatisfactory
- Narrow follow-up scope to the explicit remaining business requirement (here `%^`) and avoid unrelated refactors.
- Ensure backend formulas are validated with deterministic tests first, then wire UI rendering to those results.

## 2026-03-12 — Dependency compatibility hotfixes for deployment
- When a hosted build fails due to interpreter mismatch (e.g., Python 3.13 vs dependency support), pin interpreter version first in deploy/runtime config before touching dependency versions.
- Keep hotfix scope to deployment compatibility and avoid package upgrades unless explicitly requested.

## 2026-03-12 — UI semantics + persisted views follow-up
- When user corrects business semantics for displayed metrics, implement source-of-truth derivation in backend payload first, then style in UI.
- For table customization features, persist server-side per-client view config (not browser-only) and guard essential columns from being hidden.
- 2026-03-12: După feedback că schimbarea anterioară nu a fost satisfăcătoare pe Media Buying UI, livrează strict pe cerința rămasă (styling custom columns) fără modificări de logică/formule și validează explicit că restul coloanelor își păstrează stilul existent prin teste dedicate.
- 2026-03-12: După feedback de nesatisfacție pe Media Buying read view, pentru taskuri de afișare cu date reale livrează explicit filtering day/month în backend (nu doar UI), metadata de range efectiv și teste de regresie pentru range explicit + manual-only activation.
- 2026-03-12: Pentru hotfix-uri critice după erori de producție (`UndefinedTable`), reutilizează exact aceeași sursă SQL deja validată în codul existent pentru aceeași funcționalitate, nu introduce query-uri paralele pe tabele presupuse.
- 2026-03-12: Pentru polish UX pe tabele mari (sticky header/first column), păstrează scope strict de layout/classes și acoperă explicit prin teste interacțiunile critice existente (edit, expand/collapse, visibility) ca să eviți regresii funcționale.
- 2026-03-12: Pentru discrepanțe mari de cost pe read-side agregat, verifică explicit grain-ul sursă (`account_daily`) și aplică fereastra de validitate a mapping-ului la data reportului; altfel apar supraestimări și costuri în luni nevalide.
- Media Buying/read-side SQL changes must be cross-checked against actual runtime column names in `client_registry` schema bootstrap + migrations (e.g., `agency_platform_accounts.currency_code`, not guessed aliases like `account_currency`) before merge.
- For read-side history windows, never reuse mapping audit timestamps (`created_at`/`updated_at`) as temporal validity unless product explicitly defines business-validity fields; mapping should usually scope membership only while bounds come from fact-table dates.
- When fixing attribution regressions, treat currency source precedence as a correctness contract: prefer row/account source-of-truth currency over client-level mapping currency to avoid accidental double conversion.
- Dashboard and Media Buying must share the same attribution contract (account_daily grain, mapping validity window, account-level currency precedence); if one path diverges, platform totals will drift even when ingestion is correct.
- Do not use mapping audit timestamps (`created_at`) as historical lower bounds in read-side analytics; that turns membership metadata into data-loss filters and truncates valid history.
- 2026-03-12: După feedback că PR-ul anterior nu a adresat problema reală, pentru buguri de totals read-side livrează observability backend first (endpoint diagnostic + teste de reconciliere) înainte de orice refactor de business logic.
- 2026-03-12: După feedback că diagnosticul anterior nu era suficient, fixul de monedă pentru conturi atașate trebuie implementat cu resolver unic reutilizabil (aceeași precedență în attach/listing/dashboard) + backfill doar pentru valori blank, fără overwrite la override-uri explicite.
- 2026-03-12: După feedback pe currency pentru sub-account dashboard, separă clar rezolvarea monedei sursă per cont atașat de selecția monedei de raportare client; folosește resolver dedicat pentru reporting currency (single vs mixed vs no-account) și reutilizează-l identic în dashboard + endpointul de reconciliere.
- 2026-03-12: După feedback că read-side currency fixes nu explică discrepanțele finale, livrează un endpoint de write-side audit care corelează persisted rows (grains/dates/currencies/customer_id) cu sync run/chunk errors și semnale explicite de anomalie înainte de orice schimbare de logică de sync.
- 2026-03-12: După corecție de workflow, aplic modificări de fișiere prin patch/edit direct (nu prin comenzi shell care învelesc patch-uri) ca să respect convențiile runner-ului.
- 2026-03-12: După feedback că fixul TikTok precedent era incomplet, pentru pași de hardening write-side livrează următorul increment strict pe persistență idempotentă (natural key + teste rerun/overlap), fără extinderi cross-platform.
- 2026-03-12: Pentru cleanup istoric write-side TikTok, nu marca automat alias + canonical ca ambiguu; restrânge identitatea de reparație la setul conturilor atașate și tratează aliasurile non-atașate ca candidate de rescriere/ștergere doar în cazuri cu metrici identice.
- 2026-03-12: După feedback că observability write-side era incompletă, pentru Meta backfill/sync trebuie propagat explicit coverage_status + retry metadata din execuția chunked către payload-uri run/account și marcat status error când rămân chunk-uri nerecuperate.
- 2026-03-13: After user dissatisfaction with prior PR scope, re-audit actual target pages/payloads first and ship the narrowly requested UX on the primary page before adding broad cross-cutting changes.
- 2026-03-13: When product scope says backend-only foundation, avoid mixing frontend or formula work; deliver a stable contract + deterministic calendar bucketing first.
- 2026-03-13: For follow-up worksheet tasks, reuse existing daily source methods directly (e.g., media_buying_store day rows) instead of introducing parallel raw-query paths.
- 2026-03-13: For scope-based editable values, persist against canonical resolved period keys so different anchor dates in same scope update the same logical record.
- 2026-03-13: For staged worksheet delivery, compute core numeric rows in backend sections from existing raw metrics first, and explicitly defer comparison/% rows to later tasks.
- 2026-03-13: When editing files in this runner, use the dedicated apply_patch tool directly instead of wrapping apply_patch via shell exec.
- 2026-03-13: After backend worksheet milestones, inspect current frontend surface before implementation and ship a minimal integrated worksheet shell first (toggle + scope + fetch + read-only scaffold), without redesign/editing.
- 2026-03-13: For worksheet frontend increments, split display scaffolds into dedicated table components early so formatting/hierarchy improvements stay focused without touching shell navigation state.
- 2026-03-13: For worksheet inline editing, derive editability from backend row metadata (`is_manual_input_row`, `source_kind`, manual dependency key) instead of brittle label-based checks.
- 2026-03-13: For frontend currency/rate editors, assert test outputs using robust selectors/payload checks instead of locale-fragile exact formatted strings.
- 2026-03-13: For worksheet header labels, never use local visible-week indexes; always map from real ISO calendar week numbers derived from week_start (including year-boundary behavior).
- 2026-03-13: For sub-account views, never let attached-account currency override client display currency; always derive display currency from `agency_clients.currency` and treat attached currencies strictly as source-metadata inputs.
- 2026-03-13: For Media Buying backend reads, treat `media_buying_configs.display_currency` as synchronized storage only; always resolve actual sub-account display currency from shared client display-currency decision (`agency_clients.currency`).
- 2026-03-13: For Media Tracker worksheet payloads, propagate display currency from Media Buying/client contract and mark primary money rows as display-aware (`currency_display` + `currency_code`) instead of hardcoded `currency_ron`; keep EUR rows explicit and null-safe without rate.
- 2026-03-13: For sub-account frontend money rendering, never hardcode RON defaults; always derive currency from backend `display_currency` plus row-level worksheet metadata (`value_kind`, `currency_code`) with safe USD fallback.
- 2026-03-13: For bulk currency drift repairs, default to dry-run semantics and skip `safe_fallback` clients instead of forcing guessed updates; only mutate deterministic client-level mirror fields (e.g., `media_buying_configs.display_currency`).
- 2026-03-13: After user dissatisfaction on a performance bug, re-open the exact backend hot path first and ship a narrow backend-only optimization (query count + matching cost + timing logs) before touching unrelated areas.
- 2026-03-13: For large read payloads after backend query optimization, add an opt-in lightweight response mode plus dedicated drill-down endpoint (months-first + month-days) before frontend rewiring, while keeping default behavior backward compatible.
- 2026-03-13: For frontend lazy-loading migrations, prevent automatic silent re-fetch loops after month-level fetch errors; persist per-scope month error state and require explicit retry.
- 2026-03-13: When converting read paths to optional/no-range fetching, harden helper method signatures and guard null date comparisons (`None > None`) before rollout; add regression tests for no-range automated-only/manual-only mixes.
- 2026-03-13: For frontend currency labels, never display a fabricated hardcoded fallback (e.g., USD) when metadata is missing; prefer real source priority (table -> client context) then neutral placeholder.
