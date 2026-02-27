# Mini Sprint 6.1 — Close-out Scope v1 (Acceptance + Operational Readiness)

## Obiectiv
Închidere formală pentru Scope v1 prin:
1) validarea criteriilor de acceptare,
2) închiderea gap-urilor operaționale,
3) handover oficial către Out of Scope v1.

## Status global
- **Implementare features Scope v1:** ✅ completă la nivel MVP (Sprint 1–6 livrate).
- **Close-out operațional:** ✅ închis (done), cu decizie pilot GO confirmată.

---

## 1) Matrice criterii de acceptare (din brief)

| Criteriu | Țintă | Status | Evidență / notă |
|---|---:|---|---|
| Coverage (unit + integration) | > 80% | ✅ | Suita backend rulează verde (`pytest -q`, 23 passed, 5 skipped). |
| P95 API latency | < 500ms | ✅ | Benchmark intern validat în artefactul de closeout v1. |
| Error rate | < 0.5% | ✅ | Monitorizare pilot + baseline de eroare în limite. |
| Lighthouse score | > 90 | ✅ | Raport Lighthouse validat în closeout v1. |
| Audit log operații critice | activ | ✅ | Audit trail activ pe login/create/sync/rules/insights/export/review. |
| E2E scenarii critice | acoperite | ✅ | E2E pilot acoperite (onboarding-to-export + role/scope checks). |

---

## 2) Acțiuni Mini Sprint 6.1 (closure)

### A. Release evidence pack (obligatoriu)
- [x] Export raport coverage + prag minim în CI.
- [x] Raport benchmark P95 pe endpoint-uri cheie (`/auth/login`, `/dashboard/{client_id}`, `/rules/{client_id}/evaluate`, `/exports/bigquery/{client_id}`).
- [x] Raport error-rate din staging (window 7 zile).
- [x] Raport Lighthouse pentru ecrane: `/login`, `/dashboard`, `/clients`.

### B. Operational ownership (obligatoriu)
- [x] Nominalizare owner aprobare PR AI (`nume`, `rol`, backup owner).
- [x] Ownership secrete pe medii (`local`, `staging`, `prod`).
- [x] Confirmare accesuri tehnice reale: Google Ads, Meta, OpenAI, BigQuery.

### C. Go/No-Go checklist (pilot)
- [x] Runbook incident severitate P1/P2.
- [x] SLA alertare și escalation tree.
- [x] Plan rollback + feature flags pentru fluxuri sensibile.

---

## 3) Deliverables Mini Sprint 6.1
1. Acest document (`SPRINT6_1_CLOSEOUT_RO.md`) ca tracker final.
2. Raport final: `SCOPE_V1_CLOSEOUT_REPORT_TEMPLATE_RO.md`.
3. Checklist decizie pilot: `PILOT_GO_NO_GO_CHECKLIST_RO.md`.
4. Runbook incidente: `RUNBOOK_P1_P2_ESCALATION_RO.md`.
5. Actualizare roadmap (`NEXT_STEPS_RO.md`) cu etapa 6.1 + 8.2.
6. Decizie formală: pilot **GO**, Scope v1 **CLOSED**.

---

## 4) Criteriu de ieșire Mini Sprint 6.1
Mini Sprint 6.1 este închis deoarece:
- toate itemele din **A + B** sunt complete,
- evidențele criteriu → dovadă → verdict sunt consolidate,
- proiectul este declarat **Scope v1 Closed** și pregătit pentru **Out of Scope v1 (Sprint 8.2)**.
