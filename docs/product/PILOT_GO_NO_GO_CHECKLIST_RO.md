# Pilot Go/No-Go Checklist (executabil)

> Folosește acest checklist înainte de activarea pilotului pe client real.

## A) Pre-flight tehnic (obligatoriu)
- [x] Backend health răspunde 200:
  - `curl -i https://<backend-domain>/health`
- [x] Frontend login page este accesibil:
  - `https://<frontend-domain>/login`
- [x] Proxy frontend -> backend funcționează:
  - `curl -i https://<frontend-domain>/api/health`
- [x] Login funcționează cu user pilot:
  - din UI + verificare token localStorage.

## B) Flux critic end-to-end
- [x] Create client (`POST /clients`) cu user `agency_admin`.
- [x] Sync Google (`POST /integrations/google-ads/{client_id}/sync`).
- [x] Sync Meta (`POST /integrations/meta-ads/{client_id}/sync`).
- [x] Dashboard consolidat (`GET /dashboard/{client_id}`).
- [x] Evaluate rules (`POST /rules/{client_id}/evaluate`).
- [x] Generate insights (`POST /insights/weekly/{client_id}/generate`).
- [x] BigQuery export (`POST /exports/bigquery/{client_id}`).

## C) Securitate & control
- [x] Rolurile RBAC validate pe minim 2 roluri (`agency_admin`, `client_viewer`).
- [x] Audit events există pentru acțiuni critice.
- [x] Rate limiting activ pe endpoint-uri critice.
- [x] Secretele sunt setate din secret manager (nu hardcoded).

## D) Observabilitate & incidente
- [x] Error logs vizibile în platformă (Railway/Vercel + APM dacă există).
- [x] Alertare minimă configurată (health fail + error spike).
- [x] Owner on-call pentru pilot este nominalizat.
- [x] Runbook P1/P2 este publicat și accesibil.

## E) Criterii Go/No-Go
### GO dacă:
- toate check-urile A + B sunt bifate,
- în ultimele 24h nu există incidente P1,
- endpoint-urile critice nu au error-rate anormal.

### NO-GO dacă:
- login/health sunt instabile,
- onboarding-ul E2E eșuează,
- lipsesc ownership-ul operațional sau runbook-ul.

## Evidențe verificabile (Faza E)
- Testare backend completă: `cd apps/backend && pytest -q` -> `23 passed, 5 skipped`.
- Build frontend complet: `cd apps/frontend && npm run build` -> succes (rute agency + sub-account generate).
- RBAC + scope enforcement activ: `enforce_action_scope(...)` aplicat pe endpoint-uri agency/sub-account.
- Audit hooks critice active: login (success/fail/rate-limit), create client, sync, rules evaluate, insight generate, export, recommendation review.

## Verdict final
- [x] GO
- [ ] NO-GO

Owner decizie: Release Owner
Dată/ora: 2026-02-20
Note: Gap-urile P0 (RBAC, Audit, conectare UI la API) sunt rezolvate și validate prin testele de mai sus.
