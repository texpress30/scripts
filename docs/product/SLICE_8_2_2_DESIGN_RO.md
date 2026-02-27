# Slice 8.2.2 — TikTok sync minimal E2E

## Scope livrat
- Endpoint real de sync: `POST /integrations/tiktok-ads/{client_id}/sync` cu adapter mock determinist.
- Persistență snapshot TikTok în DB (SQLite runtime + migrare SQL pentru schema dedicată).
- Dashboard unificat extins cu blocul `tiktok_ads` + agregare totaluri (spend/conversii/ROAS).
- Audit complet pe sync: `tiktok_ads.sync.start`, `tiktok_ads.sync.success`, `tiktok_ads.sync.fail`.
- UI sub-account dashboard: card `TikTok Ads` + buton `Sync TikTok` gated de feature flag și read-only role.

## Guardrails
- Feature flag `FF_TIKTOK_INTEGRATION` rămâne OFF by default.
- RBAC neschimbat: `client_viewer` rămâne fără write (UI disabled + 403 backend).
- Rate limiting păstrat (`60/min status`, `30/min sync`).
