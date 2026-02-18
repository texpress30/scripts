# Frontend (Next.js + Tailwind)

## Ce include acest setup
- pagină `Login` (`/login`) cu autentificare către backend (`POST /auth/login`)
- pagină protejată `Dashboard` (`/dashboard`) cu grafice simple (Recharts)
- pagină `Clients` (`/clients`) pentru listare și creare client

## Config
Setează URL-ul backend în `.env.local`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Run
```bash
npm install
npm run dev
```

Aplicația pornește pe `http://localhost:3000`.


## Docker (via root docker-compose)
Frontend rulează ca serviciu `frontend` și expune `localhost:3000`.
