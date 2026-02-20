# Sprint 8.2 — Plan de Acțiune Tehnic (Out of Scope v1)

## 1) Context
După închiderea Scope v1 și decizia Pilot GO, Sprint 8.2 pornește explicit pe **Out of Scope v1**, în vertical slices mici și sigure.

Referințe:
- `NEXT_STEPS_RO.md` (secțiunea 8.2)
- `IMPLEMENTATION_BRIEF_RO.md` (secțiunea Out of scope v1)
- `docs/product/tenant-boundaries.md`
- `docs/product/ui-contract.md`

## 2) Obiective Sprint 8.2 (ce livrăm acum)

### Objective A — Foundation pentru extensii Out-of-Scope
- Stabilim contracte API + schemă DB pentru noile epics, fără a rupe fluxurile v1.
- Activăm feature flags pentru fiecare epic nou (off by default).

### Objective B — Primul vertical slice OOS (safe)
- Livrăm un singur epic cap-coadă, în variantă minimă:
  - backend endpoint(s),
  - UI route(s),
  - RBAC/scope enforcement,
  - audit hooks,
  - teste.

### Objective C — Readiness pentru extindere incrementală
- Definim template de slice reutilizabil (design doc scurt + checklist de validare) pentru sprinturile următoare.

## 3) Candidate epics Out-of-Scope v1 (prioritate propusă)

Din brief-ul curent, epics OOS includ:
1. TikTok/Pinterest/Snapchat integrări,
2. Generare creativă AI (video/imagine) + Canva,
3. Editor intern de creative,
4. Tracking propriu/click-router,
5. Mobile app.

### Recomandare pentru Sprint 8.2 (MVP de extindere)
**Începem cu TikTok integration skeleton** (cel mai apropiat de arhitectura existentă Google/Meta), pentru risc redus și reutilizare maximă.

## 4) Plan pe vertical slices (pas cu pas)

## Slice 8.2.1 — Architecture & contract freeze (2-3 zile)
### Backend
- Adăugăm `integrations:tiktok:status/sync` contract API (fără rollout prod by default).
- Definim service stub + rate limit + error mapping consistent cu Google/Meta.
- Adăugăm policy mapping în RBAC action-scope matrix.

### Frontend
- Adăugăm placeholders UI în Agency (`/agency/integrations`) și Sub (`/sub/:id/campaigns`) gated de feature flag.

### Gate
- Unit tests API contract + permission tests.
- Fără impact pe flow-urile existente v1.

## Slice 8.2.2 — TikTok sync minimal E2E (3-4 zile)
### Backend
- Endpoint real `POST /integrations/tiktok-ads/{client_id}/sync` (mock provider + adapter contract).
- Stocare snapshot minimă în modelul existent de dashboard input.
- Audit hooks complete (`status`, `sync.start`, `sync.success`, `sync.fail`).

### Frontend
- Buton "Sync TikTok" în sub-account campaigns/dashboard, vizibil doar când feature flag activ.
- Respectare read-only UX pentru `client_viewer` (disabled în UI).

### Gate
- E2E flow: login -> create client -> tiktok sync -> dashboard includes tiktok block.
- RBAC tests: `client_viewer` primește UX read-only + 403 backend pe write forțat.

## Slice 8.2.3 — Hardening & observabilitate noul canal (2 zile)
### Backend
- Metrics și structured logging pentru tiktok sync.
- Retry/backoff configurabil.

### Frontend
- Error/empty/loading states aliniate cu UI contract.

### Gate
- Smoke test + regression suite v1 full green.

## 5) Criterii de acceptare Sprint 8.2
- Niciun regression pe fluxurile pilot v1.
- Noul epic este complet feature-flagged.
- RBAC + tenant scope respectate pe toate endpoint-urile noi.
- Audit activ pe operațiile sensibile.
- Build frontend + suite backend verzi.

## 6) Checklist de execuție (operational)
- [ ] Branch strategy: `feature/sprint-8-2-<slice>`.
- [ ] Design doc scurt per slice (max 1 pagină).
- [ ] PR mici (max ~300 linii net schimbate / PR când posibil).
- [ ] Mandatory checks: `pytest -q`, `npm run build`.
- [ ] Feature flag default OFF până la validare UAT.
- [ ] Runbook stabilizare + release readiness documentat (`docs/product/SPRINT8_2_STABILIZATION_RUNBOOK_RO.md`).

## 7) Riscuri și mitigări
- **Risc:** creep de scope (prea multe epics simultan)
  - **Mitigare:** 1 epic / sprint, restul backlog.
- **Risc:** degradare v1
  - **Mitigare:** regression suite obligatorie înainte de merge.
- **Risc:** nealiniere Agency/Sub scope
  - **Mitigare:** policy matrix update + tests per scope.

## 8) Decizie recomandată pentru start coding
Pornim Sprint 8.2 cu **Slice 8.2.1 (contract freeze)** și imediat după validare trecem la **Slice 8.2.2 (TikTok minimal E2E)**.
