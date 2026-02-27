# TODO — Critical Fix: RBAC Scope + Calendar Refactor + Aggregare Multi-Platform

- [x] Audit backend RBAC și repar politica `dashboard:view` pentru scope agency + subaccount fără regresii.
- [x] Ajustez agregarea dashboard pentru Agency View / Sub-Account View astfel încât să suporte interogări globale și filtrare pe interval.
- [x] Refactorizez Date Range Picker în UI la variantă compactă cu dropdown, preset-uri, 2 calendare interactive și acțiuni Cancel/Update.
- [x] Actualizez Integration Health conform cerinței (Google connected; restul disabled/inactive până la rollout).
- [x] Rulez validări backend/frontend + screenshot pentru UI nou.
- [x] Actualizez `tasks/lessons.md`, finalizez review în TODO, commit și PR.

## Review
- Am reparat modelul RBAC pentru acțiuni multi-scope: `ActionPolicy` acceptă acum `scopes`, iar `dashboard:view` este permis atât pe `agency`, cât și pe `subaccount`, eliminând eroarea de permisiuni în Agency Dashboard.
- Endpoint-ul agency summary continuă să folosească `enforce_action_scope(..., scope="agency")`, dar acum politica permite corect acest scope pentru acțiunea `dashboard:view`.
- Agregarea agency din Postgres însumează metricile cross-platform doar pentru clienții manuali (`agency_clients.source='manual'`) și folosește explicit `WHERE synced_at::date BETWEEN start_date AND end_date` pe toate tabelele snapshot.
- Top 5 clienți este calculat pe spend agregat multi-platform (Google + Meta + TikTok + Pinterest + Snapchat) în intervalul selectat.
- Date Range Picker-ul din frontend a fost refăcut: buton compact cu intervalul selectat, dropdown cu preset-uri în stânga, două calendare interactive în dreapta, acțiuni `Cancel`/`Update`.
- Integration Health afișează Google din status real API, iar celelalte platforme sunt marcate explicit `disabled` (neutral) până la implementarea completă.
- Verificări rulate: py_compile backend, pytest țintit pentru RBAC + e2e agency summary, build frontend și screenshot-uri Playwright pentru starea closed/open a noului calendar.
