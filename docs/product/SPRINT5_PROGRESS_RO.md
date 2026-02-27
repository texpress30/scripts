# Sprint 5 — progres inițial (AI Campaign Assistant + Insights)

## Implementat
- `AIAssistantService` care analizează metrici consolidate Google + Meta și generează recomandări.
- Integrare OpenAI prin `OPENAI_API_KEY` (call la API Chat Completions), cu fallback robust.
- Guardrails pentru output AI:
  - sanitizare text,
  - blocare output invalid,
  - fallback la `Nu am destule date` când lipsesc date sau apar erori.
- `InsightsService` pentru sumar săptămânal (Spend, Conversions, ROAS) cu stocare in-memory.
- Endpoint-uri pentru recomandări AI și generare/lectură insight săptămânal.

## Endpoint-uri noi
- `GET /ai/recommendations/{client_id}`
- `POST /insights/weekly/{client_id}/generate`
- `GET /insights/weekly/{client_id}`

## Notă
- Jobul periodic este pregătit la nivel de serviciu; programarea efectivă se poate face în sprint următor (Celery/cron).
