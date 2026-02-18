# Ce urmează acum (plan practic, imediat)

Acest document îți spune exact ce facem după brief, astfel încât să trecem din zona de planificare în execuție.

## 1) Decizii de kickoff (azi)
Confirmă explicit următoarele 9 puncte:

1. Backend final: **FastAPI** (da/nu).
2. Cloud: **GCP** sau **AWS**.
3. Structură repo: **monorepo** sau **multi-repo**.
4. Branding minim v1: logo + paletă + font (sau „default propus”).
5. Medii: local / staging / production + responsabil secrete.
6. Accesuri test: Google Ads, Meta, OpenAI, BigQuery.
7. Politică AI PR: cine aprobă PR-uri generate de AI.
8. Billing v1: fără billing sau Stripe minim.
9. Deadline-uri: alpha, beta intern, pilot client.

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

## 9) Cum lucrăm cu AI „self-improving” în siguranță
Flux standard:

1. AI detectează oportunitate (perf/error/debt).
2. Creează branch + patch.
3. Rulează testele + benchmark.
4. Deschide PR etichetat `[ai-generated]`.
5. Human review obligatoriu pentru merge.

**Interdicții v1:** fără modificări automate în producție, fără schimbări DB fără aprobare, fără alterări de billing/security fără human sign-off.

---

## 10) Ce aștept de la tine chiar acum (copy/paste)
Trimite-mi răspuns în formatul:

- Backend: `FastAPI` / altceva
- Cloud: `GCP` / `AWS`
- Repo: `monorepo` / `multi-repo`
- Branding: `ai logo/paletă` sau `folosește default`
- Billing v1: `fără billing` / `Stripe`
- Deadline alpha: `data`
- Deadline beta intern: `data`
- Deadline pilot: `data`
- Owner aprobare PR AI: `nume/rol`

După acest răspuns, începem direct cu Faza 0 și livrăm scheletul tehnic.
