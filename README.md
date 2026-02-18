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

## Variabile de mediu (obligatorii)
- `APP_AUTH_SECRET`
- `OPENAI_API_KEY`
- `GOOGLE_ADS_TOKEN`
- `META_ACCESS_TOKEN`
- `BIGQUERY_PROJECT_ID`

Aplicația citește valorile din variabile de mediu prin `os.environ` și nu hardcodează date sensibile.

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
