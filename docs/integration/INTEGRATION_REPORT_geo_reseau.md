# Rapport d'intégration — Géo & Réseau (Sprint 2 · Phases 2.2–2.4)

**Date :** Juin 2026  
**Statut :** ✅ Backend validé · Frontend geo + admin réseau Vague 5

## Géo (lecture seule)

| Endpoint | Response | Statut |
|----------|----------|--------|
| `GET /geo/regions` | `ApiResponse<RegionResponse[]>` | ✅ |
| `GET /geo/delegations?region_id=` | `ApiResponse<DelegationResponse[]>` | ✅ |
| `GET /geo/agences?delegation_id=` | `ApiResponse<AgenceResponse[]>` | ✅ |
| `GET /geo/services?agence_id=` | `ApiResponse<ServiceResponse[]>` | ✅ |

## Réseau distribution

| Ressource | Prefix | RBAC lecture | RBAC écriture |
|-----------|--------|--------------|---------------|
| postes-sources, feeders, postes, troncons, sous-feeders | `/reseau/` | BCC, BRC, Admin SCR, Admin SAQS | Admin SCR |

## Réseau transport

| Ressource | Prefix | RBAC lecture | RBAC écriture |
|-----------|--------|--------------|---------------|
| equipements-transport, sources-transport, postes-lignes | `/reseau/transport/` | Dispatcher, Admin Dispatching, Admin SAQS | Admin Dispatching |

## Pagination

- Backend : `page_size` — Frontend `api.models.ts` aligné sur `page_size` ✅

## Seeds dev

- `make seed-dev` : RBAC + geo + réseau distribution minimal

## Admin réseau frontend (Vague 5)

| Route | Composant | CRUD |
|-------|-----------|------|
| `/admin/reseau/distribution` | `ReseauDistributionAdminComponent` | feeders, postes |
| `/admin/reseau/transport` | `ReseauTransportAdminComponent` | equipements-transport, sources-transport |

Services : `ReseauAdminDistributionService`, `ReseauAdminTransportService` — écriture UI réservée `ADMIN_SCR` (dist.) et `ADMIN_DISPATCHING` (transp.).

Non couvert en V5 (reporté) : tronçons, sous-feeders, postes-lignes — endpoints backend disponibles.
