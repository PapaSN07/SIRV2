# Rapport d'intégration — Workflow validation (Sprint · Vague 2)

**Date :** Juin 2026  
**Statut :** ✅ Aligné backend · Page `/workflow/validation` implémentée

## Contrats API vérifiés

| Endpoint | Backend | Frontend | Statut |
|----------|---------|----------|--------|
| `GET /interruptions/distribution?statut=cloture` | Liste paginée filtrée | `InterruptionDistributionService.list()` | ✅ |
| `GET /interruptions/distribution/{id}` | Détail enrichi | Panneau latéral `get()` | ✅ |
| `PATCH /interruptions/distribution/{id}/valider` | Validation hiérarchique | `valider()` unitaire + séquentiel bulk | ✅ |
| Enveloppe | `ApiResponse[T]` | unwrap service | ✅ |
| Pagination | `page`, `page_size` | `sir-paginator` | ✅ |

## RBAC frontend

| Action | Rôles UI (`RoleGuard`) | Backend |
|--------|------------------------|---------|
| Accès page workflow | SUPERVISEUR, ADMIN_SCR, ADMIN_SAQS | permission `validate` |
| Valider (unitaire / sélection) | idem (page protégée) | `PATCH …/valider` |
| Voir détail complet | lien vers route distribution (lecture selon rôle) | `read` |

## Route Angular

- `/workflow/validation` — file d'attente (lazy, sous `MainLayoutComponent`)
- Sidebar « Workflow » activée → même route

## Comportement UI

- Filtres : région, période (API), recherche locale (n° / localisation)
- Liste : interruptions `statut=cloture`, priorité dérivée affichage (`puissance_coupee_mw`)
- Panneau détail à droite (maquette _2) : résumé + lien détail complet + bouton Valider
- Sélection multiple : barre flottante « Valider la sélection » — appels API **séquentiels** (pas de batch backend)
- Domaine HT/MT/BT : affichage depuis `tension_kv` (indicatif, non filtrable API)

## Points d'attention

- Pas d'endpoint « rejeter » ou « demander modification » — boutons maquette non implémentés (hors scope backend)
- Comptes dev : `superviseur.dev` / `DevSir123!` pour tests validation

## Tests manuels recommandés

1. Login `superviseur.dev` → `/workflow/validation` → liste clôturées
2. Sélectionner une ligne → panneau détail → Valider → disparaît de la file
3. Sélection multiple → Valider la sélection → compteur mis à jour
4. Login `bcc.dev` → accès `/workflow/validation` → redirection `/acces-refuse`
