# Ce urmează acum (plan practic, imediat)

Acest document îți spune exact ce facem după brief, astfel încât să trecem din zona de planificare în execuție.

## 1) Decizii de kickoff (confirmate)
Deciziile de start sunt blocate astfel:

1. Backend: **FastAPI**.
2. Cloud: **GCP**.
3. Structură repo: **monorepo**.
4. Branding v1: **default propus**.
5. Billing v1: **fără billing**.
6. Deadline-uri: **Alpha 4 săpt / Beta 6 săpt / Pilot 8 săpt** (pentru 1–2 dev full-time).

Detalii complete: `DECISIONS_LOCKED_RO.md`.

---

## 2) Setup tehnic (48h)
După confirmări, construim baza proiectului:

- repo structure + convenții de branch,
- CI (lint + test + security scan),
- schelet backend FastAPI modular,
- schelet frontend Next.js + design system minim,
- PostgreSQL + Redis,
- observabilitate de bază (logs + metrics + error tracking),
- documentare API (OpenAPI/Swagger).

**Livrabil:** proiect rulabil local + pipeline CI verde.

---

## 3) Sprint 1 (săptămâna 1)
Obiectiv: fundația de produs.

- autentificare + RBAC,
- management clienți (structură MCC),
- audit trail pentru acțiuni critice,
- ecrane de bază: onboarding, client list, client detail.

**Criteriu de ieșire:** un user agency admin poate crea client, seta roluri și vedea logurile de audit.

---

## 4) Sprint 2 (săptămâna 2)
Obiectiv: primul conector real + dashboard inițial.

- integrare Google Ads OAuth,
- sincronizare date campanii,
- dashboard per client (spend, conversions, ROAS),
- job-uri periodice + retry policy.

**Criteriu de ieșire:** datele Google Ads apar corect în dashboard pentru conturi test.

---

## 5) Sprint 3 (săptămâna 3)
Obiectiv: multi-platform.

- integrare Meta Ads OAuth,
- normalizare metrici cross-platform,
- dashboard unificat Google + Meta,
- alerte de degradare conector (API down/rate limit).

**Criteriu de ieșire:** același client vede date consolidate din ambele platforme.

---

## 6) Sprint 4 (săptămâna 4)
Obiectiv: automatizare care produce valoare.

- rules engine (stop-loss + auto-scaling),
- notificări email/in-app,
- aprobări unde e necesar,
- audit complet pe acțiuni automate.

**Criteriu de ieșire:** regulile pot modifica starea campaniilor în mod controlat și trasabil.

---

## 7) Sprint 5 (săptămâna 5)
Obiectiv: stratul AI util din ziua 1.

- AI Campaign Assistant (recomandări campanie/copy/audiențe),
- AI Insights (sumar săptămânal + recomandări),
- fallback când datele sunt insuficiente,
- guardrails pe output AI.

**Criteriu de ieșire:** userul primește recomandări utile, explicabile, fără acțiuni critice autonome.

---

## 8) Sprint 6 (săptămâna 6)
Obiectiv: pregătire pilot client.

- export BigQuery + template Looker,
- hardening performanță + securitate,
- testare E2E (onboarding, OAuth, rules, degradare externă),
- UAT + checklist de lansare staging.

**Criteriu de ieșire:** produs gata de pilot pe 1-2 clienți reali.

---


## 8.1) Mini Sprint 6.1 (close-out Scope v1)
Obiectiv: închidere formală Scope v1 înainte de tranziția în Out of Scope v1.

- validare criterii de acceptare (coverage / p95 / error-rate / lighthouse),
- evidence pack de release într-un artifact unic,
- clarificare ownership operațional (owner PR AI, ownership secrete, accesuri tehnice reale),
- go/no-go checklist pentru pilot controlat.

**Criteriu de ieșire:** Scope v1 marcat explicit `Closed`, cu evidențe atașate.

---

## 8.2) Start Out of Scope v1 (după 6.1)
Obiectiv: extindere platformă pe epics non-v1, planificate pe sprinturi separate.

## 9) Cum lucrăm cu AI „self-improving” în siguranță
Flux standard:

1. AI detectează oportunitate (perf/error/debt).
2. Creează branch + patch.
3. Rulează testele + benchmark.
4. Deschide PR etichetat `[ai-generated]`.
5. Human review obligatoriu pentru merge.

**Interdicții v1:** fără modificări automate în producție, fără schimbări DB fără aprobare, fără alterări de billing/security fără human sign-off.

---

## 10) Ce rămâne de confirmat chiar acum
Pentru a porni implementarea în Faza 0 mai avem nevoie doar de:

- owner aprobare PR AI (`nume/rol`),
- responsabili secrete pe medii (local/staging/prod),
- accesurile tehnice de test: Google Ads / Meta / OpenAI / BigQuery.

După aceste 3 confirmări, începem direct setup-ul tehnic de 48h.
