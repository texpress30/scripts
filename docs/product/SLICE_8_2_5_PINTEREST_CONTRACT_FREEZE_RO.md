# Slice 8.2.5 — Pinterest integration skeleton (contract freeze)

## Scope
- Backend contract endpoints:
  - `GET /integrations/pinterest-ads/status`
  - `POST /integrations/pinterest-ads/{client_id}/sync`
- Feature flag: `FF_PINTEREST_INTEGRATION` (default OFF).
- RBAC action mapping:
  - `integrations:pinterest:status` (agency)
  - `integrations:pinterest:sync` (subaccount)
- UI placeholders:
  - card Pinterest în `/agency/integrations`
  - acțiune `Sync Pinterest (beta)` în `/sub/[id]/campaigns`, gated de `NEXT_PUBLIC_FF_PINTEREST_INTEGRATION`.

## Gate
- Teste contract + scope enforcement pentru roluri read-only.
- Fără impact pe fluxurile existente Google/Meta/TikTok.
