# Tenant boundaries: Agency vs Sub-account

Acest document definește separarea funcțională între nivelul de **agency** și nivelul de **sub-account**, plus regulile minime de acces (RBAC) pe roluri.

## 1) Funcții doar Agency

| Funcție | Descriere | Scope |
|---|---|---|
| Creare client / sub-account | Creează și configurează conturi client noi în cadrul agency-ului. | `agency` |
| Billing global | Administrează planuri, facturare consolidată și metode de plată la nivel de agency. | `agency` |
| Template library | Gestionează biblioteci de template-uri reutilizabile între clienți. | `agency` |
| Benchmark cross-client | Compară performanța între mai mulți clienți (agregat, anonimizat unde e cazul). | `agency` |
| User management agency | Invită/gestionează utilizatori și roluri la nivel de agency. | `agency` |
| Snapshots | Creează snapshot-uri executive multi-client pentru leadership/reporting intern agency. | `agency` |

## 2) Funcții doar Sub-account

| Funcție | Descriere | Scope |
|---|---|---|
| Campanii | Creează, configurează și operează campanii pentru un client specific. | `subaccount` |
| Assets active | Gestionează asset-urile active ale clientului (creative, audiențe, feed-uri). | `subaccount` |
| Integrare canale media | Conectează și operează integrări media (Meta, Google, etc.) per client. | `subaccount` |
| AI optimizări | Rulează recomandări/optimizări AI contextualizate pe datele clientului. | `subaccount` |
| Rapoarte client | Vizualizează și exportă rapoarte dedicate unui singur client/sub-account. | `subaccount` |

## 3) Reguli de acces (RBAC)

### Roluri minime

| Rol | Nivel implicit | Responsabilitate principală |
|---|---|---|
| `agency_owner` | Agency | Control complet asupra agency-ului, billing și guvernanță. |
| `agency_admin` | Agency | Administrare operațională agency, fără ownership financiar total (după politica internă). |
| `account_manager` | Sub-account | Operare campanii și activități zilnice pe unul sau mai multe conturi client asignate. |
| `client_viewer` | Sub-account | Acces read-only la datele și rapoartele clientului asignat. |

### Reguli generale

1. Un utilizator cu rol agency NU primește implicit acces la datele detaliate ale tuturor sub-account-urilor fără alocare explicită (principiul least privilege).
2. Rolurile de sub-account nu pot modifica setări globale de agency (billing, user management global, benchmark cross-client).
3. `client_viewer` este strict read-only (fără acțiuni de editare/publicare/sync).
4. Operațiile sensibile (billing, user management, exporturi globale, snapshots cross-client) trebuie auditate.

## 4) Mapare pagini -> scope și roluri permise

| Pagină | Scope | Roluri permise |
|---|---|---|
| `/` | `agency` | `agency_owner`, `agency_admin` |
| `/dashboard` | `subaccount` | `agency_owner`, `agency_admin`, `account_manager`, `client_viewer` |
| `/clients` | `agency` | `agency_owner`, `agency_admin` |
| `/creative` | `subaccount` | `agency_owner`, `agency_admin`, `account_manager` |
| `/notifications` | `subaccount` | `agency_owner`, `agency_admin`, `account_manager`, `client_viewer` |
| `/login` | `agency` | Public (neautentificat) |

> Notă: în implementare, accesul efectiv pe paginile de `subaccount` trebuie filtrat suplimentar pe lista de conturi client la care utilizatorul este asignat.
