# Faza 1 Frontend — Sprint 1 (Setup UI inițial)

## Implementat
- Setup Next.js + TypeScript + Tailwind în `apps/frontend`.
- Login page cu integrare backend (`/auth/login`) și stocare token.
- Dashboard protejat cu date din `/dashboard/{client_id}` și grafice (Recharts).
- Pagină Clienți cu listare (`GET /clients`) și creare (`POST /clients`).

## Structură principală
- `src/app/login/page.tsx`
- `src/app/dashboard/page.tsx`
- `src/app/clients/page.tsx`
- `src/lib/api.ts`
- `src/components/ProtectedPage.tsx`

## Notă
- Câmpul parolă este prezent în UI, dar backend-ul actual autentifică pe `email + role`.
