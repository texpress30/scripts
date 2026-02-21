# Sprint 8.2 — Stabilization + Release Readiness Runbook (TikTok)

## 1) Scop
Acest runbook definește pașii operaționali pentru validarea finală a integrării TikTok înainte de rollout/UAT:
- zero regresii pe fluxurile v1,
- feature flag controlat (`OFF` by default),
- validare cap-coadă pentru sync TikTok,
- criterii clare Go/No-Go.

## 2) Precondiții
- Branch curent sincronizat cu `main`.
- Migrații aplicate (`0001`, `0002`, `0003`) pe mediul țintă.
- Variabile de mediu backend:
  - `APP_AUTH_SECRET`
  - `DATABASE_URL`
  - `FF_TIKTOK_INTEGRATION`
  - `TIKTOK_SYNC_RETRY_ATTEMPTS`
  - `TIKTOK_SYNC_BACKOFF_MS`
- Variabilă frontend pentru vizibilitate UI:
  - `NEXT_PUBLIC_FF_TIKTOK_INTEGRATION`

## 3) Checklist de stabilizare

### A. Regression v1 (obligatoriu)
- [ ] Rulează backend suite completă: `cd apps/backend && pytest -q`
- [ ] Rulează build frontend: `cd apps/frontend && npm run build`
- [ ] Confirmă că nu există erori de import/config pentru `psycopg` în runtime backend.

### B. Feature flag discipline (obligatoriu)
- [ ] În production/staging inițial, `FF_TIKTOK_INTEGRATION=0`.
- [ ] În production/staging inițial, `NEXT_PUBLIC_FF_TIKTOK_INTEGRATION=0`.
- [ ] Confirmă că ruta Agency Integrations nu promovează acțiuni write când flag-ul este OFF.

### C. TikTok smoke E2E (staging cu flag ON)
Setări temporare:
- `FF_TIKTOK_INTEGRATION=1`
- `NEXT_PUBLIC_FF_TIKTOK_INTEGRATION=1`

Pași:
1. Login cu rol `agency_admin`.
2. Creează client nou (`/clients`).
3. Rulează `POST /integrations/tiktok-ads/{client_id}/sync`.
4. Verifică `/dashboard/{client_id}` include bloc `platforms.tiktok_ads` cu `is_synced=true`.
5. Verifică audit events:
   - `tiktok_ads.sync.start`
   - `tiktok_ads.sync.success`
6. Forțează scenariu fail controlat (`TIKTOK_SYNC_FORCE_TRANSIENT_FAILURES`) și verifică:
   - răspuns API fail,
   - event audit `tiktok_ads.sync.fail`.

### D. RBAC + tenant scope
- [ ] `client_viewer` primește 403 pe `POST /integrations/tiktok-ads/{client_id}/sync`.
- [ ] `client_viewer` vede UX read-only (buton disabled) pe ecranele Sub.
- [ ] Verifică endpoint-urile Agency scope nu sunt accesibile din rol subaccount-only.

### E. Persistență Postgres
- [ ] După sync, există rând în `tiktok_sync_snapshots` pentru `client_id`.
- [ ] După restart backend/container, datele rămân disponibile în dashboard.
- [ ] Indexul `idx_tiktok_sync_snapshots_synced_at` există în DB.

## 4) Criterii Go / No-Go
### GO
- toate check-urile A–E verzi,
- zero regression v1,
- audit și RBAC validate,
- persistență Postgres verificată după restart.

### NO-GO
- orice fail la regression suite,
- inconsistențe RBAC/scope,
- lipsa persistenței în Postgres,
- erori de observabilitate (audit lipsă pentru start/success/fail).

## 5) Rollout recomandat
1. Deploy cu flag OFF.
2. Smoke intern cu flag ON pe subset controlat.
3. Validare business + UAT.
4. Activare graduală pe medii/conturi.

## 6) Handoff către următorul epic
După GO:
- păstrăm acest runbook ca template pentru următoarele integrări (Pinterest/Snapchat),
- clonăm secțiunile RBAC/audit/flag discipline fără a modifica fluxurile v1 existente.
