# TODO — Settings /company (Account-View)

- [x] Analizez starea curentă a paginii `/settings/company` și contractele backend existente.
- [x] Adaug persistență backend pentru setări companie în Postgres (`companies` + GET/PATCH API).
- [x] Implementez pagina `/settings/company` conform layout-ului de carduri și etichetelor în română.
- [x] Implementez branding logo/favicon + formular detalii + formular adresă + acțiuni Anulează/Salvează.
- [x] Adaug loading/toast/error handling pentru salvare și încărcare.
- [x] Rulez verificări (backend + frontend) și capturez screenshot.
- [x] Commit + PR.

## Review
- Am implementat backend dedicat pentru setări companie cu tabel `companies` și persistență per owner email (`GET/PATCH /company/settings`).
- Am conectat inițializarea schemei la startup-ul backend pentru a evita erori runtime la primul request.
- Pagina `/settings/company` a fost reconstruită complet cu cele 3 secțiuni cerute: Branding, Detalii Companie, Adresă Companie.
- Am adăugat acțiuni de upload/replace/delete logo (preview), iar schimbarea de logo actualizează automat favicon-ul în contextul paginii.
- Fluxul de salvare are loading state, feedback toast în română, validări obligatorii în backend și opțiune `Anulează` care revine la ultima stare salvată.
- Screenshot-ul nu a putut fi generat în acest environment deoarece browser container Playwright a crăpat cu SIGSEGV la launch.
