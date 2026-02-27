# Slice 8.2.7 — Pinterest + Snapchat Provider Adapters (minimal real sync)

## Scope
- Upgrade de la contract skeleton la sync minimal real pentru `pinterest_ads` și `snapchat_ads`.
- Persistență snapshots în Postgres.
- Audit hooks complete (`sync.start`, `sync.success`, `sync.fail`).
- Dashboard unificat extins cu noile platforme.

## Ce s-a implementat
- Services Pinterest/Snapchat generează payload de metrics deterministic și persistă snapshot-ul.
- Noi store-uri Postgres (`pinterest_sync_snapshots`, `snapchat_sync_snapshots`) cu fallback in-memory în `APP_ENV=test`.
- API routes Pinterest/Snapchat păstrează RBAC + rate-limit și emit `sync.success` la finalizare.
- Dashboard agregă acum Google + Meta + TikTok + Pinterest + Snapchat.
- Teste service/e2e actualizate pentru status `connected`, sync `success`, audit și dashboard metrics.

## Out of scope
- OAuth real către API provider.
- Mapping campanii/adsets/ads pe entități externe.
- Backfill istoric și incremental sync orchestration.
