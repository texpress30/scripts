# Brief de implementare — MCC Multi-Platform cu AI (v1)

## 1) Rezumat executiv
Construim o aplicație web desktop-first pentru agenții de marketing digital, care unifică gestionarea campaniilor Google Ads + Meta Ads într-un model MCC pe clienți și adaugă un strat AI pentru recomandări, insight-uri, reguli automate și raportare unificată.

## 2) Scope v1 (aprobat)
- Structură MCC pe client și conturi conectate.
- OAuth + integrare read/write pentru Google Ads și Meta Ads.
- Dashboard unificat (spend, ROAS, conversii, cross-platform).
- Rules engine:
  - stop-loss automat,
  - auto-scaling pe praguri.
- Anomaly detection (CPC spike, CVR drop, tracking down).
- AI Campaign Assistant (structură campanie, copy, audiențe).
- AI Insights (sumar + recomandări automate).
- Raportare internă + export Looker Studio via BigQuery.
- Notificări email/in-app.
- RBAC: Super Admin, Agency Admin, Account Manager, Client Viewer.
- Audit trail complet pentru acțiuni umane + AI.
- Arhitectură modulară.

## 3) Out of scope v1
- TikTok/Pinterest/Snapchat.
- Generare creativă AI (video/imagine) + Canva.
- Editor intern de creative.
- Modele ML proprii avansate.
- Tracking propriu/click-router.
- Mobile app nativă.
- AI autonom total fără supervizare.

## 4) Arhitectură recomandată
- Frontend: Next.js + TypeScript + Tailwind.
- Backend: FastAPI (Python).
- DB: PostgreSQL.
- Cache/queues: Redis.
- Jobs: Celery + Redis.
- DWH: BigQuery.
- AI: OpenAI API.
- ETL: conectori custom (v1), Airbyte opțional ulterior.

## 5) Securitate și guvernanță
- JWT + refresh tokens, OAuth login, 2FA opțional admin.
- Encrypted at rest + in transit.
- GDPR + retention policy configurabil.
- Branch protection + PR mandatory.
- AI cu limite clare de autonomie (fără deploy prod autonom, fără modificări sensibile fără aprobare).

## 6) Criterii de acceptare
- Coverage > 80% (unit + integration).
- P95 API < 500ms.
- Error rate < 0.5%.
- Lighthouse > 90.
- Audit log activ pe operații critice.
- Scenarii critice E2E acoperite (onboarding, rules, token refresh, degradare externă, concurență).

## 7) Framework de auto-îmbunătățire AI (safe)
Buclă:
1. observă metrici,
2. propune patch,
3. rulează teste + benchmark,
4. deschide PR explicativ,
5. merge doar cu aprobare umană.

Guardrails:
- code owners pe directoare sensibile,
- staging + canary,
- rollback automat,
- feature flags.

## 8) Ce mai trebuie de la stakeholder pentru start efectiv de cod
Deși specificația este foarte solidă, pentru a începe implementarea fără blocaje mai sunt necesare:

1. Decizia finală unică pentru backend: **FastAPI** confirmat oficial.
2. Confirmare infrastructură: **GCP vs AWS** (implicit recomandat GCP).
3. Repo target + convenții:
   - mono-repo sau multi-repo,
   - naming standard,
   - branch strategy.
4. Identitate vizuală minimă:
   - logo,
   - paletă,
   - font,
   - dark mode: da/nu în v1.
5. Environment matrix:
   - local,
   - staging,
   - production,
   - cine administrează secretele.
6. Acces integrare test:
   - Google Ads test token + conturi,
   - Meta app dev + test users,
   - OpenAI key cu limită,
   - BigQuery project/sandbox.
7. Politici operaționale:
   - SLA alertare,
   - severitate incidente,
   - proces aprobare PR AI.
8. Billing model v1:
   - fără billing,
   - sau Stripe minim.
9. Deadline de milestone-uri:
   - MVP technical alpha,
   - beta intern,
   - pilot client.

## 9) Plan de execuție propus
- Faza 0: setup repo + CI/CD + schelet modular + observabilitate.
- Faza 1: auth, RBAC, clienți, audit log.
- Faza 2: conector Google Ads + sync + dashboard de bază.
- Faza 3: conector Meta + dashboard cross-platform.
- Faza 4: rules engine + notificări.
- Faza 5: AI Assistant + AI Insights.
- Faza 6: export BigQuery/Looker + hardening + UAT.

## 10) Definiție de "ready to build"
Când punctele din secțiunea 8 sunt confirmate, se poate începe implementarea de la zero, cu testare continuă, optimizări iterative și pipeline AI self-improvement controlat.
