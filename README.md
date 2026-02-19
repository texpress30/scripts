# scripts

Monorepo de pornire pentru platforma MCC multi-platform cu AI.

## Structură
- `apps/backend` — FastAPI backend (Sprint 1 + Sprint 2)
- `apps/frontend` — placeholder Next.js (Phase 0)
- `IMPLEMENTATION_BRIEF_RO.md` — brief consolidat
- `NEXT_STEPS_RO.md` — roadmap pe sprinturi
- `DECISIONS_LOCKED_RO.md` — decizii kickoff confirmate
- `PHASE0_SETUP_RO.md` — status setup tehnic inițial
- `SPRINT1_PROGRESS_RO.md` — progres Sprint 1 (auth, RBAC, audit)
- `SPRINT2_PROGRESS_RO.md` — progres Sprint 2 (Google Ads status/sync + dashboard)
- `SPRINT3_PROGRESS_RO.md` — progres Sprint 3 (Meta Ads + dashboard unificat)
- `SPRINT4_PROGRESS_RO.md` — progres Sprint 4 (rules engine + notificări)
- `SPRINT5_PROGRESS_RO.md` — progres Sprint 5 (AI assistant + insights)
- `SPRINT6_PROGRESS_RO.md` — progres Sprint 6 (BigQuery export + hardening + E2E)
- `SPRINT6_1_CLOSEOUT_RO.md` — mini sprint 6.1 (acceptance gates + close-out Scope v1)
- `SCOPE_V1_CLOSEOUT_REPORT_TEMPLATE_RO.md` — template raport final Scope v1 (criteriu/evidență/verdict)
- `PILOT_GO_NO_GO_CHECKLIST_RO.md` — checklist executabil pentru decizie pilot
- `RUNBOOK_P1_P2_ESCALATION_RO.md` — runbook incidente P1/P2 + escalation
- `SCOPE_V1_CLOSEOUT_REPORT_TEMPLATE_RO.md` — template raport final Scope v1 (criteriu/evidență/verdict)
- `PILOT_GO_NO_GO_CHECKLIST_RO.md` — checklist executabil pentru decizie pilot
- `RUNBOOK_P1_P2_ESCALATION_RO.md` — runbook incidente P1/P2 + escalation
- `READY_FOR_PILOT_RO.md` — raport final de lansare pilot
- `SPRINT_FRONTEND1_PROGRESS_RO.md` — progres Faza 1 Frontend (login/dashboard/clienți)

## Setup rapid (backend)
1. Copiază variabilele de mediu:
   - `cp .env.example .env`
2. Completează în `.env` cheile tale reale (nu se commit-uiesc).
3. Încarcă variabilele în shell:
   - `set -a && source .env && set +a`
4. Rulează backend local:
   - `cd apps/backend`
   - `pip install -r requirements.txt`
   - `uvicorn app.main:app --reload`

## Variabile de mediu
**Obligatoriu pentru boot minim (ex: login):**
- `APP_AUTH_SECRET`

**Opționale la boot, recomandate pentru funcționalitățile complete:**
- `OPENAI_API_KEY`
- `GOOGLE_ADS_TOKEN`
- `META_ACCESS_TOKEN`
- `BIGQUERY_PROJECT_ID`

Aplicația citește valorile din variabile de mediu prin `os.environ` și nu hardcodează date sensibile. Dacă lipsesc cheile de integrare, endpoint-urile de integrare/AI/export pot răspunde cu erori controlate, dar serverul nu mai cade la startup.

## Endpoint-uri disponibile (backend)
### Core
- `GET /`
- `GET /health`

### Sprint 1
- `POST /auth/login`
- `GET /clients`
- `POST /clients`
- `GET /audit`

### Sprint 2
- `GET /integrations/google-ads/status`
- `POST /integrations/google-ads/{client_id}/sync`

### Sprint 3
- `GET /integrations/meta-ads/status`
- `POST /integrations/meta-ads/{client_id}/sync`
- `GET /dashboard/{client_id}` (consolidat Google + Meta)


### Sprint 4
- `GET /rules/{client_id}`
- `POST /rules/{client_id}`
- `POST /rules/{client_id}/evaluate`


### Sprint 5
- `GET /ai/recommendations/{client_id}`
- `POST /insights/weekly/{client_id}/generate`
- `GET /insights/weekly/{client_id}`


### Sprint 6
- `POST /exports/bigquery/{client_id}`
- `GET /exports/bigquery/runs`


## Deploy troubleshooting (405 la login)
Frontend-ul folosește proxy Next (`/api/*`) către backend Railway, configurat prin `BACKEND_API_URL`.
Dacă frontend-ul pe Vercel primește `405 Method Not Allowed` la login:
- verifică în Vercel variabila `BACKEND_API_URL` să fie URL-ul backend-ului Railway (nu domeniul frontend),
- verifică endpoint-ul backend: `POST /auth/login` (nu GET),
- verifică în Railway CORS: `APP_CORS_ORIGINS` include domeniul Vercel și/sau `APP_CORS_ORIGIN_REGEX` este configurat.
- dacă `APP_CORS_ORIGIN_REGEX` este invalid, backend-ul folosește fallback sigur (`https://.*\.vercel\.app`) în loc să pice la startup.

