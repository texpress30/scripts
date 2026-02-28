# Lessons

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
- 2026-02-27: Când utilizatorul cere exact `git pull origin main`, rulează comanda exact; dacă apare eroarea de reconciliere pentru branch-uri divergente, setează minimal `git config pull.rebase false` (local) și rerulează aceeași comandă pentru a finaliza sync-ul.
- 2026-02-27: Când utilizatorul cere cherry-pick după `git fetch --all`, dacă hash-ul scurt rămâne nerezolvabil (`bad revision`), verifică explicit disponibilitatea cu `git log --all`, `git show <hash>`, `git fetch origin <hash>` și documentează clar că obiectul nu există pe remote-ul curent.
- 2026-02-27: Pentru bug-uri runtime de tip `NameError` în diagnostice backend, verifică imediat consistența importurilor modulare cu pattern-ul folosit în celelalte servicii (ex: `try: import psycopg ...`) înainte de orice schimbare logică.
- 2026-02-27: Pentru deploy Railway, păstrează explicit `psycopg[binary]` în dependențele backend și verifică Docker build că rulează `pip install -r requirements.txt` la fiecare deploy.
- 2026-02-27: Pentru diagnostice DB cross-env, implementează query compatibil de schemă (ex: `provider` vs `platform`) și tratează explicit lipsa tabelului cu mesaj clar, fără să oprești endpoint-ul de diagnostics.
- 2026-02-27: Pentru investigarea cazurilor "connected dar rows=0", adaugă endpoint debug cu agregări DB-only (count/max/group-by) și inventar de tabele relevante pe coloane-cheie, fără a expune rânduri brute.
- 2026-02-27: Pentru endpoint-uri de orchestrare sync multi-account, expune obligatoriu counters observabili + sample IDs mascate + error summary sanitizat, iar când nu există mapping-uri valide răspunde 400 explicit (nu 200 gol) pentru a evita ambiguitatea operațională.
- 2026-02-27: Pentru probleme „mapped_accounts_count=0”, evită câmpuri derivate din registry UI și citește direct mapping-urile persistente (`agency_account_client_mappings`) cu endpoint-uri dedicate map/get ca sursă unică de adevăr pentru sync orchestration.
