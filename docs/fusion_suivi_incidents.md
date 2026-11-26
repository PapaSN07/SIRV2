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

Un nouveau menu **« Suivi incidents »** dans SIRV2 (section Analyse ; route `/suivi-incidents`, `roleGuard` + `indicateurs:read`), visible depuis le 26/11/2026 (interrupteur `FONCTIONNALITES.suiviIncidents` à `true` ; à `false`, aperçu possible sur un poste avec `localStorage['sir_apercu'] = 'suivi-incidents'`) ; l'ancienne application reste l'outil de référence jusqu'au basculement. Choix validés : **6 onglets** (les doublons de l'ancienne app sont regroupés), graphiques **ngx-echarts** (chargés à la demande), période par défaut **semaine Senelec passée**.

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
- **Formats** (`shared/utils/formats-indicateurs.ts`) : SAIFI 3 décimales, SAIDI en heures 3 décimales (comme l’accueil) (détail « h mn » en infobulle), END en MWh 1 décimale (kWh sous 1 MWh), durées « 12 h 30 », pourcentages « 84,5 % ».
- **Vocabulaire** : « interruptions » pour le total ; « incidents » = Permanent, Semi-permanent, Fugitif, délestage incident HTA ; « postes touchés » ; « coupures-clients » pour Σ clients.
- **Couleurs métier** (`$nature-*`, `$reseau-*`) : Travaux marine, Incident orange, Délestage rouge, HTA violet, HTB magenta ; valeurs toujours écrites (pas d'information par la couleur seule) ; aplats.
- **États** par bloc (`sir-etat`) : squelette, vide lisible avec « Effacer les filtres », erreur en français avec « Réessayer ».
- **Accessibilité** : vrais boutons et liens, infobulles au clavier, `aria-current` sur l'onglet, contraste 4,5:1, textes ≥ 12 px ; **mobile 390 px** : filtres repliés, cibles ≥ 44 px.
- **Composants partagés** : `sir-etat`, `sir-kpi`, `sir-graphique` (ECharts réduit : barres, courbes, secteurs), `SuiviIncidentsFiltresService`.

## 3. Écarts dans le modèle de données SIRV2

| Besoin | État SIRV2 | Proposition |
|---|---|---|
| Cause « réseau HTB » (`Causes.CauseReseauHTB`) | absent de `causes` (`app/models/referentiel.py`) ; le rapport hebdo DD le déduit du libellé | pas de colonne : règle du rapport hebdo DD sur le libellé de la cause (décision du 25/11, §5), extraite dans une fonction partagée |
| Cause « facteur exogène » (`Causes.FacteursExogenes`) | ✅ `causes.est_exogene` (migration `6a7b8c9d0e1f`, posé d'après le libellé pour les causes existantes ; reprise SIR v1 par le loader référentiel) | drapeau modifiable dans Administration → Référentiel (§12, fait le 25/11/2026) ; reste à reprendre `FacteursExogenes` de SIR v1 pour les causes déjà en base (le loader ne le pose qu'à l'insertion) |
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
4. **Évolution + Réseau** — série à granularité automatique ; classements postes sources / feeders triables avec recherche, export Excel — **fait le 25/11/2026** (spécification §9).
5. **SAIFI / SAIDI** — synthèse du périmètre ou contribution des interruptions filtrées, HTA / HTB, natures, évolution mensuelle et cumul, contributions par service — **fait le 25/11/2026** (spécification §10).
6. **Géographie + Carte + Localisation** — découpée : **6a** Carte et Localisation sur les données existantes (spécification §11) — **faite le 25/11/2026** ; **6b** géographie administrative ci-dessous, quand le fichier des localités sera disponible sur le réseau SENELEC — migrations Alembic (§3), import des localités (« Postes_Affectes_Localites »), lien poste ↔ SIG par tâche Celery ; onglets Carte et Localisation ; classement territorial administratif.
7. **Administration** — reprise des corrections manuelles et du recensement dans le rapprochement Schéma / SIG / SIR.
8. **Recette et bascule** — recette par les utilisateurs de l'ancienne app (menu déjà visible depuis le 26/11/2026), redirection de l'ancienne adresse (port 8070) vers SIRV2.

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

## 10. Spécification de l'étape 5 — SAIFI / SAIDI (25/11/2026)

Formule SENELEC existante (`saifi_saidi_service`, `docs/indicateurs_sirv2.md`), **sans nouvelle règle** :
interruptions distribution **clôturées** (`statut` clôturé, `date_remise` renseignée) de **plus de
5 minutes** (`SAIFI_DUREE_MIN_MINUTES`) ; NombreClient = Σ clients estimés des postes
(`_clients_poste`) ; SAIDI en heures ; base clients = `clients_reference_exacte` du mois de la
**dernière apparition** de la période (dernier mois connu à défaut).

**Périmètre (dénominateur)** : celui des indicateurs (`indicateurs_service._resolve_scope` +
`_load_service_ids`, qui pose la région) à partir des filtres **résolus** : national, région
(`region_id` imposé au BCC / BRC ou choisi par un national) ou service (SUPERVISEUR). Le mois de
référence se calcule sur tout le périmètre, sans les autres filtres.

**Numérateur** : interruptions du périmètre (`interruptions_du_perimetre`) **et** des filtres
(`appliquer_filtres` : poste source, feeder, service choisi par un national, nature, cause, réseau,
exogène). Avec ces filtres, le résultat est la **contribution** des interruptions retenues au SAIFI /
SAIDI du périmètre (`contribution = true` dans la réponse). Sans eux, la synthèse est égale à
`calculer_perimetre(service_ids, debut, fin + 1 jour)` (même chiffre que l'accueil sur la même période).

### `GET /api/v1/suivi-incidents/saifi-saidi`

Mêmes paramètres que `/filtres`. Réponse `ApiResponse[SaifiSaidiSuivi]` :

| Champ | Contenu |
|---|---|
| `contribution` | `true` si un filtre autre que période / région / service imposé restreint le numérateur |
| `synthese` | `IndicateurSaifi` de la période |
| `mois_reference` | `{annee, mois}` de la base clients **effectivement utilisée** (après repli sur le dernier mois connu), `null` sans base |
| `reseaux` | 3 lignes `hta`, `htb`, `total` (`IndicateurSaifi` + `reseau`) ; total = hta + htb |
| `natures` | 4 lignes `incident`, `delestage`, `travaux`, `autre` (`IndicateurSaifi` + `categorie`, `libelle`, `part_saifi`) ; Σ = synthèse |
| `mensuel` | un point par mois civil touché par la période (rogné aux bornes), dans l'ordre : `{annee, mois, libelle, saifi, saidi, saifi_cumule, saidi_cumule, interruptions}` |
| `services` | contribution par service (services ayant au moins une interruption comptée), triée par SAIFI décroissant puis libellé : `{id, code, libelle}` + `IndicateurSaifi` + `part_saifi` (pas de ligne « Non renseigné » : la formule exclut les interruptions sans service) |

`IndicateurSaifi` = `{saifi, saidi, interruptions, clients_coupes, client_heures, clients_reference}` :
`interruptions` = interruptions comptées ; `clients_coupes` = Σ NombreClient ; `client_heures` =
Σ NombreClient × durée (h) ; `clients_reference` = base clients du dénominateur (la même pour toutes
les lignes, sauf `mensuel`). `part_saifi` = part du SAIFI de la ligne dans la synthèse (0 si synthèse nulle).

`mensuel` : SAIFI / SAIDI du mois = numérateur du mois ÷ base clients de ce mois (dernier mois connu à
défaut, comme `serie_perimetre`) ; `saifi_cumule` / `saidi_cumule` = Σ numérateurs depuis le début de
la période jusqu'à ce mois ÷ base du mois (cumul de la formule SENELEC, égal à la synthèse au dernier
mois quand ce mois est celui de la dernière apparition). Libellé « nov. 2026 ».

Requêtes (`suivi_incidents_repository`) : `requete_saifi(filtres, service_ids, regroupement)` avec
`regroupement` = `None` (une ligne), `"nature"` (nature, cause), `"jour"` (jour d'apparition,
`jour_de`), `"service"` (service) ; regroupement inconnu → `ValueError`. Conditions :
`appliquer_filtres` + `interruptions_du_perimetre(service_ids)` + `_distribution_saifi_saidi()`.
Cache Redis 1 h `suivi:saifi-saidi:{empreinte des filtres résolus et du périmètre}` : un national filtré sur un service et le SUPERVISEUR de ce service ont les mêmes filtres mais pas le même dénominateur.

## 11. Spécification de l'étape 6a — Carte et Localisation (25/11/2026)

Mêmes règles que les étapes 3 à 5 : interruptions distribution, tous statuts, filtres **résolus**
appliqués par `appliquer_filtres` (RBAC double), mêmes paramètres que `/filtres`, 422 enveloppés,
cache Redis 1 h `suivi:{endpoint}:{empreinte des filtres résolus et des paramètres}`.

**Postes touchés** : postes des `poste_interruptions` des interruptions filtrées, regroupés par poste.

**Localisation d'un poste** (sans nouvelle table ; le lien stocké par tâche Celery reste prévu pour 6b) :
1. `rapprochement` : une ligne `schema_unifilaire_postes` avec ce `poste_id`, un `noeud_sig_id`,
   `rapprochement_sig` = `auto` ou `manuel` (pas `ambigu`), nœud SIG actif (`est_actif`) avec des
   coordonnées dans l'emprise du Sénégal (`pilotage_repository._lon_lat`) ; plusieurs lignes → la plus
   petite `id` ;
2. `nom` : sinon, règle du pilotage — `pilotage_repository.coords_par_nom` sur le libellé puis le code
   du poste, homonymes départagés par `choisir_point` avec le **feeder du poste** (`postes.feeder_id`) ;
3. sinon le poste est **non localisé**.

### `GET /api/v1/suivi-incidents/carte`

Réponse `ApiResponse[CarteSuivi]` : `postes_touches`, `postes_localises`, `tronque` (bool), `points`.
Un point par poste **localisé** :
`{poste_id, code, libelle, feeder_id, feeder, nombre, duree_heures, clients, nature_dominante, longitude, latitude, localisation}`
- `feeder_id`, `feeder` : identifiant et libellé du feeder du poste (`null` sans feeder) ;
- `nombre` : interruptions distinctes du poste ; `duree_heures` : Σ durée de ces interruptions (h) ;
- `clients` : Σ clients du poste (`nombre_clients_estime`, sinon `nombre_clients_touches`, sinon 0) ;
- `nature_dominante` : catégorie (`categorie_nature`) la plus fréquente parmi les interruptions du
  poste ; égalité → ordre `incident`, `delestage`, `travaux`, `autre` ;
- `localisation` : `rapprochement` | `nom`.
Au plus **3 000** points : les postes aux interruptions les plus nombreuses (puis libellé) ; `tronque`
vaut `true` si des postes localisés ont été écartés. Tri des points : nombre décroissant puis libellé.

### `GET /api/v1/suivi-incidents/localisation`

Paramètres en plus : `page` (≥ 1, défaut 1), `size` (1 à 100, défaut 20) ; autre valeur → 422 enveloppé.
Réponse `ApiResponse[LocalisationSuivi]` :
- `postes_touches`, `postes_localises`, `taux` (localisés ÷ touchés, 0 si aucun) ;
- `par_mode` : `{rapprochement, nom}` (nombre de postes localisés par chaque règle) ;
- `postes_sources` : par poste source du **feeder du poste** :
  `{id, libelle, postes_touches, non_localises, taux}`, triés par `non_localises` décroissant puis libellé,
  « Non renseigné » (`id = null`, poste sans feeder ou feeder sans poste source) en dernier ;
- `non_localises` : liste paginée `{total, page, size, items}` des postes non localisés,
  `{poste_id, code, libelle, feeder, poste_source, interruptions}`, triés par interruptions
  décroissantes puis libellé.

Écran : lien « Corriger dans le rapprochement » vers Administration → Schémas unifilaires
(`/admin/schemas-unifilaires`) pour les rôles qui y ont accès.

Requêtes (`suivi_incidents_repository`) : `requete_postes_touches(filtres)` (par poste : id, code,
libellé, feeder du poste et son libellé, poste source du feeder et son libellé, interruptions distinctes,
Σ durée, Σ clients), `requete_postes_natures(filtres)` (par poste, nature, cause : nombre),
`requete_rapprochement_sig(poste_ids)` (poste → coordonnées du nœud rapproché) ; lots de 500
identifiants au plus (limite de 2 100 paramètres de SQL Server).

### Points ouverts de l'étape 6a

- **Feeder du poste ou de l'interruption** : la carte et le tableau par poste source rangent un poste
  selon **son** feeder (`postes.feeder_id`), alors que les filtres portent sur le feeder et le poste
  source de **l'interruption**. Pour un poste dont le feeder a été corrigé (23/11) ou coché sur une
  interruption d'un autre départ (19/11), « Filtrer sur ce feeder » peut donc changer ses chiffres.
  À trancher : garder la règle, ou ranger et filtrer sur les colonnes dénormalisées de
  `poste_interruptions` (`feeder_id`, `poste_source_id`).
- **Performance** : le calcul des postes localisés est mis en cache 1 h par jeu de filtres
  (`suivi:postes-localises:*`), partagé par la carte et les pages de Localisation. Reste à faire :
  index sur `noeuds_sig.station` (recherche par nom) et lien poste ↔ nœud SIG stocké par tâche Celery (6b).
- **Fond de carte** : tuiles OpenStreetMap publiques, comme l'administration SIG ; sur un serveur sans
  Internet, le fond reste gris (les postes s'affichent). Serveur de tuiles interne à prévoir pour la production.
- **Dakar au zoom national** : les postes de Dakar s'entassent tant qu'on ne zoome pas. À prévoir :
  regroupement des bulles proches (`leaflet.markercluster`) ou boutons « Dakar / National ».
- **Couleurs Incidents / Délestages** (orange / rouge) peu distinctes pour un daltonien : la nature est
  aussi écrite dans la bulle et dans la liste des postes ; une couleur plus éloignée reste à choisir dans la charte.

## 12. Facteur exogène des causes dans le Référentiel (25/11/2026)

`causes.est_exogene` (migration `6a7b8c9d0e1f`) devient lisible et modifiable dans Administration →
Référentiel, comme le reste d'une cause (mêmes droits : Admin SCR pour les causes distribution et
communes, Admin Dispatching pour transport et communes, superadmin ; lecture seule ailleurs).

- `ReferentielResponse.est_exogene` : `true` / `false` pour les causes, `null` pour les autres référentiels.
- `ReferentielCreate.est_exogene` / `ReferentielUpdate.est_exogene` (`bool | null`) : pris en compte pour
  `causes` seulement ; création sans valeur → `false` ; mise à jour sans valeur → inchangé ; une valeur
  envoyée pour un autre référentiel → **422 enveloppé** (« Le facteur exogène ne concerne que les causes »).
- Audit : `old_values` / `new_values` de la mise à jour contiennent `est_exogene` quand c'est une cause.
- Le cache du référentiel est invalidé comme pour toute modification ; les vues du suivi des incidents
  (cache 1 h) prennent le nouveau drapeau au plus tard une heure après.
- Écran : colonne « Facteur exogène » (Oui / —) et case à cocher dans le formulaire, pour les causes seulement.

