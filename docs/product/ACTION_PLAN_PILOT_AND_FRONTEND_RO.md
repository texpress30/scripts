# Plan actualizat de implementare — Pilot NO-GO -> GO + conectare design v0 la Railway Postgres

> Update făcut după recitirea documentelor de referință (`AGENTS.md`, `tenant-boundaries.md`, `ui-contract.md`) și a modulelor backend noi (creative assets, rule engine, audit, rbac, migrații DB).

## 0) Confirmare citire și context

Am citit și am folosit în plan:
- `AGENTS.md` (reguli de lucru: schimbări mici, focus, validare țintită)
- `docs/product/tenant-boundaries.md` (separare strictă Agency vs Sub-account)
- `docs/product/ui-contract.md` (route map, query contracts, RBAC matrix, states)
- module/backend noi relevante:
  - `apps/backend/app/services/creative_workflow.py`
  - `apps/backend/app/services/rules_engine.py`
  - `apps/backend/app/services/rbac.py`
  - `apps/backend/app/services/audit.py`
  - `apps/backend/db/migrations/0001_core_entities.sql`

## 1) Principii obligatorii (înainte de coding)

1. **Strict scope boundary**
   - Agency pages (`/agency/*`) consumă doar date agregate / operaționale de agency.
   - Sub-account pages (`/sub/:id/*`) consumă doar date ale clientului `:id`.
   - Nicio pagină nu amestecă scope-urile în același query.
2. **Dublu enforcement RBAC + tenant scope**
   - Frontend: ascunde/acționează UI conform rolului.
   - Backend: autorizează la endpoint + validează asignarea user -> client pentru `/sub/:id/*`.
3. **Backend-first data access**
   - Frontend v0 nu atinge direct Postgres Railway; toate datele trec prin FastAPI.
4. **Vertical slices mici**
   - livrăm incremental (agency slice, apoi sub-account slice), cu validare după fiecare pas.

## 2) Gap-uri reale care mențin NO-GO (ce atacăm primele)

### P0 — Securitate + control
- extindem `rbac.py` de la permisiuni minime la matrice completă pentru acțiunile din `ui-contract`;
- conectăm audit în toate acțiunile critice (auth, create client, sync, rule evaluate, insight generate, export, approve/dismiss);
- activăm rate limiting pe endpoint-uri sensibile (`/auth/login`, `/integrations/*/sync`, `/rules/*/evaluate`, `/insights/*/generate`, `/exports/*`).

### P0 — Fluxuri E2E pilot obligatorii
- aducem la „green” fluxurile checklist: Google sync, Meta sync, rules evaluate, weekly insights, BigQuery export;
- acoperim cu E2E minim pe roluri: `agency_admin` și `client_viewer`.

### P0 — Observabilitate
- logging consistent cu `request_id`, `agency_id`, `subaccount_id/client_id`;
- alertare minimă (health fail, error spike, export fail).

## 3) Plan tehnic actualizat pe structura Agency / Sub-Account / Client

## Faza A — Model de date & guardrails (backend)

1. **Aliniere schema la tenant boundaries**
   - folosim entitățile multi-tenant deja definite în `0001_core_entities.sql` (`agencies`, `subaccounts`, `campaigns`, `ad_sets`, `creatives`, `insights_daily`, `ai_recommendations` etc.).
2. **Membership și control acces per sub-account**
   - adăugăm/validăm maparea user -> subaccounts permise (pentru least privilege).
3. **Policy layer unificat**
   - helper central: `can_access_agency_route`, `can_access_subaccount_route`, `can_execute_action`.
4. **Audit obligatoriu by default**
   - decorator/middleware audit pentru operații sensibile; acțiuni standardizate (`rules_engine.trigger`, `client.create`, `sync.google.start`, etc.).

## Faza B — Agency View (`/agency/*`) conectat la API real

1. `/agency/clients`
   - `GET /clients`, `POST /clients` cu permission checks.
2. `/agency/dashboard`
   - KPI agregat cross-client din tabelele de insights + starea integrărilor.
3. `/agency/audit`
   - `GET /audit` cu filtre actor/acțiune/perioadă.
4. `/agency/notifications`
   - listă agency-level (inbox agregat).
5. `/agency/exports`
   - status runs BigQuery + retry controlat.

## Faza C — Sub-Account View (`/sub/:id/*`) conectat la API real

1. Route guard obligatoriu
   - validăm că user-ul are acces la `:id` înainte de orice query.
2. `/sub/:id/dashboard`
   - KPI client + quick actions sync Google/Meta.
3. `/sub/:id/campaigns` și `/sub/:id/rules`
   - integrare cu `rules_engine.py` (list/create/evaluate) + audit pe trigger.
4. `/sub/:id/creative`
   - integrare cu `creative_workflow.py` (assets, variante, publish status).
5. `/sub/:id/recommendations` + `/sub/:id/insights/weekly`
   - recomandări AI și generare insight săptămânal cu trace/audit.

## Faza D — Client View (rol `client_viewer`) hard enforcement

1. Read-only complet pe `/sub/:id/*`
   - UI: disable/hide acțiuni write;
   - API: reject write cu `403` indiferent de UI.
2. Verificare explicită pe acțiuni cu risc
   - sync/evaluate/approve/export trebuie interzise pentru `client_viewer`.

## Faza E — Testare, gate și GO decision

1. **Teste API țintite (backend)**
   - RBAC matrix tests;
   - tenant isolation tests (user fără membership nu vede datele altui sub-account);
   - audit emission tests pentru acțiuni critice.
2. **E2E smoke (frontend + backend)**
   - flow `agency_admin` end-to-end;
   - flow `client_viewer` read-only.
3. **Re-run checklist GO/NO-GO**
   - completăm evidențe în checklist și closeout (nu doar „funcțional”, ci cu output verificabil).

## 4) Ordine recomandată de implementare (pas cu pas)

1. Definim policy matrix final (role x action x scope).
2. Implementăm middleware/dependencies pentru scope enforcement.
3. Completăm audit hooks pe endpoint-urile critice.
4. Finalizăm endpoint-urile P0 pentru sync/rules/insights/exports.
5. Conectăm întâi Agency routes din frontend la API.
6. Conectăm apoi Sub-account routes la API + guard per `:id`.
7. Activăm și validăm read-only strict pentru `client_viewer`.
8. Rulăm teste backend + E2E minim.
9. Actualizăm checklist + closeout cu dovezi și luăm decizia GO.

## 5) Definition of Done (pentru start coding)

- Separarea Agency/Sub-account este enforced în backend și în frontend routing.
- `client_viewer` nu poate executa nicio operație write (confirmat prin teste).
- Audit events există pentru toate acțiunile critice P0.
- Fluxurile pilot critice sunt verzi end-to-end.
- Checklist-ul de pilot poate fi marcat GO pe baza evidențelor.
