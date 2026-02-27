# TODO — Critical Data Sync: Date Reale Google Ads în Dashboard

- [x] Verific sursa de date dashboard și identific lipsa persistenței în `ad_performance_reports`.
- [x] Implementez persistența raportului zilnic Google Ads în Postgres la sync on-demand.
- [x] Refactorizez agregarea Agency Dashboard să citească din `ad_performance_reports` cu `start_date/end_date` și mapare cont→client.
- [x] Ajustez logica Sub-Account Dashboard pentru filtrare după conturi mapate clientului.
- [x] Adaug logging de debug pentru cazurile în care query-urile de dashboard nu returnează rânduri.
- [x] Actualizez UX carduri loading ("Se încarcă datele...") și verific trimiterea date range în format YYYY-MM-DD.
- [x] Rulez verificări backend/frontend, capturez screenshot, actualizez lessons, commit și PR.

## Review
- Am introdus `PerformanceReportsStore` cu tabelul `ad_performance_reports` și indexuri, plus metodă de write pentru raport zilnic (on-demand sync path).
- `google_ads_service.sync_client` persistă acum atât snapshot-ul curent, cât și raportul zilnic în `ad_performance_reports` (inclusiv `conversion_value`).
- `UnifiedDashboardService.get_agency_dashboard` agregă acum metricile din `ad_performance_reports`, aplică `WHERE report_date BETWEEN start_date AND end_date`, calculează ROAS ca `SUM(conversion_value)/SUM(spend)` și construiește Top 5 clienți prin `GROUP BY` pe client mapat.
- Pentru mapare cont→client, agregarea folosește `COALESCE(apr.client_id, mapped.client_id)` via `agency_account_client_mappings`; conturile nemapate intră în Agency totals, dar nu apar în Top Clienți.
- `get_client_dashboard` pentru non-test citește din `ad_performance_reports` filtrând doar conturile mapate clientului (aceeași rezolvare COALESCE), asigurând separare Agency vs Sub-Account.
- Am adăugat log-uri backend (`agency_dashboard_empty_result` / `agency_dashboard_query_rows`) pentru debugging pe query-uri goale.
- Frontend trimite în continuare `start_date`/`end_date` în format `YYYY-MM-DD` și cardurile afișează textul `Se încarcă datele...` pe loading.
