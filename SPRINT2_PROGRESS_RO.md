# Sprint 2 — progres inițial (Google Ads + sync + dashboard)

## Implementat
- Integrare Google Ads de bază (status + sync) în backend.
- Endpoint status integrare: `GET /integrations/google-ads/status`.
- Endpoint sync per client: `POST /integrations/google-ads/{client_id}/sync`.
- Dashboard per client: `GET /dashboard/{client_id}` (spend, conversions, revenue, roas).
- Audit events pentru status/sync/dashboard.

## Comportament token Google Ads
- Dacă `GOOGLE_ADS_TOKEN` este placeholder (`your_...`), statusul este `pending`.
- Sync este blocat cu eroare clară până la token valid.

## Notă
- Datele Sprint 2 sunt mock/sintetice pentru a valida fluxul de integrare.
- În pasul următor conectăm API-ul Google Ads real.
