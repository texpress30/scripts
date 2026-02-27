# TODO — Settings /team: listare + adăugare utilizator

- [x] Revizuiesc structura existentă pentru `/settings/team` și contractele backend disponibile.
- [x] Adaug backend pentru echipă (`team_members`): schemă, listare și creare membri.
- [x] Construiesc pagina `/settings/team` cu două stări (listare + formular adăugare), etichete în limba română.
- [x] Implementez filtre, căutare, paginare și acțiuni în tabel (edit/delete ca UI actions).
- [x] Implementez loading state + toast pentru fluxul „Adaugă Utilizator”.
- [x] Rulez verificări (backend tests + frontend build) și documentez rezultatul.
- [x] Commit + PR cu titlu specific schimbărilor.

## Review
- Am adăugat backend dedicat pentru management echipă: tabel `team_members`, service de listare cu filtre/paginare și endpoint-uri `GET/POST /team/members`.
- Am conectat schema init la startup în backend, astfel tabela există înainte de folosire.
- Pagina `/settings/team` a fost implementată complet cu două moduri:
  - listare utilizatori cu filtre + căutare + paginare;
  - formular „Adaugă Utilizator” cu layout pe două coloane și setări avansate (parolă).
- Fluxul de creare are loading state pe buton, toast de succes/eroare și refresh automat în listă după adăugare.
