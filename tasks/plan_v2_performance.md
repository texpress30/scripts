# Plan V2: Optimizare Performanta — Probleme Noi

> Bazat pe auditul din 29.03.2026. Se adreseaza gap-urilor ramase din planul original + probleme noi descoperite.

## Obiective

- Reducere TTFB pe agency dashboard cu 50%+ (LATERAL join rewrite + pool)
- Eliminare connection churn (pool centralizat)
- Reducere transfer de date pe tabele/campaign endpoints cu 70%+ (SQL pagination)
- Imbunatatire perceived performance pe frontend (loading states + request dedup)

---

## Sprint 1 (3-4 zile) — Fundamente si P0

### 1.1 Connection Pool Centralizat
**Impact: CRITIC | Efort: 1 zi | Risc: Mic**

- [x] Creaza un modul `apps/backend/app/db/pool.py` care expune un `psycopg_pool.ConnectionPool` (sau `psycopg_pool.AsyncConnectionPool` daca migrezi la async)
- [x] Configureaza: `min_size=2, max_size=10` (ajustabil per env)
- [x] Inlocuieste `psycopg.connect(settings.database_url)` in toate serviciile cu `pool.getconn()` / context manager
- [x] Fisiere de modificat: `dashboard.py`, `performance_reports.py`, `client_registry.py`, `sync_runs_store.py`, `sync_run_chunks_store.py`, `client_data_store.py`, si altele cu `_connect()`
- [x] Adauga `psycopg_pool` in `requirements.txt`
- [x] Lifecycle: init pool la startup in `main.py`, close la shutdown

### 1.2 Rewrite Agency Dashboard Query
**Impact: CRITIC | Efort: 2 zile | Risc: Mediu**

- [x] Inlocuieste `LEFT JOIN LATERAL` din `_agency_reports_query()` cu un JOIN simplu pre-aggregat:
  ```sql
  -- In loc de LATERAL per row, pre-selecteaza mappings unice
  WITH ranked_mappings AS (
      SELECT DISTINCT ON (platform, account_id)
          platform, account_id, account_id_norm, client_id, account_currency
      FROM agency_account_client_mappings
      ORDER BY platform, account_id, updated_at DESC
  )
  SELECT ...
  FROM ad_performance_reports apr
  LEFT JOIN ranked_mappings m ON m.platform = apr.platform
      AND (m.account_id = apr.customer_id
           OR (apr.platform = 'google_ads'
               AND m.account_id_norm = apr.customer_id_norm))
  ```
- [x] Adauga filtru `AND apr.platform IN ('google_ads', 'meta_ads', 'tiktok_ads', ...)` (lipseste azi)
- [x] Adauga filtru grain `account_daily` daca agency summary nu are nevoie de campaign-level
- [ ] Verifica cu `EXPLAIN ANALYZE` pe date reale — compara LATERAL vs JOIN plan
- [ ] Snapshot test: compara output-ul vechi vs nou pe aceleasi date

### 1.3 Elimina Regex Fallback din Hot Joins (Optional P0)
**Impact: Mediu | Efort: 0.5 zile | Risc: Mic daca norm-urile sunt backfilled**

- [x] Verifica ca `customer_id_norm` si `account_id_norm` sunt NOT NULL pe toate randurile relevante
- [x] Daca da: inlocuieste `COALESCE(norm, regexp_replace(...))` cu `norm = norm` direct
- [x] Daca nu: ruleaza un backfill one-time si adauga NOT NULL constraint

---

## Sprint 2 (3-4 zile) — P1 Optimizari

### 2.1 SQL Pagination pe Account/Campaign/AdGroup Tables
**Impact: Mare | Efort: 1 zi | Risc: Mic**

- [x] Modifica `_client_platform_account_rows_query` sa accepte `LIMIT/OFFSET` in SQL
- [x] Modifica `_client_platform_campaign_rows_query` la fel
- [x] Elimina pattern-ul `fetchall() → sort in Python → items[start:end]`
- [x] Adauga `ORDER BY cost DESC LIMIT %s OFFSET %s` direct in query
- [x] Asigura ca sortarea din SQL matcheaza sortarea din Python existenta
- [x] Adauga count query separat pentru total_count (sau `COUNT(*) OVER()`)

### 2.2 Batch Sync Writes
**Impact: Mare | Efort: 1 zi | Risc: Mic**

- [x] Modifica `performance_reports.py` sa faca upsert in batch:
  ```python
  # In loc de per-row connect + insert + commit:
  with pool.getconn() as conn:
      with conn.cursor() as cur:
          execute_values(cur, upsert_sql, batch_of_rows)
      conn.commit()
  ```
- [x] Batch size: 500-1000 rows per commit
- [x] Asigura ca error handling pastreaza semantica (retry per batch, nu per row)

### 2.3 SWR / React Query pe Frontend
**Impact: Mare | Efort: 2 zile | Risc: Mic**

- [x] Adauga `@tanstack/react-query` in `apps/frontend/package.json`
- [x] Creaza `QueryClientProvider` in layout/AppShell
- [x] Migreaza dashboard data fetching de la `useEffect + useState` la `useQuery`:
  - Sub dashboard: `useQuery(['client-dashboard', clientId, dateRange])`
  - Agency dashboard: `useQuery(['agency-summary', dateRange])`
- [x] Configureaza: `staleTime: 30_000, gcTime: 300_000, refetchOnWindowFocus: true`
- [x] Deduplicate: request-uri identice concurente se fac o singura data
- [ ] AppShell: paralelizeaza boot requests cu `useQueries`

---

## Sprint 3 (2-3 zile) — P2 Polish

### 3.1 BFF Cache Per-Endpoint
**Impact: Mediu | Efort: 0.5 zile | Risc: Mic**

- [x] In `apps/frontend/src/app/api/[...path]/route.ts`, diferentiaza revalidate per path:
  - `/dashboard/*` → `revalidate: 30`
  - `/clients/*` → `revalidate: 60`
  - `/integrations/*/status` → `revalidate: 15`
  - `/team/*` → `revalidate: 120`

### 3.2 Route Loading States
**Impact: Mediu | Efort: 0.5 zile | Risc: Mic**

- [x] Adauga `loading.tsx` pe:
  - `apps/frontend/src/app/agency/dashboard/loading.tsx`
  - `apps/frontend/src/app/sub/[id]/dashboard/loading.tsx`
  - `apps/frontend/src/app/agency-accounts/loading.tsx`
- [x] Skeleton UI simplu: header placeholder + table rows animate

### 3.3 Cache pe Google Ads /status
**Impact: Mic | Efort: 0.5 zile | Risc: Mic**

- [x] Adauga `response_cache` cu TTL 30s pe `GET /integrations/google-ads/status`
- [x] Aliniaza cu pattern-ul existent de pe `/diagnostics`

### 3.4 FX Rate Batch/Prefetch
**Impact: Mediu | Efort: 1 zi | Risc: Mic**

- [x] Colecteaza toate perechile `(currency, date)` distincte inainte de iteratie
- [x] Faci un singur batch de request-uri FX (sau cache warmup)
- [x] Aplica rate-urile din cache in iteratia per-row

### 3.5 Bundle Analyzer + Cleanup
**Impact: Mic | Efort: 0.5 zile | Risc: Mic**

- [x] Adauga `@next/bundle-analyzer` in devDependencies
- [x] Script: `"analyze": "ANALYZE=true next build"`
- [x] Adauga `optimizePackageImports: ['lucide-react']` in `next.config.js`
- [x] Sterge `PerformanceCharts.tsx` daca e dead code confirmat
- [x] Verifica ca `recharts` e doar in async chunks (nu in main bundle)

---

## Sprint 4 (Optional) — P3 Nice-to-have

### 4.1 Polling cu Backoff Real
- [x] Implementeaza exponential backoff pe polling (nu doar 2 intervale fixe)
- [x] Formula: `min(baseMs * 2^consecutiveIdles, maxMs)`, reset la activitate

### 4.2 Eliminare Completa Regex din Joins
- [x] Backfill complet `*_norm` pe toate platformele (nu doar Google)
- [x] Adauga `NOT NULL` + `DEFAULT` pe coloanele norm
- [x] Simplifica join-urile la `norm = norm` fara COALESCE/regexp_replace

### 4.3 AppShell Boot Parallelization
- [x] Identifica request-urile independente din AppShell mount
- [x] Grupeaza in `Promise.all` (clients + company settings + access)
- [x] Lazy load business-profile dupa ce clientii sunt afisati

---

## Estimari de Impact

| Optimizare | TTFB Estimat | LCP Estimat |
|------------|-------------|-------------|
| Connection pool | -20-30% | - |
| Agency LATERAL rewrite | -40-60% pe agency dashboard | -30-40% |
| SQL pagination | -50-70% pe tabele mari | - |
| Batch sync writes | - (write path) | - |
| React Query dedup | - | -10-20% (mai putin waterfall) |
| loading.tsx | - | -15-25% perceived |

## Riscuri

1. **Connection pool sizing** — prea mic = queue, prea mare = Postgres OOM. Start cu 5-10, monitorizare.
2. **Agency query rewrite** — `DISTINCT ON` poate avea plan diferit. Test cu EXPLAIN pe productie-like data.
3. **React Query migration** — risc de regresia in stale data. Configureaza staleTime conservator initial.
4. **Batch writes** — error handling: daca un batch esueaza, trebuie retry inteligent, nu pierdere date.
