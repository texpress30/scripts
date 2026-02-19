# Runbook incidente P1/P2 + Escalation (RO)

## 1) Clasificare severitate

### P1 (critic)
Definiție:
- login indisponibil,
- backend indisponibil (`/health` fail),
- pierdere majoră de funcționalitate (sync/export blocate global).

SLA țintă:
- Ack: 5 minute
- Mitigare: 30 minute
- RCA preliminar: 4 ore

### P2 (major)
Definiție:
- funcționalitate degradată pentru subset de clienți,
- erori intermitente care nu blochează complet login-ul.

SLA țintă:
- Ack: 15 minute
- Mitigare: 2 ore
- RCA preliminar: 1 zi

---

## 2) Flux de răspuns incident
1. Detectare (alertă monitorizare / raport user).
2. Confirmare incident + clasificare P1/P2.
3. Deschidere canal incident (`#incident-<id>` / war-room).
4. Stabilizare:
   - rollback dacă există release recent suspect,
   - feature flag OFF pentru funcționalități non-critice,
   - restart controlat doar dacă există semnal clar.
5. Comunicare:
   - update intern la fiecare 15 min (P1), 30 min (P2),
   - update stakeholderi pilot.
6. Închidere:
   - confirmare recovery,
   - postmortem + acțiuni preventive.

---

## 3) Escalation tree (completează)
- Incident Commander (IC):
- Tech Lead Backend:
- Tech Lead Frontend:
- DevOps/Platform:
- Product Owner:
- Backup IC:

Regulă:
- dacă P1 nu e mitigat în 30 min, escalare automată la Backup IC + Product Owner.

---

## 4) Playbook rapid pe scenarii

### 4.1 Login indisponibil / 502
- Verifică:
  - `GET /health` pe backend,
  - deploy logs Railway,
  - variabile env critice (`APP_AUTH_SECRET`, CORS, DB/Redis URL).
- Acțiuni:
  - rollback la ultimul deploy stabil,
  - corectare env + redeploy,
  - validare login din UI și API.

### 4.2 Eroare conectori Google/Meta
- Verifică token validity/rate limit.
- Dezactivează temporar job-urile sync pentru client afectat.
- Menține dashboard cu ultimul snapshot disponibil.

### 4.3 Export BigQuery eșuat
- Verifică `BIGQUERY_PROJECT_ID` + autentificare.
- Rulează re-try manual controlat.
- Marchează run-ul ca failed cu motiv explicit.

---

## 5) Checklist închidere incident
- [ ] Serviciu stabil >= 30 min (P1) / 2h (P2)
- [ ] Stakeholder update trimis
- [ ] Ticket postmortem creat
- [ ] Acțiuni preventive planificate cu owner + ETA

