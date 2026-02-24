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

## 8) Decizii de start confirmate + blocaje rămase
Decizii confirmate:

1. Backend: **FastAPI**.
2. Cloud: **GCP**.
3. Structură repo: **monorepo**.
4. Branding v1: **default propus** (nu blochează execuția).
5. Billing v1: **fără billing**.
6. Milestone-uri: **Alpha 4 săpt / Beta intern 6 săpt / Pilot 8 săpt** (la 1–2 dev full-time).

Mai sunt necesare pentru start fără blocaje:

7. Environment matrix + ownership secrete (local/staging/prod).
8. Acces integrare test:
   - Google Ads test token + conturi,
   - Meta app dev + test users,
   - OpenAI key cu limită,
   - BigQuery project/sandbox.
9. Politici operaționale finale:
   - owner aprobare PR AI,
   - SLA alertare,
   - severitate incidente.

Referință: `DECISIONS_LOCKED_RO.md`.

## 9) Plan de execuție propus
- Faza 0: setup repo + CI/CD + schelet modular + observabilitate.
- Faza 1: auth, RBAC, clienți, audit log.
- Faza 2: conector Google Ads + sync + dashboard de bază.
- Faza 3: conector Meta + dashboard cross-platform.
- Faza 4: rules engine + notificări.
- Faza 5: AI Assistant + AI Insights.
- Faza 6: export BigQuery/Looker + hardening + UAT.

## 10) Definiție de "ready to build"
Se poate începe implementarea imediat după confirmarea celor 3 blocaje rămase din secțiunea 8 (owner PR AI, ownership secrete, accesuri tehnice de test), cu testare continuă, optimizări iterative și pipeline AI self-improvement controlat.
