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
- [ ] Sync Google (`POST /integrations/google-ads/{client_id}/sync`).
- [ ] Sync Meta (`POST /integrations/meta-ads/{client_id}/sync`).
- [x] Dashboard consolidat (`GET /dashboard/{client_id}`).
- [ ] Evaluate rules (`POST /rules/{client_id}/evaluate`).
- [ ] Generate insights (`POST /insights/weekly/{client_id}/generate`).
- [ ] BigQuery export (`POST /exports/bigquery/{client_id}`).

## C) Securitate & control
- [ ] Rolurile RBAC validate pe minim 2 roluri (`agency_admin`, `client_viewer`).
- [ ] Audit events există pentru acțiuni critice.
- [ ] Rate limiting activ pe endpoint-uri critice.
- [x] Secretele sunt setate din secret manager (nu hardcoded).

## D) Observabilitate & incidente
- [ ] Error logs vizibile în platformă (Railway/Vercel + APM dacă există).
- [ ] Alertare minimă configurată (health fail + error spike).
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

## Verdict final
- [ ] GO
- [x] NO-GO

Owner decizie:
Dată/ora:2/19/2026 9:11PM
Note:
