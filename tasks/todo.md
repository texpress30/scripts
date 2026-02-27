# TODO — Settings /storage (Utilizare Stocare Media)

- [x] Analizez implementarea curentă pentru `/settings/storage` și datele disponibile în backend.
- [x] Adaug backend pentru listare utilizare stocare per sub-cont din Postgres (căutare + paginare).
- [x] Extind schema existentă pentru proprietatea `media_storage` la nivel de sub-cont/client.
- [x] Implementez UI complet în română pentru `/settings/storage` (header, badge, tabel, căutare, paginare).
- [x] Implementez conversie corectă unități (MB/GB) pe frontend.
- [x] Rulez verificări backend/frontend și capturez screenshot.
- [x] Commit + PR.

## Review
- Am implementat endpoint backend `GET /storage/media-usage` cu RBAC agency scope, căutare și paginare.
- În `ClientRegistryService` am adăugat proprietatea persistentă `media_storage_bytes` pe `agency_clients` și listare dedicată pentru raportare stocare.
- Pagina `/settings/storage` a fost reconstruită complet în română, cu card principal, badge număr sub-conturi, căutare live, tabel cu nume+adresă și spațiu utilizat, plus paginare cu selector rânduri/pagină.
- Conversia unităților este implementată corect: MB implicit, GB când depășește 1024 MB.
- Screenshot-ul paginii a fost capturat cu succes prin browser tool.
