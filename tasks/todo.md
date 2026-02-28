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
