# Rapport d'intégration — Core frontend (Vague 0)

**Date :** 15 Juin 2026  
**Statut :** ✅ VALIDÉ (gate Vague 0)

## Périmètre

Socle Angular partagé : layout, intercepteurs HTTP, composants UI réutilisables, routes authentifiées unifiées.

## Vérifications

| Point | Backend | Frontend | Statut |
|-------|---------|----------|--------|
| Enveloppe `ApiResponse[T]` | `app/schemas/common.py` | `shared/models/api.models.ts` + unwrap services | ✅ |
| Pagination | `page`, `page_size` | `PaginatedResponse.page_size` | ✅ |
| Auth JWT | `POST /auth/login`, `GET /auth/me` | `AuthService` + `authInterceptor` | ✅ |
| 401 non authentifié | HTTP 401 | `errorInterceptor` → `/login` | ✅ |
| 403 interdit | HTTP 403 | `errorInterceptor` → `/acces-refuse` | ✅ |
| RoleGuard UI | permissions RBAC seed | `roleGuard` → `/acces-refuse` | ✅ |
| Layout shell | — | `MainLayoutComponent` (sidebar + topbar) | ✅ |
| Routes sous layout | — | `/`, interruptions, `/referentiel`, `/geo`, `/acces-refuse` | ✅ |

## Composants partagés livrés

- `shared/ui/page-header` — titre + fil d'Ariane + slot actions
- `shared/ui/status-chip` — badge statut interruption
- `shared/ui/paginator` — pagination custom
- `shared/utils/statut.utils.ts` — labels FR statuts
- `styles/_sir-ui.scss` — classes `.sir-btn*`
- `styles/_sir-tokens.scss` — tokens couleur (primaire logo `#3d49a0`)

## RBAC guards (extrait)

| Route | Rôles UI |
|-------|----------|
| `/interruptions/distribution` | BCC, BRC, ADMIN_SCR, ADMIN_SAQS, SUPERVISEUR |
| `/interruptions/distribution/nouveau` | BCC, ADMIN_SCR |
| `/`, `/referentiel`, `/geo` | authGuard uniquement |

## Points d'attention (non bloquants)

- `referentiel` / `geo` : UI Material legacy — refonte prévue Vague 5
- NgRx store global : non implémenté (signals + services suffisants pour l'instant)
- Export Excel liste : pas d'endpoint backend

## Prochaine vague

**Vague 1** — Refonte UI formulaire + détail distribution selon maquettes + `PUT` édition.
