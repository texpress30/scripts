# scripts

Monorepo de pornire pentru platforma MCC multi-platform cu AI.

## Structură
- `apps/backend` — schelet FastAPI (Phase 0)
- `apps/frontend` — placeholder Next.js (Phase 0)
- `IMPLEMENTATION_BRIEF_RO.md` — brief consolidat
- `NEXT_STEPS_RO.md` — roadmap pe sprinturi
- `DECISIONS_LOCKED_RO.md` — decizii kickoff confirmate
- `PHASE0_SETUP_RO.md` — statusul setup-ului tehnic inițial implementat
- `SPRINT1_PROGRESS_RO.md` — progresul Sprint 1 (auth, RBAC, audit trail)
- `SPRINT2_PROGRESS_RO.md` — progresul Sprint 2 (Google Ads status/sync + dashboard)

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
- `GET /health`
- `POST /auth/login`
- `GET /clients`
- `POST /clients`
- `GET /audit`
- `GET /integrations/google-ads/status`
- `POST /integrations/google-ads/{client_id}/sync`
- `GET /dashboard/{client_id}`
