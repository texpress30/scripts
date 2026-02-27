# Sprint 8.2 — Stabilization + Release Readiness Runbook (Multi-provider)

## 1) Scop
Acest runbook definește pașii operaționali pentru validarea finală a integrărilor (TikTok/Pinterest/Snapchat) înainte de rollout/UAT:
- zero regresii pe fluxurile v1,
- feature flags controlate (`OFF` by default),
- validare cap-coadă pentru sync + audit + RBAC,
- criterii clare Go/No-Go.

## 2) Precondiții
- Branch curent sincronizat cu `main`.
- Migrații aplicate (`0001`, `0002`, `0003`, `0004`) pe mediul țintă.
- Variabile de mediu backend:
  - `APP_AUTH_SECRET`
  - `DATABASE_URL`
  - Feature flags: `FF_TIKTOK_INTEGRATION`, `FF_PINTEREST_INTEGRATION`, `FF_SNAPCHAT_INTEGRATION`
  - Retry/backoff:
    - `TIKTOK_SYNC_RETRY_ATTEMPTS`, `TIKTOK_SYNC_BACKOFF_MS`
    - `PINTEREST_SYNC_RETRY_ATTEMPTS`, `PINTEREST_SYNC_BACKOFF_MS`
    - `SNAPCHAT_SYNC_RETRY_ATTEMPTS`, `SNAPCHAT_SYNC_BACKOFF_MS`
- Variabile frontend pentru vizibilitate UI:
  - `NEXT_PUBLIC_FF_TIKTOK_INTEGRATION`
  - `NEXT_PUBLIC_FF_PINTEREST_INTEGRATION`
  - `NEXT_PUBLIC_FF_SNAPCHAT_INTEGRATION`

## 3) Checklist de stabilizare

### A. Regression v1 (obligatoriu)
- [ ] Rulează backend suite completă: `cd apps/backend && pytest -q`
- [ ] Rulează build frontend: `cd apps/frontend && npm run build`
- [ ] Confirmă că nu există erori de import/config pentru `psycopg` în runtime backend.

### B. Feature flag discipline (obligatoriu)
- [ ] În production/staging inițial, toate flag-urile sunt `0`:
  - `FF_TIKTOK_INTEGRATION`
  - `FF_PINTEREST_INTEGRATION`
  - `FF_SNAPCHAT_INTEGRATION`
- [ ] În production/staging inițial, toate flag-urile frontend sunt `0`.
- [ ] Confirmă că ruta Agency Integrations nu promovează acțiuni write când flag-urile sunt OFF.

### C. Smoke E2E per provider (staging cu flag ON)
Setări temporare: activăm provider-ul vizat (`FF_*_INTEGRATION=1`) + flag-ul frontend corespondent.

Pași comuni:
1. Login cu rol `agency_admin`.
2. Creează client nou (`/clients`).
3. Rulează `POST /integrations/<provider>-ads/{client_id}/sync`.
4. Verifică `/dashboard/{client_id}` include bloc `platforms.<provider>_ads` cu `is_synced=true`.
5. Verifică audit events:
   - `<provider>_ads.sync.start`
   - `<provider>_ads.sync.success`
6. Forțează scenariu fail controlat (`*_SYNC_FORCE_TRANSIENT_FAILURES`) și verifică:
   - răspuns API fail,
   - event audit `<provider>_ads.sync.fail`.

### D. RBAC + tenant scope
- [ ] `client_viewer` primește 403 pe endpoint-urile write (`POST /integrations/*/sync`).
- [ ] `client_viewer` nu poate accesa endpoint-urile Agency status pentru provider-e.
- [ ] Verifică endpoint-urile Agency scope nu sunt accesibile din rol subaccount-only.

### E. Persistență Postgres
- [ ] După sync, există rânduri în snapshot table pentru provider-ele active:
  - `tiktok_sync_snapshots`
  - `pinterest_sync_snapshots`
  - `snapchat_sync_snapshots`
- [ ] După restart backend/container, datele rămân disponibile în dashboard.
- [ ] Indexurile sunt prezente în DB (unde au fost definite prin migrare).

### F. Observabilitate + retry/backoff
- [ ] Retry/backoff configurabil validat pentru Pinterest/Snapchat (success după fail-uri tranziente controlate).
- [ ] Audit include `duration_ms` la `sync.success` și `sync.fail`.
- [ ] Counter-ele in-memory (`sync_started/sync_succeeded/sync_failed`) sunt incrementate la fiecare execuție.

## 4) Criterii Go / No-Go
### GO
- toate check-urile A–F verzi,
- zero regression v1,
- audit + RBAC validate,
- persistență Postgres verificată după restart.

### NO-GO
- orice fail la regression suite,
- inconsistențe RBAC/scope,
- lipsa persistenței în Postgres,
- lipsa observabilității (fără `sync.start/success/fail` sau fără metrici minimale).

## 5) Rollout recomandat
1. Deploy cu flags OFF.
2. Smoke intern cu câte un provider ON pe subset controlat.
3. Validare business + UAT.
4. Activare graduală pe medii/conturi.

## 6) Handoff către următorul epic
După GO:
- păstrăm acest runbook ca template multi-provider,
- clonăm secțiunile RBAC/audit/flag discipline fără a modifica fluxurile v1,
- publicăm un stabilization report dedicat pentru fiecare canal nou.
