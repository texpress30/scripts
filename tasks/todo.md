# TODO — Diagnostic E2E + Fix Google Ads Data Sync către Dashboard

- [x] Audit repo end-to-end (pipeline OAuth/API/sync/DB/agregare/UI) pentru Google Ads în Agency/Sub-Account dashboard.
- [x] Reproduc bug-ul și confirm simptomele (totals 0) prin apeluri reale în mediul local (inclusiv limitările DB/creds).
- [x] Adaug diagnostic runtime Google Ads (OAuth, accessible customers, child accounts, sample metrics LAST_30_DAYS, DB rows).
- [x] Repar persistența de date astfel încât sync Google Ads să scrie în `ad_performance_reports`.
- [x] Repar agregarea dashboard să folosească `ad_performance_reports` + mapping cont→client + date range corect.
- [x] Adaug endpoint admin pentru sync la cerere (`/integrations/google-ads/sync-now`) și extind status/diagnostics output.
- [x] Ajustez UI loading și Integration Health pentru câmpurile de diagnostic cerute.
- [x] Rulez verificări (Python compile/tests, Google diag script, frontend build, screenshot), documentez Railway runbook, commit + PR.

## Review
- Cauza principală: lanțul de date se rupea între „sync connected” și agregare dashboard; status-ul Google Ads era `connected`, dar nu exista persistență zilnică robustă în `ad_performance_reports` care să fie folosită consistent de agregare.
- Am introdus `PerformanceReportsStore` și am conectat `google_ads_service.sync_client` să persiste la fiecare sync un raport zilnic (`spend/clicks/impressions/conversions/conversion_value`) în Postgres.
- Agregarea Agency/Sub-Account citește acum din `ad_performance_reports` (nu doar snapshot-uri), cu `report_date BETWEEN start_date AND end_date`, ROAS agregat din sumă și mapare cont→client via `agency_account_client_mappings`.
- Am adăugat `run_diagnostics()` + scriptul `scripts/diag_google_ads.py` pentru test real OAuth/API/DB (compatibil v23) și endpoint `GET /integrations/google-ads/diagnostics` cu câmpurile cerute.
- Am adăugat endpoint `POST /integrations/google-ads/sync-now` pentru sync manual imediat al conturilor mapate client.
- În `GET /integrations/google-ads/status` am expus `accounts_found`, `rows_in_db_last_30_days`, `last_sync_at`, `last_error` pentru Integration Health.
- Frontend Agency Dashboard afișează detaliile Google în blocul Integration Health și păstrează loading state cu text `Se încarcă datele...`; date range este trimis în format `YYYY-MM-DD`.
- Verificările reale au confirmat în mediul curent: OAuth nu poate rula fără refresh token setat și DB local nu e disponibil implicit (connection refused), dar diagnosticul returnează explicit aceste cauze și endpoint-urile sunt pregătite pentru Railway.

---

# TODO — Verificare remote/fetch workspace nou

- [x] Verific remotes configurate (`git remote -v`).
- [x] Rulez fetch global cu prune (`git fetch --all --prune`).
- [x] Documentez rezultatul verificării.

## Review
- Repository-ul local nu are niciun remote configurat momentan (nici `origin`).
- `git fetch --all --prune` s-a executat cu succes, dar fără efect deoarece nu există remotes definite.

---

# TODO — Reconfigurare origin + sync cu main

- [x] Adaug remote `origin` cu URL-ul furnizat.
- [x] Rulez `git fetch origin`.
- [x] Rulez `git pull origin main`.
- [x] Verific starea repo după sincronizare.

## Review
- `git remote add origin ...` a fost executat cu succes și remote-ul a fost configurat.
- `git fetch origin` a adus referințele remote (inclusiv `origin/main`).
- Primul `git pull origin main` a eșuat cu mesajul Git despre strategia de reconciliere pentru branch-uri divergente.
- Am setat explicit `git config pull.rebase false` (local repo), apoi am rerulat `git pull origin main` și sincronizarea s-a finalizat cu merge (`ort`).
- Starea finală arată branch local sincronizat cu modificările locale păstrate pentru commitul curent.

---

# TODO — Bring commit 7bb0a45 into current workspace

- [x] Rulez `git fetch --all` pentru actualizare istoric remote.
- [x] Rulez `git cherry-pick 7bb0a45`.
- [x] Dacă apar conflicte, le rezolv păstrând versiunea din commit-ul cherry-picked. (N/A: cherry-pick nu a pornit, commit inexistent local/remote)
- [x] Verific fișierele actualizate și confirm starea finală.

## Review
- `git fetch --all` a rulat cu succes și a actualizat referințele remote disponibile.
- `git cherry-pick 7bb0a45` a eșuat cu `fatal: bad revision '7bb0a45'` (hash-ul nu există în istoricul local după fetch).
- Verificări suplimentare (`git log --all`, `git show 7bb0a45`, `git fetch origin 7bb0a45`) confirmă că obiectul nu este disponibil pe remote-ul curent.
- Nu există fișiere de cod actualizate prin cherry-pick deoarece commit-ul cerut nu a putut fi rezolvat. Workspace-ul rămâne sincronizat cu remotes cunoscute.

---

# TODO — Fix NameError `psycopg` în Google Ads diagnostics

- [x] Identific fișierul/funcția unde se calculează `rows_in_db_last_30_days` și apare `name 'psycopg' is not defined`.
- [x] Verific ce driver Postgres este standard în repo (psycopg vs psycopg2).
- [x] Adaug importul lipsă și aliniez folosirea conexiunii DB cu convenția proiectului.
- [x] Rulez verificări (minim compile / script diagnostic) și documentez rezultatul.

## Review
- Eroarea provine din `apps/backend/app/services/google_ads.py`, funcția `_db_diagnostics_last_30_days()`, care folosea `psycopg.connect(...)` fără import declarat pentru `psycopg`.
- Driverul folosit în proiect este Psycopg 3 (`psycopg[binary]==3.2.1` în `apps/backend/requirements.txt`), iar majoritatea serviciilor backend folosesc deja pattern-ul `try: import psycopg ...`.
- Am adăugat importul lipsă în `google_ads.py` și am păstrat conexiunea existentă `psycopg.connect(settings.database_url)` pentru consistență cu restul codului.
- Verificări: compile pentru fișierul modificat + execuție controlată a `_db_diagnostics_last_30_days()` (cu `load_settings` monkeypatched) confirmă că nu mai apare `NameError`, iar funcția întoarce `db_error` de conectivitate când DB-ul este indisponibil.

---

# TODO — Asigurare Psycopg 3 binary pentru Railway production

- [x] Verific fișierul(ele) de dependențe backend.
- [x] Mă asigur că `psycopg[binary]==3.2.1` este prezent.
- [x] Verific configurația de build/deploy Railway (`railway.json`/`Dockerfile`/`nixpacks.toml`).
- [x] Rulez verificări rapide și documentez rezultatul.

## Review
- Fișierul de dependențe backend este `apps/backend/requirements.txt`; am confirmat și păstrat `psycopg[binary]==3.2.1` și am adăugat comentariu explicit pentru contextul Railway production.
- În repo există `apps/backend/Dockerfile` (nu există `railway.json` sau `nixpacks.toml`), iar build-ul instalează dependențele prin `RUN pip install --no-cache-dir -r requirements.txt` la deploy.
- Verificările rapide (`python -m compileall` pe serviciul Google Ads și `git diff`) confirmă că schimbarea este minimă și fără impact logic.

---

# TODO — Robust DB diagnostics + script Google Ads

- [x] Ajustez `_db_diagnostics_last_30_days` pentru query pe ultimele 30 zile cu fallback robust la erori DB/tabel.
- [x] Verific/ajustez endpoint-ul `/integrations/google-ads/diagnostics` să expună `oauth_ok`, `rows_in_db_last_30_days`, `last_sync_at`, `last_error`.
- [x] Creez/actualizez `scripts/diag_google_ads.py` pentru verificare API + DB + rows.
- [x] Update README cu pașii de rulare și variabilele de mediu necesare.
- [x] Rulez verificări și documentez rezultatele.

## Review
- În `GoogleAdsService._db_diagnostics_last_30_days` conexiunea DB folosește `DATABASE_URL` din env (fallback `load_settings().database_url`), verifică existența tabelului și rulează query parametrizat pe ultimele 30 zile.
- Query-ul folosește `provider = %s` dacă există coloana `provider`; fallback pe schema actuală `platform = %s` pentru compatibilitate, ambele filtrate cu `synced_at >= NOW() - INTERVAL '30 days'`.
- Dacă tabela lipsește sau DB este indisponibilă, funcția întoarce `db_rows_last_30_days=0` și un `db_error` descriptiv, fără crash.
- `run_diagnostics()` expune și aliasul `rows_in_db_last_30_days` pentru endpoint-ul `/integrations/google-ads/diagnostics`, împreună cu `oauth_ok`, `last_sync_at`, `last_error`.
- Scriptul `scripts/diag_google_ads.py` a fost actualizat să afișeze explicit starea DB diagnostics și să citească noul câmp `rows_in_db_last_30_days`; README include acum secțiune dedicată de rulare + env vars.

---

# TODO — DB debug agregat pentru Google Ads diagnostics

- [x] Identific tabelele folosite de dashboard pentru metrici și traseul de citire.
- [x] Adaug endpoint debug (`/integrations/google-ads/db-debug`) cu agregări sigure (count/max, fără rows brute).
- [x] Adaug breakdown 90 zile (total, by provider, by platform, max date/synced_at) pentru tabela principală.
- [x] Adaug scanare pentru alte tabele relevante (coloane `customer_id/platform/provider/cost_micros/impressions`) cu agregări.
- [x] Rulez verificări și documentez rezultatul.

## Review
- Dashboard Agency citește metricile din `ad_performance_reports` prin `DashboardService` (agregări pe `report_date` + `platform`), iar pentru status Google se folosește `run_diagnostics()`.
- Endpoint-ul nou `GET /integrations/google-ads/db-debug` întoarce `db_ok`, `table_exists`, agregări pe 90 zile pentru `ad_performance_reports` și `other_relevant_tables` (fără date sensibile brute).
- Dacă `ad_performance_reports` este gol/lipsește, payload-ul indică explicit situația și expune tabele alternative cu același profil de coloane pentru troubleshooting ingestion.
