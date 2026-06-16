# Rapport d'intégration — Référentiels (Sprint 2 · Phase 2.1)

**Date :** Juin 2026  
**Statut :** ✅ CRUD frontend Vague 5 · Aligné backend

## Contrats API vérifiés

| Endpoint | Backend (Pydantic) | Frontend TS | Statut |
|----------|-------------------|-------------|--------|
| `GET /referentiel/{ressource}` | `PaginatedResponse[ReferentielResponse]` | `ReferentielService.list()` | ✅ |
| `POST /referentiel/{ressource}` | `ReferentielCreate` | `ReferentielService.create()` | ✅ |
| `PUT /referentiel/{ressource}/{id}` | `ReferentielUpdate` | `ReferentielService.update()` | ✅ |
| `DELETE /referentiel/{ressource}/{id}` | soft delete | `ReferentielService.delete()` | ✅ |
| Enveloppe | `ApiResponse[T]` | `ApiResponse<T>` | ✅ |

## RBAC

- Lecture : tous rôles authentifiés (route guard élargi en admin)
- Écriture UI : `ADMIN_SCR`, `ADMIN_DISPATCHING` via `canWrite()` — aligné backend `require_role`

## Routes frontend

| Route | Notes |
|-------|-------|
| `/admin/referentiel` | Liste + CRUD, 5 onglets (causes, sièges, signalisations, natures, types_end) |
| `/referentiel` | redirect → `/admin/referentiel` |

## Points d'attention

- Cache Redis côté backend transparent pour le frontend
- `type_reseau` : union `distribution | transport | commun` — filtre sur causes/sièges/signalisations uniquement
