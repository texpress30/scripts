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
- `STORAGE_MEDIA_REMOTE_FETCH_TIMEOUT_SECONDS` (timeout fetch remote ingest, default 15)
- `STORAGE_MEDIA_REMOTE_FETCH_MAX_BYTES` (limită bytes fetch remote ingest, default 10485760)
- `CREATIVE_WORKFLOW_MONGO_CORE_WRITES_SOURCE_ENABLED` (default `false`; când e `true`, `create_asset` / `add_variant` / `link_to_campaign` folosesc Mongo ca source-of-truth pentru write path)
- `CREATIVE_WORKFLOW_MONGO_DERIVED_WRITES_SOURCE_ENABLED` (default `false`; devine activ doar împreună cu `CREATIVE_WORKFLOW_MONGO_CORE_WRITES_SOURCE_ENABLED` pentru `generate_variants` / `update_approval` / `set_performance_scores`)
- `CREATIVE_WORKFLOW_MONGO_PUBLISH_PERSIST_ENABLED` (default `false`; persistă `publish_to_channel` în Mongo doar când sunt active și `CORE_WRITES` + `DERIVED_WRITES`)
- `CREATIVE_WORKFLOW_MEDIA_ID_LINKING_ENABLED` (default `false`; permite `media_id` opțional în `add_variant`, cu validare minimă prin media metadata repository)
- `AI_RECOMMENDATIONS_MONGO_SOURCE_ENABLED` (default `false`; mută recommendations history pe Mongo source-of-truth pentru generate/list/get/review/actions)
- `APP_ENV=test` trebuie folosit doar în teste automate (pytest), altfel aplicația poate porni în mod de test și pierde persistența la restart.
- Google Ads production flow:
  - `GOOGLE_ADS_MODE=production`
  - `GOOGLE_ADS_CLIENT_ID`
  - `GOOGLE_ADS_CLIENT_SECRET`
  - `GOOGLE_ADS_DEVELOPER_TOKEN`
  - `GOOGLE_ADS_MANAGER_CUSTOMER_ID`
  - `GOOGLE_ADS_REDIRECT_URI`
  - `INTEGRATION_SECRET_ENCRYPTION_KEY` (secret pentru criptarea token-urilor integration în DB; dacă lipsește se folosește `APP_AUTH_SECRET`)
  - TikTok OAuth flow (Business advertiser auth):
    - `TIKTOK_APP_ID`
    - `TIKTOK_APP_SECRET`
    - `TIKTOK_REDIRECT_URI` = `https://scripts-chi-nine.vercel.app/agency/integrations/tiktok/callback`
    - opțional: `TIKTOK_API_BASE_URL` (default `https://business-api.tiktok.com`)
    - opțional: `TIKTOK_API_VERSION` (default `v1.3`)
  - Meta OAuth flow:
    - `META_APP_ID`
    - `META_APP_SECRET`
    - `META_REDIRECT_URI` = `https://scripts-chi-nine.vercel.app/agency/integrations/meta/callback`
    - opțional: `META_API_VERSION` (default `v20.0`)

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

### Mapping conturi la clienți (generic, extensibil multi-platform)
- Un cont de platformă este atașat la **un singur client** la un moment dat.
- Un client poate avea **mai multe conturi** pe aceeași platformă sau pe platforme diferite.
- Persistența se face în tabelul de legătură `agency_account_client_mappings`.

Endpoint-uri generice:
- `POST /clients/{client_id}/attach-account` cu body `{ "platform": "google_ads|meta_ads|...", "account_id": "..." }`
- `POST /clients/{client_id}/detach-account` cu body `{ "platform": "...", "account_id": "..." }`
- `GET /clients/{client_id}/accounts` (opțional `?platform=meta_ads`)
- `GET /clients/accounts/{platform}`

Endpoint-uri Google legacy (compatibile):
- `POST /clients/{client_id}/attach-google-account`
- `DELETE /clients/{client_id}/detach-google-account`
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
- `INTEGRATION_SECRET_ENCRYPTION_KEY`


### Meta Ads OAuth (connect foundation)
- Variabile env noi (backend): `META_APP_ID`, `META_APP_SECRET`, `META_REDIRECT_URI`, opțional `META_API_VERSION` (default `v20.0`).
- Endpoints:
  - `GET /integrations/meta-ads/connect` → `{ authorize_url, state }`
  - `POST /integrations/meta-ads/oauth/exchange` cu `{ code, state }` → persistă long-lived token securizat în `integration_secrets` (`provider=meta_ads`, `secret_key=access_token`).
  - `POST /integrations/meta-ads/{client_id}/sync` → sync real pentru `account_daily` (default), `campaign_daily`, `ad_group_daily` (Meta ad sets mapate pe grain-ul generic `ad_group_daily`) sau `ad_daily` (Meta ads mapate pe grain-ul generic `ad_daily`) pe toate conturile `meta_ads` atașate clientului; body opțional `{ "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "grain": "account_daily|campaign_daily|ad_group_daily|ad_daily" }` (implicit ultimele 7 zile complete + `account_daily`).
  - `POST /integrations/meta-ads/{client_id}/backfill` → enqueue backfill istoric chunked (implicit `2024-01-09` → ieri) pentru grains `account_daily|campaign_daily|ad_group_daily|ad_daily`; body opțional `{ "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "grains": ["..."] }`.
- Status-ul `GET /integrations/meta-ads/status` expune `token_source`, `token_updated_at`, `token_expires_at` (dacă există) și `oauth_configured`.

### Shopify Feed Integration (VOXEL app - OAuth)
Integrare completă OAuth pentru import de produse din magazine Shopify, folosind un Public App VOXEL înregistrat în Shopify Partners. Flow-ul end-to-end: Add New Source → OAuth redirect → callback → token encrypted → import produse.

- Variabile env (backend):
  - `SHOPIFY_APP_CLIENT_ID`
  - `SHOPIFY_APP_CLIENT_SECRET`
  - `SHOPIFY_REDIRECT_URI` (default `https://admin.omarosa.ro/agency/integrations/shopify/callback`)
  - `SHOPIFY_API_VERSION` (default `2026-04`)
  - `SHOPIFY_SCOPES` (default `read_products,read_product_listings,read_inventory,read_locations`)
  - opțional: `SHOPIFY_WEBHOOK_BASE_URL` (default `https://admin.omarosa.ro`; prefix pentru URL-ul public al endpoint-ului webhook înregistrat la OAuth exchange)
- OAuth endpoints:
  - `GET /integrations/shopify/status` → `{ oauth_configured, connected_shops, token_count }`
  - `GET /integrations/shopify/connect?shop={shop}.myshopify.com` → `{ authorize_url, state }` (state HMAC-signed)
  - `POST /integrations/shopify/oauth/exchange` cu `{ code, state, shop, client_id? }` → exchange code → offline token; token + scope persistate criptat în `integration_secrets` (`provider=shopify`, `scope=shop_domain`); înregistrează best-effort webhook `app/uninstalled` pe magazin.
- Feed source lifecycle (per subaccount, scope `/subaccount/{subaccount_id}/feed-sources`):
  - `POST /feed-management/sources` cu `source_type=shopify` + `shop_domain` → creează rândul `feed_sources` (status `pending`) și returnează `{ source, authorize_url, state }` pentru redirect imediat.
  - `POST /feed-management/sources/{source_id}/complete-oauth` cu `{ code, state, shop? }` → finalizează OAuth pe sursă, stochează token-ul și marchează `connection_status='connected'`.
  - `POST /feed-management/sources/{source_id}/reconnect` → regenerează `authorize_url` pentru o sursă aflată în `error`/`disconnected`/`pending`.
  - `POST /feed-management/sources/{source_id}/test-connection` → probe `GET /admin/api/{version}/shop.json` cu token-ul stocat și actualizează `last_connection_check`.
  - `POST /feed-management/sources/{source_id}/import` → import sincron produse Shopify (paginare cursor-based, mapping variante) cu counts imported/deactivated/total întoarse direct în răspuns.
- Webhook public (HMAC-verified, fără JWT): `POST /integrations/shopify/webhooks/app-uninstalled`
  - Verifică header-ul `X-Shopify-Hmac-Sha256` cu `SHOPIFY_APP_CLIENT_SECRET` (timing-safe via `hmac.compare_digest`); HMAC invalid → 401; secret neconfigurat → 503 (fail closed).
  - Pe HMAC valid întoarce mereu `200 OK` (Shopify reîncearcă la non-2xx în 5s); cleanup: marchează toate feed-sources legate de shop ca `disconnected` cu `last_error="App uninstalled by merchant"`, șterge `access_token` + `scope` din `integration_secrets`, scrie `audit_log` (`shopify.app.uninstalled`). Idempotent la re-delivery.
  - Înregistrat automat la OAuth exchange via `register_uninstall_webhook()` (POST `/admin/api/{version}/webhooks.json` cu topic `app/uninstalled`); eșecul e logat dar nu blochează flow-ul OAuth.
- Frontend:
  - Callback page: `/agency/integrations/shopify/callback` — pattern identic cu Meta/TikTok, recuperează `shopify_oauth_context` din `sessionStorage` și apelează `complete-oauth` pe sursă.
  - Add New Source Step 3 colectează doar `Source Name` + shop URL (normalizare automată `my-store` → `my-store.myshopify.com`, strip `https://`) și pornește OAuth la click pe „Conectează la Shopify". NU mai colectează API Key/Secret manual.
  - Lista de surse afișează `connection_status` badge (`Conectat` / `În așteptare` / `Eroare` / `Deconectat`), buton `Importă` pentru sursele conectate și `Reconectează` pentru cele în eroare/deconectate.
- Note operaționale:
  - Token-ul Shopify offline **NU expiră** (nu are refresh token). Se revocă doar la dezinstalarea app-ului (webhook `app/uninstalled`).
  - Rate limit Shopify Admin API: 2 req/sec (bucket 40); conectorul throttle-ază la ≥ 35/40 și retry pe 429.
  - Paginare cursor-based via `Link` header, max 250 produse/pagină.
  - Token-urile sunt mascate (`shpua_XXXXXX***`) în orice log output (`_mask_token`).
  - Callback URL frontend (Shopify Partners): `https://admin.omarosa.ro/agency/integrations/shopify/callback`.
  - Webhook URL backend `app/uninstalled`: `https://admin.omarosa.ro/api/integrations/shopify/webhooks/app-uninstalled`.
  - Webhook URL backend GDPR (toate cele 3 topic-uri partajează endpoint-ul): `https://admin.omarosa.ro/api/integrations/shopify/webhooks/compliance`.

#### Shopify CLI deploy (GDPR webhooks la nivel de App)

GDPR mandatory webhooks (`customers/data_request`, `customers/redact`, `shop/redact`) sunt obligatorii pentru orice Public App înainte de App Store review. Le declarăm la nivel de App via `shopify-app/shopify.app.toml`, deployat o singură dată cu Shopify CLI dintr-o stație autentificată în Shopify Partners. Subscripțiile devin active automat pentru orice instalare nouă.

```bash
# o singură dată per stație
npm install -g @shopify/cli@latest
shopify auth login

# de fiecare dată când shopify-app/shopify.app.toml se schimbă
cd shopify-app
shopify app deploy --client-id 57f055a691df0b88ab9b50f0900556ad --allow-updates
```

`--allow-updates` e flag-ul CI/CD-friendly care sare peste prompt-ul interactiv de confirmare. Folosește `--no-release` pentru un dry-run care creează versiunea fără să o publice merchant-ilor.

Ca **fallback** pentru development stores sau orice mediu unde CLI deploy nu a rulat încă, `shopify_oauth_exchange()` apelează best-effort `register_compliance_webhooks()` care POST-ează cele 3 topic-uri pe `/admin/api/{version}/webhooks.json` per-shop. La fel ca la `app/uninstalled`, eșecul e logat dar nu blochează flow-ul OAuth.

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
- `GET /integrations/meta-ads/connect`
- `POST /integrations/meta-ads/oauth/exchange`
- `POST /integrations/meta-ads/import-accounts`
- `POST /integrations/meta-ads/{client_id}/sync`
- `GET /integrations/tiktok-ads/status`
- `GET /integrations/tiktok-ads/connect`
- `POST /integrations/tiktok-ads/oauth/exchange`
- `POST /integrations/tiktok-ads/import-accounts`

`POST /integrations/tiktok-ads/import-accounts` face advertiser discovery real prin TikTok Business API (`/open_api/{version}/oauth2/advertiser/get/`) și persistă/upsertează conturile în registrul generic de platform accounts; dacă discovery întoarce 0 conturi, răspunsul include mesaj clar + diagnostice safe (`api_code`, `api_message`, `page_count_checked`, `row_container_used`).
- `POST /integrations/tiktok-ads/{client_id}/sync` (opțional body: `start_date`, `end_date`, `grain` in {`account_daily`,`campaign_daily`,`ad_group_daily`,`ad_daily`}; fără body => `grain=account_daily` + ultimele 7 zile complete)
- `POST /integrations/tiktok-ads/{client_id}/backfill` (opțional body: `start_date`, `end_date`, `grains`; default: `2024-01-09` → ieri, toate grain-urile TikTok, chunked 30 zile)
- `GET /integrations/pinterest-ads/status`
- `POST /integrations/pinterest-ads/{client_id}/sync`
- `GET /integrations/snapchat-ads/status`
- `POST /integrations/snapchat-ads/{client_id}/sync`
- `GET /integrations/shopify/status`
- `GET /integrations/shopify/connect?shop={shop}.myshopify.com`
- `POST /integrations/shopify/oauth/exchange`
- `POST /integrations/shopify/webhooks/app-uninstalled` (public, HMAC-verified)
- `POST /subaccount/{subaccount_id}/feed-sources` (creare sursă Shopify cu `shop_domain` → `{ source, authorize_url, state }`)
- `POST /subaccount/{subaccount_id}/feed-sources/{source_id}/complete-oauth`
- `POST /subaccount/{subaccount_id}/feed-sources/{source_id}/reconnect`
- `POST /subaccount/{subaccount_id}/feed-sources/{source_id}/import`

`GET /dashboard/agency/summary` include în `integration_health` status real pentru `google_ads`, `meta_ads` și `tiktok_ads`; `pinterest_ads` și `snapchat_ads` rămân placeholder `disabled` până la integrare completă.


## Redirect URI alignment (production)
- TikTok Developers (Advertiser redirect URL) + Railway `TIKTOK_REDIRECT_URI` trebuie setate la: `https://scripts-chi-nine.vercel.app/agency/integrations/tiktok/callback`.
- Meta Developers (OAuth Valid Redirect URI) + Railway `META_REDIRECT_URI` trebuie setate la: `https://scripts-chi-nine.vercel.app/agency/integrations/meta/callback`.
- Shopify Partners (VOXEL App Allowed redirection URL) + Railway `SHOPIFY_REDIRECT_URI` trebuie setate la: `https://admin.omarosa.ro/agency/integrations/shopify/callback`.
- Callback pages frontend folosite în aplicație:
  - TikTok: `/agency/integrations/tiktok/callback`
  - Meta: `/agency/integrations/meta/callback`
  - Shopify: `/agency/integrations/shopify/callback`

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
   - `INTEGRATION_SECRET_ENCRYPTION_KEY`
   - opțional: `GOOGLE_ADS_API_VERSION` (default `v23`)
2. Rulează migrațiile DB cu runner-ul idempotent: `cd apps/backend && PYTHONPATH=. python -m app.db.migrate`.
2.1 OAuth callback salvează automat refresh token-ul Google în DB (criptat); nu mai este necesar copy/paste manual în Railway pentru `GOOGLE_ADS_REFRESH_TOKEN`.
3. Rulează diagnostic local/remote: `PYTHONPATH=apps/backend python scripts/diag_google_ads.py`.
4. Rulează sync on-demand pentru conturile mapate: `POST /integrations/google-ads/sync-now` (agency admin).
5. Verifică datele în DB (`ad_performance_reports`) pe ultimele 30 zile și endpoint-ul `GET /dashboard/agency/summary?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`.
6. Confirmă în UI că Google Ads arată `rows30 > 0` și cardurile dashboard nu mai rămân pe 0 după sync.



## Railway: rulare migrații Postgres (idempotent + lock)
- Runner migrații: `cd apps/backend && PYTHONPATH=. python -m app.db.migrate`
- Comportament: creează `schema_migrations` dacă lipsește, aplică fișierele `apps/backend/db/migrations/*.sql` în ordine lexicografică și marchează fiecare fișier aplicat o singură dată.
- Siguranță concurență: runner-ul folosește advisory lock Postgres global, deci rulări paralele nu aplică dublu migrațiile.
- Recomandare Railway (web start command): `python -m app.db.migrate --migrations-dir db/migrations --baseline-before 0015_ && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.


## Meta/TikTok sync diagnostics (real errors)
- Eroarea reală pentru run-urile Meta/TikTok este expusă în progresul sync (`/agency/sync-runs/accounts/{platform}/progress`) prin câmpurile additive:
  - `active_run.last_error_summary`
  - `active_run.last_error_details`
- `last_error_details` include (când există): `platform`, `account_id`, `client_id`, `grain`, `chunk_index`, `start_date`, `end_date`, `provider_error_code`, `provider_error_message`, `http_status`, `endpoint`, `retryable`.
- UI Agency Accounts afișează sumarul real sub statusul de eroare, fără redesign.
- Repro rapid diagnostic:
  1. Pornește un historical batch pentru Meta/TikTok din Agency Accounts.
  2. Urmărește polling-ul batch/progress și verifică `last_error_summary` + `last_error_details`.
  3. În logs backend caută `sync_worker.chunk_failed` pentru `job_id/chunk_index` + metadatele sanitizate.
- Sanitizare: token-urile/secretele sunt mascate (`***`) în snippets/metadata/log strings pentru a evita expunerea credentialelor.

## Railway: rolling sync zilnic (cron)
- **Comandă cron Railway (daily enqueue):** `cd apps/backend && PYTHONPATH=. python -m app.workers.rolling_scheduler`
- **Worker de procesare chunk-uri (service separat, continuu):** `cd apps/backend && PYTHONPATH=. python -m app.workers.sync_worker`
- Cron-ul creează run-uri `job_type=rolling_refresh` cu `trigger_source=cron` în `sync_runs`, vizibile în Agency Account Detail → Sync runs.
- Regula exactă pentru fereastra zilnică rolling: `end_date = yesterday` (în timezone-ul contului), `start_date = end_date - 6 zile` ⇒ fix 7 zile calendaristice complete.
- Eligibilitate minimă rolling cron: cont mapat la client + `sync_start_date` inițiat (altfel este omis explicit ca `history_not_initialized`).
- Feature flag opțional: `ROLLING_ENTITY_GRAINS_ENABLED=1` (alias compatibil cu API: `ENTITY_GRAINS_ENABLED=1`; dacă oricare e activ, feature-ul este ON).
  - Default (lipsă/0): scheduler enqueuiește doar `grain=account_daily` (comportament actual).
  - Activ (1/true/yes/on): pentru conturi Google Ads, scheduler enqueuiește și `campaign_daily`, `ad_group_daily`, `ad_daily`, `keyword_daily`; pentru conturi Meta Ads enqueuiește `campaign_daily`, `ad_group_daily`, `ad_daily`; pentru conturi TikTok Ads enqueuiește `campaign_daily`, `ad_group_daily`, `ad_daily` (toate plus `account_daily`) pe aceeași fereastră rolling de 7 zile complete.
- Același flag (ENTITY/ROLLING alias) activează și auto-expand pentru `POST /agency/sync-runs/batch` pe request-uri legacy Google (`grain` lipsă sau `account_daily`) astfel încât historical backfill să includă și entity grains.

## Railway: repair sweeper (historical + rolling stale runs)
- **One-shot manual sweep (historical + rolling):** `cd apps/backend && PYTHONPATH=. python -m app.workers.historical_repair_sweeper`
- **Periodic sweeper loop (historical + rolling, service separat):** `cd apps/backend && PYTHONPATH=. python -m app.workers.historical_repair_sweeper_loop`
- Env vars suportate:
  - `HISTORICAL_REPAIR_SWEEPER_ENABLED` (`true/false`, default `true` pentru loop runner)
  - `HISTORICAL_REPAIR_SWEEPER_INTERVAL_SECONDS` (default `300`)
  - `HISTORICAL_REPAIR_SWEEPER_STALE_MINUTES` (override la `SYNC_RUN_REPAIR_STALE_MINUTES`)
  - `HISTORICAL_REPAIR_SWEEPER_LIMIT` (default `100`)
- Loop-ul loghează explicit `iteration_started`/`iteration_finished` + summary; dacă o iterație eșuează, eroarea este logată și loop-ul continuă la următoarea iterație.

## Team management foundation (users + user_memberships)
- Backend team management folosește acum modelul normalizat `users` (identity) + `user_memberships` (scope + rol canonic) pentru a pregăti autentificarea reală în pasul următor.
- Contractul API existent pentru `GET/POST /team/members` rămâne compatibil cu frontend-ul curent (payload/shape legacy), dar persistența nouă este făcută în `users` + `user_memberships`.
- Rolurile canonice interne pentru memberships sunt:
  - `agency_admin`, `agency_member`, `agency_viewer`
  - `subaccount_admin`, `subaccount_user`, `subaccount_viewer`
- Endpoint nou: `GET /team/subaccount-options` (id, name, label) pentru selecția de sub-account în flow-urile viitoare.
- Login/token flow nu este modificat în acest pas; acest task pregătește migrarea către auth real user-based în pasul următor.
- RBAC/session folosesc acum rolurile canonice ca sursă de adevăr (`agency_admin`, `agency_member`, `agency_viewer`, `subaccount_admin`, `subaccount_user`, `subaccount_viewer`).
- Aliasurile legacy rămân tranzitoriu compatibile: `account_manager` -> `subaccount_user`, `client_viewer` -> `subaccount_viewer`.
- Autentificarea `/auth/login` este acum DB-first (`users` + `user_memberships`) cu fallback de urgență pe credentials din env (token `super_admin` cu `is_env_admin=true`).
- Când un user are mai multe memberships active pentru același rol, login-ul returnează `409` până la implementarea selecției explicite de sub-account la autentificare.
- Endpointuri noi Sub-account Team (backend):
  - `GET /team/subaccounts/{subaccount_id}/members`
  - `POST /team/subaccounts/{subaccount_id}/members`
- Scope enforcement: rolurile `subaccount_*` sunt limitate la propriul `subaccount_id` din token; rolurile agency/global pot accesa orice sub-account permis de RBAC.
- Role picker-ul rămâne sursa de adevăr pentru rolul de bază; în plus, membership-urile `subaccount` pot avea acum `module_keys` (catalog canonic: `dashboard`, `campaigns`, `rules`, `creative`, `recommendations`) pentru restricții fine pe module.
- Pentru membership-uri `subaccount`, dacă `module_keys` lipsește la create se aplică default-ul „toate modulele”; pentru membership-uri `agency`, trimiterea `module_keys` este respinsă explicit (400).
- Grant ceiling backend: un actor `subaccount_*` poate acorda doar subset din modulele pe care le are deja pe același sub-account; actorii agency/global pot acorda orice modul valid.
- Endpoint nou: `GET /team/module-catalog?scope=subaccount` pentru UI-ul viitor (returnează `key`, `label`, `order`, `scope`).
- În acest pas nu sunt implementate încă: edit/deactivate/delete member, reassignment din UI, invite/reset password.
- Mailgun backend foundation (agency-level) este disponibilă prin endpointurile:
  - `GET /agency/integrations/mailgun/status`
  - `POST /agency/integrations/mailgun/config`
  - `POST /agency/integrations/mailgun/test`
- Config-ul Mailgun se salvează în `integration_secrets` (scope `agency_default`), iar `api_key` este returnat doar mascat (`api_key_masked`).
- Flow-urile `invite/reset password` rămân intenționat în afara acestui pas.
- Backend forgot/reset password este implementat prin endpointurile publice `POST /auth/forgot-password` și `POST /auth/reset-password/confirm`.
- `POST /auth/forgot-password` folosește Mailgun agency-level existent și răspunde generic (fără user enumeration).
- Tokenurile de reset rămân one-time, expirabile, stocate doar ca hash în `auth_email_tokens`.
- UI forgot/reset este conectat în frontend (`/forgot-password`, `/reset-password`, link din `/login`).
- Invite backend este implementat prin `POST /team/members/{membership_id}/invite` (admin-only, Mailgun agency-level).
- `POST /auth/reset-password/confirm` acceptă acum tokenuri `password_reset` și `invite_user`.
- UI „Trimite invitație” este disponibil în Agency Team și apelează backend-ul `POST /team/members/{membership_id}/invite`.
- Invite UI în Sub-account Team rămâne pentru taskul următor.


## Storage media cleanup batch runner (manual + Railway Scheduled Job)
- **Manual run (default limit from config):** `cd apps/backend && PYTHONPATH=. python -m app.workers.storage_media_cleanup_runner`
- **Manual run (explicit limit):** `cd apps/backend && PYTHONPATH=. python -m app.workers.storage_media_cleanup_runner --limit 200`
- **Railway Scheduled Job command (recommended):** `cd apps/backend && PYTHONPATH=. python -m app.workers.storage_media_cleanup_runner`
- Batch size env: `STORAGE_MEDIA_CLEANUP_BATCH_LIMIT` (default `100`).
- Runner output: JSON summary cu `limit`, `processed`, `purged`, `skipped`, `failed` (plus `status`).
- Exit code semantics:
  - `0` când batch-ul rulează (inclusiv dacă are item-uri `failed`/`skipped`)
  - non-zero doar la eroare globală (ex: provider/config indisponibil, excepție neprevăzută înainte/în jurul run-ului).

## Railway: `worker-bgremoval` service (background removal Celery worker)
- Acest worker rulează pipeline-ul `rembg` + ONNX pentru cutout-uri. Este **separat** de restul serviciilor Railway pentru că imaginea lui include dependențe ML (onnxruntime, opencv-python-headless, rembg) care adaugă ~800MB peste baseline.
- Dockerfile dedicat: `apps/backend/Dockerfile.bgworker`. NU folosi `apps/backend/Dockerfile` pentru acest serviciu.
- Config-as-Code: `apps/backend/railway.bgworker.json` — conține `build.dockerfilePath` + `deploy.startCommand` + restart policy. Pune acest path în câmpul **Config-as-Code** al serviciului Railway.
- Setări Railway dashboard pentru serviciul `worker-bgremoval`:
  1. **Root Directory** = `apps/backend` (pentru ca `dockerfilePath: "Dockerfile.bgworker"` și `railway.bgworker.json` să fie găsite relative la acest subdirector, la fel ca restul serviciilor).
  2. **Config-as-Code path** = `railway.bgworker.json`.
  3. **Variables** (share din `api-backend` sau set explicit): `DATABASE_URL`, `MONGO_URI`, `MONGO_DATABASE`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`, `STORAGE_S3_ENDPOINT_URL`, `STORAGE_S3_PRESIGNED_TTL_SECONDS`, `APP_AUTH_SECRET`, `INTEGRATION_SECRET_ENCRYPTION_KEY`. Opțional: `REMBG_MODEL` (default `u2net`), `CUTOUT_CONCURRENCY_PER_CLIENT`, `CUTOUT_ORPHAN_RETENTION_DAYS`.
- Start command (redus în `railway.bgworker.json`): `celery -A app.workers.celery_app worker -Q bgremoval_interactive,bgremoval_prime,bgremoval,bgremoval_bulk,sync_hooks -c 2 -n bgremoval@%h --loglevel=info`.
- Verificare post-deploy: log-urile runtime trebuie să conțină `rembg_session_warmed model=u2net` + `celery@bgremoval ready.`. Dacă vezi `ModuleNotFoundError: onnxruntime`, serviciul a fost build-uit cu Dockerfile-ul greșit (baseline). Dacă vezi `Cannot connect to redis://...`, `CELERY_BROKER_URL` lipsește.
- Fără healthcheck HTTP: workerul nu expune port. Lasă `healthcheckPath` gol în UI (JSON-ul nu setează path).
