# Sprint 4 — progres inițial (Rules Engine + Notificări)

## Implementat
- Model de date Rule în backend (`id`, `name`, `rule_type`, `threshold`, `action_value`, `status`).
- Rules Engine in-memory cu evaluare periodică (endpoint-triggered) pentru:
  - `stop_loss` (spend peste prag),
  - `auto_scale` (ROAS peste prag).
- Sistem de notificări mock (email în consolă + event store in-memory).
- Audit automat pentru acțiuni din rules engine cu actor `system_bot`.

## Endpoint-uri noi
- `GET /rules/{client_id}`
- `POST /rules/{client_id}`
- `POST /rules/{client_id}/evaluate`

## Notă
- Execuția periodică este pregătită la nivel de service și se poate programa ulterior cu scheduler/Celery.
