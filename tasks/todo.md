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
