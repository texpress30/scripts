# Sprint 6 — progres (BigQuery Export + Hardening + Ready for Pilot)

## Implementat
- Export BigQuery pentru date normalizate în 2 tabele:
  - `campaign_performance`
  - `ad_performance`
- Endpoint-uri export:
  - `POST /exports/bigquery/{client_id}`
  - `GET /exports/bigquery/runs`
- Hardening:
  - rate-limiting pe endpoint-uri critice (`auth`, `google/meta sync`, `ai`, `rules`, `exports`),
  - gestionare erori externe cu răspunsuri controlate (`400/429/502`) fără crash de server.
- Testare E2E onboarding-to-export (`test_e2e.py`).

## Notă BigQuery
- Fluxul folosește `BIGQUERY_PROJECT_ID` și e pregătit pentru integrare directă.
- În lipsa auth complet BigQuery în mediu, exportul intră în mod mock controlat.
