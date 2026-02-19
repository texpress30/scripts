# Decizii confirmate (locked) — Kickoff

Acest document blochează deciziile de start pentru a elimina ambiguitățile și a începe execuția imediat.

## Decizii aprobate

| Punct | Decizie | Motivație |
|---|---|---|
| Backend | **FastAPI** | Cel mai potrivit pentru AI + data processing + ads APIs |
| Cloud | **GCP** | BigQuery nativ, Looker Studio, Cloud Run simplu |
| Repo | **Monorepo** | Setup mai simplu la început: un singur CI, shared types, viteză de livrare |
| Branding | **Default propus** | Nu blocăm dezvoltarea pentru identitate vizuală finală |
| Billing v1 | **Fără billing** | Focus pe produs; billing planificat după stabilizarea MVP |

## Deadline-uri asumate

- **Alpha:** 4 săptămâni
- **Beta intern:** 6 săptămâni
- **Pilot client:** 8 săptămâni

> Presupunere de capacitate: 1–2 developeri full-time.

## Implicații de plan

- Toate task-urile din sprinturi se calibrează la această capacitate.
- Scope creep intră pe backlog, nu în milestone-urile alpha/beta.
- Integrările non-v1 (TikTok/Pinterest/Snapchat, creative AI avansat) rămân în faze ulterioare.
