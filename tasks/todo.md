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

# TODO — Monedă editabilă per cont și afișare în Sub-account

- [x] Extind modelul de profil cont-client cu `account_currency` în persistență (Postgres + memorie test).
- [x] Extind endpoint-ul PATCH `/clients/display/{display_id}` ca să salveze moneda per `platform+account_id`.
- [x] Extind payload-ul detaliilor clientului ca UI să primească `account_currency` pentru fiecare cont.
- [x] Adaug în UI Agency Client Details câmp editabil (cu creion) pentru selecția monedei per cont.
- [x] Fac Sub-account Dashboard să folosească moneda selectată și să formateze Spend/Revenue cu aceasta.
- [x] Rulez verificări backend/frontend și documentez review.

## Review — Monedă editabilă per cont și afișare în Sub-account
- Root-cause: dashboard-ul Sub-account afișa sume doar cu simbol fix `$`, fără o preferință de monedă configurabilă per cont atașat.
- Backend: am adăugat `account_currency` la mapping-ul `agency_account_client_mappings`, l-am expus în payload-ul conturilor atașate și l-am făcut editabil prin același PATCH profile endpoint.
- Frontend Agency: în fiecare rând de cont atașat există acum câmp „Monedă” editabil din icon-ul creion (USD/EUR/RON/GBP/CAD/AUD).
- Frontend Sub-account: dashboard-ul citește `currency` din API și formatează Spend/Revenue cu `Intl.NumberFormat` pe moneda selectată.
- Observație: pentru clienții cu mai multe conturi Google atașate, moneda folosită în Sub-account este prima monedă validă disponibilă în mapping-urile Google ale clientului (fallback USD).
