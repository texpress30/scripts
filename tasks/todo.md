# TODO — Branding dinamic în Sidebar (Logo & Context Selector)

- [x] Analizez AppShell curent și sursele de date disponibile pentru context Agency/Sub-account.
- [x] Extind backend client/company payload unde e necesar pentru logo context (agency/sub-account).
- [x] Implementez secțiunea de branding în partea de sus a sidebar-ului, deasupra selectorului Agency MCC.
- [x] Aplic logica dinamică: logo agency în Agency View, logo client/sub-cont în Sub-Account View.
- [x] Rulez verificări (build/test), fac screenshot și finalizez documentarea task/lessons.
- [x] Commit + PR.

## Review
- Am extins modelul client cu `client_logo_url` în backend (schema, listare, update profil), astfel AppShell poate primi logo specific pe sub-cont.
- Am adăugat card de branding în vârful sidebar-ului, deasupra selectorului Agency MCC, cu avatar circular, titlu context și locație.
- Logica de context este dinamică: în Agency View se folosește logo-ul agenției din `/company/settings`; în Sub-Account View se folosește `client_logo_url` (fallback pe inițiale).
- Contextul este detectat atât pe `/sub/:id/*`, cât și pe `/subaccount/:id/settings/*`, pentru consistență în settings mode.
- Screenshot-ul nu a putut fi generat în această rulare din cauza crash-ului Playwright Chromium (SIGSEGV) în container.
