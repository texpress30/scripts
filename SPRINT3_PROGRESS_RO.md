# Sprint 3 — progres inițial (Meta Ads + Dashboard Unificat)

## Implementat
- Integrare Meta Ads de bază (status + sync) în backend.
- Endpoint status integrare: `GET /integrations/meta-ads/status`.
- Endpoint sync per client: `POST /integrations/meta-ads/{client_id}/sync`.
- Normalizare metrici pe format comun pentru Google + Meta:
  - `spend`, `impressions`, `clicks`, `conversions`, `revenue`.
- Dashboard unificat: `GET /dashboard/{client_id}` returnează total consolidat + breakdown pe platforme.

## Comportament token Meta Ads
- Dacă `META_ACCESS_TOKEN` este placeholder (`your_...`), statusul este `pending`.
- Sync este blocat cu eroare clară până la token valid.

## Notă
- Datele Sprint 3 sunt mock/sintetice pentru validarea fluxului end-to-end.
- Codul este pregătit pentru token real din `.env`.
