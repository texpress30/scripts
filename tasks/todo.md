# TODO — Dashboard Dinamic cu Date Range și Date Reale

- [x] Analizez fluxul actual Agency Dashboard (frontend + backend) și identific sursa reală de date din Postgres pentru agregări pe interval.
- [x] Extind backend-ul cu endpoint de agregare agency pe interval (`start_date`, `end_date`) folosind query-uri SQL cu `WHERE ... BETWEEN ...` pentru metrici + top clienți.
- [x] Adaug selector de perioadă în dashboard (preset + custom range + buton Update) și reîncarc datele la schimbare.
- [x] Înlocuiesc valorile statice din cele 7 carduri cu agregări reale din backend și adaug loading state vizual (skeleton/spinner).
- [x] Actualizez secțiunile "Top clienți (după spend)" și "Integration health" pentru afișare conform cerințelor UI/UX.
- [x] Rulez verificări (tests/build), fac screenshot pentru schimbarea vizuală și finalizez review + commit + PR.

## Review
- Am adăugat endpoint-ul `GET /dashboard/agency/summary` cu filtrare pe interval (`start_date`, `end_date`) și validare de interval; rezultatul include metrici agregate, top 5 clienți și număr clienți activi.
- În service-ul dashboard am introdus agregare SQL multi-platform pe Postgres, cu `WHERE synced_at::date BETWEEN start_date AND end_date` în toate query-urile pentru totals și top clienți.
- Dashboard-ul agency include acum Date Range Picker (Astăzi, Ultimele 7/30 zile, Luna aceasta, Custom range) cu buton `Update` care reîncarcă datele.
- Cele 7 carduri afișează valori reale din backend pentru intervalul selectat și afișează skeleton loading la refresh.
- Secțiunea Top clienți afișează nume + spend real (fără `#id`), iar Integration Health colorează status-ul (`connected` verde, `disabled` neutru, `error` roșu).
- Verificări rulate: `py_compile`, subset `pytest` (skip în mediu), `npm run build`, plus screenshot UI cu Playwright.
