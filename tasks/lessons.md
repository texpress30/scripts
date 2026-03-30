# Lessons

- 2026-03-25: După orice răspuns incomplet de tip status-only (ex. „Implemented.”), finalizez obligatoriu workflow-ul complet în același turn: verificări executate, commit făcut și `make_pr` apelat înainte de mesajul final.

- 2026-03-25: Pentru Media Tracker migrez business/manual pe regulă Data-layer-first la nivel de săptămână (nu pe zi), cu fallback legacy strict pe săptămânile fără rânduri Data layer și fără combinare în aceeași săptămână.

- 2026-03-25: După un PR marcat nesatisfăcător, aplic strict scope-ul nou cerut (aici doar Media Buying read path + UI read-only) și evit orice extindere în Media Tracker/Data page/business rules adiacente.

- 2026-03-25: Când userul reafirmă instrucțiuni AGENTS/process, execut imediat end-to-end în același turn (plan în todo + implementare + teste + commit + make_pr), fără răspuns intermediar de confirmare.

- 2026-03-25: Pentru endpoint-uri protejate apelate din layout/global effects (ex. favicon/branding), folosesc explicit guard de auth în helper (`requireAuth`) ca să evit requesturi 401 înainte de disponibilitatea tokenului.

- 2026-03-25: Când cerința impune compatibilitate backward pe payload opțional (`dynamic_custom_values`), tratez explicit diferența între „câmp omis” (păstrez existent) și „câmp prezent” (replace-all), pentru comportament determinist fără regresii.

- 2026-03-25: Când taskul cere canonicitate pentru un sub-domeniu (aici sales), mut explicit derivările în API/store pe sursa canonică nouă și păstrez bridge backward-compatible în același endpoint existent, fără extindere de scope UI.

- 2026-03-25: După feedback de tip “scope prea larg/nesatisfăcător”, următorul patch trebuie blocat strict pe cerința explicită (aici doar management definiții custom fields), fără schimbări în flow-urile excluse.

- 2026-03-25: După orice corecție/instrucțiune AGENTS de la user, pornesc execuția cu workflow complet în același turn (plan în `tasks/todo.md` + implementare + verificări), nu doar cu confirmări narative.

- 2026-03-24: Pentru roadmap Data în pași, livrez incremental strict pe slice-ul cerut (custom fields + daily custom values în acest task), fără să ating frontend sau alte write/read slices deja livrate.

- 2026-03-24: După feedback negativ pe un patch mixt, următorul task trebuie livrat strict pe scope-ul cerut (aici backend write API Data), fără atingeri frontend sau endpointuri adiacente.

- 2026-03-24: Când taskul cere explicit scope frontend-only după un PR nesatisfăcător, nu modific backend-ul deloc și tratez endpointurile existente ca contract fix; schimb doar paginile/tab-urile și testele UI relevante.

- 2026-03-24: La primul răspuns după corecții AGENTS, pornesc imediat cu workflow complet (plan în `tasks/todo.md` + execuție + verificare), nu trimit doar promisiuni de implementare.

- 2026-03-22: Pentru publish persistence feature-flagged pe Mongo, tratez strict ordinea `next_publish_id -> external publish (single call) -> upsert`; dacă upsert-ul cade după publish extern reușit, nu retry/replay în același apel și returnez succesul extern cu mirror local compatibil.

- 2026-03-22: Pentru mutații derivate migrate pe Mongo source-of-truth, activez flag-ul derivat doar împreună cu core-writes și tratez erorile Mongo read/upsert ca hard-fail (fără fallback local), cu local hydrate doar după persist reușit.

- 2026-03-22: Când feedback-ul cere Mongo source-of-truth doar pentru mutații specifice, adaugă un flag dedicat de core writes și separă explicit write snapshot (Mongo-first/fallback) de local mirror/cache; nu lăsa mutații locale înainte de succesul `upsert_asset`.

- 2026-03-22: Pentru rollout Mongo-first pe citiri, aplică flag separat doar pe `get_asset`/`list_assets`, prioritizează snapshot-ul Mongo când există și păstrează fallback local predictibil pe erori sau miss-uri.

- 2026-03-22: Pentru read-through incremental în creative workflow, implementează helper local-first + lazy hydration din Mongo doar pentru lipsuri, fără overwrite local și cu fallback predictibil pe erori (`not found`/list local).

- 2026-03-22: Pentru wiring incremental la Mongo în creative workflow, păstrează in-memory ca source of truth și aplică shadow-write best-effort doar pe mutații, cu flag OFF by default și fără mutarea read path-ului/publish flow în același task.

- 2026-03-22: Pentru ID-uri persistente cerute pe creative workflow, livrează întâi un repository Mongo separat de counters (atomic `find_one_and_update + $inc + upsert`), fără modificări în `creative_workflow.py` sau `/creative` până la taskul de wiring.

- 2026-03-22: Pentru fundamente de persistență cerute pe creative workflow, livrează întâi un repository Mongo pe agregat (colecție + indexuri + teste), fără wiring în `creative_workflow_service`/`/creative` până la taskul dedicat de integrare.

- 2026-03-22: După feedback „unsatisfied” pe un PR foundation mare, următorul pas trebuie să fie strict un singur punct real de integrare în worker (feature-flag OFF by default, best-effort, reversibil), fără extinderi în mai multe flow-uri sau endpoint-uri noi.

- 2026-03-21: Pentru TikTok ad-group facts, păstrez explicit ambele chei în `extra_metrics` (`adgroup_name` și `ad_group_name`) și propag `campaign_id`/`campaign_name` în upsert payload; altfel dashboard queries pe alias pot returna `NULL` deși numele sunt parse-uite.

- 2026-03-21: În metadata resolve TikTok, nu fac upsert fallback pentru entity rows fără semnal real (name/status/raw_payload toate goale); altfel pot suprascrie `platform_campaigns`/`platform_ad_groups` cu `NULL` și `{}` chiar când fetch-ul management API eșuează.

- 2026-03-21: Pentru TikTok ad_group_daily/campaign_daily, numele entity trebuie enrich-uite explicit din endpoint-urile de management (`campaign/get`, `adgroup/get`) imediat după report fetch; nu mă bazez pe `report/integrated/get` pentru name fields.

- 2026-03-21: Când userul cere explicit commit + make_pr în același task, finalizez obligatoriu în ordinea: verificări -> git commit -> make_pr; nu închid răspunsul înainte de ambele.

- 2026-03-21: După pull-uri cu merge conflict, verific imediat că test expectations rămân aliniate cu contractul runtime al schemelor (dimensiuni exacte), altfel apar regresii false.

- 2026-03-21: Pentru cerințe "EXACT tuple", rulez imediat comanda de introspecție pe runtime (`_report_schema_for_grain`) și atașez rezultatul, nu mă bazez doar pe diff-ul din commit.

- 2026-03-21: La TikTok `report/integrated/get`, `campaign_id` este valid în `campaign_daily`, dar pentru `AUCTION_ADGROUP` și `AUCTION_AD` trebuie menținute dimensiunile minime (`adgroup_id` / `ad_id`) și campania se rezolvă din metadata endpoint-uri.

- 2026-03-21: Pentru TikTok reporting cu IDs-only dimensions, păstrez alias parsing (`ad_group_id` și `adgroup_id`) în maparea răspunsului și aliniez schema per grain la contractul de persistență (campaign_id/ad_group_id/ad_id).

- 2026-03-21: După eliminarea `campaign_name` din report dimensions, tratez `campaign/get` și `adgroup/get` ca sursă principală pentru nume și acopăr explicit prin teste că fetch-ul rulează pe toate ID-urile, nu doar pe cele fără fallback.

- 2026-03-21: Pentru TikTok campaign_daily, persistența numelor în dashboard depinde de upsert metadata entity (`platform_campaigns`/`platform_ad_groups`) înaintea fact tables; dacă metadata fetch cade, sync-ul de performance trebuie să continue.

- 2026-03-21: Când userul marchează PR-ul ca nesatisfăcător, evit schimbări administrative-only; livrez fixul tehnic cerut în codul de producție și rulez verificările solicitate înainte de PR.

- 2026-03-21: În AppShell sub-account, nu folosi `company_settings.city/country` pentru cardul clientului; locația trebuie derivată din business profile-ul sub-account-ului (oraș + țară) cu fallback neutru.

- 2026-03-21: Pentru rute sub-account (`/subaccount/[id]`), validează explicit dacă `id` este `client_id` sau `display_id`; endpoint-urile noi trebuie fie să folosească identifier-ul canonic, fie să accepte robust ambele mappări pentru a evita `Client not found`.

- 2026-03-21: Dacă userul cere explicit „fără prefill”, nu folosesc nici fallback din endpointuri de display (`/clients/display`) și nici rehydrate localStorage; formularul se alimentează exclusiv din endpointul de profil dedicat sau rămâne gol.

- 2026-03-21: După ce utilizatorul corectează procesul/formatul, actualizez imediat `tasks/lessons.md` în același task și evit să trimit promisiuni de implementare înainte de execuție reală în repo.

- 2026-03-20: Când un sub-route placeholder devine pagină de lucru (ex. Google Ads), izolează schimbarea pe pagina respectivă și ajustează testele placeholder ca să nu rupi celelalte rute „Coming Soon”.

- 2026-03-20: Pentru chart-uri multi-line comparate cu un chart de referință, ascunde dots implicit (`dot={false}`) și lasă doar `activeDot` pe hover pentru claritate vizuală; crește min-height-ul (ex. `h-96`) înainte de a ajusta alte stiluri.

- 2026-03-20: Pentru cerințe de redesign chart punctual (ex. bar -> multi-line), păstrează contractul existent și extinde doar granularitatea seriei (`platform_spend` per zi) astfel încât frontendul să schimbe vizualizarea fără endpoint nou.

- 2026-03-20: Pentru cerințe de dashboard vizual, livrează întâi contractul additive pe endpoint-ul existent (`spend_by_day`) și construiește chart-urile direct din datele deja disponibile (ex. platform table), evitând endpoint-uri noi sau redesign.

- 2026-03-20: Pentru UI Agency Team cu grants, tratează selectorul de sub-account-uri strict condiționat de rol (`agency_member/viewer`), iar pentru `agency_owner/admin` ascunde controlul și nu trimite restricții în payload.

- 2026-03-20: Pentru roluri agency cu acces restricționabil pe sub-account, modelul corect este tabel de grants dedicat pe membership; listă goală înseamnă explicit acces nelimitat, iar enforcement/listing trebuie să aplice aceeași semantică.

- 2026-03-20: Când login-ul trebuie simplificat la email+parolă, nu păstra selecția de rol în frontend; fă `role` opțional doar pentru compatibilitate backward și derivă contextul exclusiv pe backend din memberships active cu prioritate agency/global.

- 2026-03-19: Când semantica auth se schimbă (forgot vs invite vs account-ready), aliniază simultan catalogul backend (descrieri + sample vars) și UI admin (Email Templates + Notifications hints), altfel runtime corect rămâne opac pentru operatori.

- 2026-03-19: Când același endpoint confirmă tokenuri de invite și forgot-reset, expune un endpoint mic de context (validate-only, non-consuming) pentru frontend, ca să poți diferenția copy-ul UX fără să fragmentezi contractul de confirm.

- 2026-03-19: Pentru create user fără parolă explicită, nu folosi niciodată hash fallback reutilizabil; persistă hash gol + `must_reset_password=true` și blochează login-ul DB până la confirmarea tokenului de setare inițială.

- 2026-03-19: Pentru Sub-account Team wizard create, nu păstra submit button cu label ambiguu (`Înainte`) în același `<form>` cross-tab; separă structural pasul 1 non-form și pasul 2 form cu CTA final explicit `Creează utilizator`.

- 2026-03-19: Pentru cerințe “delete user de peste tot”, nu reutiliza endpointul de remove membership; adaugă endpoint dedicat pe `user_id` + guard DB-backed în auth pentru a invalida tokenurile vechi după hard delete.

- 2026-03-19: Pentru wizard create în doi pași, evită `<form>` global peste etape; separă structural step1 non-form și step2 form cu footere distincte, altfel apar click-through/submit-through greu de eliminat doar cu guard-uri.

- 2026-03-19: După corecție de proces, nu raporta niciodată implementări/teste ca finalizate fără execuție reală în workspace; verifică explicit `git status` + comenzile rulate înainte de mesajul final.

- 2026-03-18: Pentru cerințe de nav filtering pe permissions, livrează în același patch atât filtrarea sidebar/settings cât și redirect guards pure + teste unit pentru fiecare scope (agency main, agency settings, subaccount main/settings), ca să eviți regresii de rute nepermise.

- 2026-03-18: După feedback "unsatisfied" pe un PR mare, livrează următorul increment strict pe pagina/flow cerut (aici Sub-account Team roles & permissions), cu wiring real pe contractele existente și teste compacte de regresie pentru create/edit + grant ceiling.

- 2026-03-14: Pentru ecrane tip wizard cu tab-uri verticale, validează în teste atât starea implicită (tab activ + secțiune avansată colapsată), cât și tranziția de expand + erori câmpuri obligatorii după submit.

- 2026-03-14: Pentru formulare UI mari cu mai multe carduri de update, adaugă teste separate pentru render-ul secțiunilor obligatorii și validările critice (email/telefon/url) plus confirmare toast pe submit valid.

- 2026-03-14: Pentru label-uri dinamice bazate pe config, testează separat cazul explicit cu label-uri setate și fallback-ul pentru null/whitespace, plus un assert de no-regression numeric pe același payload.

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
- 2026-03-21: Pentru buguri de denumiri campanii TikTok, verifică explicit ambele verigi: dimensiunile cerute în report API (`campaign_name`) și persistența entity în `platform_campaigns`; fixuri doar pe fallback UI nu rezolvă cauza.
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
- 2026-03-16: După feedback că schimbarea pentru "Echipa Mea" a deviat spre listă/tabel, la task-uri de UI trebuie revalidat explicit ecranul țintă și fluxul cerut (ex. wizard Add/Edit) înainte de implementare, fără a înlocui produsul cu altă interfață necerută.
- 2026-03-16: După feedback că soluția precedentă nu a adresat taskul real, la cereri de UI trebuie livrată implementarea efectivă în ruta țintă (component + teste), nu doar actualizare de documentație/task list.
- 2026-03-16: După feedback că taskul a fost mutat greșit pe frontend, pentru cerințe backend-only livrează fundația de date/API + teste fără redesign UI și fără schimbări de login dacă sunt explicit out-of-scope.
- 2026-03-16: După feedback pe Agency Team, când backend livrează endpoint dedicat de options, frontendul trebuie legat la acel endpoint (fără opțiuni hardcodate) și validarea dependentă de tip utilizator trebuie acoperită prin teste de submit payload.
- 2026-03-16: Pentru psycopg3, evită parametrizarea DDL (`CREATE TABLE ... DEFAULT %s`); folosește SQL static sau `sql.Literal`, altfel startup poate crăpa cu `IndeterminateDatatype`.
- 2026-03-16: La migrarea rolurilor, normalizează central aliasurile legacy înainte de verificări RBAC/Auth și testează explicit mapping-ul (`account_manager`/`client_viewer`) ca să eviți regressii de compatibilitate.
- 2026-03-16: Când userul cere auth DB-first, prioritizează explicit validarea membership-ului la login (inclusiv caz ambiguu 409) și păstrează fallback-ul env admin strict ca mecanism de urgență.
- 2026-03-16: Pentru endpointuri sub-account, aplică enforcement în doi pași: întâi RBAC scope `subaccount`, apoi restricție pe `subaccount_id` din token pentru rolurile `subaccount_*`; nu te baza doar pe rol.
- 2026-03-16: După renumirea/helper unificarea funcțiilor de hash, caută global referințele legacy (ex. `_hash_password`) înainte de livrare și rulează startup import check pentru a preveni NameError la boot.
- 2026-03-16: Când primești un crash report pe o linie specifică, rulează imediat verificările exacte cerute (`rg '_hash_password\('` + startup import) înainte de a presupune că fixul precedent nu a fost aplicat.
- 2026-03-17: Când utilizatorul semnalează că o pagină frontend folosește încă mock-uri locale, verifică explicit constantele de tip `INITIAL_*` și acțiunile locale CRUD, apoi înlocuiește-le cu apeluri reale + refetch.
- 2026-03-17: Pentru integrări noi agency-level, reutilizează `integration_secrets_store` + patternul de router/audit/RBAC existent; evită sisteme paralele și testează explicit masking-ul secretelor în status/read endpoints.
- 2026-03-17: Pentru carduri de integrare care colectează secrete (ex. API keys), UI-ul trebuie să afișeze exclusiv valori mascate din backend și să ceară reintroducerea secretului la update, fără prefill sensibil.
- 2026-03-17: La flow-uri forgot/reset, păstrează răspunsul generic pentru email necunoscut (anti-enumeration), stochează doar hash-ul tokenului și marchează tokenurile one-time cu expirare + consumed_at.
- 2026-03-17: După corecție pe scope auth reset, când taskul cere explicit foundation backend-only trebuie eliminate endpointurile/features out-of-scope (ex. forgot-password și Mailgun send) și livrat strict contractul cerut.
- 2026-03-17: Când taskul următor reactivează explicit forgot-password + Mailgun peste fundația reset, trebuie reintrodus endpointul incremental fără a atinge login/impersonation și cu răspuns generic anti-enumeration.
- 2026-03-17: Pentru pagini App Router care citesc query params în client components, evită blocajele de build cu `useSearchParams` în rute statice; folosește fallback robust (ex. citire din `window.location.search` în `useEffect`) dacă nu vrei Suspense boundary.
- 2026-03-17: Pentru invite backend pe memberships existente, aplică autorizare în funcție de `scope_type` al membership-ului (agency vs subaccount) și reutilizează `reset-password/confirm` pentru consumul tokenurilor `invite_user` fără schimbarea contractului public.

- 2026-03-17: Pentru acțiuni UI per-rând (ex. invite), păstrează loading local pe item și mapează explicit codurile backend critice (403/404/503) în mesaje UX clare, fără blocarea întregii pagini.

## 2026-03-17 — Respect bug-report scope before adjacent hotfixes
- When user reports a concrete production blocker on specific endpoints, reproduce and fix those endpoints first before touching adjacent auth flows.
- Add an explicit “scope guard” checklist item in `tasks/todo.md` naming out-of-scope endpoints to avoid drift.
- For 500 regressions on list endpoints, always test malformed legacy rows (invalid IDs/unknown role keys/null-ish fields) to prevent serialization crashes.
- 2026-03-17: Când endpointul backend pentru o acțiune UI există deja (ex. invite), reutilizează helperul API comun în toate paginile relevante înainte de a crea logică nouă; păstrează loading per-row + mapping explicit 403/404/503 pentru UX stabil.
- 2026-03-17: Când un flux devine multi-step în același submit (ex. create + invite), tratează success complet vs success parțial explicit în UI și nu te baza pe erori globale care pot fi resetate de refetch imediat.
- 2026-03-17: Pentru auth subaccount, evită modelul single-active-subaccount în token; păstrează listă explicită de sub-account-uri permise și tratează enforce pe această listă, cu fallback backward-compatible pentru tokenuri legacy.

- 2026-03-17: După feedback de tip "unsatisfied" pe PR anterior, re-verific strict scope-ul cerut (evită schimbări extra), apoi livrează incremental cu teste țintite exact pe cerințe înainte de commit/PR.
- 2026-03-17: La UI condițional cu secțiuni similare textual (ex. "Roluri și Permisiuni" în sidebar + content), în teste validează prezența controalelor funcționale (checkbox/toggle) în locul textului comun pentru a evita false-positive.
- 2026-03-17: După feedback de tip "unsatisfied", livrează strict pe scope-ul nou cerut (fără zone adiacente) și include explicit contractele UI↔API necesare în teste (payload + grant ceiling) înainte de commit/PR.

## 2026-03-17 — After user correction: avoid placeholder-only PR state
- Pattern: User was unsatisfied with prior output where progress was not reflected as substantive feature implementation.
- Rule: For feature requests, always implement code + tests end-to-end before finalizing; never leave a docs-only/placeholder-style change when concrete scope was requested.
- Rule: Validate requested behavioral outcomes explicitly (not only command execution), and summarize any remaining scope as intentional next-task items.
- 2026-03-17: După feedback de tip "unsatisfied" pe enforcement backend, mapează explicit fiecare modul din sidebar către endpointuri backend reale folosite de UI (inclusiv endpoint dedicat când mapping-ul lipsește), nu te baza doar pe filtrare frontend.
- 2026-03-17: După feedback de tip "unsatisfied" pe foundation backend membership edit, păstrează strict modelul pe `membership` (nu `user identity`) și validează explicit prin teste separate agency vs subaccount vs inherited înainte de commit.
- 2026-03-17: După feedback pe taskul UI edit Agency Team, reutilizează form-ul existent pentru edit fără redesign, dar mapează strict payload-ul PATCH la câmpurile suportate de backend și blochează explicit câmpurile identity în UI.

## 2026-03-17 — Recovery after unsatisfactory prior PR
- When a user signals the previous PR was unsatisfactory, explicitly re-validate scope boundaries first (what must change vs what must stay untouched), then map each requirement to tests before coding.
- For lifecycle tasks, verify both state transition endpoints and all read/access consumers (login, access-context, grantable modules, list/detail contracts), not just write paths.

- 2026-03-17: Pentru lifecycle actions în tabele existente, mock-uiește explicit helperii noi din `@/lib/api` în teste (nu doar `apiRequest`), altfel funcțiile reale pot folosi `fetch` și dau erori de URL în test runner.

- 2026-03-17: Pentru teste lifecycle pe rânduri de tabel, evită scenarii multi-eroare într-un singur test când list-refetch schimbă datele; split în teste mici (403/404/409 separat) pentru stabilitate și diagnoză rapidă.
- 2026-03-18: Când userul cere explicit scope minim backend-only, livrează strict endpoint+service+teste cerute și evită extinderi UI/workflow; validează criteriile de protecție (inherited/self/RBAC) înainte de commit.
- 2026-03-18: Pentru task-uri cu cerință explicită de PR non-placeholder, după `make_pr` validează imediat title/body și pregătește fallback GitHub REST API (`curl`) când `gh` nu este disponibil.
- 2026-03-18: Când taskul cere explicit implementare pe o pagină target (ex. Sub-account Team), evită extinderea în alte pagini și reutilizează helperii comuni existenți fără duplicare de API helpers.
- 2026-03-18: Când utilizatorul cere explicit "backend minimal foundation" (read-only catalog + list/detail), păstrează patch-ul strict la service/router/scheme/teste backend și evită orice UI, DB overrides sau migrare a fluxurilor existente în același task.
- 2026-03-18: După feedback "unsatisfied" pe Email Templates, livrează incremental backend în doi pași separați (read-only catalog, apoi DB overrides + save/reset), cu teste explicite pentru fallback default vs override și fără migrarea fluxurilor forgot/invite în același task.
- 2026-03-18: Pentru migrarea emailurilor operaționale la template-uri DB-backed, introduce mai întâi un renderer deterministic simplu (`{{var}}`) în service, apoi conectează incremental fiecare flow (forgot/invite) cu fallback default, gating pe `enabled`, și teste explicite pe text+html.
- 2026-03-18: Pentru task-uri UI admin peste API deja existent (ex. Email Templates), livrează întâi un editor simplu list/detail/save/reset cu stări clare (loading/error/success) și teste pe contracte API, lăsând preview/test-send/WYSIWYG pentru pași ulteriori.
- 2026-03-18: După feedback "unsatisfied" pe un PR full-stack, următorul increment trebuie să fie strict pe UX-ul cerut (frontend-only, contract backend existent), cu teste țintite pe stările cerute și fără extinderi backend premature.
- 2026-03-18: Pentru taskuri de preview render peste template-uri existente, livrează endpoint dedicat + sample variables canonice + wiring UI Preview cu teste pentru draft payload și erori, fără a adăuga test-send în același pas.
- 2026-03-18: Pentru incrementalul de test-send pe Email Templates, reutilizează render preview + sample variables existente și tratează explicit regula "enabled=false permite test send" ca behavior documentat și testat.
- 2026-03-18: Pentru WYSIWYG incremental pe câmp HTML existent, preferă implementare lightweight fără dependențe grele când proiectul nu are editor existent; păstrează toggle Visual/HTML și verifică explicit că preview/test-send folosesc draftul curent.

- 2026-03-18: După un mesaj de corecție cu reguli AGENTS, oprește execuția curentă și aliniază imediat workflow-ul (plan în `tasks/todo.md`, verificare scope, commit+PR), fără a presupune că starea precedentă este încă validă.
- 2026-03-18: Când un item Agency trebuie mutat în Settings fără schimbare de rută, tratează ruta respectivă ca settings context în AppShell și mută link-ul în `AGENCY_SETTINGS_ITEMS`, astfel încât navigarea rămâne coerentă și testabilă.
- 2026-03-18: Pentru integrare sensibilă la secrete (Mailgun), păstrează precedence DB > env, dar expune explicit `config_source` și oferă endpoint admin de bootstrap din env în DB pentru migrare fără dublă introducere manuală.
- 2026-03-18: Pentru foundation notifications separat de templates, livrează întâi modelul backend (catalog + override `enabled` + CRUD + RBAC + teste) și păstrează explicit flow-urile runtime neschimbate până la taskul de migrare.
- 2026-03-18: Pentru test-send prin provider extern (Mailgun), răspunsul/UI trebuie să declare explicit "accepted" (nu "delivered") și să expună diagnostice minime (`provider_id`, `provider_message`, `delivery_status`) + hint pentru sandbox domains.
- 2026-03-18: După corecții AGENTS, verifică imediat `git status` și livrează final doar după pașii obligatorii complet executați (teste, commit, `make_pr`) + raport final cu citări pe fișiere/linie.
- 2026-03-18: Pentru cleanup UX incremental, elimină controalele duplicate dintre Integrations și Email Templates (ex. test-send) doar din UI-ul redundant, fără să ștergi backend-ul dacă poate fi reutilizat de alte ecrane.
- 2026-03-18: Când se elimină exporturi din fișiere partajate (ex. api.ts), validează obligatoriu că nicio altă componentă nu le mai importă; curățarea codului mort (inclusiv funcții șterse) trebuie să includă și curățarea importurilor și stărilor frontend corespunzătoare pentru a preveni erori TypeScript în CI/Vercel.
- 2026-03-19: Pentru erori de tip `ConnectionTimeout` la startup în mediul de producție/serverless, adaugă un mecanism de retry cu sleep fix in blocul de `startup` (ex: `main.py`) înainte ca modulele dependente să încerce să inițializeze conexiuni.
- 2026-03-19: Evită executarea de DDL (`CREATE TABLE`, `ALTER TABLE`) în cadrul evenimentelor de startup (`@app.on_event("startup")`) ale aplicației web. Într-un deploy blue-green (ex. Railway), noul container va încerca să obțină `ACCESS EXCLUSIVE` lock pe tabele active, blocând procesul de startup și declanșând un crash loop prin timeout-uri repetate pe rutele de sănătate. Bazează-te pe migration runner în producție.
- 2026-03-19: Pentru integrări dezactivate prin feature flag, asigură-te că erorile de tip "disabled by feature flag" salvate în backend sunt interpretate corect în frontend ca status "unknown" / "Disabled". Nu le trata ca erori sau warning-uri obișnuite, altfel UI-ul va afișa bannere de degradare a sincronizării în mod fals.

- 2026-03-19: Când adaugi un nou parametru într-un INSERT SQL (`must_reset_password`), aliniază explicit numărul placeholderelor din VALUES cu tuple-ul de parametri și adaugă test țintit pe query/params pentru a preveni regressii de tip "X placeholders but Y parameters".

- 2026-03-19: Pentru wizard-uri pe un singur `<form>`, nu e suficient ca butonul de step să fie `type="button"`; trebuie și guard în `onSubmit` pentru pasul curent, altfel Enter key poate declanșa submit/create prematur din pasul 1.

- 2026-03-19: Pentru cron-uri one-shot DB-backed, tratează explicit erorile de conexiune la nivel de entrypoint (nu doar în store) și returnează un summary controlat + warning scurt, altfel deploy-ul vede crash opac pe timeout tranzitoriu.

- 2026-03-19: Când un câmp legacy (ex. `location`) nu mai are semnificație de business, nu îl cosmetiza cu valori hardcodate; elimină-l din UI-ul editabil și afișează explicit un summary derivat din datele reale de acces (`subaccount`/`agency`).

- 2026-03-19: Când un wizard folosește un singur `<form>`, aplică guarduri în două straturi (event-level + submit-level) și adaugă test separat pentru `fireEvent.keyDown(..., Enter)`; doar `fireEvent.submit` nu acoperă toate căile reale din browser.
- 2026-03-19: După feedback că un wizard "deja fixat" încă nu satisface review-ul, adaugă un guard defensiv în `submit` pentru pasul activ și un test explicit "no API before final + exact one call on final CTA" în pagina țintă.

## 2026-03-20 — Duplication fix after user dissatisfaction
- Când userul cere explicit replicarea unei structuri existente pe alte rute/platforme, extrage imediat un component comun reutilizabil în loc de copiere/implementări separate.
- În același task, aliniază contractele backend/frontend pe toate platformele vizate și adaugă teste dedicate per rută nouă, plus ajustări pe testele vechi de placeholder.

## 2026-03-20 — Drilldown follow-up after unsatisfied review
- Când userul cere explicit drilldown navigabil (listă -> detaliu), verifică din primul patch existența rutei țintă App Router + link-uri reale în tabelul sursă și adaugă teste pentru href/navigation contract.

## 2026-03-20 — Status semantics and normalization after unsatisfied review
- Nu seta fallback implicit `active` pentru statusuri când metadata lipsește; folosește `unknown` neutru și mapare UI explicită (active / paused / unknown).
- Pentru platforme cu multiple formate de account id (ex. Meta `act_123` vs `123`), normalizează account_id în toate join-urile și filtrele (facts + mappings + metadata), nu doar într-un singur query.
- 2026-03-20: Când utilizatorul re-atrage atenția asupra AGENTS workflow, aplică imediat pașii obligatorii în ordine (plan în `tasks/todo.md`, verificări executate, commit, apoi `make_pr`) înainte de mesajul final.
- 2026-03-20: Când drilldown-ul depinde de tabele entity-level, verifică explicit că write helpers pentru fiecare grain persistă și în non-test-mode; un helper care întoarce `0` în producție poate face UI-ul gol chiar dacă account_daily are date.
- 2026-03-20: Pentru erori Postgres `numeric field overflow` pe sync-uri chunked, investighează întâi derivarea metricilor (ex. `action_values` sum) și adaugă izolare row-level la persistență; altfel un singur row invalid poate bloca tot chunk-ul.
- 2026-03-21: Pentru TikTok când UI arată `campaign_id`, verifică mai întâi schema `report.integrated.get` pe `dimensions` (ex. lipsa `campaign_name`) și completează cu metadata fetch + persist în `platform_campaigns` înainte de orice fix frontend.
- 2026-03-21: Nu adăuga câmpuri nevalidate în TikTok reporting `dimensions` (ex. `campaign_name`); confirmă suportul endpoint-ului și rezolvă numele prin `campaign/get` + persist în `platform_campaigns`.
- 2026-03-21: Pentru buguri runtime TikTok dimensions, adaugă test direct pe request params finali din `_fetch_*_metrics` (nu doar pe schema) ca să previi regresii unde builder-ul reintroduce câmpuri invalide.
- 2026-03-21: Nu randa niciodată în UI normal blob-uri tehnice (`Observability: {...}`); convertește marker-ele interne în mesaje operaționale scurte și păstrează dump-ul doar pentru debugging intern.
- 2026-03-21: După feedback "unsatisfied" pe un PR complex, următorul patch trebuie să înceapă cu audit explicit al rutelor existente + surselor reale de date și să livreze drilldown complet navigabil (link în tabel sursă + rută destinație + endpoint backend filtrat) în același increment, cu teste pe ambele capete.
- 2026-03-21: Pentru TikTok `ad_group_daily`, nu presupune că reporting returnează `campaign_id`/`adgroup_name`; rezolvă explicit metadata prin `adgroup/get` pe `adgroup_id`, mapează `campaign_id` înainte de upsert facts și păstrează flow-ul best-effort dacă metadata fetch/persist eșuează.
- 2026-03-21: Pentru cerințe UI de navigație repetate pe mai multe pagini similare, auditează mai întâi componenta shared (dacă există) și implementează linkul o singură dată acolo, cu teste per pagină pentru href corect.
- 2026-03-21: Când utilizatorul reamintește explicit AGENTS workflow, încep imediat cu plan documentat în `tasks/todo.md`, marchez progresul în același task și includ obligatoriu commit + `make_pr` în același turn de livrare.
- 2026-03-21: Pentru dropdown-uri cerute explicit cu "sortare alfabetică", verific ordinea tuturor opțiunilor (nu doar cele noi) și acopăr ordinea exactă într-un test de UI pe lista de `<option>`.
- 2026-03-21: După feedback pe persistența TikTok names/IDs, verific explicit atât payloadurile fact (`extra_metrics` + foreign keys), cât și clauzele SQL `ON CONFLICT DO UPDATE` care trebuie să suprascrie valorile NULL existente cu `EXCLUDED`, apoi acopăr prin teste țintite.
- 2026-03-22: După feedback "unsatisfied", la task-uri de infrastructură minimală păstrez strict fundația cerută (deps + config + providers + teste) și evit explicit endpoint-uri noi sau schimbări de contract API.
- 2026-03-22: După feedback pe foundation storage, păstrez strict stratul de metadata (model + repository + indexuri + teste) fără a atinge endpoint-uri, upload/presigned flow sau creative workflow.
- 2026-03-22: Pentru upload-init direct în S3, separ logică în service dedicat (validare + key + draft + presign), las router-ul subțire și mappez explicit erorile de config/provider la 503 runtime, fără side effects la startup.
- 2026-03-22: Pentru upload-complete, tratez `media_id` ca sursă unică de adevăr (draft Mongo + storage intern), verific obiectul prin `head_object`, fac `mark_ready` doar după succes și păstrez endpointul idempotent pentru status `ready`.
- 2026-03-22: Pentru API-urile read media, păstrez service separat de router, filtrez strict pe client_id, aplic default status safe (`exclude purged/delete_requested`) și folosesc 404 pentru inexistent/mismatch fără leak.
- 2026-03-22: După un review "unsatisfied" pe storage read, refac auditul pe codul deja introdus și aplic un patch minim, focalizat pe contractul endpointurilor + predictibilitate (sort deterministic, validări explicite client_id) cu teste țintite înainte de commit/PR.
- 2026-03-22: Pentru presigned access URL task, păstrez flow-ul izolat într-un service dedicat (record Mongo -> ownership/status/storage validation -> presign get_object) și evit explicit head_object/delete/creative/frontend; acopăr fiecare stare cerută cu teste mici și clare.
- 2026-03-22: Pentru soft delete media, aplic service separat strict Mongo-only (fără S3 calls), cu reguli explicite pe statusuri (ready/draft delete, delete_requested idempotent, purged/not-found/mismatch => 404) și teste dedicate pe fiecare caz.
- 2026-03-22: Pentru cleanup batch peste `delete_requested`, tratez `NoSuchKey` ca succes logic idempotent, continui batch-ul la erori per-item și marchez `purged` doar după delete_object reușit (sau obiect deja lipsă), păstrând datele storage în Mongo.
- 2026-03-22: Pentru rulare operațională Railway fără endpoint public, adaug un runner non-HTTP minim (`python -m ...`) care parsează limit opțional, face fallback la config, emite summary JSON în stdout și întoarce exit code 0 pentru per-item failures/skips, non-zero doar la eroare globală.
- 2026-03-22: Pentru helper intern ingest bytes, păstrez fluxul simplu și paralel cu user upload (draft -> put_object -> mark_ready), restricționez `source` la backend intern, reutilizez sanitize/key format existent și evit endpoint/job wiring în același task.
- 2026-03-22: Pentru remote fetch ingest, păstrez helper separat care validează URL minim (scheme + host local block), aplică timeout/max-bytes din config și deleagă strict upload/persist către `StorageMediaIngestService`, fără endpoint/retry/SSRF hardening complet în același pas.
- 2026-03-22: După un reminder AGENTS explicit în mesajul userului, opresc orice execuție implicită și fac imediat alinierea de proces în ordine: note plan/check-in în `tasks/todo.md`, rulez verificare minimă, apoi finalizez obligatoriu cu commit + `make_pr` în același turn.
- 2026-03-22: După feedback „unsatisfied” pe un foundation PR mare, următorul increment trebuie livrat strict pe cerința punctuală (aici `media_id` feature-flagged în creative variants), cu validări centralizate, compatibilitate legacy explicită și teste focused pentru OFF/ON + persistență/hidratare.
- 2026-03-22: Pentru recommendations history source-of-truth incremental, migrez strict metodele service cerute pe repository Mongo feature-flagged (generate/list/get/review/actions), păstrez `get_impact_report` + `/ai/legacy` intacte și evit orice fallback in-memory când flag-ul ON.
- 2026-03-22: Pentru migrare incrementală logo profile la storage, înlocuiesc strict fluxul FileReader/dataURL cu helper reutilizabil init->upload->complete și persist `logo_media_id` + fallback preview robust în backend, fără delete storage/backfill sau extinderi Creative UI.

- 2026-03-22: După orice corecție de proces din partea userului, verific imediat AGENTS.md, aliniez workflow-ul (plan/check-in/track/review) și actualizez `tasks/lessons.md` în același turn.
- 2026-03-22: Pentru buguri storage `/uploads/init` cu 500 generic, investighez mai întâi excepția reală din path-ul `initialize_indexes/create_draft`, mapez predictibil la RuntimeError/StorageUploadInitError și adaug logging contextual în router (client_id/kind/original_filename) înainte de a atinge UI.
- 2026-03-22: Pentru cerințe de branding sidebar după profil business update, prefer sursa canonicală deja disponibilă (`/clients/{id}/business-profile` cu `logo_url`) și reutilizez evenimentul existent de refresh; evit extinderi backend inutile când payloadul deja conține logo preview.
- 2026-03-23: Pentru company logo migration la storage, extind minim contractul existent cu `logo_media_id` opțional și mențin `logo_url` ca fallback preview; evit dependențe noi de UI prin eveniment simplu `company-settings-updated` pentru refresh de branding în AppShell.
- 2026-03-23: După un request explicit de branding global (favicon), verific întotdeauna dacă side-effect-ul există doar într-o pagină locală și îl mut în shell/layout global reutilizabil, păstrând sursa de date agency-only și fallback default testat.
- 2026-03-23: Pentru favicon global, nu este suficient să adaug un link nou în head; trebuie actualizate/sincronizate explicit toate link-urile icon relevante (`rel=icon` și `rel=shortcut icon`) ca să devină autoritare față de metadata statică.

- 2026-03-23: Pentru favicon bazat pe URL-uri de preview storage semnate, nu adăuga cache-busting în query string (`?v=`) deoarece poate invalida semnătura; folosește fragment (`#v=`) sau alt mecanism care nu modifică request query.

- 2026-03-23: Când brandingul global (favicon/title) trebuie să fie coerent pe landing + zone autentificate, nu monta logica doar în shell-ul intern; montează componenta globală în root layout comun și acoperă explicit navigarea între contexte.

- 2026-03-23: Când un task cere UI foundation pentru un modul existent, păstrez componentele curente intacte și adaug extensia într-un card/panou separat, cu callback simplu pentru integrarea viitoare, fără a conecta încă payload-urile backend sensibile.

- 2026-03-23: Pentru integrarea incrementală a media în Creative, dacă nu există UI real de add-variant, implementez fallback compact `create asset + first variant` în aceeași pagină și trimit simultan `media_id` + `media` legacy predictibil.

- 2026-03-23: Dacă backend-ul nu oferă endpoint detail separat, folosesc list endpoint-ul canonical pentru a deriva detail-ul selectat și evit inventarea de API nou; completez cu stări locale explicite pentru selecție/preview/add-variant.
- 2026-03-23: După feedback "unsatisfied" pe Creative UI incremental, păstrez patch-ul strict local și verific explicit cerințele UX minime (blocare acțiune fără context, metadate vizibile pentru variante, loading/error robust) înainte de commit, fără extinderi backend inutile.
- 2026-03-23: După feedback "unsatisfied" pe Creative, adaug incremental doar secțiunea UI cerută (ex. publish) în cardul existent al asset-ului selectat, mapând strict contractul endpointului real (`required + optional`) și acoperind explicit loading/success/error + refresh/context în teste.
- 2026-03-23: După feedback “unsatisfied” pentru scope depășit, păstrez patch-ul strict pe domeniul cerut (aici doar migrații), fără modificări în API/services chiar dacă există schimbări anterioare în branch.
- 2026-03-23: Când taskul cere strict helper-e pure într-un store nou, evit implementarea prematură a CRUD/SQL și stabilizez întâi contractele pure + teste izolate.
- 2026-03-23: Pentru rollout CRUD incremental pe store, implementez strict bucata cerută (ex. custom fields list/create/validate) și las explicit neatinse funcțiile din fazele următoare.
- 2026-03-24: Când branch-ul diverge la pull și apar conflicte largi nelegate de task, finalizez sync minim cu strategie non-disruptivă (`merge -X ours`) și continui strict pe fișierele din scope.
- 2026-03-24: Pentru taskuri de archive soft-delete incremental, implementez comportament idempotent (nu rescriu `archived_at` la re-apel) și verific explicit efectul asupra listărilor active/inactive în teste.
- 2026-03-24: Pentru `get_or_create` incremental pe cheie unică, păstrez fluxul simplu lookup-first + insert defaulturi canonice, cu validări stricte de input și teste explicite de idempotency.
- 2026-03-24: Pentru `upsert` incremental pe rânduri daily, folosesc `get_or_create` ca sursă unică de canonical lookup/create și limitez update-ul strict la câmpurile numerice permise în task.
- 2026-03-24: Pentru note text pe entități daily, normalizez la trim + blank->NULL și păstrez update strict pe coloana `notes`, fără side-effects pe câmpurile numerice.
- 2026-03-24: Pentru listări daily filtrate pe interval, aplic validare strictă a capetelor și ordonare deterministică explicită în query (`metric_date DESC`, `source ASC`, `id ASC`).
- 2026-03-24: Pentru mapări derivate din list endpoint intern, refolosesc lista canonicală existentă și construiesc cheia compusă deterministic `(metric_date, source)` pentru a evita duplicarea logicii de query/validare.
- 2026-03-24: Pentru sale entries incrementale, separ explicit validarea părintelui daily input de validarea amount/text/sort și calculez `gross_profit_amount` strict derivat în payload, fără coloană stocată.
- 2026-03-24: Pentru update/delete incremental pe sale entries, folosesc lookup explicit pe `sale_entry_id`, update parțial doar pe câmpurile primite și delete hard fără reordonarea automată a sort_order-urilor rămase.
- 2026-03-24: Pentru daily custom values, validez obligatoriu ownership-ul `daily_input.client_id == custom_field.client_id` înainte de upsert și aplic validarea `count` vs `amount` pe `numeric_value` la nivel de store.
- 2026-03-24: Pentru delete pe cheie compusă la daily custom values, fac lookup strict pe `(daily_input_id, custom_field_id)` și returnez payloadul rândului șters în același contract folosit de list/upsert.
- 2026-03-24: După un feedback de corecție pe livrare incompletă, finalizez în același turn fixul până la teste verzi și închid obligatoriu cu commit + make_pr, fără mesaje intermediare de "continui după confirmare".

- 2026-03-24: Când userul cere rewiring Media Buying/Media Tracker pe Data layer, aplic strict source-of-truth swap + UI read-only cu CTA către /data, fără extindere în migrații/cleanup sau refactoruri laterale.
- 2026-03-24: După un feedback de tip „nu opri la jumătate”, nu trimit status intermediar; închid taskul end-to-end în același turn (fix + teste + commit + make_pr) sau nu livrez deloc ca final.
- 2026-03-24: Când userul limitează explicit taskul la un sub-form (`Adaugă rând`), nu ating alte zone (tabel principal, Media Buying/Tracker, backend) și implementez strict câmpurile/calculul/salvarea cerute.
- 2026-03-24: Pentru feedback UI strict pe formular, tratez explicit cerințele de ordine/label/blank-state înainte de logică suplimentară și evit complet placeholder/default-uri vizibile dacă userul cere formular clasic.
- 2026-03-24: Când business rule-ul corect schimbă source-of-truth (manual fields vs derivat din sale entries), aliniez simultan store+API+reporting readers+UI și testele, ca să evit inconsistențe între pagini.
- 2026-03-26: Pentru flow canonic Data, validez explicit `source` atât în frontend (pre-submit), cât și în backend (422 clar cu allowed values), ca să evit false-success când config/fallback trimite chei invalide.
- 2026-03-26: La cleanup-ul Data page, elimin complet atât UI-ul cât și state/handlers dedicate fluxurilor legacy (vânzări/mențiuni) și păstrez strict payloadul canonic editabil, cu teste care verifică explicit absența controalelor scoase.
- 2026-03-26: Pentru endpoint-ul canonic daily-input, resping explicit câmpurile legacy (422) și evit orice side-effect implicit pe sale_entries/derivări, ca să nu apară ștergeri ascunse la save standard.
- 2026-03-26: Când separ contractul read-side Data config, țin `fixed_fields` strict pentru inputuri canonice editabile și mut labels read-only în `derived_fields`, iar frontend-ul citește explicit ambele hărți de label.
- 2026-03-26: După feedback de tip “readu câmpurile lipsă”, restaurez strict slotul unic de vânzare în Data (form + tabel + POST dedicat) fără a redeschide multi-sale/mențiuni și fără a modifica payloadul canonic daily-input.
- 2026-03-26: Când userul cere ordine exactă UI + delete per rând, aliniez explicit secvența formularului cu ordinea header-elor din tabel și folosesc identificatorul canonic `daily_input_id` pentru endpoint dedicat de ștergere (fără delete pe toată ziua).
- 2026-03-26: Dacă business-ul cere revenirea unor summary fields în canonical save (`custom_value_4_amount`, `sales_count`), le mut în `fixed_fields` + payload canonic și păstrez `custom_value_5_amount` strict derivat/read-only, fără cuplare implicită la `sale_entries`.
- 2026-03-26: Când există cerință de multi-rând pe aceeași zi+sursă, separ explicit create (POST nou) de update (PATCH pe `daily_input_id`) și elimin presupunerea de unicitate la nivel DB, altfel frontend-ul singur nu poate evita suprascrierea.
- 2026-03-26: După ce userul cere explicit relaxarea unei validări (`source` optional), aliniez simultan frontend + backend + teste pentru aceeași regulă canonică (blank -> `unknown`, non-blank invalid -> 422) înainte de mesajul final.
- 2026-03-26: Când userul cere eliminarea completă a unor câmpuri UI (`Marcă`/`Model`), elimin simultan inputuri + coloane + state/type/payload locale și adaug test explicit de absență atât în formular, cât și în header-ul tabelului.
- 2026-03-26: Pentru cerințe de prezentare strict UI pe o coloană (`Val. Vândută`), modific doar formatter-ul/randarea acelei coloane și acopăr explicit total lunar + rând zilnic cu test de absență paranteze.
- 2026-03-26: Pentru task-uri Media Tracker UI+backend punctuale, verific explicit endpoint-uri blocate `410` și reactivez doar cele cerute (`eur-ron-rate`) în paralel cu teste front/back pe edit+persist, fără a redeschide editări manuale necerute.
- 2026-03-26: Când userul cere styling pe o coloană "de sus până jos", verific explicit ambele rânduri de header + toate celulele de date ale coloanei, nu doar header-ul principal și un singur cell.

## 2026-03-26 — După feedback de respingere: refacere completă pe commitul curent, fără presupuneri
- Când user-ul spune explicit că ultimul commit este nesatisfăcător, pornesc de la codul efectiv din HEAD și refac analiza înainte de orice afirmație.
- Pentru task-uri cu cerințe de UI+backend pe același flow, introduc payload backend dedicat și testez explicit integrarea frontend pe endpointul nou.
- Pentru grafice în vitest/jsdom, adaug imediat mock pentru `ResizeObserver` ca să evit false negatives și crash-uri la `ResponsiveContainer`.
- 2026-03-26: Când feedback-ul cere layout specific din exemplu vizual (ex. „2 coloane”), aplic direct grila cerută în componenta de charts (`grid-cols-2` pe breakpoint relevant) fără a schimba logica dataset-urilor.
- 2026-03-26: Dacă userul cere explicit scoaterea unui chart și schimbarea controlului de perioadă cu calendar, fac update strict pe UI/UX (elimin cardul și introduc selector range) fără extindere inutilă în backend.
- 2026-03-26: Pentru feedback-uri fine de layout (swap poziții), schimb doar ordinea blocurilor în toolbar și păstrez funcționalitatea neschimbată.
- 2026-03-27: Pentru cerințe noi de charting, prefer să extind payload-ul existent minim (ex. adaug câmp `sales` în funnel) și să evit endpoint-uri noi dacă nu sunt necesare.
- 2026-03-27: Când userul cere metrică totală (nu pe platforme), evit să deriv din seriile pe canale și folosesc direct rândul agregat din worksheet/payload (`cost_per_new_client_eur`).
- 2026-03-27: Dacă userul cere revenire explicită de la EUR la RON pentru un chart, fac rollback strict pe metrica/legendă (fără alte schimbări de layout sau formule).
- 2026-03-27: Când userul cere eliminare completă a unui chart/section, șterg explicit componenta UI și exclud secțiunea și din sursa backend (nu doar ascundere vizuală).
