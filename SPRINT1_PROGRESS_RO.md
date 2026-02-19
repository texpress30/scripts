# Sprint 1 — progres inițial (auth + RBAC + audit)

## Implementat
- Endpoint autentificare mock: `POST /auth/login` (role-based token).
- Control acces RBAC pentru resursele de clienți și audit.
- Audit trail in-memory pentru acțiuni de list/create client.
- Registry in-memory pentru clienți (create/list).

## Endpoint-uri noi
- `POST /auth/login`
- `GET /clients`
- `POST /clients`
- `GET /audit`

## Notă securitate
- Token-urile sunt semnate HMAC cu `APP_AUTH_SECRET` (din env).
- Nu există secrete hardcodate în cod.
