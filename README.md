# scripts

Monorepo pentru platforma MCC multi-provider (Google/Meta/TikTok/Pinterest/Snapchat) cu backend FastAPI și frontend Next.js.

## Structură principală
- `apps/backend` — API FastAPI, RBAC action+scope, servicii integrare, audit, persistență Postgres.
- `apps/frontend` — aplicație Next.js (Agency + Sub-account UI).
- `apps/backend/db/migrations` — migrații SQL pentru snapshot-uri, importuri și mapări.
- `scripts` — scripturi operaționale (ex: refresh nume conturi Google).
- `tasks` — TODO + lessons pentru execuție și postmortem.

## Setup rapid
### Backend
```bash
cd apps/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd apps/frontend
npm install
npm run dev
```

## Config minim
Variabile importante:
- `APP_AUTH_SECRET` (obligatoriu)
- `DATABASE_URL` (pentru persistență non-test)
- `APP_ENV=test` trebuie folosit doar în teste automate (pytest), altfel aplicația poate porni în mod de test și pierde persistența la restart.
- Google Ads production flow:
  - `GOOGLE_ADS_MODE=production`
  - `GOOGLE_ADS_CLIENT_ID`
  - `GOOGLE_ADS_CLIENT_SECRET`
  - `GOOGLE_ADS_DEVELOPER_TOKEN`
  - `GOOGLE_ADS_MANAGER_CUSTOMER_ID`
  - `GOOGLE_ADS_REDIRECT_URI`
  - `GOOGLE_ADS_REFRESH_TOKEN` (după OAuth exchange)

Feature flags:
- `FF_TIKTOK_INTEGRATION`
- `FF_PINTEREST_INTEGRATION`
- `FF_SNAPCHAT_INTEGRATION`

## Flux Agency Accounts (Google)
### Import + naming real
1. Import conturi prin endpoint-urile Google Ads.
2. Numele conturilor se persistă din `descriptive_name` (fallback: ID simplu).
3. Refresh operațional al numelor deja importate:
```bash
cd apps/backend
python ../../scripts/refresh_google_account_names.py
```

### Mapping conturi la clienți (many-to-many client-side)
- Un cont Google Ads este atașat la **un singur client**.
- Un client poate avea **mai multe conturi Google Ads**.
- Persistența se face în tabelul de legătură `agency_account_client_mappings`.

Endpoint-uri relevante:
- `POST /clients/{client_id}/attach-google-account`
- `DELETE /clients/{client_id}/detach-google-account`
- `GET /clients/{client_id}/accounts`
- `GET /clients/accounts/google`

## Script diagnostic Google Ads
Rulează scriptul pentru verificare rapidă API + DB (oauth, conturi accesibile, rows din Postgres, last_sync_at, last_error):

```bash
PYTHONPATH=apps/backend python scripts/diag_google_ads.py
```

Variabile minime necesare:
- `APP_AUTH_SECRET`
- `DATABASE_URL`
- `GOOGLE_ADS_MODE=production`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_MANAGER_CUSTOMER_ID`
- `GOOGLE_ADS_REDIRECT_URI`
- `GOOGLE_ADS_REFRESH_TOKEN`

## Endpoint-uri cheie
### Core
- `POST /auth/login`
- `GET /clients`
- `POST /clients`
- `GET /audit`

### Agency accounts / integrations
- `GET /integrations/google-ads/status`
- `GET /integrations/google-ads/accounts`
- `POST /integrations/google-ads/import-accounts`
- `POST /integrations/google-ads/refresh-account-names`
- `POST /integrations/google-ads/{client_id}/sync`
- `POST /integrations/google-ads/sync-now`
- `GET /integrations/google-ads/diagnostics`
- `GET /integrations/meta-ads/status`
- `POST /integrations/meta-ads/{client_id}/sync`
- `GET /integrations/tiktok-ads/status`
- `POST /integrations/tiktok-ads/{client_id}/sync`
- `GET /integrations/pinterest-ads/status`
- `POST /integrations/pinterest-ads/{client_id}/sync`
- `GET /integrations/snapchat-ads/status`
- `POST /integrations/snapchat-ads/{client_id}/sync`

## Verificare locală
```bash
cd apps/backend && pytest -q
cd apps/frontend && npm run build
```


## UI Agency
- `/agency/clients`: listă clienți manuali (ID afișat secvențial de la 1).
- Click pe numele clientului duce la `/agency/clients/{id}` (ID afișat) pentru detalii complete (platforme active + conturi atașate per platformă).
- În pagina de detalii client poți seta `tip client` (lead/e-commerce/programmatic) și `responsabil cont` (membru echipă).
- `/agency-accounts`: atașare/detașare conturi Google la clienți, inclusiv re-atașare.


## Railway: verificare Google Ads end-to-end
1. Setează env vars (doar nume):
   - `APP_AUTH_SECRET`
   - `DATABASE_URL`
   - `GOOGLE_ADS_MODE`
   - `GOOGLE_ADS_CLIENT_ID`
   - `GOOGLE_ADS_CLIENT_SECRET`
   - `GOOGLE_ADS_DEVELOPER_TOKEN`
   - `GOOGLE_ADS_MANAGER_CUSTOMER_ID`
   - `GOOGLE_ADS_REDIRECT_URI`
   - `GOOGLE_ADS_REFRESH_TOKEN`
   - opțional: `GOOGLE_ADS_API_VERSION` (default `v23`)
2. Rulează migrațiile DB (în ordinea fișierelor din `apps/backend/db/migrations`).
3. Rulează diagnostic local/remote: `PYTHONPATH=apps/backend python scripts/diag_google_ads.py`.
4. Rulează sync on-demand pentru conturile mapate: `POST /integrations/google-ads/sync-now` (agency admin).
5. Verifică datele în DB (`ad_performance_reports`) pe ultimele 30 zile și endpoint-ul `GET /dashboard/agency/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`.
6. Confirmă în UI că Google Ads arată `rows30 > 0` și cardurile dashboard nu mai rămân pe 0 după sync.
