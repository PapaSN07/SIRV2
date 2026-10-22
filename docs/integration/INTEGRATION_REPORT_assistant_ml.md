# Rapport d'intégration — Assistant ML

## Contrat backend ↔ frontend

| Endpoint | Schéma TS | UI |
|---|---|---|
| `GET /assistant/risk` | `RiskListResponse` | Hub + panneau |
| `GET /assistant/datamart` | `DatamartSummary` | Hub |
| `POST /assistant/chat` | `AssistantChatResponse` | Panneau |
| `POST /assistant/scoring/run` | `ScoringJobResponse` | Hub (admins) |

## RBAC

- `assistant:read` : BCC, BRC, ADMIN_SCR, ADMIN_SAQS, SUPERVISEUR
- `assistant:admin` : ADMIN_SCR, ADMIN_SAQS (+ SUPERADMIN)

Scope : service (BCC/SUPERVISEUR), région→services (BRC), national (SCR/SAQS).

## Non-régression

- Aucun blocage clôture / validation
- Pas d’appel LLM externe en P0
