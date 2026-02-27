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
