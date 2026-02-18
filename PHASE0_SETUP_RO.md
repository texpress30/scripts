# Faza 0 — Setup tehnic inițial (implementat)

## Livrate acum
- Monorepo skeleton (`apps/backend`, `apps/frontend`).
- Backend FastAPI minimal, cu endpoint-uri:
  - `GET /`
  - `GET /health`
- Configurare strict pe variabile de mediu prin `os.environ`.
- Placeholder-uri standard pentru secrete în `.env.example`:
  - `OPENAI_API_KEY`
  - `GOOGLE_ADS_TOKEN`
  - `META_ACCESS_TOKEN`
  - `BIGQUERY_PROJECT_ID`
- `docker-compose.yml` cu servicii de bază: PostgreSQL, Redis, backend.
- Teste unitare pentru încărcarea și validarea variabilelor de mediu.

## Principii de securitate respectate
- Fără hardcoding de token-uri/chei.
- Fără expunere de secrete în repo.
- `.env` este ignorat prin `.gitignore`.

## Următorii pași (imediat)
1. Tu configurezi local `.env` cu cheile reale.
2. Pornim backend-ul și validăm health check.
3. Trecem la implementarea Sprint 1 (auth + RBAC + audit trail).
