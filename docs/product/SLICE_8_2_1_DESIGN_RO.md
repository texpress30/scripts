# Slice 8.2.1 — TikTok Integration Skeleton (contract freeze)

## Scope
- Endpoint-uri backend noi:
  - `GET /integrations/tiktok-ads/status`
  - `POST /integrations/tiktok-ads/{client_id}/sync`
- Feature flag `FF_TIKTOK_INTEGRATION` (default OFF).
- Placeholder UI:
  - `/agency/integrations`
  - card `Sync TikTok (beta)` în `/sub/[id]/campaigns` (vizibil doar când flag-ul frontend este activ).

## Guardrails
- RBAC dedicat pentru acțiuni TikTok (`integrations:tiktok:status`, `integrations:tiktok:sync`).
- Rate limiting identic cu Google/Meta (`60/min status`, `30/min sync`).
- Audit hook pe status și sync contract acceptat.

## Out of scope (mutat în Slice 8.2.2)
- Adapter real TikTok API.
- Persistență snapshot pentru dashboard.
- Retry/backoff operațional.
