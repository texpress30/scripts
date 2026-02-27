# Slice 8.2.6 — Snapchat Contract Freeze (OOS)

## Scope
- Endpoint contract skeleton pentru Snapchat Ads:
  - `GET /integrations/snapchat-ads/status`
  - `POST /integrations/snapchat-ads/{client_id}/sync`
- Feature flag backend: `FF_SNAPCHAT_INTEGRATION` (default OFF).
- Feature flag frontend: `NEXT_PUBLIC_FF_SNAPCHAT_INTEGRATION`.
- RBAC pe action+scope:
  - `integrations:snapchat:status` (agency)
  - `integrations:snapchat:sync` (subaccount)
- Audit events:
  - `snapchat_ads.status`
  - `snapchat_ads.sync.start`
  - `snapchat_ads.sync.fail`
  - `snapchat_ads.sync.accepted`

## Notes
- Slice-ul îngheață contractul API/UI, fără adapter provider real.
- Implementarea reală de sync + metrici va fi inclusă într-un slice ulterior.
