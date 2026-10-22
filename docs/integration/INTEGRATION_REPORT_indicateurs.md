# Rapport d'intégration — Indicateurs (Sprint 5 · F5)

**Date :** Juin 2026  
**Référence métier :** [docs/indicateurs_sirv2.md](../indicateurs_sirv2.md)  
**Statut :** ✅ Backend Sprint 5 · ✅ Hub frontend aligné (KPI + répartitions + historique END + top feeders)

---

## Vue d'ensemble

Le module indicateurs expose des **GET synchrones** agrégés par scope géographique (service → délégation → région → national). Les calculs lourds (END à la clôture, SAIFI/SAIDI à la validation) passent par **Celery** ; les endpoints lisent les tables persistées (`energie_nd`, `interruptions_distribution.end_mwh`, `saifi_saidi`) avec cache Redis cache-aside (TTL 1 h).

**Prérequis runtime :** worker Celery actif pour recalcul après clôture/validation ; Redis ; seed `nombre_client_mois` pour SAIFI/SAIDI (`make seed-dev`).

---

## Contrats API vérifiés

| Endpoint | Service Angular | Page / usage |
|----------|-----------------|--------------|
| `GET /api/v1/indicateurs/tableau-de-bord` | `IndicateursService.getTableauDeBord` | `/indicateurs` — KPI + répartitions |
| `GET /api/v1/indicateurs/historique` | `getHistorique` | `/indicateurs` — graphique END (24 mois max) |
| `GET /api/v1/indicateurs/top-feeders` | `getTopFeeders` | `/indicateurs` |
| `GET /api/v1/indicateurs/end` | `getEnd` | service prêt — pas d'écran dédié |
| `GET /api/v1/indicateurs/saifi` | `getSaifi` | service prêt — pas d'écran dédié |
| `GET /api/v1/indicateurs/saidi` | `getSaidi` | service prêt — pas d'écran dédié |

**Paramètres communs :** `periode` (`YYYY-MM`), ou `annee` + `mois`, `region_id` optionnel (filtrage scope).

**Enveloppe JSON :**

```json
{"status": "success", "data": { ... }, "error": null}
```

---

## Schémas Pydantic ↔ TypeScript

### `TableauDeBordResponse`

| Champ API | Type TS | Affiché hub |
|-----------|---------|-------------|
| `end_mois` | `number` | KPI END (MWh) |
| `saifi` | `number` | KPI SAIFI |
| `saidi` | `number` | KPI SAIDI (min) |
| `nb_interruptions_actives` | `number` | KPI interruptions actives |
| `nb_interruptions_mois` | `number` | Sous-texte KPI |
| `causes_repartition[]` | `CauseRepartitionItem[]` | Donut causes |
| `natures_repartition[]` | `NatureRepartitionItem[]` | Tableau natures FIS |

```typescript
export interface CauseRepartitionItem {
  label: string;
  nombre: number;
  percent: number;
}

export interface NatureRepartitionItem {
  code: string;
  libelle: string;
  nombre: number;
  end_kwh: number;
  percent: number;
}
```

Fichier : `sir-frontend/src/app/shared/models/indicateurs.models.ts`

---

## Workflow → indicateurs

| Événement | Worker | Invalidation cache |
|-----------|--------|-------------------|
| Clôture interruption | `calcul_end` | END (après calcul) |
| Validation interruption | `calcul_saifi_saidi` | Sync + SAIFI/SAIDI/TB |

Clés Redis : `indicateurs:{type}:{region_id}:{annee}:{mois}` — voir `indicateurs_cache_service.py`.

---

## RBAC

| Rôle | Route `/indicateurs` | Scope |
|------|---------------------|-------|
| BCC, BRC | ✅ `indicateurs:read` | Région (`scope_service_id` = `region_id`) |
| SUPERVISEUR | ✅ | Service unique |
| ADMIN_SCR, ADMIN_SAQS | ✅ | National (SAQS : + comptage transport au TB) |
| DISPATCHER, ADMIN_DISPATCHING | ❌ pas de permission indicateurs | Transport / rapports uniquement |

Route Angular : guard `RoleGuard` + permission backend `require_permission("indicateurs", "read")`.

---

## Seed dev (Docker)

| Seed | Rôle |
|------|------|
| `seed_natures` | Codes FIS : PERMANENT, SEMI_PERM, FUGITIF, DELESTAGE, COUPURE |
| `seed_interruptions` | 3 interruptions avec causes/natures distinctes (répartitions testables) |
| `seed_indicateurs` | `nombre_client_mois`, `energie_nd`, `saifi_saidi` de démo |

Compte test : `saqs.dev` / `bcc.dev` — mot de passe `DevSir123!`

---

## Écarts connus / hors scope

| Sujet | Statut |
|-------|--------|
| END transport HTB | Rapports uniquement — pas d'endpoint `/indicateurs` |
| Historique SAIFI/SAIDI dans le hub | Non affiché (API prête via `getHistorique`) |
| Pages détaillées `/indicateurs/end\|saifi\|saidi` | Non implémentées |
| Coefficients END CRSE | Bloqué validation SENELEC |
| Exclusions SAIFI/SAIDI (délestages, travaux) | Bloqué validation SENELEC |

---

## Tests manuels

1. `make seed-dev` → login `saqs.dev` → `/indicateurs`
2. Vérifier KPI END / SAIFI / SAIDI pour période `06/2026`
3. Vérifier donut **causes** (top 5) et tableau **natures FIS** alimentés par l'API
4. Changer région (Dakar / Thiès) et période → rechargement `forkJoin`
5. Clôturer puis valider une interruption → worker → indicateurs mis à jour (après invalidation cache)

## Tests automatisés backend

- `tests/integration/test_indicateurs_tableau_de_bord.py`
- `tests/integration/test_indicateurs_*.py` (end, saifi, saidi, historique, top-feeders)
- `tests/unit/test_end_service.py`, `test_indicateurs_cache_service.py`

---

## Fichiers clés

| Couche | Fichier |
|--------|---------|
| API | `sir-backend/app/api/v1/indicateurs/router.py` |
| Service | `sir-backend/app/services/indicateurs_service.py` |
| Frontend hub | `sir-frontend/src/app/features/indicateurs/indicateurs-hub/` |
| Modèles TS | `sir-frontend/src/app/shared/models/indicateurs.models.ts` |
| Doc métier | `docs/indicateurs_sirv2.md` |
