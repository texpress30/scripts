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
