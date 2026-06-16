# Rapport d'intégration — Administration (Vague 5 · F9)

**Date :** Juin 2026  
**Statut :** ✅ Frontend admin utilisateurs + navigation activée

## Routes frontend

| Route | Composant | RBAC route guard |
|-------|-----------|------------------|
| `/admin/utilisateurs` | `UtilisateursListComponent` | `ADMIN_SCR`, `ADMIN_DISPATCHING` |
| `/utilisateurs` | redirect → `/admin/utilisateurs` | — |

## Contrats API

| Endpoint | Frontend | Statut |
|----------|----------|--------|
| `GET /admin/utilisateurs` | `AdminUtilisateurService.list()` | ✅ |
| `POST /admin/utilisateurs` | `AdminUtilisateurService.create()` | ✅ |
| `PUT /admin/utilisateurs/{id}` | `AdminUtilisateurService.update()` | ✅ |
| `PATCH .../activer` | `AdminUtilisateurService.activer()` | ✅ |
| `PATCH .../desactiver` | `AdminUtilisateurService.desactiver()` | ✅ |
| `POST .../reset-password` | `AdminUtilisateurService.resetPassword()` | ✅ |

## UI

- Navigation latérale : **Administration** → `/admin/referentiel`, **Utilisateurs** → `/admin/utilisateurs`
- Onglets internes : `sir-admin-nav` (Référentiels | Réseau dist. | Réseau transp. | Utilisateurs)
- Formulaire inline création/édition (pas de modal Material — pattern panel SIR)
- Écriture conditionnée par `AuthService.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING')`

## Points d'attention

- **Sélection des rôles** : pas d'endpoint `GET /roles` — dropdown alimenté par `SEED_ROLE_OPTIONS` (IDs alignés seed RBAC). À remplacer par API dédiée en production.
- **Rôle unique** en création/édition (premier rôle) — suffisant pour MVP ; multi-rôles à prévoir si besoin métier.
- Périmètre `scope_service_id` non exposé dans l'UI (optionnel backend).
