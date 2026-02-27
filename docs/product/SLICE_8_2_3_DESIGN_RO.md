# Slice 8.2.3 — Hardening TikTok channel

## Scope
- Retry/backoff configurabil pentru sync TikTok:
  - `TIKTOK_SYNC_RETRY_ATTEMPTS`
  - `TIKTOK_SYNC_BACKOFF_MS`
- Observabilitate backend:
  - metrici in-memory (`sync_started/sync_succeeded/sync_failed`)
  - structured logging la success/fail cu `duration_ms` și `attempts`
  - audit details extinse cu durata execuției.
- UI hardening în sub-dashboard:
  - stări explicite `Loading / No data / Synced` pe cardurile de integrare,
  - mesaj de eroare clar în container vizibil.

## Note
- Da, alinierea finală pentru persistență către Postgres rămâne validă pentru pasul de hardening ulterior / rollout production.
