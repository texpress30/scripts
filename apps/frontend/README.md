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
BACKEND_API_URL=http://localhost:8000
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
În `docker-compose.yml`, `BACKEND_API_URL` trebuie să fie `http://backend:8000` (request-urile trec prin proxy-ul Next din containerul frontend).
Dacă modifici această valoare, rulează rebuild: `docker compose up --build`.


## Dashboard nou (instalat)
- componentă layout reutilizabilă: `src/components/AppShell.tsx`
- overview KPI: `src/components/NewDashboardOverview.tsx`
- pagină principală dashboard: `src/app/dashboard/page.tsx`


## Deploy (Vercel + Railway)
Setează în Vercel variabila **server-side**:

```bash
BACKEND_API_URL=https://<railway-backend-domain>
```

Frontend-ul nu mai cheamă direct backend-ul din browser; toate request-urile merg prin proxy-ul Next:
- browser -> `https://<vercel-domain>/api/*`
- Next proxy -> `https://<railway-backend-domain>/*`

Avantaj: elimină problemele de CORS și reduce riscul de configurare greșită a `NEXT_PUBLIC_API_BASE_URL`.

Debug rapid pentru 405:
- deschide `https://<vercel-domain>/api/auth/login` în browser: trebuie să vezi `405` la GET (normal),
- rulează un POST către același endpoint (din UI/login sau curl): trebuie să ajungă la Railway.



## Notă importantă
Dacă ai setat anterior `NEXT_PUBLIC_API_BASE_URL`, poți să îl elimini din Vercel ca să eviți confuzii; proxy-ul folosește `BACKEND_API_URL`.
