# Indicateurs SIRV2 — Définitions et calculs

> Référence technique pour l'équipe SENELEC/SMDT.  
> Toutes les formules marquées **TODO(CRSE)** doivent être confirmées par l'équipe SAQS avant mise en production.

---

## État d'implémentation SIRV2

| Composant | Statut | Fichiers / routes |
|---|---|---|
| Calcul END (worker) | Implémenté | `sir-backend/app/services/end_service.py`, tâche `calcul_end` |
| Calcul SAIFI/SAIDI (worker) | Implémenté | `sir-backend/app/services/saifi_saidi_service.py`, tâche `calcul_saifi_saidi` |
| API `/api/v1/indicateurs/*` | Implémenté (Sprint 5) | `sir-backend/app/api/v1/indicateurs/router.py` |
| Cache Redis | Implémenté | `sir-backend/app/services/indicateurs_cache_service.py` |
| END transport HTB | Rapports uniquement | `rapport_transport_repository.py` — **pas** d'endpoint `/indicateurs` |
| Frontend hub | Partiel | `sir-frontend/.../indicateurs/indicateurs-hub/` — KPI, historique END, top feeders, répartitions |
| Import FIS | Implémenté | `sir-backend/app/services/fis_import_service.py` |
| Coefficients CRSE | Bloqué | Validation SENELEC requise (voir fin de document) |

---

## 1. END — Énergie Non Distribuée

### Définition

L'END mesure l'énergie électrique qui aurait dû être fournie aux clients mais ne l'a pas été du fait d'une interruption réseau.

### Formule de base (vérifiée sur données FIS réelles)

```
END (MWh) = Puissance_Coupée (MW) × Durée (heures) × Coefficient
```

Équivalent en unités FIS (avant conversion) :
```
END (kWh) = Puissance_Coupée (kW) × Durée (minutes) / 60
```

### Paramètres

| Paramètre | Source dans la BDD | Table | Colonne |
|---|---|---|---|
| Puissance coupée (MW) | Interruption principale | `interruptions` | `puissance_coupee_mw` |
| Puissance (fallback transport) | Interruption transport | `interruptions_transport` | `puissance_transit_mw` |
| Puissance (fallback postes) | Somme postes impactés | `postes` | `puissance_kva / 1000` |
| Durée (heures) | Calculé à la clôture | `interruptions` | `duree_minutes / 60` |
| Coefficient | Règle par nature | service `end_service.py` | voir `REGLES_END_PAR_NATURE` |

### Résolution de la puissance (priorité)

1. `interruptions.puissance_coupee_mw` si renseigné
2. `interruptions_transport.puissance_transit_mw` si interruption transport
3. Somme des `postes.puissance_kva / 1000` des postes impactés (table `poste_interruptions`)
4. 0 si aucune source disponible

### Coefficients par nature (provisoires — TODO CRSE)

Ces codes servent à la **pondération END** (`REGLES_END_PAR_NATURE` dans `end_service.py`). Ils sont distincts des codes **FIS** utilisés pour l'affichage du tableau de bord (voir §4). Le code `DELESTAGE` est partagé entre les deux nomenclatures.

| Code Nature (pondération) | Type END | Coefficient |
|---|---|---|
| INCIDENT | END_IMPUTABLE | 1.0 |
| DELESTAGE | END_PROGRAMME | 1.0 |
| MAINTENANCE | END_PROGRAMME | 1.0 |
| Codes FIS (PERMANENT, SEMI_PERM, …) | END_IMPUTABLE (défaut) | 1.0 |
| Autres | END_IMPUTABLE | 1.0 |

### Règles d'exclusion

- `is_force_majeure = true` → END = 0 (exclus du calcul imputable)
- Interruptions en statut `en_cours` → non comptées (seuls `cloture` et `valide`)

### Persistance

L'END est calculé et persisté à deux endroits pour des raisons de performance :

| Table | Colonne | Usage |
|---|---|---|
| `energie_nd` | `valeur_mwh` | Résultat détaillé avec type END, audit, date de calcul |
| `interruptions_distribution` | `end_mwh` | Miroir pour les requêtes agrégées rapides |

Pour les imports FIS : `end_mwh` est pris directement du fichier Excel (valeur déjà calculée et vérifiée).

### Agrégation mensuelle (requête BDD)

```sql
SELECT
    i.service_id,
    COALESCE(SUM(id.end_mwh), 0) AS end_mwh,
    COUNT(i.id) AS nb_interruptions
FROM interruptions i
JOIN interruptions_distribution id ON id.interruption_id = i.id
WHERE
    i.service_id IN (:service_ids)
    AND i.type_direction = 'distribution'
    AND i.statut IN ('cloture', 'valide')
    AND i.is_force_majeure = 0
    AND i.date_remise IS NOT NULL
    AND YEAR(i.date_remise) = :annee
    AND MONTH(i.date_remise) = :mois
    AND id.end_mwh IS NOT NULL
GROUP BY i.service_id
```

### Aggregation multi-niveaux

| Niveau | Méthode |
|---|---|
| Service | Somme directe `end_mwh` de ses interruptions |
| Délégation | Somme des services de la délégation |
| Région | Somme des services de la région |
| National | Somme de tous les services |

### Endpoint API

```
GET /api/v1/indicateurs/end?annee=2024&mois=5&region_id=1
```

Paramètres : `annee`, `mois`, `region_id` (optionnel), `include_services`, `page`, `page_size`

---

## 2. SAIFI et SAIDI — formule SENELEC (Power BI SIR, 28/10/2026)

Formule communiquée par SENELEC le 28/10/2026 (mesures DAX du rapport Power BI SIR) :

```dax
NombreClient = SUM('PosteInterruption'[nombreclientposteEstime])
TotalDureeInterruption = SUM(Interruptions[dureeHeure])
NbClients_DateFin_Interuption =
    VAR DateFin = MAX('Interruptions'[DateApparition])
    RETURN CALCULATE(SUM('NombreClientMois'[Nombreclient]),
        FILTER('NombreClientMois', 'NombreClientMois'[Annee] = YEAR(DateFin)
            && VALUE('NombreClientMois'[MoisNumerique]) = MONTH(DateFin)))
SAIFI = DIVIDE([NombreClient], [NbClients_DateFin_Interuption])
SAIDI = DIVIDE(SUMX('Interruptions', [NombreClient] * [TotalDureeInterruption]),
               [NbClients_DateFin_Interuption])
```

### Correspondance SIRV2

| Mesure Power BI | SIRV2 |
|---|---|
| `nombreclientposteEstime` | `poste_interruptions.nombre_clients_estime` (repli : `nombre_clients_touches`) |
| `dureeHeure` | `interruptions.duree_minutes / 60` |
| `NombreClientMois[Nombreclient]` | `nombre_client_mois.nombre_clients` (import : `scripts/migration/import_nombre_client_mois.py`) |
| Mois de `MAX(DateApparition)` | mois de la dernière apparition de la période, dans le périmètre (service, région, national) |

- **SAIDI en heures** (client-heures / clients).
- **Aucune exclusion** : la force majeure est comptée (la formule SENELEC n'en prévoit pas).
- Datation par `date_apparition`.
- Indicateurs officiels (`/indicateurs/saifi|saidi`, tableau de bord, rapports) : interruptions validées
  et archivées, table `saifi_saidi` par service et mois, recalculée à la validation et à la dévalidation.
- Pilotage (réalisé du jour / cumul) : interruptions clôturées, validées ou archivées, calcul direct.
- Sans ligne `NombreClientMois` pour le mois de référence, l'indicateur est vide (comme `DIVIDE`).

Code : `app/services/saifi_saidi_service.py`, `app/repositories/pilotage_repository.py`
(`sommer_clients`, `mois_derniere_apparition`, `clients_reference_exacte`).
Recalcul après import : `docker compose exec api python -m scripts.recalcul_saifi_saidi --depuis 2024-01`.

### Agrégation service → région → national (un mois)

`Σ(SAIFI_service × clients_service) / Σ clients_service` = `Σ NombreClient / Σ NombreClientMois`,
identique à la mesure Power BI sur un mois.

### Endpoint API

```
GET /api/v1/indicateurs/saidi?annee=2024&mois=5&region_id=1
```

---

## 4. Répartition par Nature (Tableau de Bord FIS)

### Définition

Distribution des interruptions par nature, avec END cumulé, alignée sur le format Tableau de Bord des fichiers FIS SENELEC.

> **Nomenclature FIS vs pondération END** : les codes ci-dessous sont stockés dans la table `natures` et utilisés pour l'affichage (`natures_repartition`). La pondération END (§1) utilise une table de règles séparée (`REGLES_END_PAR_NATURE`) avec des codes métier (`INCIDENT`, `MAINTENANCE`, …). Seul `DELESTAGE` est commun. Mapping import FIS : `fis_import_service.NATURE_LIBELLE_TO_CODE`.

### Codes et ordre canonique FIS

| Ordre | Code | Libellé |
|---|---|---|
| 1 | PERMANENT | Défaut permanent |
| 2 | SEMI_PERM | Défaut semi-permanent |
| 3 | FUGITIF | Défaut fugitif |
| 4 | DELESTAGE | Délestage incident HTA |
| 5 | COUPURE | Coupure travaux |
| - | AUTRE | Non catégorisé |

### Formule par nature

```
Nombre_N = COUNT(interruptions WHERE nature.code = N)
END_N (kWh) = SUM(interruptions_distribution.end_mwh WHERE nature.code = N) × 1000
Percent_N = (Nombre_N / total_interruptions) × 100
```

### Requête BDD

```sql
SELECT
    COALESCE(n.code, 'AUTRE') AS code,
    COALESCE(n.libelle, 'Non renseignee') AS libelle,
    COUNT(i.id) AS nombre,
    COALESCE(SUM(id.end_mwh), 0) AS end_mwh
FROM interruptions i
LEFT JOIN natures n ON n.id = i.nature_id
LEFT JOIN interruptions_distribution id ON id.interruption_id = i.id
WHERE
    i.type_direction = 'distribution'
    AND i.service_id IN (:service_ids)
    AND i.statut IN ('cloture', 'valide')
    AND YEAR(i.date_apparition) = :annee
    AND MONTH(i.date_apparition) = :mois
GROUP BY n.code, n.libelle
```

### Endpoint API

Inclus dans le tableau de bord :
```
GET /api/v1/indicateurs/tableau-de-bord?annee=2024&mois=5
```
Champ : `natures_repartition[]` dans la réponse.

---

## 5. Répartition par Cause

### Définition

Top 5 des causes d'interruptions les plus fréquentes sur la période.

### Requête BDD

```sql
SELECT
    COALESCE(c.libelle, 'Non renseignée') AS label,
    COUNT(i.id) AS nombre
FROM interruptions i
LEFT JOIN causes c ON c.id = i.cause_id
WHERE
    i.type_direction = 'distribution'
    AND i.service_id IN (:service_ids)
    AND YEAR(i.date_apparition) = :annee
    AND MONTH(i.date_apparition) = :mois
GROUP BY c.libelle
ORDER BY COUNT(i.id) DESC
LIMIT 5
```

### Calcul du pourcentage

```
Percent = (nombre_cause / total_interruptions_mois) × 100
```

### Endpoint API

Inclus dans le tableau de bord :
```
GET /api/v1/indicateurs/tableau-de-bord
```
Champ : `causes_repartition[]`

---

## 6. Top Feeders (END par feeder)

### Définition

Classement des feeders par END cumulé sur la période, du plus impactant au moins impactant.

### Formule

```
END_feeder (MWh) = SUM(interruptions_distribution.end_mwh)
                   pour toutes les interruptions du feeder sur la période
```

### Requête BDD

```sql
SELECT
    f.id, f.code, f.libelle, f.service_id,
    COALESCE(SUM(id.end_mwh), 0) AS end_mwh,
    COUNT(i.id) AS nb_interruptions
FROM feeders f
JOIN interruptions i ON i.feeder_id = f.id
JOIN interruptions_distribution id ON id.interruption_id = i.id
WHERE
    i.type_direction = 'distribution'
    AND i.service_id IN (:service_ids)
    AND i.statut IN ('cloture', 'valide')
    AND i.is_force_majeure = 0
    AND i.date_remise IS NOT NULL
    AND YEAR(i.date_remise) = :annee
    AND MONTH(i.date_remise) = :mois
GROUP BY f.id, f.code, f.libelle, f.service_id
ORDER BY end_mwh DESC
LIMIT :limit  -- défaut 10, max 50
```

### Endpoint API

```
GET /api/v1/indicateurs/top-feeders?annee=2024&mois=5&limit=10
GET /api/v1/indicateurs/top-feeders?annee=2024&mois=5  (via tableau de bord)
```

---

## 7. Historique (séries temporelles)

### Définition

Évolution mensuelle d'un indicateur (END, SAIFI ou SAIDI) sur N années glissantes.

### Paramètres

| Paramètre | Valeur |
|---|---|
| Types supportés | `end`, `saifi`, `saidi` |
| Fenêtre max | 3 ans (36 mois) |
| Fenêtre défaut | 1 an (12 mois) |
| Ordre | Chronologique (du plus ancien au plus récent) |

### Algorithme

```python
# Itérer N×12 mois en arrière depuis le mois courant
for (annee, mois) in mois_glissants(N_annees):
    if type == "end":
        valeur = SUM(end_mwh) pour les services du scope
    elif type == "saifi":
        valeur = SAIFI agrégé pondéré des services du scope
    elif type == "saidi":
        valeur = SAIDI agrégé pondéré des services du scope
```

### Endpoint API

```
GET /api/v1/indicateurs/historique?type=end&annees=2&region_id=1
GET /api/v1/indicateurs/historique?type=saifi&annees=1
GET /api/v1/indicateurs/historique?type=saidi&annees=3
```

---

## 8. END Transport (HTB)

### Définition

Énergie non distribuée sur le réseau transport HTB. Distinct de l'END distribution.

### Source de données

Table : `interruptions_transport`  
Colonne : `energie_non_fournie_mwh`

### Agrégation mensuelle

```sql
SELECT COALESCE(SUM(it.energie_non_fournie_mwh), 0) AS end_mwh
FROM interruptions i
JOIN interruptions_transport it ON it.interruption_id = i.id
WHERE
    i.type_direction IN ('transport', 'omvg')
    AND i.statut IN ('cloture', 'valide')
    AND YEAR(i.date_remise) = :annee
    AND MONTH(i.date_remise) = :mois
```

### Utilisé dans

- Rapport mensuel transport (`POST /api/v1/rapports/mensuel/transport`)
- Rapport annuel consolidé (distribution + transport)

### Non exposé en API indicateurs

Il n'existe **pas** de `GET /api/v1/indicateurs/end-transport` ni de champ `end_transport` dans le tableau de bord. Le comptage d'interruptions transport au niveau national est réservé au rôle `ADMIN_SAQS` dans `indicateurs_service.get_tableau_de_bord`.

---

## 9. Tableau de Bord (vue synthétique)

### Définition

Vue agrégée combinant tous les indicateurs du mois courant (ou d'un mois donné) pour un scope géographique.

### Contenu

| Champ | Calcul | Source |
|---|---|---|
| `end_mois` | SUM(end_mwh) du mois | `interruptions_distribution.end_mwh` |
| `saifi` | SAIFI pondéré | table `saifi_saidi` |
| `saidi` | SAIDI pondéré | table `saifi_saidi` |
| `nb_interruptions_actives` | COUNT WHERE statut='en_cours' | `interruptions` |
| `nb_interruptions_mois` | COUNT WHERE mois = période | `interruptions` |
| `causes_repartition` | Top 5 causes | `interruptions JOIN causes` |
| `natures_repartition` | Par nature (ordre FIS) | `interruptions JOIN natures` |

### Cache Redis

Les résultats sont mis en cache par `(type, region_id, annee, mois)`.  
Clé pattern : `indicateurs:{type}:{region_id}:{annee}:{mois}`  
Clés dérivées : `indicateurs:historique:{type}:{region_id}:{annees}`, `indicateurs:tableau-de-bord:…`, `indicateurs:top-feeders:…`  
TTL : 1 h (3600 s) — voir `indicateurs_cache_service.py` et `CLAUDE.md`.

**Invalidation :**

- **Clôture** (`statut → cloture`) : tâche Celery `calcul_end` → invalidation cache END à la fin du calcul
- **Validation** (`statut → valide`) : invalidation synchrone des caches indicateurs + tâche Celery `calcul_saifi_saidi`

### Endpoint API

```
GET /api/v1/indicateurs/tableau-de-bord
GET /api/v1/indicateurs/tableau-de-bord?annee=2024&mois=5
GET /api/v1/indicateurs/tableau-de-bord?periode=2024-5
GET /api/v1/indicateurs/tableau-de-bord?region_id=2
```

---

## 10. Nombre de Clients de Référence

### Définition

Base clients mensuelle par service, utilisée comme dénominateur pour SAIFI et SAIDI.

### Source

Table : `nombre_client_mois`  
Clé : `(service_id, annee, mois)` — contrainte UNIQUE

### Alimentation

Saisie manuelle ou import mensuel (pas encore automatisé).  
Seed dev : `make seed-dev` charge des snapshots via `seed_indicateurs.py`.  
Si absent pour un service/période → SAIFI et SAIDI ne peuvent pas être calculés pour ce service.

---

## 11. NAPT — Note d'Autorisation Préalable de Travaux

### Définition

Ce n'est pas un indicateur calculé mais un indicateur de gestion opérationnelle. Il trace les autorisations de travaux planifiés avec potentielle coupure.

### États du workflow

```
brouillon → soumis → approuve → [exécution] → archive
```

### Lien avec les interruptions

- Une NAPT approuvée peut générer une interruption `is_programme = true`
- Ces interruptions sont comptées dans l'END mais classées `END_PROGRAMME`
- Elles peuvent être exclues du SAIFI/SAIDI selon les règles CRSE (TODO validation)

### Tables

| Table | Description |
|---|---|
| `napt` | Autorisation principale (objet, dates, feeder, service) |
| `consignations` | Consignations électriques liées à la NAPT |

---

## Schéma de déclenchement des calculs

```
Interruption clôturée (statut → 'cloture')
    │
    └── Celery Task: calcul_end(interruption_id)
            └── calculer_et_persister_end → energie_nd + miroir interruptions_distribution.end_mwh
                └── Invalide cache Redis END (région, mois de date_remise)

Interruption validée (statut → 'valide')
    │
    ├── Invalidation synchrone cache Redis (END, SAIFI, SAIDI, tableau-de-bord, …)
    │
    └── Celery Task: calcul_saifi_saidi(interruption_id)
            └── Recalcule SAIFI + SAIDI pour (service_id, annee, mois de date_apparition)
                └── Persiste dans saifi_saidi
```

---

## Périmètres RBAC par indicateur

Aligné sur `seed_rbac.py` et `indicateurs_service._resolve_scope` (BCC/BRC : `user_roles.scope_service_id` = `region_id`).

| Rôle | Périmètre | Permission `indicateurs:read` | Indicateurs accessibles |
|---|---|---|---|
| BCC | Région (distribution) | Oui | END, SAIFI, SAIDI, TB, Top Feeders, Historique |
| BRC | Région (lecture) | Oui | END, SAIFI, SAIDI, TB, Top Feeders, Historique |
| SUPERVISEUR | Service unique | Oui | END, SAIFI, SAIDI, TB (son service uniquement) |
| DISPATCHER | Transport national | **Non** | Interruptions transport uniquement (pas d'API indicateurs) |
| ADMIN_DISPATCHING | Transport national | **Non** | Interruptions transport + rapports transport |
| ADMIN_SCR | National distribution | Oui | Tous indicateurs distribution |
| ADMIN_SAQS | National | Oui | Distribution + comptage interruptions transport au TB national |

---

## Points en attente de validation SENELEC/CRSE

1. **Coefficients de pondération END** : les coefficients par nature (INCIDENT, DELESTAGE, MAINTENANCE) sont provisoirement à 1.0 — les vrais coefficients CRSE doivent être saisis dans la table `types_end`.
2. ~~Exclusions SAIFI/SAIDI~~ — tranché le 28/10/2026 : aucune exclusion (formule Power BI SENELEC).
3. ~~Base clients de référence~~ — tranché : NombreClientMois du mois de la dernière apparition.
4. ~~Unité SAIDI~~ — tranché : heures.
5. **Objectifs annuels** : les seuils CRSE cibles (END max, SAIFI max, SAIDI max) ne sont pas encore configurés.
