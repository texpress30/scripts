# UI Contract v0 — MCC Command Center

> Acest document este **promptul de bază** pentru fiecare generație v0 (UI, flows, states, analytics, RBAC).

## 1) Route map complet

### 1.1 Public / shared

| Route | Tip | Scop |
|---|---|---|
| `/` | public | Landing + CTA către login/dashboard. |
| `/login` | public | Autentificare user (`agency_admin`, `account_manager`, `client_viewer`). |

### 1.2 Agency workspace (`/agency/...`)

| Route | Tip | Scop |
|---|---|---|
| `/agency/dashboard` | agency-level | KPI agregat pe toți clienții + starea integrărilor. |
| `/agency/clients` | agency-level | Listă clienți, creare client nou, căutare/filtrare. |
| `/agency/integrations` | agency-level | Status Google Ads / Meta Ads + acțiuni globale de reconectare. |
| `/agency/rules` | agency-level | Vizualizare politici automatizare la nivel de organizație (template-uri). |
| `/agency/notifications` | agency-level | Inbox notificări agregat (alerte, warnings, info). |
| `/agency/audit` | agency-level | Audit log pentru acțiuni admin/sistem. |
| `/agency/exports` | agency-level | Istoric exporturi BigQuery și status job-uri. |

### 1.3 Subscriber workspace (`/sub/:id/...`)

| Route | Tip | Scop |
|---|---|---|
| `/sub/:id/dashboard` | client-level | Dashboard consolidat client (spend, conversions, ROAS, breakdown platforme). |
| `/sub/:id/campaigns` | client-level | Listă campanii + acțiuni sync/evaluate/recomandări. |
| `/sub/:id/creative` | client-level | Librărie asset-uri creative + aprobare/reject. |
| `/sub/:id/recommendations` | client-level | Recomandări AI + aprobări de optimizare. |
| `/sub/:id/rules` | client-level | Reguli automate (list/create/evaluate). |
| `/sub/:id/insights/weekly` | client-level | Generare și istoric insight-uri săptămânale. |
| `/sub/:id/notifications` | client-level | Inbox notificări pentru clientul curent. |
| `/sub/:id/settings` | client-level | Setări canal/bugete/praguri locale. |

---

## 2) Contract pe pagini (scop, widgeturi, query-uri, states)

## 2.1 `/login`
- **Scop:** autentificare și bootstrap sesiune.
- **Widgeturi:** email input, password input, role select, submit button.
- **Query/Mutation:**
  - `POST /auth/login` cu `{ email, password, role }`.
- **States:**
  - `loading`: buton disabled + label `Se autentifica...`.
  - `error`: mesaj inline roșu (`401`, `400`, `429`).
  - `success`: persist token în `localStorage`, redirect.
  - `empty`: N/A (formular static).

## 2.2 `/agency/dashboard`
- **Scop:** overview cross-client pentru management agency.
- **Widgeturi:**
  - KPI cards (total spend, conversions, ROAS, nr. clienți activi).
  - Chart trend (spend/conversions), top clienți după performanță.
  - Integration health (Google/Meta), recent activity feed.
- **Query-uri necesare:**
  - `GET /clients`
  - `GET /integrations/google-ads/status`
  - `GET /integrations/meta-ads/status`
  - opțional agregare locală din `GET /dashboard/{client_id}` pe setul de clienți.
- **States:**
  - `loading`: skeleton cards + skeleton chart.
  - `empty`: zero clienți -> CTA `Creează primul client`.
  - `error`: card alert cu retry.

## 2.3 `/agency/clients`
- **Scop:** lifecycle clienți (list + create).
- **Widgeturi:**
  - tabel listă clienți (`name`, `owner_email`, `id`).
  - formular rapid creare client.
  - search/filter local.
- **Query-uri necesare:**
  - `GET /clients`
  - `POST /clients`
- **States:**
  - `loading`: tabel skeleton.
  - `empty`: mesaj `Nu există clienți`, CTA create.
  - `error`: toast/banner + retry.

## 2.4 `/agency/notifications`
- **Scop:** observabilitate operațională la nivel agency.
- **Widgeturi:**
  - counters (total, unread, alerts, warnings).
  - filter by type (`all/unread/alert/warning/success/info`).
  - list notificări + acțiuni mark read / mark all read.
- **Query-uri necesare:**
  - v0 mock/local state (compatibil API viitor).
  - API recomandat v1.1: `GET /notifications`, `PATCH /notifications/{id}`.
- **States:**
  - `loading`: skeleton list.
  - `empty`: zero notificări cu icon info.
  - `error`: fallback + retry.

## 2.5 `/agency/audit`
- **Scop:** trasabilitate acțiuni user/system.
- **Widgeturi:** tabel audit, filtre pe actor/acțiune/perioadă, export CSV.
- **Query-uri necesare:**
  - `GET /audit`
- **States:** loading/empty/error standard tabel.

## 2.6 `/agency/exports`
- **Scop:** monitorizare exporturi BigQuery.
- **Widgeturi:** list job-uri, status chip (`success`, `failed`), dată execuție.
- **Query-uri necesare:**
  - `GET /exports/bigquery/runs`
- **States:** loading/empty/error standard list.

## 2.7 `/sub/:id/dashboard`
- **Scop:** sănătate și performanță client curent.
- **Widgeturi:**
  - client switcher / command palette.
  - KPI cards (spend, conversions, ROAS), trend charts.
  - integration quick actions (sync Google/Meta).
  - AI recommendation preview + recent activity.
- **Query-uri necesare:**
  - `GET /dashboard/{client_id}`
  - `GET /clients` (pentru switcher)
  - `GET /ai/recommendations/{client_id}`
- **States:**
  - `loading`: skeleton cards/charts.
  - `empty`: dacă `is_synced=false`, CTA sync.
  - `error`: alert cu buton `Reîncarcă`.

## 2.8 `/sub/:id/campaigns`
- **Scop:** operațiuni campanii și sync date.
- **Widgeturi:** tabel campanii, acțiuni sync Google/Meta, evaluate rules.
- **Query-uri necesare:**
  - `POST /integrations/google-ads/{client_id}/sync`
  - `POST /integrations/meta-ads/{client_id}/sync`
  - `POST /rules/{client_id}/evaluate`
- **States:** loading action-level, empty list, error toast per action.

## 2.9 `/sub/:id/creative`
- **Scop:** management asset-uri creative.
- **Widgeturi:**
  - galerie/grid asset-uri cu status (`pending`, `approved`, `rejected`).
  - filtru status, preview modal, butoane approve/reject.
- **Query-uri necesare:**
  - v0 mock/local state.
  - API recomandat v1.1: `GET /creatives?client_id=...`, `POST /creatives/{id}/approve`, `POST /creatives/{id}/reject`.
- **States:** loading skeleton cards, empty gallery, error banner.

## 2.10 `/sub/:id/recommendations`
- **Scop:** decizie umană pe recomandări AI.
- **Widgeturi:** recommendation card, confidence/source, approve/dismiss.
- **Query-uri necesare:**
  - `GET /ai/recommendations/{client_id}`
  - API recomandat v1.1: `POST /ai/recommendations/{id}/approve`, `POST /ai/recommendations/{id}/dismiss`.
- **States:**
  - `loading`: placeholder text.
  - `empty`: mesaj `Nu am destule date`.
  - `error`: retry + status code mapping (`429` rate limit explicit).

## 2.11 `/sub/:id/rules`
- **Scop:** automatizare optimizări.
- **Widgeturi:** list reguli, create form, evaluate button, triggered actions table.
- **Query-uri necesare:**
  - `GET /rules/{client_id}`
  - `POST /rules/{client_id}`
  - `POST /rules/{client_id}/evaluate`
- **States:** loading list, empty rules set, error inline pe validări/permisiuni.

## 2.12 `/sub/:id/insights/weekly`
- **Scop:** insight-uri rezumative executive.
- **Widgeturi:** summary card, buton generate, timeline insight-uri.
- **Query-uri necesare:**
  - `GET /insights/weekly/{client_id}`
  - `POST /insights/weekly/{client_id}/generate`
- **States:** loading spinner pe generate, empty cu fallback text, error toast.

## 2.13 `/sub/:id/notifications`
- **Scop:** notificări client-specific.
- **Widgeturi:** identic cu agency notifications, dar scope client.
- **Query-uri necesare:**
  - v0 mock/local state.
- **States:** loading/empty/error standard.

---

## 3) Contract acțiuni UI (buton/link): `onClick -> API -> success -> redirect`

| UI element | onClick | API call | Success state | Redirect |
|---|---|---|---|---|
| `Login: Intra in platforma` | submit formular | `POST /auth/login` | token salvat + sesiune activă | `/agency/dashboard` (sau `/sub/:id/dashboard` pentru viewer) |
| `Landing: Intra in platforma` | navigate | none | N/A | `/login` |
| `Landing: Dashboard` | navigate | none | N/A | `/agency/dashboard` |
| `Clients: Adauga client` | submit create client | `POST /clients` | toast success + refresh list | stay (`/agency/clients`) |
| `Client row: Deschide workspace` | navigate cu client id | opțional preload `GET /dashboard/{id}` | workspace pregătit | `/sub/{id}/dashboard` |
| `Dashboard: Sync Google` | click action | `POST /integrations/google-ads/{id}/sync` | KPI refresh + badge synced | stay |
| `Dashboard: Sync Meta` | click action | `POST /integrations/meta-ads/{id}/sync` | KPI refresh + badge synced | stay |
| `Recommendations: Refresh` | click | `GET /ai/recommendations/{id}` | card recomandare actualizat | stay |
| `Recommendations: Approve` | click | `POST /ai/recommendations/{recId}/approve`* | badge `Approved` + event analytics | stay |
| `Recommendations: Dismiss` | click | `POST /ai/recommendations/{recId}/dismiss`* | badge `Dismissed` | stay |
| `Rules: Creeaza regula` | submit form | `POST /rules/{id}` | row nou în tabel | stay |
| `Rules: Evalueaza reguli` | click | `POST /rules/{id}/evaluate` | tabel `triggered actions` actualizat | stay |
| `Insights: Genereaza weekly` | click | `POST /insights/weekly/{id}/generate` | summary nou + timestamp | stay |
| `Exports: Ruleaza export BigQuery` | click | `POST /exports/bigquery/{id}` | run nou în listă | `/agency/exports` |
| `Notifications: Marcheaza toate` | click | `PATCH /notifications/mark-all`* | unread=0 | stay |

\* endpoint propus pentru extensie v1.1 (nu există încă în backend curent).

---

## 4) Matrice `permissions x action`

## 4.1 Permisiuni backend existente

| Role | `clients:read` | `clients:create` | `audit:read` |
|---|---:|---:|---:|
| `super_admin` | ✅ | ✅ | ✅ |
| `agency_admin` | ✅ | ✅ | ✅ |
| `account_manager` | ✅ | ❌ | ❌ |
| `client_viewer` | ✅ | ❌ | ❌ |

## 4.2 Acțiuni UI vs rol

| Action UI | super_admin | agency_admin | account_manager | client_viewer |
|---|---:|---:|---:|---:|
| Login | ✅ | ✅ | ✅ | ✅ |
| Vezi listă clienți | ✅ | ✅ | ✅ | ✅ |
| Creează client | ✅ | ✅ | ❌ | ❌ |
| Vezi dashboard client | ✅ | ✅ | ✅ | ✅ |
| Sync Google/Meta | ✅ | ✅ | ❌ | ❌ |
| Vezi recomandări AI | ✅ | ✅ | ✅ | ✅ |
| Approve recomandare | ✅ | ✅ | ⚠️ (policy-dependent) | ❌ |
| Creează regulă | ✅ | ✅ | ❌ | ❌ |
| Evaluează reguli | ✅ | ✅ | ❌ | ❌ |
| Generează insight weekly | ✅ | ✅ | ❌ | ❌ |
| Rulează export BigQuery | ✅ | ✅ | ❌ | ❌ |
| Vezi audit log | ✅ | ✅ | ❌ | ❌ |

---

## 5) Definiții evenimente analytics

## 5.1 Convenții
- Toate evenimentele includ: `event_name`, `timestamp`, `user_email`, `user_role`, `route`, `client_id?`, `request_id?`.
- Naming: snake_case, verb la final (`campaign_created`, `recommendation_approved`).

## 5.2 Event catalog (v0)

| Event name | Trigger UI | Payload minim | Success criteria |
|---|---|---|---|
| `login_submitted` | click submit login | `role`, `email_domain` | request trimis |
| `login_succeeded` | răspuns 200 login | `role` | token set + redirect |
| `login_failed` | răspuns !=200 | `status_code`, `reason` | eroare afișată |
| `campaign_sync_google_started` | click sync Google | `client_id` | request trimis |
| `campaign_sync_google_succeeded` | sync Google success | `client_id`, `rows_synced` | KPI refresh |
| `campaign_sync_meta_started` | click sync Meta | `client_id` | request trimis |
| `campaign_sync_meta_succeeded` | sync Meta success | `client_id`, `rows_synced` | KPI refresh |
| `campaign_created` | create campaign/manual (viitor) | `client_id`, `channel` | apare în listă |
| `recommendation_viewed` | recomandare afișată | `client_id`, `source` | card renderizat |
| `recommendation_approved` | click approve | `client_id`, `recommendation_id` | status approved |
| `recommendation_dismissed` | click dismiss | `client_id`, `recommendation_id` | status dismissed |
| `rule_created` | submit create rule | `client_id`, `rule_type`, `threshold` | regulă salvată |
| `rule_evaluated` | click evaluate | `client_id`, `triggered_count` | rezultat primit |
| `weekly_insight_generated` | click generate insight | `client_id` | summary nou disponibil |
| `bigquery_export_started` | click export | `client_id` | run inițiat |
| `bigquery_export_succeeded` | export status success | `client_id`, `run_id` | run în listă |
| `notification_marked_read` | click mark read | `notification_id`, `client_id?` | unread decrementat |
| `notification_mark_all_read` | click mark all | `scope` (`agency`/`client`) | unread=0 |

## 5.3 Proprietăți standard recomandate
- `platform`: `web`
- `app_version`: git sha / semantic version
- `env`: `prod` / `staging`
- `latency_ms`: durată acțiune (pentru funnel quality)

---

## 6) Instrucțiuni de folosire ca prompt v0 (copy/paste)

```
Folosește strict UI Contract v0 (docs/product/ui-contract.md) ca sursă de adevăr.
Generează ecrane și flows pentru namespace-urile /agency/* și /sub/:id/*.
Respectă:
1) route map,
2) query/mutation contracts,
3) loading/empty/error states,
4) action chains (onClick -> API -> success -> redirect),
5) RBAC matrix,
6) analytics event catalog.
Dacă lipsește un endpoint marcat "v1.1 propus", păstrează UI-ul și folosește mock action explicit.
```
