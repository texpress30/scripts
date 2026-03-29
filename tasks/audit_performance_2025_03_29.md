# Audit de Performanta - 29 Martie 2026

## Partea I: Verificarea Planului de Optimizare

### Status general: 13/13 todo-uri marcate "completed" — implementare reala ~75%

Toate task-urile din plan sunt marcate `completed`, dar verificarea in cod releva **gap-uri semnificative** la unele puncte. Mai jos, statusul real per faza.

---

### Faza 1 — Quick wins (5 items)

| # | Item | Verdict | Detalii |
|---|------|---------|---------|
| 1 | Frontend caching policy | **PARTIAL** | `api.ts` are logica pe path (auth/sync-runs = no-store, rest = force-cache). BFF route (`[...path]/route.ts`) aplica **o singura politica** (30s revalidate) pe toate GET-urile — nu per-endpoint. |
| 2 | AppShell slimming | **PARTIAL** | Team members list e lazy (se incarca doar cand profile/loginAs e deschis). Dar `getAgencyMyAccess`/`getSubaccountMyAccess` se executa eager pe fiecare mount — ramane pe critical path. Nu exista `React.lazy` / dynamic import pe sub-componente shell. |
| 3 | Polling backoff | **PARTIAL** | Pause pe tab hidden: DA (10-15s delay). Backoff real (intervale crescatoare): NU. Doar doua intervale fixe (2.5s activ / 10s idle pe list; 4s/12s pe detail). |
| 4 | Dashboard lazy charts | **DA** | Sub-dashboard: charts + date picker = dynamic import. Agency dashboard: date picker dynamic (nu are charts proprii). |
| 5 | Backend short TTL cache | **PARTIAL** | Dashboard API: 45s TTL + Cache-Control headers. `google_ads /status`: **necached** (fara TTL). `/diagnostics`: 90s TTL. `services/dashboard.py` nu are cache propriu. |

### Faza 2 — Eliminare bottleneck-uri (5 items)

| # | Item | Verdict | Detalii |
|---|------|---------|---------|
| 1 | N+1 sync summary | **DA** | Batched run fetch (`ANY(%s::text[])`) + batched chunk counts intr-un singur GROUP BY. |
| 2 | Paginare heavy endpoints | **PARTIAL** | Tabele (google/meta/tiktok-ads-table): DA, limit/offset cu default 200, max 500. Dashboard summary/client: **NU** — nu au limit/offset. |
| 3 | Batch sale entries | **DA** | `list_sale_entries_for_daily_input_ids` cu `ANY(%s::int[])`. |
| 4 | Indexuri ad_performance_reports | **DA** | Migrare `0026`: `(platform, customer_id, report_date DESC)`, `(client_id, platform, report_date DESC)`, `(platform, customer_id_norm, report_date DESC)`. |
| 5 | Status vs diagnostics split | **DA** | `/status` e lightweight; `/diagnostics` e separat cu 90s cache. Nota: `/db-debug` inca cheama `run_diagnostics()`. |

### Faza 3 — Scalare (3 items)

| # | Item | Verdict | Detalii |
|---|------|---------|---------|
| 1 | account_id_norm + index | **DA** (schema), **PARTIAL** (query-uri) | Migrarile 0026/0027 adauga coloane norm + indexuri. Dar join-urile hot inca folosesc `COALESCE(norm, regexp_replace(...))` — regex ramane fallback activ. |
| 2 | Daily rollup table | **DA** | Tabel + meta + endpoint refresh + citire din rollup cand meta acopera intervalul. |
| 3 | Sync health precomputat | **DA** | Tabel `sync_health_summary` + batch read + campuri pe `list_client_platform_accounts`. |

---

## Partea II: Audit Bazat pe Sugestiile din Imagini

Imaginile (din discutii GitHub) evidentiaza ca:
- Backend-ul e **tight-coupled** cu Postgres (psycopg direct, SQL manual, migrari .sql, advisory locks)
- Bottleneck-ul e in **query patterns, volum de date, indexare, agregari** — nu in numarul de tabele
- **Nu se recomanda** migrare la MongoDB pentru core reporting/sync
- Se recomanda: **profiling Postgres**, **repository pattern**, **pilot MongoDB doar pentru arhiva/creative**

### Probleme critice gasite in audit

#### 1. FARA CONNECTION POOL (Severitate: CRITICA)

Toate serviciile folosesc `psycopg.connect(settings.database_url)` per apel — conexiune noua la fiecare request/operatie. Sub load, asta inseamna:
- Connection churn masiv
- Tail latency ridicat
- Risc de a lovi `max_connections` pe Postgres
- Overhead TCP handshake + TLS per query

**Fisiere afectate:** `dashboard.py`, `performance_reports.py`, `client_registry.py`, `sync_runs_store.py`, `sync_run_chunks_store.py`, si altele.

#### 2. LATERAL JOIN pe Agency Dashboard (Severitate: MARE)

`_agency_reports_query()` foloseste `LEFT JOIN LATERAL` care, pentru **fiecare rand** din `ad_performance_reports` in intervalul de date:
- Cauta in `agency_account_client_mappings`
- Aplica `regexp_replace` pentru Google
- `ORDER BY updated_at DESC, created_at DESC LIMIT 1`

**Nu are filtru pe grain** (`account_daily`) — scaneaza si randuri campaign/adgroup/keyword. Nu are filtru pe `platform IN (...)` ca query-ul client. Scaleaza prost pe volume mari.

#### 3. Paginare in Python, nu in SQL (Severitate: MARE)

`get_client_platform_account_performance` (si variante campaign/adgroup) face:
- `fetchall()` — aduce **toate** randurile
- Sorteaza in Python
- Aplica `items[start_idx:end_idx]`

La volume mari de date, asta inseamna transfer si procesare inutila.

#### 4. Sync Writes Per-Row (Severitate: MEDIE)

`performance_reports.py` face upsert `ON CONFLICT` **per rand** — fiecare write deschide conexiune, face INSERT, commit, inchide. La bulk sync cu mii de randuri, asta e bottleneck major.

#### 5. Fara SWR/React Query pe Frontend (Severitate: MEDIE)

- Nicio deduplicare de request-uri client-side
- Nicio invalidare inteligenta de cache
- Waterfall-uri: sub-dashboard face access guard → apoi data load secvential
- AppShell: clients → business-profile e secvential (waterfall)

#### 6. Bundle Size Nemonitorizat (Severitate: MICA)

- Niciun bundle analyzer configurat
- `recharts` e potentail mare dar e lazy-loaded pe sub-dashboard
- `next.config.js` minimal: nu are `optimizePackageImports` pentru `lucide-react`
- Nu exista `loading.tsx` pe rute — nicio stare de loading la nivel de ruta

#### 7. FX Rate Calls In-Line (Severitate: MEDIE)

Agregarile din dashboard fac `_get_fx_rate_to_ron` **per rand** in Python. Chiar cu cache de 6h pe modul, prima executie poate genera multe HTTP calls catre Frankfurter API.

#### 8. Cod Duplicat / Dead Code

- `_platform_sync_audit_rows_query` e definit de **doua ori** in `dashboard.py`
- `PerformanceCharts.tsx` importa `recharts` dar nu e referit nicaieri — posibil dead code in bundle

---

## Partea III: Matrice de Impact si Prioritizare

| Problema | Impact pe Load Time | Efort | Risc | Prioritate |
|----------|-------------------|-------|------|------------|
| Connection pool | Foarte mare | Mic | Mic | **P0** |
| Agency LATERAL rewrite | Foarte mare | Mediu | Mediu | **P0** |
| SQL pagination (nu Python) | Mare | Mic | Mic | **P1** |
| Sync batch writes | Mare | Mediu | Mic | **P1** |
| SWR/React Query | Mare | Mediu | Mic | **P1** |
| BFF cache per-endpoint | Mediu | Mic | Mic | **P2** |
| loading.tsx pe rute | Mediu | Mic | Mic | **P2** |
| google_ads /status cache | Mic | Mic | Mic | **P2** |
| Bundle analyzer + cleanup | Mic | Mic | Mic | **P3** |
| FX rate batch/prefetch | Mediu | Mediu | Mic | **P2** |
| Polling backoff real | Mic | Mic | Mic | **P3** |
| Eliminare regex fallback din joins | Mediu | Mare | Mediu | **P3** |
