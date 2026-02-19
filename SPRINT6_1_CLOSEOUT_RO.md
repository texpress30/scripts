# Mini Sprint 6.1 — Close-out Scope v1 (Acceptance + Operational Readiness)

## Obiectiv
Închidere formală pentru Scope v1 prin:
1) validarea criteriilor de acceptare,
2) clarificarea gap-urilor operaționale rămase,
3) pregătirea handover-ului către Out of Scope v1.

## Status global
- **Implementare features Scope v1:** ✅ completă la nivel MVP (Sprint 1–6 livrate).
- **Close-out operațional:** 🟡 în progres (acțiuni de mai jos).

---

## 1) Matrice criterii de acceptare (din brief)

| Criteriu | Țintă | Status | Evidență / notă |
|---|---:|---|---|
| Coverage (unit + integration) | > 80% | 🟡 | Testele există (`test_config.py`, `test_services.py`, `test_e2e.py`), dar pragul procentual nu este încă raportat într-un artifact unic de release. |
| P95 API latency | < 500ms | 🟡 | Endpoint-urile critice sunt funcționale + hardening activ, dar lipsește benchmark formal per mediu de staging. |
| Error rate | < 0.5% | 🟡 | Tratare erori externe este implementată (`400/429/502` controlat), dar lipsește raport de observabilitate pe fereastră minimă (ex. 7 zile staging). |
| Lighthouse score | > 90 | 🟡 | Frontend este livrat, însă nu există încă raport Lighthouse versionat. |
| Audit log operații critice | activ | ✅ | Audit trail livrat în Sprint 1 și folosit pe fluxurile critice. |
| E2E scenarii critice | acoperite | 🟡 | Există E2E onboarding-to-export; recomand extindere explicită pe token refresh / concurență / degradare externă în raportul final. |

---

## 2) Acțiuni Mini Sprint 6.1 (closure)

### A. Release evidence pack (obligatoriu)
- [ ] Export raport coverage + prag minim în CI.
- [ ] Raport benchmark P95 pe endpoint-uri cheie (`/auth/login`, `/dashboard/{client_id}`, `/rules/{client_id}/evaluate`, `/exports/bigquery/{client_id}`).
- [ ] Raport error-rate din staging (window 7 zile).
- [ ] Raport Lighthouse pentru ecrane: `/login`, `/dashboard`, `/clients`.

### B. Operational ownership (obligatoriu)
- [ ] Nominalizare owner aprobare PR AI (`nume`, `rol`, backup owner).
- [ ] Ownership secrete pe medii (`local`, `staging`, `prod`).
- [ ] Confirmare accesuri tehnice reale: Google Ads, Meta, OpenAI, BigQuery.

### C. Go/No-Go checklist (pilot)
- [ ] Runbook incident severitate P1/P2.
- [ ] SLA alertare și escalation tree.
- [ ] Plan rollback + feature flags pentru fluxuri sensibile.

---

## 3) Deliverables Mini Sprint 6.1
1. Acest document (`SPRINT6_1_CLOSEOUT_RO.md`) ca tracker central.
2. Actualizare roadmap (`NEXT_STEPS_RO.md`) cu etapă explicită 6.1.
3. Actualizare README pentru vizibilitate status close-out.

---

## 4) Criteriu de ieșire Mini Sprint 6.1
Mini Sprint 6.1 se închide când:
- toate itemele din **A + B** sunt marcate complete,
- există un singur artifact de release care mapează clar **criteriu → evidență → verdict**,
- proiectul poate fi declarat **Scope v1 Closed** și mutat oficial pe **Out of Scope v1**.
