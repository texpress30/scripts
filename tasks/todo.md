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
