# Rapport d'intégration — Indicateurs F5 (Vague 4)

**Date :** Juin 2026  
**Statut :** ✅ Frontend aligné backend

## Contrats API

| Endpoint | Service Angular | Page |
|----------|-----------------|------|
| `GET /indicateurs/tableau-de-bord` | `IndicateursService.getTableauDeBord` | Dashboard, `/indicateurs` |
| `GET /indicateurs/historique` | `getHistorique` | Dashboard, `/indicateurs` |
| `GET /indicateurs/top-feeders` | `getTopFeeders` | `/indicateurs` |
| `GET /indicateurs/end` | `getEnd` | service prêt |
| `GET /indicateurs/saifi` | `getSaifi` | service prêt |
| `GET /indicateurs/saidi` | `getSaidi` | service prêt |

Paramètre `periode` : format `YYYY-MM` (tableau-de-bord, top-feeders).

## RBAC

Route `/indicateurs` : BCC, BRC, ADMIN_SCR, ADMIN_SAQS, SUPERVISEUR (`indicateurs:read`).

## Limitation documentée (F2)

**Répartition par cause (donut dashboard)** : pas d'endpoint backend — données illustratives conservées avec mention explicite dans l'UI.

## Tests manuels

1. Login `admin.saqs` → `/indicateurs` → KPI + top feeders
2. Changer période et région → rechargement API
3. Dashboard → sélecteur période → KPI mis à jour
