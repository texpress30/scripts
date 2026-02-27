# TODO — Modernizare Header/Sidebar + Profil Dropdown cu Login As

- [x] Analizez structura curentă AppShell și cerințele pentru header, dropdown profil și sidebar.
- [x] Adaug backend minim pentru impersonare admin (`POST /auth/impersonate`).
- [x] Refactorizez header-ul: profil dropdown, iconițe (notificări, temă, fullscreen), meniu profil și signout.
- [x] Implementez flyout "Login As" cu search + listă utilizatori (ALL USERS) și acțiune de impersonare.
- [x] Implementez indicator persistent "Impersonating" cu buton "Switch back to Admin".
- [x] Curăț sidebar-ul: elimin opțiunile "Schimbă tema" și "Logout" din meniul lateral.
- [x] Rulez verificări (backend/frontend), încerc screenshot, finalizez review și commit + PR.

## Review
- Endpoint-ul backend `POST /auth/impersonate` permite adminilor să genereze token pentru user țintă și loghează evenimentul de audit aferent.
- Header-ul are acțiuni dedicate (notificări/temă/fullscreen) și dropdown profil cu structură compactă + opțiuni `Login As`, `Profil`, `Signout`.
- `Login As` include search + listă utilizatori cu scroll, iar acțiunea setează sesiunea impersonată și afișează banner persistent pentru revenire la admin.
- Sidebar-ul a fost simplificat prin eliminarea acțiunilor de temă/logout mutate în zona de profil.
- Verificări rulate: `py_compile`, subset `pytest` (skip în mediu), `npm run build`; screenshot-uri generate cu Playwright pentru header/dropdown.
