# Frontend (Next.js + Tailwind)

## Ce include acest setup
- pagină `Login` (`/login`) cu autentificare către backend (`POST /auth/login`)
- pagină protejată `Dashboard` (`/dashboard`) cu shell nou (sidebar + overview cards + grafic Recharts)
- pagină `Clients` (`/clients`) pentru listare și creare client

## Config
Creează `apps/frontend/.env.local` din template:

```bash
cp .env.local.example .env.local
```

Valoare necesară:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Credențiale test (default)
- Email: `admin@example.com`
- Parolă: `admin123`
- Rol recomandat: `agency_admin`

Acestea pot fi schimbate din backend `.env` prin:
- `APP_LOGIN_EMAIL`
- `APP_LOGIN_PASSWORD`

## Run
```bash
npm install
npm run dev
```

Aplicația pornește pe `http://localhost:3000`.

## Docker (via root docker-compose)
Frontend rulează ca serviciu `frontend` și expune `localhost:3000`.


## Important pentru Docker
În `docker-compose.yml`, `NEXT_PUBLIC_API_BASE_URL` trebuie să fie `http://localhost:8000` pentru request-uri din browser (nu `http://backend:8000`).
Dacă modifici această valoare, rulează rebuild: `docker compose up --build`.


## Dashboard nou (instalat)
- componentă layout reutilizabilă: `src/components/AppShell.tsx`
- overview KPI: `src/components/NewDashboardOverview.tsx`
- pagină principală dashboard: `src/app/dashboard/page.tsx`


## Deploy (Vercel + Railway)
Setează în Vercel variabila:

```bash
NEXT_PUBLIC_API_BASE_URL=https://<railway-backend-domain>
```

Important:
- nu folosi trailing slash la finalul URL-ului,
- verifică să pointeze către backend Railway, nu către frontend Vercel,
- testează manual: `POST https://<railway-backend-domain>/auth/login`.

