# Fusion « Suivi incidents SIR » dans SIRV2

> Branche : `feat/fusion-suivi-incidents` (tirée de `origin/SIR_MSENE` le 25/11/2026).
> App source : dépôt `lamaneND/suivi-incidents-SIR`, branche `feat/retours-cheikh-seck-hta-htb` (18/11/2026).
> Objectif : une seule application. Les écrans du tableau de bord « Suivi incidents » sont réécrits dans SIRV2 (FastAPI + Angular).
>
> **Principe (25/11/2026)** : le suivi incidents intégré se base sur **SIRV2** — ses données (base `SIRV2`), ses règles (région d'exploitation du service, base clients BI_ODS, règle des 5 minutes), ses utilisateurs et ses droits. Il ne cherche pas à reproduire les chiffres de l'ancienne app. L'ancienne app reste en service jusqu'au déploiement de SIRV2, puis elle est arrêtée.

## 1. Pourquoi une réécriture et pas une fusion de code

| | Suivi incidents | SIRV2 |
|---|---|---|
| Frontend | React 19 + Vite, Tailwind, Recharts, Leaflet | Angular 17, Material, graphiques SVG maison, Leaflet |
| Backend | pandas en mémoire (~800 000 lignes, un seul worker), SQL brut | SQLAlchemy async, routers → services → repositories, Celery |
| Données | Tables SIR v1 de `IndicateursTransportDistribution` (copie rechargée chaque heure), lecture seule (`LectSIP`) | Base `SIRV2` (srv-bddomtech), alimentée par `scripts/migration/delta_periode.py` |
| Auth | LDAPS + JWT 480 min, rôles `admin` / `user` (`SIR_UserRoles`, groupe AD `SIR_Admins`) | LDAP + JWT 30 min / refresh 7 j, RBAC 8 rôles + permissions |
| Tests | 156 snapshots de non-régression (jeu figé du 15/10/2026) | ~571 tests pytest |

Le code React et le modèle « tout en mémoire » ne sont pas transposables. On reprend **les écrans et les fonctions** ; les calculs sont ceux de SIRV2.

## 2. Inventaire écran par écran

Légende : ✅ existe dans SIRV2 · 🟡 existe en partie · ❌ à créer.

| Écran Suivi incidents | Contenu | SIRV2 | Écart à combler |
|---|---|---|---|
| Barre de filtres | dates, zone Dakar/Régions, poste source, nature, cause, réseau HTB, exogène | 🟡 période + région (`/indicateurs/tableau-de-bord`) | filtres poste source, nature, cause, HTB, exogène |
| Cartes KPI (3 rangées) | interruptions / incidents, Dakar, Régions, END HTA/HTB/total, durée moyenne et cumulée, taux de localisation, SAIFI/SAIDI Dakar | 🟡 indicateurs clés du dashboard | END HTA/HTB/total, durées, taux de localisation, distinction interruption / incident |
| Vue d'ensemble | drill-down Région → Département → Commune → Localité, légende par nature, en-tête semaine Senelec | ❌ (semaine Senelec ✅ côté backend) | géographie administrative des postes, drill-down |
| Carte & évolution | carte Leaflet des incidents, série journalière | 🟡 carte des postes sans remise, historique mensuel | marqueurs agrégés par position, série journalière |
| Carte SAIFI/SAIDI | bulles par service et par poste, tableau des contributions par service | ❌ | contributions par service / poste (dénominateur commun) |
| Focus opérationnel | tableaux par poste source et par feeder | 🟡 `/indicateurs/top-feeders` | classement par poste source, contribution SAIFI/SAIDI |
| Qualité de service | barres par région | 🟡 pilotage Dakar / Régions | barres par région administrative |
| SAIFI / SAIDI | synthèse HTA/HTB/total × 3 périodes ; rapport par nature (format outil bureau, 6 décimales) ; graphique et tableau mois × nature | 🟡 synthèse ✅ (`/indicateurs/synthese-saifi-saidi`), historique ✅ | ventilation par nature, tableau mois × nature |
| Nature | répartition par nature agrégée (Incident, Travaux, Délestage) | 🟡 répartition par nature (import FIS, dashboard) | règle `NatureAgregee` / `EstIncident` à aligner |
| Localisation | taux de géolocalisation, types de correspondance, non-localisés par poste source | ❌ | statut de localisation par poste |
| Correspondances (admin) | validation manuelle poste SIR ↔ poste SIG, recensement terrain | 🟡 rapprochement Schéma / SIG / SIR (23/11) | réutiliser cet écran pour les corrections manuelles ; reprendre `MatchingManuel` et `Recensement_Postes` |
| Administration (admin) | rôles des utilisateurs, recherche AD | ✅ Administration → Utilisateurs / Rôles et droits | aucun : utilisateurs et droits de SIRV2 (permission `indicateurs:read`) |

### Organisation retenue (25/11/2026)

Un nouveau menu **« Suivi incidents »** dans SIRV2 (section Analyse ; route `/suivi-incidents`, `roleGuard` + `indicateurs:read`), masqué par l'interrupteur `FONCTIONNALITES.suiviIncidents` jusqu'à la recette (aperçu sur un poste : `localStorage['sir_apercu'] = 'suivi-incidents'`). Choix validés : **6 onglets** (les doublons de l'ancienne app sont regroupés), graphiques **ngx-echarts** (chargés à la demande), période par défaut **semaine Senelec passée**.

| Onglet (route enfant) | Contenu | Remplace (ancienne app) |
|---|---|---|
| Vue d'ensemble | 6 KPI avec écart vs période précédente ; Travaux / Incident / Délestage (nombre, durée) ; END HTA / HTB / total ; classement territorial cliquable | Vue d'ensemble, KPI, Nature, Qualité de service |
| Carte | postes touchés (taille = nombre, couleur = nature) ; mode SAIFI / SAIDI par service ; clic → filtre | Carte (1re moitié) |
| Évolution | nombre + durée, granularité automatique (jour ≤ 31 j, semaine Senelec ≤ 6 mois, mois au-delà), par nature | Carte & évolution (2e moitié) |
| Réseau | postes sources puis feeders : tableaux triables avec recherche, contribution SAIFI, export Excel ; clic → filtre | Focus opérationnel |
| SAIFI / SAIDI | synthèse HTA / HTB / total + courbe mois / cumul ; sections dépliables : rapport par nature, mois × nature, contribution par service | SAIFI / SAIDI |
| Localisation | taux de postes localisés, non-localisés par poste source, lien « Corriger » | Localisation |
| — | Correspondances → Administration → SIG / rapprochement Schéma-SIG-SIR ; Administration → Utilisateurs / Rôles et droits | Correspondances, Administration |

Classement territorial : Région d'exploitation → Service → Poste source → Feeder tant que la géographie administrative n'est pas chargée (étape 6), puis Région → Département → Commune → Localité ; « Non localisé » toujours en dernière ligne.

### Règles UX communes

- **Filtres** : barre collante, application immédiate, pastilles des filtres actifs (✕, « Tout effacer »), **dans l'URL** (`?du=&au=&region=&service=&poste_source=&feeder=&nature=&cause=&reseau=&exogene=`), conservés d'un onglet à l'autre ; période Semaine / Mois / Année / Personnalisé avec ◀ ▶ ; « Plus de filtres » : cause, réseau HTA / HTB, facteur exogène ; région ou service imposés par le rôle (API `GET /suivi-incidents/filtres`). Un clic dans un graphique, la carte ou un classement ajoute le filtre.
- **Formats** (`shared/utils/formats-indicateurs.ts`) : SAIFI 2 décimales, SAIDI en heures 1 décimale (détail « h mn » en infobulle), END en MWh 1 décimale (kWh sous 1 MWh), durées « 12 h 30 », pourcentages « 84,5 % ».
- **Vocabulaire** : « interruptions » pour le total ; « incidents » = Permanent, Semi-permanent, Fugitif, délestage incident HTA ; « postes touchés » ; « coupures-clients » pour Σ clients.
- **Couleurs métier** (`$nature-*`, `$reseau-*`) : Travaux marine, Incident orange, Délestage rouge, HTA violet, HTB magenta ; valeurs toujours écrites (pas d'information par la couleur seule) ; aplats.
- **États** par bloc (`sir-etat`) : squelette, vide lisible avec « Effacer les filtres », erreur en français avec « Réessayer ».
- **Accessibilité** : vrais boutons et liens, infobulles au clavier, `aria-current` sur l'onglet, contraste 4,5:1, textes ≥ 12 px ; **mobile 390 px** : filtres repliés, cibles ≥ 44 px.
- **Composants partagés** : `sir-etat`, `sir-kpi`, `sir-graphique` (ECharts réduit : barres, courbes, secteurs), `SuiviIncidentsFiltresService`.

## 3. Écarts dans le modèle de données SIRV2

| Besoin | État SIRV2 | Proposition |
|---|---|---|
| Cause « réseau HTB » (`Causes.CauseReseauHTB`) | absent de `causes` (`app/models/referentiel.py`) ; le rapport hebdo DD le déduit du libellé | pas de colonne : règle du rapport hebdo DD sur le libellé de la cause (décision du 25/11, §5), extraite dans une fonction partagée |
| Cause « facteur exogène » (`Causes.FacteursExogenes`) | ✅ `causes.est_exogene` (migration `6a7b8c9d0e1f`, posé d'après le libellé pour les causes existantes ; reprise SIR v1 par le loader référentiel) | à faire : exposer le drapeau dans Administration → Référentiel et reprendre `FacteursExogenes` de SIR v1 pour les causes déjà en base (le loader ne le pose qu'à l'insertion) |
| Coordonnées des postes | calculées à la volée par nom de nœud SIG (`pilotage_repository`, ~l.560-615) | lien `postes.noeud_sig_id` (FK) + statut de localisation, calculés par une tâche Celery et non à chaque requête |
| Géographie administrative (département, commune, localité) | absente | table `localites` (région, département, commune, localité) reprise du fichier « Postes_Affectes_Localites », FK depuis `noeuds_sig` ou `postes` |
| Corrections manuelles (`MatchingManuel`) et recensement (`Recensement_Postes`) | partiellement couvert par le rapprochement Schéma / SIG / SIR | reprise des lignes existantes dans les tables SIRV2 du rapprochement |
| Coordonnées des services (`Localisation_Service`) | absente | colonnes lat/lon sur `services` |

## 4. Règles métier : comparaison du code (25/11/2026, hors ligne)

SIRV2 fait foi. Ce tableau sert à **expliquer** les écarts de chiffres entre l'ancienne app et SIRV2 pendant la période où les deux tournent, et à repérer ce que SIRV2 doit encore calculer (lignes ❌ « absent »).

Références : Suivi incidents `backend/app/services/saifi.py` et `chargement.py` (branche `feat/retours-cheikh-seck-hta-htb`) ; SIRV2 `app/repositories/pilotage_repository.py`, `app/services/indicateurs_service.py`, `app/services/rapport_hebdo_dd_service.py`.

| Règle | Suivi incidents | SIRV2 | Verdict |
|---|---|---|---|
| Exclusion ≤ 5 min | `round(dureeHeure × 60) ≤ 5` → exclue | `duree_minutes > 5` (`pilotage_repository.py:101`) ; reprise SIR v1 : `round(dureeHeure × 60)` (`transforms/dates.py`) | ✅ identique pour les interruptions reprises de SIR v1. ⚠️ Saisie SIRV2 : durée tronquée à la minute (`interruption_distribution_service._compute_duree_minutes`), 5 min 40 s → 5 → exclue, alors que l'outil arrondit à 6 → comptée |
| Durée SAIDI | `dureeHeure` exacte | `duree_minutes / 60` (minutes entières) | 🟡 écart d'arrondi < 30 s par interruption, négligeable |
| Interruptions comptées | toutes les lignes Dakar (durée nulle = brève) | clôturées avec date de remise (`_distribution_saifi_saidi`) | 🟡 équivalent en pratique ; une interruption en cours n'entre pas dans SIRV2 |
| Clients d'une interruption | Σ `nombreclientposteEstime` des postes, sans déduplication | Σ `COALESCE(nombre_clients_estime, nombre_clients_touches)` (`_clients_poste`) | ✅ même formule ; SIRV2 ajoute un repli sur les clients saisis |
| Dénominateur | `NombreClientMois` IDRegions 15 du mois de MAX(DateApparition), brèves comprises ; sinon dernier mois connu | même principe (`avec_duree_min=False`) ; base BI_ODS depuis le 19/11 | 🟡 **source différente** (NombreClientMois SIR v1 vs BI_ODS) : écart attendu à partir de novembre |
| Périmètre Dakar | colonne `Regions` de SIR v1 (`_dakar_mask` : nulle ou « DAKAR ») | `interruptions.region_id` déduit du service (décision 02/11) | ❌ **différent** : CLAUDE.md constate que `Regions` de SIR v1 n'est pas fiable (6 471 interruptions SDDV de 2026 rangées en Régions). Les SAIFI Dakar des deux apps ne portent pas sur les mêmes interruptions |
| Zone Régions | non calculée (pas de `PosteInterruption`) | calculée | SIRV2 va plus loin |
| Semaine Senelec | samedi → vendredi, dernière semaine terminée ; numéro = semaine ISO du vendredi (S43 2026 = 17 → 23/10) | même découpage (`periodes_synthese`) ; libellé « Semaine passée (jj/mm → jj/mm) » sans numéro | ✅ mêmes bornes ; ❌ numéro « S47 » à ajouter |
| HTA / HTB | HTB = cause marquée `Causes.CauseReseauHTB` sur les interruptions distribution | **deux définitions dans SIRV2** : synthèse = interruptions transport / OMVG (`get_synthese_saifi_saidi`) ; rapport hebdo DD = cause contenant « HTB », « PRODUCTION » ou « BLACK START » (`rapport_hebdo_dd_service.categorie`) | ✅ **décidé le 25/11** : règle du rapport hebdo DD partout (§5) ; la synthèse SAIFI/SAIDI de l'accueil est à aligner |
| Facteurs exogènes | drapeau `Causes.FacteursExogenes` | mots-clés de la cause (`rapport_hebdo_dd_service.est_exogene`) | 🟡 même idée, source différente : à aligner sur le drapeau SIR v1 |
| NatureAgregee | IDNature 3/4/5 → Incident ; 2 + cause 47 → Incident ; 1 → Travaux ; 2 sinon → Délestage | catégories du rapport hebdo DD : Permanent, Semi permanent, Fugitif, Délestage HTA, Travaux (cause « Travaux »), Manœuvre, Autres, HTB | 🟡 deux découpages différents ; le découpage du rapport hebdo DD est plus fin et validé (29/10) : le réutiliser plutôt que d'en créer un troisième |
| Durée totale (rapport par nature) | durée × nombre d'UR distinctes touchées | absent | ❌ à porter |
| Clients distincts | Σ sur (poste, UR) uniques du max de clients | absent | ❌ à porter |

## 5. Décisions à prendre (SENELEC / équipe)

Réglé par le principe du 25/11 : périmètre Dakar = région du service (SIRV2) ; données = base SIRV2 ; comptes = utilisateurs et rôles SIRV2.

**Décidé le 25/11/2026 — HTB** : une interruption distribution est « HTB » quand sa cause contient « HTB », « PRODUCTION » ou « BLACK START » (règle du rapport hebdo DD, `rapport_hebdo_dd_service.categorie`). HTA = toutes les autres. Même règle partout : filtre « réseau HTB », tuile END HTA/HTB, synthèse SAIFI/SAIDI de l'accueil (qui utilise aujourd'hui les interruptions transport / OMVG et doit être alignée).

Restent ouvertes :

1. **Lecteurs actuels** : les personnes qui n'ont qu'un accès lecture à l'ancienne app doivent avoir un compte SIRV2 avec la permission `indicateurs:read` (rôle à choisir ou à créer dans Rôles et droits).
2. ~~**Graphiques**~~ — **décidé le 25/11/2026** : ngx-echarts, chargé seulement dans le menu Suivi incidents.

## 6. Comparaison des chiffres (facultative)

Pas un préalable : SIRV2 fait foi. Utile pour préparer les questions des utilisateurs qui voient des chiffres différents dans les deux apps pendant la transition.

- Références Suivi incidents : snapshots `suivi incidents/backend/tests/snapshots/` (jeux `aout_dakar`, `aout_regions`, `mars`, `mars_htb`, `mars_incident`, `mars_non_exogene`, `s1_cause_hta`, `toute_periode`) — données figées au 15/10/2026.
- SIRV2 : `GET /api/v1/indicateurs/synthese-saifi-saidi`, `/tableau-de-bord`, `/historique` sur la base `srv-bddomtech/SIRV2`.
- Collecte : `python scripts/fusion/collecter_chiffres.py`, à lancer sur le réseau SENELEC (lecture seule sur les deux API déployées, résultats dans `scripts/fusion/resultats_*.json`, ignorés par git).
- Écarts attendus avant même la collecte : périmètre Dakar (§4) et base clients BI_ODS à partir de novembre.

## 7. Plan de livraison (une PR par étape, circuit « tests avant le code »)

1. **HTB par la cause** dans la synthèse SAIFI/SAIDI de l'accueil — **fait le 25/11/2026**.
2. **Fondations** — route `/suivi-incidents` et 6 onglets (routes enfants), barre de filtres dans l'URL, `GET /suivi-incidents/filtres` (période par défaut, périmètre du rôle), `causes.est_exogene`, composants partagés (KPI, états, graphiques ngx-echarts) — **fait le 25/11/2026**.
3. **Vue d'ensemble** — `GET /suivi-incidents/vue-ensemble` (KPI et période précédente, natures, réseaux HTA / HTB) et `GET /suivi-incidents/classement` (service / poste source / feeder, clic → filtre) — **fait le 25/11/2026** (spécification §8).
4. **Évolution + Réseau** — série à granularité automatique ; classements postes sources / feeders triables avec recherche, export Excel.
5. **SAIFI / SAIDI** — rapport par nature, mois × nature, contributions par service.
6. **Géographie + Carte + Localisation** — migrations Alembic (§3), import des localités (« Postes_Affectes_Localites »), lien poste ↔ SIG par tâche Celery ; onglets Carte et Localisation ; classement territorial administratif.
7. **Administration** — reprise des corrections manuelles et du recensement dans le rapprochement Schéma / SIG / SIR.
8. **Recette et bascule** — recette par les utilisateurs de l'ancienne app, retrait de l'interrupteur, redirection de l'ancienne adresse (port 8070) vers SIRV2.

## 8. Spécification de l'étape 3 — Vue d'ensemble (25/11/2026)

Données : interruptions **distribution**, **tous statuts** (comme le rapport hebdo DD), datées par
`date_apparition` sur [debut, fin] (fin incluse), filtrées par `appliquer_filtres` sur les filtres
**résolus** (`resoudre_filtres`) : la région imposée au BCC / BRC et le service imposé au
SUPERVISEUR deviennent des clauses `WHERE` (RBAC double avec `require_permission("indicateurs","read")`).
Mêmes paramètres de requête que `GET /suivi-incidents/filtres`.

### `GET /api/v1/suivi-incidents/vue-ensemble`

Réponse `ApiResponse[VueEnsemble]` :

| Champ | Contenu |
|---|---|
| `filtres` | `FiltresResolus` (comme `/filtres`) |
| `periode_precedente` | `{debut, fin, libelle}` — `periodes.periode_precedente(debut, fin)` |
| `kpi`, `kpi_precedent` | `KpiSuivi` de la période et de la période précédente (mêmes filtres hors période) |
| `natures` | 4 lignes, toujours dans l'ordre `incident`, `delestage`, `travaux`, `autre` |
| `reseaux` | 3 lignes : `hta`, `htb`, `total` (réseau par la cause, `condition_reseau`) |

`KpiSuivi` : `nombre_interruptions` (int) ; `duree_totale_heures` (Σ `duree_minutes` / 60, nulles = 0) ;
`duree_moyenne_minutes` (moyenne des durées renseignées, `null` si aucune) ; `postes_touches`
(postes distincts de `poste_interruptions`) ; `coupures_clients` (Σ `nombre_clients_touches`, nulles = 0) ;
`end_mwh` (Σ `interruptions_distribution.end_mwh`, nulles = 0).

`RepartitionNature` : `categorie`, `libelle`, `nombre`, `duree_heures`, `end_mwh`, `part`
(nombre / total, 0 si total nul). Catégorie = `suivi_incidents_service.categorie_nature(nature, cause)`,
dérivée de `rapport_hebdo_dd_service.categorie` :

| Catégorie hebdo DD | Catégorie suivi | Libellé |
|---|---|---|
| Permanent, Semi permanent, Fugitif | `incident` | Incidents |
| Délestage incident HTA, Délestage HTB / production | `delestage` | Délestages |
| Travaux réseau HTA | `travaux` | Travaux |
| Manœuvre, Autres coupures HTA, Autres HTB | `autre` | Autres coupures |

`RepartitionReseau` : `reseau` (`hta` | `htb` | `total`), `nombre`, `duree_heures`, `end_mwh` ; total = hta + htb.

`periode_precedente` : semaine Senelec → semaine précédente ; mois civil complet → mois précédent
complet ; année civile → année précédente ; sinon même nombre de jours juste avant `debut`.

### `GET /api/v1/suivi-incidents/classement`

Paramètres en plus des filtres : `niveau` = `service` | `poste_source` | `feeder` (obligatoire),
`limite` 1 à 50 (défaut 10) ; autre valeur → 422 enveloppé.

Réponse `ApiResponse[ClassementSuivi]` : `niveau`, `total_interruptions`, `lignes`
(`{id, code, libelle, nombre, duree_heures, end_mwh, part}`), `autres` (somme des lignes au-delà de
`limite`, `null` s'il n'y en a pas). Tri : nombre décroissant puis libellé. La ligne sans
rattachement (`id = null`, libellé « Non renseigné ») est toujours **la dernière**, hors limite.

Cache Redis 1 h par (endpoint, filtres résolus) — clé `suivi:{endpoint}:{empreinte}`.

### Points ouverts de l'étape 3

- **Cache d'une heure sans invalidation** : une interruption saisie apparaît dans la Vue d'ensemble au plus une heure après (la liste des interruptions la montre tout de suite). À décider : garder 1 h, ou invalider `suivi:*` à la création, la clôture et la validation.
- **Catégorie « Travaux »** : suit la règle du rapport hebdo DD (cause contenant « Travaux »). Une interruption de nature « Travaux » dont la cause ne le dit pas tombe dans « Autres coupures » — à confirmer sur les natures réelles de SIRV2.
- **Interruptions en cours** : comptées dans le nombre, pas dans la durée (durée non encore connue).

## 9. Spécification de l'étape 4 — Évolution et Réseau (25/11/2026)

Mêmes règles que l'étape 3 : interruptions distribution, tous statuts, filtres **résolus**
(`resoudre_filtres`) appliqués par `appliquer_filtres` (RBAC double), mêmes paramètres de requête
que `/filtres`, erreurs 422 **enveloppées** `{"status":"error","data":null,"error":…}`, cache Redis
1 h `suivi:{endpoint}:{empreinte des filtres résolus et des paramètres}`.

### `GET /api/v1/suivi-incidents/evolution`

Paramètre en plus : `granularite` = `auto` (défaut) | `jour` | `semaine` | `mois` ; autre valeur → 422.
`auto` : `jour` si la période fait ≤ 31 jours, `semaine` (semaine Senelec) si ≤ 186 jours, `mois` sinon.
`jour` demandé sur plus de 366 jours → 422 (trop de points).

Réponse `ApiResponse[EvolutionSuivi]` : `granularite` (celle appliquée, jamais `auto`), `points`.
Un point par intervalle, **tous les intervalles de la période, vides compris**, dans l'ordre :
`{debut, fin, libelle, nombre, duree_heures, end_mwh, natures}` où `natures` =
`{incident, delestage, travaux, autre}` (nombre d'interruptions par catégorie, `categorie_nature`).

- `jour` : `debut = fin` = le jour, libellé « 14/11 ».
- `semaine` : semaine Senelec (samedi → vendredi), libellé « S47 » ; le premier et le dernier point
  sont **rognés** aux bornes de la période (`debut` ≥ début demandé, `fin` ≤ fin demandée).
- `mois` : mois civil, libellé « nov. 2026 » (abréviations françaises : janv., févr., mars, avr.,
  mai, juin, juil., août, sept., oct., nov., déc.), rogné de même.

Somme des `nombre` des points = `kpi.nombre_interruptions` de la Vue d'ensemble pour les mêmes filtres.
Requête : `suivi_incidents_repository.requete_evolution(filtres)` — regroupement par **jour**
(`CAST(date_apparition AS DATE)`), nature et cause ; regroupement en semaines / mois en Python.

### `GET /api/v1/suivi-incidents/reseau`

Paramètre en plus : `niveau` = `poste_source` | `feeder` (obligatoire, sinon 422).
Réponse `ApiResponse[ReseauSuivi]` : `niveau`, `total_interruptions`, `lignes` — **toutes** les lignes
(pas de limite : tri, recherche et pagination côté écran), triées par nombre décroissant puis libellé,
« Non renseigné » (`id = null`) en dernier. Une ligne :
`{id, code, libelle, poste_source, nombre, duree_heures, end_mwh, coupures_clients, postes_touches, part}`
- `poste_source` : libellé du poste source du feeder (niveau `feeder`), `null` au niveau `poste_source` ;
- `coupures_clients` : Σ `interruptions.nombre_clients_touches` ; `postes_touches` : postes distincts
  de `poste_interruptions` ; `part` = nombre / total.
Requêtes : `requete_reseau(filtres, niveau)` (sommes) et `requete_reseau_postes(filtres, niveau)`
(postes distincts par ligne) ; niveau inconnu → `ValueError`.

### `GET /api/v1/suivi-incidents/reseau/export`

Mêmes paramètres que `/reseau`. Fichier Excel (`openpyxl`, construit dans un thread) :
`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`,
`Content-Disposition: attachment; filename="suivi_{niveau}_{debut}_{fin}.xlsx"`. Une feuille, une
ligne de titre (période et filtres), puis l'en-tête et les lignes de `/reseau` dans le même ordre
(colonnes : Poste source / Feeder, Code, [Poste source], Interruptions, Durée (h), END (MWh),
Coupures-clients, Postes touchés, Part (%)). Mêmes droits et même périmètre que `/reseau`.

La contribution au SAIFI par poste source / feeder est reportée à l'étape 5 (base clients).

