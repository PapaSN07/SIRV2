# Rapport d'intégration — Interruptions Transport F4 (Vague 3)

**Date :** Juin 2026  
**Statut :** ✅ Aligné backend · Module Angular F4 implémenté

## Contrats API vérifiés

| Endpoint | Backend (Pydantic) | Frontend TS | Statut |
|----------|-------------------|-------------|--------|
| `GET /interruptions/transport` | `PaginatedResponse[InterruptionTransportResponse]` | `InterruptionTransportListParams` | ✅ |
| `GET /interruptions/transport/{id}` | `InterruptionTransportDetailResponse` | `InterruptionTransportDetail` | ✅ |
| `POST /interruptions/transport` | `InterruptionTransportCreate` | `InterruptionTransportCreate` | ✅ |
| `PUT /interruptions/transport/{id}` | `InterruptionTransportUpdate` | `InterruptionTransportUpdate` | ✅ |
| `PATCH …/{id}/cloturer` | `InterruptionClotureRequest` | réutilisé depuis distribution | ✅ |
| `PATCH …/{id}/valider` | body vide | `{}` | ✅ |
| `GET /reseau/transport/equipements-transport` | `EquipementTransportResponse` | `ReseauTransportService` | ✅ |
| `GET /reseau/transport/sources-transport` | `SourceTransportResponse` | idem | ✅ |
| `GET /reseau/transport/postes-lignes` | `PosteLigneResponse` | idem | ✅ |

## RBAC frontend

| Action | Rôles UI | Backend |
|--------|----------|---------|
| Liste / détail | DISPATCHER, ADMIN_DISPATCHING, ADMIN_SAQS | `read` |
| Création / modification / clôture | DISPATCHER, ADMIN_DISPATCHING | `create` / `update` |
| Validation | ADMIN_DISPATCHING, ADMIN_SAQS | `validate` |

## Routes Angular (lazy)

- `/interruptions/transport` — liste HTB / OMVG
- `/interruptions/transport/nouveau` — création
- `/interruptions/transport/:id/modifier` — édition (en cours)
- `/interruptions/transport/:id` — détail, clôture, validation
- Onglets `sir-interruptions-nav` : Distribution | Transport

## Champs spécifiques transport

- `type_direction` : `transport` | `omvg`
- `equipement_transport_id`, `source_transport_id`, `poste_ligne_id` (création)
- `tension_kv`, `puissance_transit_mw`, `puissance_coupee_mw`
- `energie_non_fournie_mwh` / `energie_nd` au détail

## Tests manuels recommandés

1. Login dispatcher (seed) → créer interruption transport → clôturer
2. Login ADMIN_DISPATCHING → valider interruption clôturée
3. Login BCC → onglet Transport → `/acces-refuse` si rôle absent
4. Filtre `type_direction=omvg` sur la liste
